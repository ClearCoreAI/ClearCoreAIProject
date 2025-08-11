"""
Module: auditor
Component: Agent API
Purpose: Audit the output of other agents from execution traces and return a detailed quality report

Description:
This ClearCoreAI agent receives a full execution trace and analyzes the results of each step.
It verifies the presence of outputs and uses an LLM to assess the trustworthiness of agent results. It exposes a `/run` endpoint compatible with orchestration via the manifest.

Philosophy:
- All capabilities must be declared in the manifest
- No tight coupling with orchestrator
- Stateless, analytical behavior
- Tracks mood and water usage like other agents

Initial State:
- manifest.json is present and valid
- mood.json is present or initialized
- aiwaterdrops.json file is present or initialized

Final State:
- A structured audit report is returned
- Mood and water usage are updated and exposed via /metrics

Version: 0.1.0
Validated by: Olivier Hays
Date: 2025-08-06

Estimated Water Cost:
- 1 waterdrop per /health call
- ~2 waterdrops per /run audit (LLM only)
- 0.02 waterdrops per /execute dispatch
"""

# ----------- Imports ----------- #
import json
import time
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, List, Optional
from tools.water import increment_aiwaterdrops, load_aiwaterdrops, get_aiwaterdrops
from tools.llm_utils import audit_trace_with_mistral

# ----------- Constants ----------- #
AGENT_NAME = "auditor"
VERSION = "0.1.0"

# ----------- Credentials ----------- #
# LLM Key for auditor (Mistral)
try:
    with open("license_keys.json", "r") as license_json:
        license_keys = json.load(license_json)
except FileNotFoundError as license_error:
    # Not fatal: we will fallback to heuristic audit if key missing
    license_keys = {}

# ----------- App Initialization ----------- #
app = FastAPI(title="Auditor Agent", version=VERSION)
start_time = time.time()

# ----------- State Management ----------- #
# Mood
try:
    with open("mood.json", "r") as mood_json:
        mood = json.load(mood_json)
except FileNotFoundError:
    mood = {"current_mood": "neutral", "last_check": None}

# Current water consumption
aiwaterdrops_consumed = load_aiwaterdrops()

# ----------- Data Models ----------- #
class StepResult(BaseModel):
    """
    Represents a single agent step result from the orchestrator.

    Parameters:
        - agent (str): Name of the agent executed
        - input (Any): Input data provided to the agent
        - output (Any): Output returned by the agent
        - error (Optional[str]): Error message, if any

    Returns:
        - Structured agent result used for auditing
    """
    agent: str
    input: Any
    output: Any
    error: Optional[str] = None

class ExecutionTrace(BaseModel):
    """
    Represents the full trace of execution for a pipeline.

    Parameters:
        - steps (List[StepResult]): List of step results to audit

    Returns:
        - Validated trace structure for analysis
    """
    steps: List[StepResult]

class AuditFeedback(BaseModel):
    """
    Feedback issued by the auditor for one step.

    Parameters:
        - agent (str): Name of the agent being evaluated
        - status (str): Audit result (valid, warning, fail)
        - comment (str): Explanation of the audit status
        - score (float): Confidence score between 0 and 1

    Returns:
        - Structured audit result per step
    """
    agent: str
    status: str
    comment: str
    score: float

class AuditResult(BaseModel):
    """
    Full result of the audit across all steps.

    Parameters:
        - status (str): Global status of audit (ok, partial, fail)
        - summary (str): Text summary of validation count
        - details (List[AuditFeedback]): List of feedback objects

    Returns:
        - Audit report covering all agents in the trace
    """
    status: str
    summary: str
    details: List[AuditFeedback]

# ----------- Core Logic ----------- #

# ----------- Endpoints ----------- #
@app.get("/manifest")
def get_manifest() -> dict:
    """
    Returns the agent manifest loaded from disk.

    Parameters:
        None

    Returns:
        dict: Parsed contents of manifest.json.

    Initial State:
        - manifest.json file is present in the working directory
        - File is readable and contains valid JSON

    Final State:
        - Manifest is returned unchanged to the caller

    Raises:
        HTTPException: If manifest.json is missing (404)

    Water Cost:
        - 0 waterdrops per call
    """
    try:
        with open("manifest.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")

@app.get("/health")
def health() -> dict:
    """
    Reports basic liveness/health information for the auditor agent.

    Parameters:
        None

    Returns:
        dict: A static health message indicating the service is running.

    Initial State:
        - Application has started successfully

    Final State:
        - A short status JSON is returned

    Raises:
        None

    Water Cost:
        - 1 waterdrop per call
    """
    return {"status": "Auditor Agent is up and running."}

