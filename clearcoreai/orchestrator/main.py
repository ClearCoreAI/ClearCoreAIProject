"""
Module: orchestrator
Process: Central Orchestrator API for ClearCoreAI

Description:
This orchestrator acts as the central coordinator for ClearCoreAI agents.
It supports agent registration, dynamic capability discovery, manifest validation,
and persistent memory of connected agents.

Version: 0.2.0
Initial State: Loads previous agents and manifest schema.
Final State: Runs a REST API to register and list agents dynamically.

Exceptions handled:
- FileNotFoundError — if persistent memory or template is missing.
- HTTPException 400 — for invalid inputs or unreachable agents.
- ValidationError — for schema mismatches in agent manifests.

Validation:
- Validated by: Olivier Hays
- Date: 2025-06-15

Estimated Water Cost:
- 0.2 waterdrops per registration
- 0.05 waterdrops per listing
"""

import json
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from jsonschema import validate, ValidationError

# Constants
AGENTS_FILE = "agents.json"
TEMPLATE_FILE = "manifest_template.json"
AGENT_DIR = "agents"

# App
app = FastAPI(
    title="ClearCoreAI Orchestrator",
    description="Central hub for registering and connecting ClearCoreAI agents.",
    version="0.2.0"
)

# Global registry (in memory)
agents_registry = {}

# Load manifest template schema for validation
try:
    with open(TEMPLATE_FILE, "r") as f:
        manifest_template = json.load(f)
except FileNotFoundError:
    raise RuntimeError("Missing manifest_template.json file. Cannot start orchestrator.")
except Exception as e:
    raise RuntimeError(f"Could not load manifest_template.json: {e}")

# Load previously registered agents
def _load_agents() -> dict:
    if Path(AGENTS_FILE).exists():
        try:
            with open(AGENTS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load agents.json: {e}")
    return {}

# Save current registry
def _save_agents(registry: dict) -> None:
    with open(AGENTS_FILE, "w") as f:
        json.dump(registry, f, indent=2)

# Load agent manifest from filesystem
def _load_agent_manifest(agent_name: str) -> dict:
    manifest_path = Path(AGENT_DIR) / agent_name / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found for agent: {agent_name}")
    with open(manifest_path, "r") as f:
        return json.load(f)

# Compare specs to infer compatibility
def _are_specs_compatible(output_spec: dict, input_spec: dict) -> bool:
    return output_spec.get("type") == input_spec.get("type")

# Populate memory on startup
agents_registry = _load_agents()


# -------- API Endpoints -------- #

class AgentRegistration(BaseModel):
    name: str
    base_url: str


@app.get("/health")
def health():
    return {
        "status": "ClearCoreAI Orchestrator is running.",
        "registered_agents": list(agents_registry.keys())
    }


@app.post("/register_agent")
def register_agent(agent: AgentRegistration):
    try:
        response = requests.get(f"{agent.base_url}/capabilities", timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Cannot reach agent at {agent.base_url}: {e}")

    try:
        manifest = response.json()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to persist registry: {e}")

    return {"message": f"Agent '{agent.name}' registered successfully."}


@app.get("/agents")
def list_agents():
    return {
        "agents": {
            name: {
                "base_url": agent["base_url"],
                "capabilities": agent["manifest"].get("capabilities", [])
            }
            for name, agent in agents_registry.items()
        }
    }


@app.get("/agent_manifest/{agent_name}")
def get_agent_manifest(agent_name: str):
    if agent_name not in agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return agents_registry[agent_name]["manifest"]


@app.get("/agents/connections")
def detect_agent_connections():
    """
    Analyzes input/output specs of all registered agents to infer valid data flow connections.
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
    Module: orchestrator
    Function: aggregate_agent_metrics

    Description:
    Aggregates real-time /metrics info from all registered agents.

    Version: 0.2.0
    Initial State: All agents must be registered with valid base_url.
    Final State: No change. Data fetched and returned on-demand.

    Exceptions handled:
    - ConnectionError or Timeout — when agent is unreachable.
    - ValueError — when JSON is invalid or response is not parsable.

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-15

    Estimated Water Cost:
    - 0.1 waterdrops per call per agent

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