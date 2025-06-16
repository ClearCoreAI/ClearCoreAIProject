"""
Module: orchestrator
Component: Central Orchestrator API
Purpose: Core routing and coordination layer for ClearCoreAI

Description:
This orchestrator exposes the REST API and manages all agent coordination within ClearCoreAI.
It enables agent registration, manifest validation, capability discovery, compatibility checking,
plan generation, and full pipeline execution. All operations follow a traceable and deterministic
model compatible with multi-agent orchestration.

Philosophy:
- The orchestrator must only work with agents declared and validated through their manifest.
- Each step must be auditable and reproducible from input to output.
- All failures should return clear, structured messages to calling clients.
- Execution plans must use only compatible agent capabilities based on declared I/O specs.
- Energy usage is expressed in waterdrops to measure execution cost.

Initial State:
- `manifest_template.json` is present and valid
- `license_keys.json` is present and contains required API keys
- Agents may be pre-registered in `agents.json` or dynamically added
- The FastAPI server is launched and ready to accept connections

Final State:
- Agents are validated and stored in memory and on disk
- Connections between agents are inferred based on I/O spec compatibility
- Plans are generated via LLM and executed across agents in sequence
- All state changes and plan steps are returned as structured logs

Version: 0.3.0
Validated by: Olivier Hays
Date: 2025-06-15

Estimated Water Cost:
- 0.2 waterdrops per /register_agent
- 0.05 waterdrops per /agents or /manifest call
- 3 waterdrops per complete planning and execution pipeline (/run_goal)
"""

import json
import requests
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from jsonschema import validate, ValidationError
from tools.llm_utils import generate_plan_with_mistral

# ----------- Constants ----------- #
AGENTS_FILE = "agents.json"
TEMPLATE_FILE = "manifest_template.json"
AGENT_DIR = "agents"

# ----------- FastAPI App ----------- #
app = FastAPI(
    title="ClearCoreAI Orchestrator",
    description="Central hub for registering and connecting ClearCoreAI agents.",
    version="0.3.0"
)

# ----------- In-Memory Agent Registry ----------- #
agents_registry = {}

# ----------- Startup Initialization ----------- #

# Load JSON schema template for validating agent manifests
try:
    with open(TEMPLATE_FILE, "r") as f:
        manifest_template = json.load(f)
except FileNotFoundError:
    raise RuntimeError("Missing manifest_template.json file. Cannot start orchestrator.")
except Exception as e:
    raise RuntimeError(f"Could not load manifest_template.json: {e}")

# Restore memory of registered agents from disk
def _load_agents() -> dict:
    if Path(AGENTS_FILE).exists():
        try:
            with open(AGENTS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load agents.json: {e}")
    return {}

# Persist registered agents to disk
def _save_agents(registry: dict) -> None:
    try:
        with open(AGENTS_FILE, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        raise RuntimeError(f"Failed to persist registry: {e}")

# Load manifest directly from agent directory (not used in live registration)
def _load_agent_manifest(agent_name: str) -> dict:
    manifest_path = Path(AGENT_DIR) / agent_name / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found for agent: {agent_name}")
    with open(manifest_path, "r") as f:
        return json.load(f)

# Check if one agent's output is compatible with another agent's input
def _are_specs_compatible(output_spec: dict, input_spec: dict) -> bool:
    return output_spec.get("type") == input_spec.get("type")

# Initialize agent registry
agents_registry = _load_agents()

# ----------- API Models ----------- #
class AgentRegistration(BaseModel):
    name: str
    base_url: str

# ----------- API Endpoints ----------- #

@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ClearCoreAI Orchestrator is running.",
        "registered_agents": list(agents_registry.keys())
    }

@app.post("/register_agent")
def register_agent(agent: AgentRegistration):
    """
    Registers an agent by querying its manifest and validating it.
    """
    try:
        response = requests.get(f"{agent.base_url}/capabilities", timeout=5)
        response.raise_for_status()
        manifest = response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Cannot reach agent at {agent.base_url}: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON from agent: {e}")

    try:
        validate(instance=manifest, schema=manifest_template)
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=f"Manifest invalid: {ve.message}")

    agents_registry[agent.name] = {
        "base_url": agent.base_url,
        "manifest": manifest
    }

    try:
        _save_agents(agents_registry)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": f"Agent '{agent.name}' registered successfully."}

