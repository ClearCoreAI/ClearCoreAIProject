"""
Module: orchestrator
Component: Central Orchestrator API for ClearCoreAI

Description:
This orchestrator acts as the central coordinator for ClearCoreAI agents.
It supports agent registration, dynamic capability discovery, manifest validation,
execution planning, and persistent memory of connected agents.

Philosophy:
- Agents declare capabilities via manifest.json
- Agent connectivity and compatibility are analyzed dynamically
- Orchestrator drives plan-based execution and centralized monitoring

Initial State:
- Loads agents.json if it exists
- Loads manifest_template.json to validate agent capabilities

Final State:
- Runs a REST API to register agents, generate execution plans, and coordinate workflows

Exceptions handled:
- FileNotFoundError — if persistent memory or template is missing
- HTTPException — for invalid inputs or unreachable agents
- ValidationError — for schema mismatches in agent manifests
- RuntimeError — for startup failures or persistence errors

Estimated Water Cost:
- 0.2 waterdrops per registration
- 0.05 waterdrops per listing
- 3 waterdrops per planning

Validated by: Olivier Hays
Date: 2025-06-18
Version: 0.3.0
"""

# ----------- Imports ----------- #
import json
import re
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from jsonschema import validate, ValidationError
from tools.llm_utils import generate_plan_with_mistral

# ----------- Constants ----------- #
ROOT = Path(__file__).parent
AGENTS_FILE = ROOT / "agents.json"
TEMPLATE_FILE = ROOT / "manifest_template.json"
AGENT_DIR = ROOT / "agents"
LICENSE_FILE = ROOT / "license_keys.json"

# ----------- FastAPI App ----------- #
app = FastAPI(
    title="ClearCoreAI Orchestrator",
    description="Central hub for registering and connecting ClearCoreAI agents.",
    version="0.3.0"
)

# ----------- In-Memory Agent Registry ----------- #
agents_registry = {}

# ----------- Load Template ----------- #
try:
    with TEMPLATE_FILE.open("r", encoding="utf-8") as template_file:
        manifest_template = json.load(template_file)
except FileNotFoundError:
    raise RuntimeError("Missing manifest_template.json file. Cannot start orchestrator.")
except Exception as template_error:
    raise RuntimeError(f"Could not load manifest_template.json: {template_error}")

# ----------- Internal Utilities ----------- #
def _load_agents() -> dict:
    """
    Loads the saved registry of agents from disk.
    """
    if AGENTS_FILE.exists():
        try:
            with AGENTS_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as load_error:
            raise RuntimeError(f"Failed to load agents.json: {load_error}")
    return {}

