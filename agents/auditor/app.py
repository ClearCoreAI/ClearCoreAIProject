"""
Module: auditor
Component: Agent API
Purpose: LLM-only audit that forwards per-agent policies to the LLM

Description:
This ClearCoreAI auditor receives an execution trace and strictly fetches each agent's
/audit_policy. It forwards both the steps and the per-agent policies to the LLM, which
returns a structured audit (status/summary/details). No local rule evaluation is performed.

How it works (end‑to‑end call graph):
1) Client → POST /run
   - FastAPI parses the body into `ExecutionTrace` (Pydantic).
   - `run_audit()` converts Pydantic models to plain dicts (steps_payload).

2) Policy discovery for each agent in the trace
   - `run_audit()` → `_build_agent_policy_map(steps_payload)`
       • Iterates unique agents present in the trace.
       • For each step:
            `_require_base_url_from_step(step)`  ⟶ reads `_agent_base_url` from step.input or step.output.
            `_fetch_audit_policy(base_url)`      ⟶ performs GET `{base_url}/audit_policy` and loads JSON.
       • Returns `{ "<agent>": <policy_json>, ... }`.
   - This step is **strict**: if an agent policy is missing or unreachable, a 422 is raised.

3) LLM audit (policies + trace passthrough)
   - `run_audit()` builds: `llm_input = {"steps": steps_payload, "policies": policies}`.
   - `run_audit()` → `audit_trace_with_mistral(llm_input, api_key)` (tools/llm_utils.py):
       • `_validate_trace()` and `_validate_policies_mandatory()` ensure inputs are well‑formed.
       • `_compact_trace()` builds a token‑safe view of the trace.
       • `_build_messages()` constructs strict system/user messages that embed the **per‑agent policies**.
       • `_call_mistral_chat()` calls Mistral’s Chat Completions API.
       • `_parse_and_coerce_audit_json()` parses the model’s JSON and coerces to the auditor schema.
       • Returns `(audit_dict, waterdrops_used)` with **LLM as source of truth**.

4) Response shaping & persistence
   - `run_audit()` maps `audit_dict["details"]` to Pydantic `AuditFeedback`.
   - It persists mood in `mood.json` and increments water with `increment_aiwaterdrops(waterdrops_used)`.
   - Returns `AuditResult` to the client.

5) Orchestrated execution flow
   - Alternatively, a client can POST /execute with:
       `{ "capability": "audit_trace", "input": { "steps": [...] } }`
   - `execute()` simply forwards to `run_audit()` and returns its result.

Observability endpoints:
- GET /health        → quick liveness probe.
- GET /capabilities  → manifest capabilities passthrough.
- GET /metrics       → uptime, mood, and water usage snapshot.
- GET /mood          → current mood + last summary.

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

Version: 0.3.1 (LLM + policy passthrough)
Validated by: Olivier Hays
Date: 2025-08-21

Estimated Water Cost:
- ~6 + 0.5*steps waterdrops per /run (LLM call)
- 0.02 waterdrops per /execute dispatch

----------------------------------------------------------------------
Usage Example (Python):

from pydantic import BaseModel
import requests, json

# 1) Prepare an execution trace step (include _agent_base_url so the auditor can fetch /audit_policy)
trace = {
    "steps": [
        {
            "agent": "summarize_articles",
            "input": {
                "_agent_base_url": "http://summarize_articles:8600",
                "articles": [
                    {"title": "AI in healthcare",
                     "content": "Artificial intelligence is transforming diagnostics and precision medicine..."}
                ]
            },
            "output": {
                "_agent_base_url": "http://summarize_articles:8600",
                "summaries": [
                    "AI is improving diagnostics and enabling more precise treatments across clinical workflows."
                ],
                "waterdrops_used": 2.0
            },
            "error": None
        }
    ]
}

# 2) POST to the auditor /run
resp = requests.post("http://auditor:8700/run", json=trace, timeout=30)
resp.raise_for_status()
audit = resp.json()
print(json.dumps(audit, indent=2, ensure_ascii=False))

----------------------------------------------------------------------
Usage Example (curl):

curl -s -X POST http://localhost:8700/run \
  -H "Content-Type: application/json" \
  -d '{
    "steps":[
      {
        "agent":"summarize_articles",
        "input":{
          "_agent_base_url":"http://summarize_articles:8600",
          "articles":[
            {"title":"AI in healthcare","content":"Artificial intelligence is transforming diagnostics and precision medicine..."}
          ]
        },
        "output":{
          "_agent_base_url":"http://summarize_articles:8600",
          "summaries":[
            "AI is improving diagnostics and enabling more precise treatments across clinical workflows."
          ],
          "waterdrops_used": 2.0
        },
        "error": null
      }
    ]
  }'
----------------------------------------------------------------------
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
VERSION = "0.3.1"


# ----------- Credentials ----------- #
try:
    with open("license_keys.json", "r") as f:
        license_keys = json.load(f)
except FileNotFoundError:
    # We keep startup lenient for health/capabilities endpoints; /run will enforce.
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

    Initial State:
        - Input/Output are arbitrary JSON structures provided by agents/orchestrator.

    Final State:
        - Validated container used for auditing.

    Raises:
        (Validation handled by Pydantic)

    Water Cost:
        - 0
    """
    agent: str
    input: Any
    output: Any
    error: Optional[str] = None


