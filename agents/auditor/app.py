"""
Module: auditor
Component: Agent API
Purpose: LLM-only audit that forwards per-agent policies to the LLM

Description:
This ClearCoreAI auditor receives an execution trace and strictly fetches each agent's
/audit_policy. It forwards both the steps and the per-agent policies to the LLM, which
returns a structured audit (status/summary/details). No local rule evaluation is performed.

Philosophy:
- 100% LLM judgment; auditor does not enforce rules locally
- Policies are mandatory and passed verbatim to the LLM
- Clear, minimal surface: health/capabilities/metrics/mood/run/execute

Initial State:
- manifest.json present and valid
- mood.json present or initialized
- memory/short_term/aiwaterdrops.json present or initialized
- license_keys.json contains a valid Mistral API key

Final State:
- Structured audit is returned
- Mood and water usage are updated

Version: 0.3.0 (LLM + policy passthrough)
Validated by: Olivier Hays
Date: 2025-08-11

Estimated Water Cost:
- ~6 + 0.5*steps waterdrops per /run (LLM call)
- 0.02 waterdrops per /execute dispatch
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from tools.water import increment_aiwaterdrops, load_aiwaterdrops, get_aiwaterdrops
from tools.llm_utils import audit_trace_with_mistral


# ----------- Constants ----------- #
AGENT_NAME = "auditor agent"
VERSION = "0.3.0"

# ----------- Credentials ----------- #
try:
    with open("license_keys.json", "r") as f:
        license_keys = json.load(f)
except FileNotFoundError:
    print("Error: license_keys.json missing — /run will fail without a Mistral API key.")
    license_keys = {}

# ----------- App Initialization ----------- #
app = FastAPI(title=AGENT_NAME, version=VERSION)
start_time = time.time()

# ----------- State ----------- #
try:
    with open("mood.json", "r") as f:
        mood = json.load(f)
except FileNotFoundError:
    print("Warning: mood.json missing, initializing defaults.")
    mood = {"current_mood": "neutral", "last_check": None}

aiwaterdrops_consumed = load_aiwaterdrops()


# ----------- Models ----------- #
class StepResult(BaseModel):
    """
    Represents one agent step from the orchestrator.

    Parameters:
        agent (str): Agent name (e.g. "summarize_articles")
        input (Any): Input payload (arbitrary JSON). Should include '_agent_base_url'.
        output (Any): Output payload (arbitrary JSON). May also include '_agent_base_url'.
        error (str|None): Optional error string

    Returns:
        StepResult
    """
    agent: str
    input: Any
    output: Any
    error: Optional[str] = None


class ExecutionTrace(BaseModel):
    """
    Full pipeline execution trace.

    Parameters:
        steps (List[StepResult]): steps to audit

    Returns:
        ExecutionTrace
    """
    steps: List[StepResult]


class AuditFeedback(BaseModel):
    """
    Per-agent audit line produced by the LLM.

    Parameters:
        agent (str)
        status (str): 'valid' | 'warning' | 'fail'
        comment (str)
        score (float 0..1)
    """
    agent: str
    status: str
    comment: str
    score: float


class AuditResult(BaseModel):
    """
    Final audit.

    Parameters:
        status (str): 'ok' | 'partial' | 'fail'
        summary (str)
        details (List[AuditFeedback])
    """
    status: str
    summary: str
    details: List[AuditFeedback]


# ----------- Helpers (policy passthrough) ----------- #
def _require_base_url_from_step(step: Dict[str, Any]) -> str:
    """
    Extract a mandatory base URL from the step. No heuristics.
    Looks in step.input._agent_base_url, then step.output._agent_base_url.

    Raises:
        HTTPException(422) if missing
    """
    for container_key in ("input", "output"):
        container = step.get(container_key) or {}
        url = container.get("_agent_base_url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    raise HTTPException(
        status_code=422,
        detail=f"Missing '_agent_base_url' in step for agent '{step.get('agent','?')}'. "
               "Ensure orchestrator forwards this hint."
    )


def _fetch_audit_policy(base_url: str, timeout_secs: float = 4.0) -> Dict[str, Any]:
    """
    GET {base_url}/audit_policy and return JSON.
    Enforces minimal shape (object, ideally with 'rules' list) but does not evaluate it.
    """
    try:
        resp = requests.get(f"{base_url}/audit_policy", timeout=timeout_secs)
        resp.raise_for_status()
        policy = resp.json()
        if not isinstance(policy, dict):
            raise ValueError("Policy is not a JSON object.")
        # Keep it permissive for LLM: 'rules' recommended but not strictly required here.
        return policy
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to fetch audit policy from {base_url}: {e}"
        )


def _build_agent_policy_map(steps: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Build {agent_name: policy_dict} for all unique agents in the trace.
    Strict: every agent in the trace must provide a policy.
    """
    policies: Dict[str, Dict[str, Any]] = {}
    seen: Dict[str, bool] = {}

    for s in steps:
        agent = s.get("agent")
        if not agent:
            raise HTTPException(status_code=422, detail="Trace step missing 'agent' name.")
        if seen.get(agent):
            continue
        seen[agent] = True

        base_url = _require_base_url_from_step(s)       # may raise 422
        policy = _fetch_audit_policy(base_url)          # may raise 422
        policies[agent] = policy

    return policies


