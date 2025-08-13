# tools/llm_audit_utils.py
"""
Module: llm_audit_utils
Component: Utility Function
Purpose: LLM-powered audit of multi-agent execution traces (Auditor agent)

Description:
Provides helper functions to call the Mistral API and produce a structured,
schema-conformant audit for a ClearCoreAI execution trace.

Philosophy:
- Entrées strictes et validées (liste de steps avec agent/input/output/error)
- Sortie JSON strictement conforme au manifest de l'agent 'auditor'
- Support des politiques d'audit par agent via execution_trace.policies + politique globale en fallback
- Coercition et garde‑fous côté client (scores clampés, champs obligatoires)
- Coût waterdrops déterministe par appel pour le suivi d’énergie

Initial State:
- A valid Mistral API key is provided
- The execution trace is a dict with a "steps" list

Final State:
- Returns a well-formed audit object + estimated waterdrop cost

Version: 0.1.0
Validated by: Olivier Hays
Date: 2025-08-11

Estimated Water Cost:
- 6 waterdrops per call + 0.5 per step (heuristic)
"""

from __future__ import annotations
import json
import math
from typing import Any, Dict, List, Tuple, Optional

import requests


# ------------------------------ Public API ------------------------------ #
def audit_trace_with_mistral(
    execution_trace: Dict[str, Any],
    api_key: str,
    model: str = "mistral-small",
    temperature: float = 0.2,
    policy: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], float]:
    """
    Summary:
        Ask Mistral to audit an execution trace and return a schema-conformant report.

    Parameters:
        execution_trace (dict): {"steps": [{"agent": str, "input": any, "output": any, "error": str|None}, ...]}
        api_key (str): Mistral API key (Bearer)
        model (str): Mistral model name
        temperature (float): Sampling temperature
        policy (dict|None): Optional audit policy to guide the LLM and enforce post-rules.
            Supported keys:
              - min_score (float 0..1): if a detail score is below this, mark status as 'warning' and append a note.
              - required_agents (list[str]): ensure each appears in details; otherwise add a warning entry.
              - status_rules (dict): e.g., {"agent_name": {"if_error": "fail"}} to force status based on trace conditions.

    Returns:
        (audit: dict, waterdrops_used: float)
        where `audit` strictly matches the auditor manifest:
        {
          "status": "ok" | "partial" | "fail",
          "summary": "string",
          "details": [
            {"agent":"...","status":"valid|warning|fail","comment":"...","score":0.0..1.0},
            ...
          ]
        }

    Raises:
        ValueError: if input is malformed
        Exception: on API / parsing errors
    """
    _validate_trace(execution_trace)

    # Optional per-agent policies may be embedded by the orchestrator under execution_trace["policies"].
    # Shape: {"agent_name": { ... rules ... }, "__global__": { ... rules ... }}
    policies_by_agent: Optional[Dict[str, Any]] = None
    try:
        raw_policies = execution_trace.get("policies")
        if isinstance(raw_policies, dict):
            # Shallow copy to avoid mutating caller input
            policies_by_agent = {str(k): v for k, v in raw_policies.items() if isinstance(v, dict)}
    except Exception:
        policies_by_agent = None

    # Backward-compat global policy provided as function arg still supported
    global_policy: Optional[Dict[str, Any]] = policy if isinstance(policy, dict) else None

    # Build compact, token-safe trace for the prompt
    compact_trace = _compact_trace(execution_trace, max_chars_per_field=800)

    messages = _build_messages(compact_trace, global_policy, policies_by_agent)
    result = _call_mistral_chat(messages, api_key, model=model, temperature=temperature)

    # Force JSON parse + coercion to schema
    audit = _parse_and_coerce_audit_json(result)

    # Apply optional global and per-agent policies deterministically
    try:
        audit = _apply_policy(audit, execution_trace, global_policy=global_policy, policies_by_agent=policies_by_agent)
    except Exception:
        # Fail-soft: keep LLM result if policy application crashes
        pass

    # Deterministic waterdrop estimate (same spirit as your summarize util)
    steps = len(execution_trace.get("steps", []))
    waterdrops_used = 6.0 + 0.5 * steps

    return audit, waterdrops_used