@app.get("/agents")
def list_agents():
    """Returns all registered agents and their declared capabilities."""
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
    """Returns full manifest for a specific agent."""
    if agent_name not in agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return agents_registry[agent_name]["manifest"]

@app.get("/agents/connections")
def detect_agent_connections():
    """
    Detects agent-to-agent connections based on I/O compatibility.
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
                if not to_in:
                    continue

                if _are_specs_compatible(from_out, to_in):
                    connections.append({
                        "from": from_name,
                        "to": to_name,
                        "reason": f"Output from '{from_name}' matches input of '{to_name}'"
                    })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection analysis failed: {str(e)}")

    return {"connections": connections}

@app.get("/agents/metrics")
def aggregate_agent_metrics():
    """
    Calls each agent’s /metrics endpoint and aggregates results.
    """
    results = {}
    for name, data in agents_registry.items():
        base_url = data.get("base_url")
        try:
            response = requests.get(f"{base_url}/metrics", timeout=3)
            response.raise_for_status()
            results[name] = response.json()
        except Exception as e:
            results[name] = {"error": f"Failed to fetch metrics: {str(e)}"}
    return results

@app.get("/agents/raw")
def get_all_agent_manifests():
    """
    Returns the full manifest of all agents for debugging purposes.
    """
    return {
        name: data["manifest"]
        for name, data in agents_registry.items()
    }

# ----------- Planning & Execution ----------- #

def generate_plan_from_goal(goal: str) -> str:
    """
    Internal utility: generate a textual plan from a natural language goal.
    """
    try:
        with open("license_keys.json", "r") as f:
            license_keys = json.load(f)
        plan, _ = generate_plan_with_mistral(goal, agents_registry)
        if isinstance(plan, list):
            plan = "\n".join(map(str, plan))  # safety fallback
        elif not isinstance(plan, str):
            raise RuntimeError(f"Invalid plan format: expected str, got {type(plan)}")
        return plan
    except Exception as e:
        raise RuntimeError(f"Plan generation failed: {e}")

@app.post("/plan")
def plan_goal(request: dict):
    """Exposes the planning step as a REST endpoint."""
    goal = request.get("goal")
    if not goal:
        raise HTTPException(status_code=400, detail="Missing 'goal' field.")
    try:
        plan = generate_plan_from_goal(goal)
        return {"goal": goal, "plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def execute_plan_string(plan: str) -> dict:
    """
    Internal utility: executes a multi-step plan across agents, forwarding context between steps.
    """
    results = []
    context = None

    for step in plan.splitlines():
        step = step.strip()
        if not step or step.startswith("#"):
            continue

        match = re.match(r"^\d+\.\s*(\w+)[^\w]+(\w+)$", step)
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
            r = requests.post(url, json=payload, timeout=30)
            r.raise_for_status()
            context = r.json()
            results.append({"step": step, "output": context})

        except Exception as e:
            results.append({"step": step, "error": str(e)})
            break

    return {
        "plan": plan,
        "execution": results,
        "final_output": context
    }

@app.post("/execute_plan")
def execute_plan(request: dict):
    """Receives a plan string and executes it sequentially across agents."""
    plan = request.get("plan")
    if not plan:
        raise HTTPException(status_code=400, detail="Missing 'plan' field.")
    return execute_plan_string(plan)

@app.post("/run_goal")
def run_goal(payload: dict):
    """
    Executes a full goal in one call: generates plan and runs it.
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))