# ----------- Endpoints ----------- #
@app.get("/manifest")
def get_manifest() -> dict:
    """Return manifest.json content."""
    try:
        with open("manifest.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/health")
def health() -> dict:
    """Basic liveness."""
    return {"status": "Auditor Agent is up and running."}


@app.get("/capabilities")
def get_capabilities() -> dict:
    """Expose capabilities declared in manifest."""
    try:
        with open("manifest.json", "r") as f:
            manifest = json.load(f)
        return {"capabilities": manifest.get("capabilities", [])}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/metrics")
def get_metrics() -> dict:
    """Uptime, mood, and water usage."""
    uptime = int(time.time() - start_time)
    return {
        "agent": AGENT_NAME,
        "version": VERSION,
        "uptime_seconds": uptime,
        "current_mood": mood.get("current_mood", "unknown"),
        "aiwaterdrops_consumed": get_aiwaterdrops()
    }


@app.get("/mood")
def get_mood() -> dict:
    """Return current mood and last summary."""
    return {
        "current_mood": mood.get("current_mood", "unknown"),
        "last_check": mood.get("last_check")
    }


@app.post("/run", response_model=AuditResult)
def run_audit(trace: ExecutionTrace):
    """
    LLM-only audit with per-agent policy passthrough.

    Flow:
      1) Convert Pydantic models to dict
      2) Build {agent: policy} by calling each agent's /audit_policy
      3) Call audit_trace_with_mistral({"steps": ..., "policies": ...}, api_key)
      4) Coerce response to schema, persist mood, account water
    """
    api_key = license_keys.get("mistral")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing Mistral API key in license_keys.json")

    # 1) Steps -> plain dicts
    steps_payload: List[Dict[str, Any]] = []
    for s in trace.steps:
        steps_payload.append({
            "agent": s.agent,
            "input": s.input,
            "output": s.output,
            "error": s.error,
        })

    # 2) Strict: fetch policies for all agents present in the trace
    policies = _build_agent_policy_map(steps_payload)  # may raise 422

    # 3) LLM call with policies passthrough
    try:
        llm_input = {"steps": steps_payload, "policies": policies}
        audit_dict, water_used = audit_trace_with_mistral(llm_input, api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM audit failed: {e}")

    # 4) Map to Pydantic models
    details_models: List[AuditFeedback] = []
    for d in audit_dict.get("details", []):
        details_models.append(
            AuditFeedback(
                agent=str(d.get("agent", "unknown")),
                status=str(d.get("status", "warning")),
                comment=str(d.get("comment", "")).strip() or "No comment.",
                score=float(d.get("score", 0.5)),
            )
        )

    result_model = AuditResult(
        status=str(audit_dict.get("status", "partial")),
        summary=str(audit_dict.get("summary", "")) or "LLM audit completed.",
        details=details_models if details_models else [
            AuditFeedback(agent="unknown", status="warning", comment="No details from LLM.", score=0.2)
        ],
    )

    # Persist mood
    mood["current_mood"] = "active"
    mood["last_check"] = result_model.summary
    with open("mood.json", "w") as f:
        json.dump(mood, f)

    # Water accounting
    try:
        increment_aiwaterdrops(float(water_used))
    except Exception:
        pass

    return result_model


@app.post("/execute")
async def execute(request: Request) -> dict:
    """
    Dispatch capability (currently only 'audit_trace').

    Body:
      { "capability": "audit_trace", "input": { "steps": [...] } }
    """
    payload = await request.json()
    capability = payload.get("capability")
    input_data = payload.get("input", {})

    if capability == "audit_trace":
        trace = ExecutionTrace(**input_data)
        result = run_audit(trace)
        try:
            return result.model_dump()  # Pydantic v2
        except AttributeError:
            return result.dict()        # Pydantic v1 fallback

    raise HTTPException(status_code=400, detail=f"Unknown capability: {capability}")