# ---------------------------- Prompt Building --------------------------- #
def _build_messages(
    compact_trace: Dict[str, Any],
    global_policy: Optional[Dict[str, Any]] = None,
    policies_by_agent: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Build strict messages for the chat.completions endpoint.
    The assistant MUST return JSON only, matching the schema in the manifest.
    Supports optional global and per-agent policies to guide the LLM.
    """
    system = (
        "You are a rigorous pipeline auditor for ClearCoreAI. "
        "You receive an execution trace (list of steps from different agents). "
        "Audit quality, structure, and consistency. "
        "Return ONLY a JSON object that matches EXACTLY this schema:\n\n"
        "{\n"
        '  "status": "ok" | "partial" | "fail",\n'
        '  "summary": "string",\n'
        '  "details": [\n'
        '    {\n'
        '      "agent": "string",\n'
        '      "status": "valid" | "warning" | "fail",\n'
        '      "comment": "string",\n'
        '      "score": number between 0.0 and 1.0\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Use 'valid' if output looks coherent and non-empty, 'warning' for suspicious/short/partially empty, 'fail' if errors or missing critical data.\n"
        "- The global 'status' is 'ok' if all are valid; 'partial' if mix of valid/warning; 'fail' if any fail.\n"
        "- 'score' reflects confidence [0.0..1.0].\n"
        "- Do NOT include extra keys or commentary outside JSON."
    )
    policy_block = ""
    if global_policy:
        try:
            gp_json = json.dumps(global_policy, ensure_ascii=False)
        except Exception:
            gp_json = "{}"
        policy_block += "\n\nGlobal Audit Policy (MUST FOLLOW):\n" + gp_json + (
            "\n- If a 'min_score' is provided, do not inflate scores; judge honestly.\n"
            "- Prefer 'warning' over 'valid' when evidence is weak or outputs are too short."
        )

    if policies_by_agent:
        try:
            ap_json = json.dumps(_summarize_policies_for_prompt(policies_by_agent), ensure_ascii=False)
        except Exception:
            ap_json = "{}"
        policy_block += "\n\nPer-Agent Policies (MUST FOLLOW):\n" + ap_json

    user = (
        "Here is the compact execution trace to audit. "
        "Please follow the rules and return ONLY JSON:" + policy_block + "\n\n" +
        f"{json.dumps(compact_trace, ensure_ascii=False)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------- Policy Summarization Helper ---------------------- #
def _summarize_policies_for_prompt(policies_by_agent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a prompt-compact view of per-agent policies: keep only simple scalars and short lists.
    """
    summary: Dict[str, Any] = {}
    for agent, pol in policies_by_agent.items():
        if not isinstance(pol, dict):
            continue
        compact = {}
        for k, v in pol.items():
            if isinstance(v, (int, float, str, bool)):
                compact[k] = v
            elif isinstance(v, list) and len(v) <= 10:
                compact[k] = [x for x in v if isinstance(x, (int, float, str, bool))][:10]
            elif isinstance(v, dict):
                # Keep shallow keys that are scalars
                compact[k] = {sk: sv for sk, sv in v.items() if isinstance(sv, (int, float, str, bool))}
        if compact:
            summary[agent] = compact
    return summary


# ---------------------------- HTTP to Mistral --------------------------- #
def _call_mistral_chat(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str,
    temperature: float,
) -> Dict[str, Any]:
    """
    Low-level call to Mistral chat.completions.
    """
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
        # Defensive shape check
        content = data["choices"][0]["message"]["content"]
        return {"raw": data, "content": content}
    except requests.exceptions.RequestException as e:
        raise Exception(f"Mistral API call failed: {e}")
    except Exception as e:
        raise Exception(f"Unexpected response shape from Mistral: {e}")


# -------------------------- Parsing & Coercion -------------------------- #
def _parse_and_coerce_audit_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse assistant content as JSON; coerce to the auditor schema with guardrails.
    """
    content = result.get("content", "")
    try:
        parsed = json.loads(content)
    except Exception as e:
        # Last-ditch: try to extract JSON substring
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(content[start : end + 1])
            except Exception:
                raise Exception(f"Failed to parse LLM JSON: {e}")
        else:
            raise Exception(f"Failed to parse LLM JSON: {e}")

    # Coerce required top-level fields
    audit: Dict[str, Any] = {
        "status": str(parsed.get("status", "partial")).lower(),
        "summary": str(parsed.get("summary", "")),
        "details": [],
    }

    # Coerce per-detail items safely
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
        score = max(0.0, min(1.0, score))  # clamp

        # Normalize status
        if status not in {"valid", "warning", "fail"}:
            status = "warning"

        audit["details"].append(
            {
                "agent": agent,
                "status": status,
                "comment": comment if comment else "No comment.",
                "score": score,
            }
        )

    # If details empty, degrade gracefully
    if not audit["details"]:
        audit["details"] = [
            {
                "agent": "unknown",
                "status": "warning",
                "comment": "LLM returned no details.",
                "score": 0.2,
            }
        ]

    # Normalize global status if missing/invalid
    if audit["status"] not in {"ok", "partial", "fail"}:
        # Recompute from details
        statuses = {d["status"] for d in audit["details"]}
        if "fail" in statuses:
            audit["status"] = "fail"
        elif "warning" in statuses:
            audit["status"] = "partial"
        else:
            audit["status"] = "ok"

    # Ensure summary
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
    """
    Reduce large nested structures into compact previews:
    - strings trimmed
    - dicts/lists recursively trimmed
    - primitives left intact
    """
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
    # Fallback to string
    txt = str(value)
    return txt[:max_chars]


# --------------------------- Policy Post-Processing --------------------------- #
def _apply_policy(
    audit: Dict[str, Any],
    execution_trace: Dict[str, Any],
    global_policy: Optional[Dict[str, Any]] = None,
    policies_by_agent: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Apply lightweight, deterministic rules after the LLM response.

    Supports global and per-agent policies:
      - min_score (float 0..1)
      - required_agents (list[str])
      - status_rules: { agent_name: {"if_error": "fail"|"warning"} }
      - Per-agent: min_score, required_output_keys, min_items, if_error, etc.
    """
    details = audit.get("details", [])

    # Helper to locate or create a detail entry by agent
    def _ensure_detail(a_name: str) -> Dict[str, Any]:
        for d in details:
            if d.get("agent") == a_name:
                return d
        d = {"agent": a_name, "status": "warning", "comment": "", "score": 0.2}
        details.append(d)
        return d

    # Build quick lookup of outputs and errors from the execution trace per agent (last occurrence wins)
    trace_by_agent = {}
    for s in execution_trace.get("steps", []):
        a = s.get("agent")
        if not a:
            continue
        trace_by_agent[a] = {"output": s.get("output"), "error": s.get("error")}

    # Apply GLOBAL policy first (backward compatible)
    gp = global_policy or {}
    min_score = gp.get("min_score") if isinstance(gp, dict) else None
    if isinstance(min_score, (int, float)):
        try:
            min_score = float(min_score)
        except Exception:
            min_score = None
    if isinstance(min_score, float):
        for d in details:
            if d.get("score", 1.0) < min_score and d.get("status") == "valid":
                d["status"] = "warning"
                d["comment"] = (d.get("comment") or "").rstrip() + " (below global min_score)"

    # Required agents (global)
    req_agents = gp.get("required_agents") if isinstance(gp, dict) else None
    if isinstance(req_agents, list):
        for a in req_agents:
            if not any(d.get("agent") == a for d in details):
                d = _ensure_detail(str(a))
                d["status"] = "warning"
                d["comment"] = (d.get("comment") or "") + "Missing from audit details per global policy."
                d["score"] = min(d.get("score", 0.3), 0.3)

    # Status rules based on presence of error in the trace (global)
    status_rules = gp.get("status_rules") if isinstance(gp, dict) else None
    if isinstance(status_rules, dict):
        for a_name, rules in status_rules.items():
            if not isinstance(rules, dict):
                continue
            if trace_by_agent.get(a_name, {}).get("error"):
                rule = rules.get("if_error")
                if rule in {"fail", "warning"}:
                    d = _ensure_detail(a_name)
                    d["status"] = rule
                    d["comment"] = (d.get("comment") or "").rstrip() + " (policy: error observed)"

    # Apply PER-AGENT policies
    if isinstance(policies_by_agent, dict):
        for a_name, pol in policies_by_agent.items():
            if not isinstance(pol, dict):
                continue
            d = _ensure_detail(a_name)
            out = trace_by_agent.get(a_name, {}).get("output")

            # Agent-specific min_score
            a_min = pol.get("min_score")
            if isinstance(a_min, (int, float)):
                try:
                    a_min = float(a_min)
                except Exception:
                    a_min = None
                if isinstance(a_min, float) and d.get("score", 1.0) < a_min and d.get("status") == "valid":
                    d["status"] = "warning"
                    d["comment"] = (d.get("comment") or "").rstrip() + " (below agent min_score)"

            # Required output keys (shallow check)
            req_keys = pol.get("required_output_keys")
            if isinstance(req_keys, list) and isinstance(out, dict):
                missing = [k for k in req_keys if k not in out]
                if missing:
                    d["status"] = "warning" if d.get("status") != "fail" else d.get("status")
                    d["comment"] = (d.get("comment") or "") + f" Missing output keys: {missing}."
                    d["score"] = min(d.get("score", 0.6), 0.6)

            # Minimum items in array field, e.g., {"min_items": {"articles": 1}}
            min_items = pol.get("min_items")
            if isinstance(min_items, dict) and isinstance(out, dict):
                for field, min_n in min_items.items():
                    try:
                        min_n = int(min_n)
                    except Exception:
                        continue
                    val = out.get(field)
                    if isinstance(val, list) and len(val) < min_n:
                        d["status"] = "warning"
                        d["comment"] = (d.get("comment") or "") + f" Field '{field}' has only {len(val)} items (< {min_n})."
                        d["score"] = min(d.get("score", 0.5), 0.5)

            # If error present and agent rule forces fail
            if trace_by_agent.get(a_name, {}).get("error") and pol.get("if_error") in {"fail", "warning"}:
                d["status"] = pol.get("if_error")
                d["comment"] = (d.get("comment") or "").rstrip() + " (agent policy: error observed)"

    # Recompute global status from details
    statuses = {d.get("status") for d in details}
    if "fail" in statuses:
        audit["status"] = "fail"
    elif "warning" in statuses:
        audit["status"] = "partial"
    else:
        audit["status"] = "ok"

    audit["details"] = details
    return audit