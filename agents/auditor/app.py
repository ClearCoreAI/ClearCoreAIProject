"""
Module: auditor
Component: Agent API
Purpose: Audit the output of other agents from execution traces and return a detailed quality report

Description:
This ClearCoreAI agent receives a full execution trace and analyzes the results of each step.
It verifies the presence of outputs, checks for errors, and uses heuristics to assess the trustworthiness
of agent results. It exposes a `/run` endpoint compatible with orchestration via the manifest.

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
- 2 waterdrops per /run audit
- 0.02 waterdrops per /execute dispatch
"""

# ----------- Imports ----------- #
import json
import time
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, List, Optional
from tools.water import increment_aiwaterdrops, load_aiwaterdrops, get_aiwaterdrops

# ----------- Constants ----------- #
AGENT_NAME = "auditor"
VERSION = "0.1.0"

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
def audit_step(step: StepResult) -> AuditFeedback:
    """
    Evaluates a single agent's step for quality and correctness.

    Parameters:
        - step (StepResult): The result of one agent execution

    Returns:
        - AuditFeedback: Quality evaluation for the step

    Initial State:
        - Input step is received as JSON

    Final State:
        - Audit status and score are calculated

    Water Cost:
        - 0.5 waterdrops per call
    """
    if step.error:
        return AuditFeedback(agent=step.agent, status="fail", comment=f"Error: {step.error}", score=0.0)
    if not step.output:
        return AuditFeedback(agent=step.agent, status="warning", comment="Empty output", score=0.3)
    if isinstance(step.output, str) and len(step.output.strip()) < 10:
        return AuditFeedback(agent=step.agent, status="warning", comment="Output too short", score=0.4)
    return AuditFeedback(agent=step.agent, status="valid", comment="Looks good", score=0.95)

# ----------- Endpoints ----------- #
@app.get("/manifest")
def get_manifest() -> dict:
    """
    Returns the agent's manifest file to the orchestrator.

    Returns:
        - dict: Manifest contents

    Initial State:
        - manifest.json file must be present

    Final State:
        - Manifest is returned as JSON

    Raises:
        - HTTPException: If manifest file is missing

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
    Confirms the agent is alive and running.

    Returns:
        - dict: Static health message

    Water Cost:
        - 1 waterdrop
    """
    return {"status": "Auditor Agent is up and running."}

@app.get("/capabilities")
def get_capabilities() -> dict:
    """
    Loads and returns the list of declared capabilities from the manifest.

    Returns:
        - dict: {"capabilities": [...]}

    Initial State:
        - manifest.json must be readable

    Final State:
        - List of capabilities is returned

    Water Cost:
        - 0
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
    Provides runtime and usage metrics for the agent.

    Returns:
        - dict: Uptime, mood, water usage and version

    Initial State:
        - mood.json and aiwaterdrops.json are loaded

    Final State:
        - Live snapshot is returned

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
    Returns current mood status of the agent.

    Returns:
        - dict: Mood state and last evaluated result

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
    Executes the audit logic on a full execution trace.

    Parameters:
        - trace (ExecutionTrace): List of steps from orchestrator

    Returns:
        - AuditResult: Report with validation status per step

    Initial State:
        - Steps are received and parsed

    Final State:
        - Mood is updated and water usage tracked

    Water Cost:
        - 2 waterdrops per trace
    """
    results = [audit_step(step) for step in trace.steps]
    nb_valid = sum(1 for r in results if r.status == "valid")
    nb_total = len(results)

    status = "ok" if nb_valid == nb_total else "fail" if nb_valid == 0 else "partial"
    summary = f"{nb_valid}/{nb_total} agents validated"

    mood["current_mood"] = "active"
    mood["last_check"] = summary

    with open("mood.json", "w") as mood_file:
        json.dump(mood, mood_file)

    increment_aiwaterdrops(2.0)

    return AuditResult(
        status=status,
        summary=summary,
        details=results
    )


@app.post("/execute")
async def execute(request: Request) -> dict:
    """
    Dispatches execution to the correct capability handler.

    Parameters:
        - request (Request): JSON request with 'capability' and 'input'

    Returns:
        - dict: Result of the executed capability

    Initial State:
        - Auditor agent is registered and manifest is valid

    Final State:
        - Matching capability is executed

    Raises:
        - HTTPException: If capability is unknown or input is invalid

    Water Cost:
        - 0.02 per dispatch
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