@app.get("/capabilities")
def get_capabilities() -> dict:
    """
    Loads and returns the capabilities declared in the manifest.

    Parameters:
        None

    Returns:
        dict: {"capabilities": <list from manifest.json>}

    Initial State:
        - manifest.json is present and readable

    Final State:
        - Extracted capabilities list is returned without modification

    Raises:
        HTTPException: If manifest.json cannot be found (404)

    Water Cost:
        - 0 waterdrops per call
    """
    try:
        with open("manifest.json", "r") as manifest_file:
            manifest = json.load(manifest_file)
        return {"capabilities": manifest.get("capabilities", [])}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")

@app.get("/metrics")
def get_metrics() -> dict:
    """
    Provides runtime metrics including uptime, mood, and water usage.

    Parameters:
        None

    Returns:
        dict: Metrics snapshot with agent name, version, uptime_seconds, current_mood, and aiwaterdrops_consumed.

    Initial State:
        - Agent start_time is initialized
        - Mood and water accounting are available

    Final State:
        - No persistent changes; a metrics JSON is returned

    Raises:
        None

    Water Cost:
        - 0 waterdrops per call
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

    Parameters:
        None

    Returns:
        dict: Current mood and the last audit summary reference.

    Initial State:
        - mood.json was loaded at startup (or defaulted)

    Final State:
        - No state change; mood snapshot is returned

    Raises:
        None

    Water Cost:
        - 0 waterdrops per call
    """
    return {
        "current_mood": mood.get("current_mood", "unknown"),
        "last_check": mood.get("last_check")
    }

@app.post("/run", response_model=AuditResult)
def run_audit(trace: ExecutionTrace):
    """
    Executes an LLM-based audit over a full execution trace.

    Parameters:
        trace (ExecutionTrace): Validated list of pipeline steps to audit.

    Returns:
        AuditResult: Structured audit status with summary and per-step details.

    Initial State:
        - A valid Mistral API key is available in license_keys.json
        - The input trace has been validated by Pydantic

    Final State:
        - LLM is called to produce an audit judgment
        - Mood is updated and persisted to mood.json
        - Waterdrop usage is incremented

    Raises:
        HTTPException: If the LLM API key is missing (500)
        HTTPException: If the LLM audit fails for any reason (500)

    Water Cost:
        - ~2.0 waterdrops per audit (based on LLM usage)
    """
    # Convert Pydantic objects to plain dicts for the LLM tool
    steps_payload = []
    for s in trace.steps:
        steps_payload.append({
            "agent": s.agent,
            "input": s.input,
            "output": s.output,
            "error": s.error,
        })

    # Try LLM-based audit first if API key is present
    api_key = license_keys.get("mistral")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM API key for mistral not found, cannot perform audit")

    try:

        llm_result, llm_water = audit_trace_with_mistral(
            {"steps": steps_payload},
            api_key
        )
        # Expecting llm_result to contain keys: status, summary, details
        status = llm_result.get("status", "partial")
        summary = llm_result.get("summary", "n/a")
        details_list = llm_result.get("details", [])

        # Convert detail dicts into AuditFeedback models safely
        details_models = []
        for d in details_list:
            details_models.append(
                AuditFeedback(
                    agent=d.get("agent", "unknown"),
                    status=d.get("status", "warning"),
                    comment=d.get("comment", ""),
                    score=float(d.get("score", 0.0)),
                )
            )

        water_used = float(llm_water or 2.0)

        result_model = AuditResult(
            status=status,
            summary=summary,
            details=details_models,
        )
        result_model.summary = f"[LLM] {result_model.summary}"
        print(f"[auditor] LLM audit used; waterdrops={water_used}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM audit failed: {str(e)}")

    # Update mood and persist
    mood["current_mood"] = "active"
    mood["last_check"] = result_model.summary
    with open("mood.json", "w") as mood_file:
        json.dump(mood, mood_file)

    # Track waterdrops
    increment_aiwaterdrops(water_used)

    return result_model


@app.post("/execute")
async def execute(request: Request) -> dict:
    """
    Dispatches the requested capability using the provided input payload.

    Parameters:
        request (Request): HTTP request containing 'capability' and 'input' fields.

    Returns:
        dict: Result object for the executed capability (e.g., AuditResult as dict for 'audit_trace').

    Initial State:
        - Agent is running and manifest declares the 'audit_trace' capability
        - Input payload contains a known capability and well-formed input

    Final State:
        - Matching handler is executed (currently only 'audit_trace')
        - Successful output is returned as a plain dict

    Raises:
        HTTPException: If the capability is unknown (400)
        HTTPException: If input validation fails during model parsing (422/500)

    Water Cost:
        - 0.02 waterdrops per dispatch
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
            return result.dict()  # Fallback for Pydantic v1

    raise HTTPException(status_code=400, detail=f"Unknown capability: {capability}")