def _save_agents(registry: dict) -> None:
    """
    Persists the current agent registry to disk.
    """
    try:
        with AGENTS_FILE.open("w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
    except Exception as save_error:
        raise RuntimeError(f"Failed to persist registry: {save_error}")

def _load_agent_manifest(agent_name: str) -> dict:
    """
    Loads the manifest.json of a given agent.
    """
    manifest_path = AGENT_DIR / agent_name / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found for agent: {agent_name}")
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _are_specs_compatible(output_spec: dict, input_spec: dict) -> bool:
    """
    Determines whether an output spec and input spec are type-compatible.
    """
    return output_spec.get("type") == input_spec.get("type")

# Load registry at startup
agents_registry = _load_agents()

# ----------- API Models ----------- #
class AgentRegistration(BaseModel):
    name: str
    base_url: str

# ----------- API Endpoints ----------- #
@app.get("/health")
def health():
    return {
        "status": "ClearCoreAI Orchestrator is running.",
        "registered_agents": list(agents_registry.keys())
    }

@app.post("/register_agent")
def register_agent(agent: AgentRegistration):
    """
    Registers a new agent, validates its manifest, and saves it to the registry.
    """
    try:
        # ➤ Use /manifest instead of /capabilities to get the full manifest
        manifest_response = requests.get(f"{agent.base_url}/manifest", timeout=5)
        manifest_response.raise_for_status()
        manifest = manifest_response.json()
    except requests.exceptions.RequestException as req_error:
        raise HTTPException(status_code=400, detail=f"Cannot reach agent at {agent.base_url}: {req_error}")
    except Exception as json_error:
        raise HTTPException(status_code=400, detail=f"Invalid JSON from /manifest: {json_error}")

    try:
        validate(instance=manifest, schema=manifest_template)
    except ValidationError as validation_error:
        raise HTTPException(status_code=400, detail=f"Manifest invalid: {validation_error.message}")

    agents_registry[agent.name] = {
        "base_url": agent.base_url,
        "manifest": manifest
    }

    try:
        _save_agents(agents_registry)
    except RuntimeError as save_error:
        raise HTTPException(status_code=500, detail=str(save_error))

    return {"message": f"Agent '{agent.name}' registered successfully."}

@app.get("/agents")
def list_agents():
    """
    Returns a list of registered agents and their capabilities.
    """
    return {
        "agents": {
            name: {
                "base_url": data["base_url"],
                "capabilities": data["manifest"].get("capabilities", [])
            }
            for name, data in agents_registry.items()
        }
    }

@app.get("/agent_manifest/{agent_name}")
def get_agent_manifest(agent_name: str):
    """
    Returns the manifest.json for a given agent.
    """
    if agent_name not in agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return agents_registry[agent_name]["manifest"]

@app.get("/agents/connections")
def detect_agent_connections():
    """
    Computes a list of compatible input/output links between agents.
    """
    connections = []
    try:
        for from_name, from_data in agents_registry.items():
            from_out = from_data["manifest"].get("output_spec")
            if not from_out:
                continue
            for to_name, to_data in agents_registry.items():
                if from_name == to_name:
                    continue
                to_in = to_data["manifest"].get("input_spec")
                if to_in and _are_specs_compatible(from_out, to_in):
                    connections.append({
                        "from": from_name,
                        "to": to_name,
                        "reason": f"Output from '{from_name}' matches input of '{to_name}'"
                    })
    except Exception as conn_error:
        raise HTTPException(status_code=500, detail=f"Connection analysis failed: {str(conn_error)}")

    return {"connections": connections}

@app.get("/agents/metrics")
def aggregate_agent_metrics():
    """
    Queries all agents for /metrics and aggregates results.
    """
    results = {}
    for name, data in agents_registry.items():
        base_url = data.get("base_url")
        try:
            response = requests.get(f"{base_url}/metrics", timeout=3)
            response.raise_for_status()
            results[name] = response.json()
        except Exception as metrics_error:
            results[name] = {"error": f"Failed to fetch metrics: {str(metrics_error)}"}
    return results

@app.get("/agents/raw")
def get_all_agent_manifests():
    """
    Returns all registered agents' manifest.json content.
    """
    return {
        name: data["manifest"]
        for name, data in agents_registry.items()
    }

# ----------- Planning & Execution ----------- #
def generate_plan_from_goal(goal: str) -> str:
    """
    Generates an execution plan from a natural language goal using LLM inference.
    """
    try:
        with LICENSE_FILE.open("r", encoding="utf-8") as f:
            license_keys = json.load(f)
        plan, _ = generate_plan_with_mistral(goal, agents_registry, license_keys)
        if isinstance(plan, list):
            return "\n".join(map(str, plan))
        elif isinstance(plan, str):
            return plan
        else:
            raise RuntimeError(f"Invalid plan format: expected str or list, got {type(plan)}")
    except Exception as plan_error:
        raise RuntimeError(f"Plan generation failed: {plan_error}")

@app.post("/plan")
def plan_goal(request: dict):
    """
    Converts a goal into a multi-step execution plan.
    """
    goal = request.get("goal")
    if not goal:
        raise HTTPException(status_code=400, detail="Missing 'goal' field.")
    try:
        plan = generate_plan_from_goal(goal)
        return {"goal": goal, "plan": plan}
    except Exception as planning_error:
        raise HTTPException(status_code=500, detail=str(planning_error))

def execute_plan_string(plan: str) -> dict:
    """
    Executes a step-by-step plan and returns traceable outputs for each stage.
    """
    results = []
    context = None

    for step in plan.splitlines():
        step = step.strip()
        if not step or step.startswith("#"):
            continue

        match = re.match(r"^\d+\.\s*(\w+)\s*→\s*(\w+)$", step)
        if not match:
            results.append({"step": step, "error": "Unrecognized format"})
            continue

        agent_name, capability = match.groups()
        agent = agents_registry.get(agent_name)
        if not agent:
            results.append({"step": step, "error": f"Agent '{agent_name}' not registered"})
            continue

        try:
            input_data = context
            if capability == "structured_output_generation" and isinstance(context, dict):
                summaries = context.get("summaries")
                if summaries:
                    input_data = {"summaries": summaries}

            url = f"{agent['base_url']}/execute"
            payload = {"capability": capability, "input": input_data}
            execution_response = requests.post(url, json=payload, timeout=30)
            execution_response.raise_for_status()
            context = execution_response.json()
            results.append({"step": step, "output": context})
        except Exception as execution_error:
            results.append({"step": step, "error": str(execution_error)})
            break

    return {
        "plan": plan,
        "execution": results,
        "final_output": context
    }

@app.post("/execute_plan")
def execute_plan(request: dict):
    """
    Executes a plan provided in plain text.
    """
    plan = request.get("plan")
    if not plan:
        raise HTTPException(status_code=400, detail="Missing 'plan' field.")
    return execute_plan_string(plan)

@app.post("/run_goal")
def run_goal(payload: dict):
    """
    High-level endpoint to handle natural language goal:
    generates a plan and executes it fully.
    """
    goal = payload.get("goal")
    if not goal:
        raise HTTPException(status_code=400, detail="Missing 'goal' field.")
    try:
        plan = generate_plan_from_goal(goal)
        result = execute_plan_string(plan)
        return {
            "goal": goal,
            "plan": plan,
            "result": result
        }
    except Exception as run_error:
        raise HTTPException(status_code=500, detail=str(run_error))