class ExecutionTrace(BaseModel):
    """
    Full pipeline execution trace.

    Parameters:
        steps (List[StepResult]): Steps to audit.

    Returns:
        ExecutionTrace

    Initial State:
        - At least one step is present.

    Final State:
        - Validated trace for processing.

    Water Cost:
        - 0
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

    Returns:
        AuditFeedback

    Water Cost:
        - 0
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

    Returns:
        AuditResult

    Water Cost:
        - 0
    """
    status: str
    summary: str
    details: List[AuditFeedback]


# ----------- Helpers (policy passthrough) ----------- #
def _require_base_url_from_step(step: Dict[str, Any]) -> str:
    """
    Extracts the agent base URL from the step payload without heuristics.

    Parameters:
        step (dict): A step dict with 'input'/'output' possibly holding '_agent_base_url'.

    Returns:
        str: The base URL found (e.g., "http://summarize_articles:8600").

    Initial State:
        - Orchestrator/agents include '_agent_base_url' in step.input or step.output.

    Final State:
        - A non-empty URL string is returned.

    Raises:
        HTTPException(422): If the URL is missing.

    Water Cost:
        - 0
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
    Fetches an agent's audit policy document.

    Parameters:
        base_url (str): Base URL for the agent (e.g., http://agent_name:port)
        timeout_secs (float): HTTP timeout in seconds

    Returns:
        dict: The policy JSON as provided by the agent.

    Initial State:
        - The target agent exposes GET {base_url}/audit_policy.

    Final State:
        - Policy JSON is returned verbatim (shape minimally checked).

    Raises:
        HTTPException(422): On network/HTTP or invalid JSON shape.

    Water Cost:
        - ~0
    """
    try:
        resp = requests.get(f"{base_url}/audit_policy", timeout=timeout_secs)
        resp.raise_for_status()
        policy = resp.json()
        if not isinstance(policy, dict):
            raise ValueError("Policy is not a JSON object.")
        # Keep permissive for LLM: do not enforce structure here; LLM will decide.
        return policy
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to fetch audit policy from {base_url}: {e}"
        )


def _build_agent_policy_map(steps: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Builds a mapping {agent_name: policy_dict} for all unique agents in the trace.

    Parameters:
        steps (List[dict]): The execution steps (plain dicts)

    Returns:
        dict: Mapping of agent -> policy

    Initial State:
        - Each step carries '_agent_base_url' (input or output).
        - Each agent exposes /audit_policy.

    Final State:
        - Policies for all agents present in the trace are retrieved.

    Raises:
        HTTPException(422): If base_url is missing or /audit_policy fails.

    Water Cost:
        - ~0
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
    """
    Returns the agent manifest loaded from disk.

    Parameters:
        None

    Returns:
        dict: Parsed manifest.json content.

    Initial State:
        - manifest.json file is present.

    Final State:
        - Manifest is returned unchanged.

    Raises:
        HTTPException(404): If manifest.json missing.

    Water Cost:
        - 0
    """
    try:
        with open("manifest.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/health")
def health() -> dict:
    """
    Reports basic liveness/health information.

    Returns:
        dict: Static health message.

    Water Cost:
        - 0 waterdrop per call
    """
    return {"status": "Auditor Agent is up and running."}


@app.get("/capabilities")
def get_capabilities() -> dict:
    """
    Loads and returns capabilities declared in the manifest.

    Returns:
        dict: {"capabilities": [...]}

    Raises:
        HTTPException(404): If manifest.json missing.

    Water Cost:
        - 0
    """
    try:
        with open("manifest.json", "r") as f:
            manifest = json.load(f)
        return {"capabilities": manifest.get("capabilities", [])}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/metrics")
def get_metrics() -> dict:
    """
    Provides runtime metrics including uptime, mood, and water usage.

    Returns:
        dict: Metrics snapshot.

    Water Cost:
        - 0
    """
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
    """
    Returns the current mood state of the auditor.

    Returns:
        dict: Current mood and last audit summary.

    Water Cost:
        - 0
    """
    return {
        "current_mood": mood.get("current_mood", "unknown"),
        "last_check": mood.get("last_check")
    }


@app.post("/run", response_model=AuditResult)
def run_audit(trace: ExecutionTrace):
    """
    Executes an LLM-only audit using per-agent policies fetched at runtime.

    Parameters:
        trace (ExecutionTrace): Validated list of pipeline steps to audit.

    Returns:
        AuditResult: Structured audit status with summary and per-step details.

    Initial State:
        - Each step carries '_agent_base_url' in input or output.
        - Each agent exposes /audit_policy endpoint.
        - license_keys.json contains a Mistral API key under "mistral".

    Final State:
        - Policies are fetched and forwarded to the LLM.
        - LLM returns the final audit; mood persisted; water usage incremented.

    Raises:
        HTTPException(500): If Mistral API key missing or LLM call fails.
        HTTPException(422): If base URL/policy discovery fails.

    Water Cost:
        - ~6 + 0.5*steps waterdrops per audit (LLM)
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

    # 2) Fetch policies for all agents present in the trace (strict)
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
    Dispatches the requested capability using the provided input payload.

    Parameters:
        request (Request): HTTP request containing 'capability' and 'input' fields.

    Returns:
        dict: Result object for the executed capability (AuditResult as dict for 'audit_trace').

    Initial State:
        - Agent is running and manifest declares the 'audit_trace' capability.
        - Input payload contains a known capability and well-formed input.

    Final State:
        - Matching handler is executed (currently only 'audit_trace').
        - Successful output is returned as a plain dict.

    Raises:
        HTTPException(400): If the capability is unknown.

    Water Cost:
        - 0.02 waterdrops per dispatch
    """
    increment_aiwaterdrops(0.02)
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