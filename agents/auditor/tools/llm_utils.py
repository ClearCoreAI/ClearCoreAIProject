"""
Module: llm_utils
Component: Utility Function
Purpose: LLM-powered audit of multi-agent execution traces (Auditor agent)

Description:
- STRICT: Per-agent policies are MANDATORY and must be provided in execution_trace["policies"].
- Sends full per-agent policies to the LLM. The LLM must apply them when deciding
  per-step status ('valid'|'warning'|'fail') and the global status ('ok'|'partial'|'fail').
- No deterministic post-processing: the LLM's JSON is the source of truth, only schema
  coercion is applied for safety.

Philosophy:
- 100% LLM judgment guided by explicit policies
- Strict input validation (trace + policies)
- Strict JSON output schema with minimal coercion
- Deterministic waterdrop estimate

Initial State:
- A valid Mistral API key is provided.
- execution_trace = {"steps":[{agent,input,output,error}...], "policies":{agent_name:policy_dict,...}}

Final State:
- Returns (audit_dict, waterdrops_used) where audit_dict matches the auditor schema.

Version: 0.2.0
Validated by: Olivier Hays
Date: 2025-08-11

Estimated Water Cost:
- 6 waterdrops per call + 0.5 per step (heuristic)
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple

import requests


# ------------------------------ Public API ------------------------------ #
def audit_trace_with_mistral(
    execution_trace: Dict[str, Any],
    api_key: str,
    model: str = "mistral-small",
    temperature: float = 0.2,
) -> Tuple[Dict[str, Any], float]:
    """
    Ask Mistral to audit an execution trace and return a schema-conformant report.

    Parameters:
        execution_trace (dict): {
          "steps": [{"agent": str, "input": any, "output": any, "error": str|None}, ...],
          "policies": { "<agent>": { ... policy json ... }, ... }
        }
        api_key (str): Mistral API key (Bearer)
        model (str): Mistral model name
        temperature (float): Sampling temperature

    Returns:
        (audit: dict, waterdrops_used: float)
        where `audit` strictly matches:
        {
          "status": "ok" | "partial" | "fail",
          "summary": "string",
          "details": [
            {"agent":"...","status":"valid|warning|fail","comment":"...","score":0.0..1.0},
            ...
          ]
        }

    Raises:
        ValueError: if input is malformed (trace or policies)
        Exception: on API / parsing errors
    """
    _validate_trace(execution_trace)
    _validate_policies_mandatory(execution_trace)

    compact_trace = _compact_trace(execution_trace, max_chars_per_field=800)
    policies_by_agent: Dict[str, Any] = execution_trace["policies"]

    messages = _build_messages(compact_trace, policies_by_agent)
    result = _call_mistral_chat(messages, api_key, model=model, temperature=temperature)

    # Parse and coerce only (no post-processing overrides)
    audit = _parse_and_coerce_audit_json(result)

    # Waterdrop estimate
    steps = len(execution_trace.get("steps", []))
    waterdrops_used = 6.0 + 0.5 * steps

    return audit, waterdrops_used


# ---------------------------- Prompt Building --------------------------- #
def _build_messages(
    compact_trace: Dict[str, Any],
    policies_by_agent: Dict[str, Any],
) -> List[Dict[str, str]]:
    """
    Build strict messages for the chat.completions endpoint.
    The assistant MUST return JSON only, matching the schema, and MUST apply the provided policies.
    """
    system = (
        "You are a rigorous pipeline auditor for ClearCoreAI.\n"
        "You will receive:\n"
        "  (1) A compact execution trace (list of steps from different agents)\n"
        "  (2) A dictionary of per-agent audit policies\n\n"
        "Your job:\n"
        "- Apply the per-agent policies STRICTLY to evaluate each step:\n"
        "    • If a policy rule indicates a FAIL condition for a step, mark that step 'fail'.\n"
        "    • Use 'warning' for policy soft breaches (quality/length/etc.).\n"
        "    • Use 'valid' only when the step output clearly satisfies all required rules.\n"
        "- Derive the GLOBAL status: 'ok' if ALL details are 'valid'; 'partial' if any 'warning' and none 'fail'; 'fail' if ANY step is 'fail'.\n"
        "- Return ONLY a JSON object that matches EXACTLY this schema:\n"
        "{\n"
        '  \"status\": \"ok\" | \"partial\" | \"fail\",\n'
        '  \"summary\": \"string\",\n'
        '  \"details\": [\n'
        '    {\n'
        '      \"agent\": \"string\",\n'
        '      \"status\": \"valid\" | \"warning\" | \"fail\",\n'
        '      \"comment\": \"string\",\n'
        '      \"score\": number between 0.0 and 1.0\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "- Do NOT include extra keys or any text outside JSON.\n"
    )

    try:
        ap_json = json.dumps(policies_by_agent, ensure_ascii=False)
    except Exception:
        # Should not happen — policies were validated already.
        ap_json = "{}"

    user = (
        "Per-agent policies (MUST APPLY AS WRITTEN):\n"
        f"{ap_json}\n\n"
        "Compact execution trace to audit (use for evidence, but policies govern decisions):\n"
        f"{json.dumps(compact_trace, ensure_ascii=False)}\n"
        "Return ONLY the JSON object."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------- HTTP to Mistral --------------------------- #
def _call_mistral_chat(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str,
    temperature: float,
) -> Dict[str, Any]:
    """Low-level call to Mistral chat.completions."""
    if not api_key or not isinstance(api_key, str):
        raise ValueError("Missing Mistral API key.")

    endpoint = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=45)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return {"raw": data, "content": content}
    except requests.exceptions.RequestException as e:
        raise Exception(f"Mistral API call failed: {e}")
    except Exception as e:
        raise Exception(f"Unexpected response shape from Mistral: {e}")


# -------------------------- Parsing & Coercion -------------------------- #
def _parse_and_coerce_audit_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """Parse assistant content as JSON; coerce to the auditor schema with guardrails."""
    content = result.get("content", "")
    try:
        parsed = json.loads(content)
    except Exception as e:
        # Last-ditch: extract JSON substring
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(content[start : end + 1])
            except Exception:
                raise Exception(f"Failed to parse LLM JSON: {e}")
        else:
            raise Exception(f"Failed to parse LLM JSON: {e}")

    audit: Dict[str, Any] = {
        "status": str(parsed.get("status", "partial")).lower(),
        "summary": str(parsed.get("summary", "")),
        "details": [],
    }

    details_in = parsed.get("details", [])
    if not isinstance(details_in, list):
        details_in = []

    for item in details_in:
        agent = str(item.get("agent", "unknown"))
        status = str(item.get("status", "warning")).lower()
        comment = str(item.get("comment", "")).strip()
        score = item.get("score", 0.5)
        try:
            score = float(score)
        except Exception:
            score = 0.5
        score = max(0.0, min(1.0, score))

        if status not in {"valid", "warning", "fail"}:
            status = "warning"

        audit["details"].append(
            {"agent": agent, "status": status, "comment": comment or "No comment.", "score": score}
        )

    if not audit["details"]:
        audit["details"] = [
            {"agent": "unknown", "status": "warning", "comment": "LLM returned no details.", "score": 0.2}
        ]

    if audit["status"] not in {"ok", "partial", "fail"}:
        statuses = {d["status"] for d in audit["details"]}
        if "fail" in statuses:
            audit["status"] = "fail"
        elif "warning" in statuses:
            audit["status"] = "partial"
        else:
            audit["status"] = "ok"

    if not audit["summary"]:
        ok = sum(1 for d in audit["details"] if d["status"] == "valid")
        total = len(audit["details"])
        audit["summary"] = f"{ok}/{total} agents validated"

    return audit


# --------------------------- Validation & Prep -------------------------- #
def _validate_trace(execution_trace: Dict[str, Any]) -> None:
    if not isinstance(execution_trace, dict):
        raise ValueError("execution_trace must be a dict")
    steps = execution_trace.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("execution_trace.steps must be a non-empty list")

    for idx, s in enumerate(steps):
        if not isinstance(s, dict):
            raise ValueError(f"steps[{idx}] must be a dict")
        if "agent" not in s or "output" not in s:
            raise ValueError(f"steps[{idx}] must contain 'agent' and 'output' keys")


def _validate_policies_mandatory(execution_trace: Dict[str, Any]) -> None:
    """
    Enforce that per-agent policies are present and cover all agents in the trace.
    Raises ValueError if missing/invalid.
    """
    policies = execution_trace.get("policies")
    if not isinstance(policies, dict) or not policies:
        raise ValueError("execution_trace.policies must be a non-empty dict")

    # Collect agent names present in the trace
    agents_in_trace: List[str] = []
    for s in execution_trace.get("steps", []):
        a = s.get("agent")
        if not isinstance(a, str) or not a:
            raise ValueError("Each step must include a non-empty 'agent' string")
        agents_in_trace.append(a)

    missing: List[str] = [a for a in sorted(set(agents_in_trace)) if a not in policies]
    if missing:
        raise ValueError(f"Missing policies for agents: {', '.join(missing)}")

    # Shallow shape check per policy
    for a, pol in policies.items():
        if not isinstance(pol, dict):
            raise ValueError(f"Policy for agent '{a}' must be a JSON object")
        # Require a rules list to ensure substance (the agents’ /audit_policy should include it)
        if "rules" not in pol or not isinstance(pol["rules"], list) or len(pol["rules"]) == 0:
            raise ValueError(f"Policy for agent '{a}' must include a non-empty 'rules' list")


def _compact_trace(execution_trace: Dict[str, Any], max_chars_per_field: int = 800) -> Dict[str, Any]:
    """
    Make the trace token-safe: trim big strings, keep essential keys only.
    """
    compact_steps: List[Dict[str, Any]] = []
    for s in execution_trace.get("steps", []):
        compact_steps.append(
            {
                "agent": s.get("agent"),
                "has_error": bool(s.get("error")),
                "input_preview": _preview(s.get("input"), max_chars_per_field),
                "output_preview": _preview(s.get("output"), max_chars_per_field),
                "error": s.get("error"),
            }
        )
    return {"steps": compact_steps}


def _preview(value: Any, max_chars: int) -> Any:
    """Reduce large nested structures into compact previews."""
    if value is None:
        return None
    if isinstance(value, str):
        return value[:max_chars]
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        return [_preview(v, max_chars) for v in value[:10]]
    if isinstance(value, dict):
        out = {}
        for k, v in list(value.items())[:20]:
            out[str(k)] = _preview(v, max_chars)
        return out
    return str(value)[:max_chars]


