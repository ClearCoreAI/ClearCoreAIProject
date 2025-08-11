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
    Summary:
        Ask Mistral to audit an execution trace and return a schema-conformant report.

    Parameters:
        execution_trace (dict): {"steps": [{"agent": str, "input": any, "output": any, "error": str|None}, ...]}
        api_key (str): Mistral API key (Bearer)
        model (str): Mistral model name
        temperature (float): Sampling temperature

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

    # Build compact, token-safe trace for the prompt
    compact_trace = _compact_trace(execution_trace, max_chars_per_field=800)

    messages = _build_messages(compact_trace)
    result = _call_mistral_chat(messages, api_key, model=model, temperature=temperature)

    # Force JSON parse + coercion to schema
    audit = _parse_and_coerce_audit_json(result)

    # Deterministic waterdrop estimate (same spirit as your summarize util)
    steps = len(execution_trace.get("steps", []))
    waterdrops_used = 6.0 + 0.5 * steps

    return audit, waterdrops_used


# ---------------------------- Prompt Building --------------------------- #
def _build_messages(compact_trace: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Build strict messages for the chat.completions endpoint.
    The assistant MUST return JSON only, matching the schema in the manifest.
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
    user = (
        "Here is the compact execution trace to audit. "
        "Please follow the rules and return ONLY JSON:\n\n"
        f"{json.dumps(compact_trace, ensure_ascii=False)}"
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