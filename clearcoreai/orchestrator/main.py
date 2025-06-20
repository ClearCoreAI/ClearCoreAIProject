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
Date: 2025-06-20
Version: 0.3.1
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
from tools.water import increment_aiwaterdrops, load_aiwaterdrops, get_aiwaterdrops

# ----------- Constants ----------- #
ROOT = Path(__file__).parent
AGENTS_FILE = ROOT / "agents.json"
TEMPLATE_FILE = ROOT / "manifest_template.json"
AGENT_DIR = ROOT / "agents"
LICENSE_FILE = ROOT / "license_keys.json"
AIWATERDROPS_FILE  = ROOT / "memory" / "short_term" / "aiwaterdrops.json"
VERSION = "0.3.1"

# ----------- Credentials ----------- #
# LLM Key
try:
    with open("license_keys.json", "r") as license_json:
        license_keys = json.load(license_json)
except FileNotFoundError as license_error:
    raise RuntimeError("Missing license_keys.json. Cannot proceed without license.") from license_error

# ----------- App Initialization ----------- #
app = FastAPI(
    title="ClearCoreAI Orchestrator",
    description="Central hub for registering and connecting ClearCoreAI agents.",
    version=VERSION
)

# ----------- State Management ----------- #

# Current water consumption
aiwaterdrops_consumed = load_aiwaterdrops()
# Agents storage
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
    Summary:
        Load the registry of agents from disk if it exists.

    Parameters:
        None

    Returns:
        dict: Parsed content of agents.json, or empty dict if file not found.

    Initial State:
        `agents.json` may or may not exist.

    Final State:
        Returns loaded registry or initializes an empty one.

    Raises:
        RuntimeError — if agents.json is malformed or cannot be read.

    Water Cost:
        0 (internal function)
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
    Summary:
        Save the current agent registry to disk.

    Parameters:
        registry (dict): The agent registry to persist.

    Returns:
        None

    Initial State:
        In-memory `registry` is populated.

    Final State:
        `agents.json` is written or overwritten.

    Raises:
        RuntimeError — if writing to disk fails.

    Water Cost:
        0 (internal function)
    """
    try:
        with AGENTS_FILE.open("w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
    except Exception as save_error:
        raise RuntimeError(f"Failed to persist registry: {save_error}")

def _load_agent_manifest(agent_name: str) -> dict:
    """
    Summary:
        Load manifest.json of a specific agent by name.

    Parameters:
        agent_name (str): Name of the agent.

    Returns:
        dict: Parsed content of the agent's manifest.json.

    Initial State:
        Agent's manifest file must exist under agents/<agent_name>/.

    Final State:
        Manifest is loaded and returned.

    Raises:
        FileNotFoundError — if manifest does not exist.

    Water Cost:
        0 (internal function)
    """
    manifest_path = AGENT_DIR / agent_name / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found for agent: {agent_name}")
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _are_specs_compatible(output_spec: dict, input_spec: dict) -> bool:
    """
    Summary:
        Check if the output type of one agent matches the input type of another.

    Parameters:
        output_spec (dict): Output specification from an agent manifest.
        input_spec (dict): Input specification from another agent manifest.

    Returns:
        bool: True if specs match on type, else False.

    Initial State:
        Both specs must be valid dictionaries.

    Final State:
        Compatibility is evaluated.

    Raises:
        None

    Water Cost:
        0 (internal function)
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
    """
    Summary:
        Check orchestrator status and return list of registered agents.

    Parameters:
        None

    Returns:
        dict: Dictionary with orchestrator status and agent names.

    Initial State:
        Orchestrator must be running and registry loaded.

    Final State:
        Returns basic health information and current agent list.

    Raises:
        None

    Water Cost:
        0
    """
    return {
        "status": "ClearCoreAI Orchestrator is running.",
        "registered_agents": list(agents_registry.keys())
    }

@app.post("/register_agent")
def register_agent(agent: AgentRegistration):
    """
    Summary:
        Register a new agent by validating its manifest and storing it persistently.

    Parameters:
        agent (AgentRegistration): Object containing agent name and base URL.

    Returns:
        dict: Confirmation message upon success.

    Initial State:
        Agent must expose a valid `/manifest` endpoint.

    Final State:
        Agent manifest is stored and visible in registry.

    Raises:
        HTTPException — if unreachable, malformed, or manifest is invalid.

    Water Cost:
        0.2 waterdrops
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
    increment_aiwaterdrops(0.2)
    return {"message": f"Agent '{agent.name}' registered successfully."}

@app.get("/agents")
def list_agents():
    """
    Summary:
        List all registered agents along with their declared capabilities.

    Parameters:
        None

    Returns:
        dict: Mapping of agent names to base_url and capabilities.

    Initial State:
        Registry must be loaded.

    Final State:
        Returns a filtered view of registered agents.

    Raises:
        None

    Water Cost:
        0.05 waterdrops
    """
    increment_aiwaterdrops(0.05)
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
    Summary:
        Retrieve full manifest for a given agent.

    Parameters:
        agent_name (str): The name of the agent to query.

    Returns:
        dict: Parsed manifest of the agent.

    Initial State:
        Agent must be registered.

    Final State:
        Manifest is returned unchanged.

    Raises:
        HTTPException — if agent not found.

    Water Cost:
        0
    """
    if agent_name not in agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return agents_registry[agent_name]["manifest"]

@app.get("/agents/connections")
def detect_agent_connections():
    """
    Summary:
        Detect compatible input/output connections between all registered agents.

    Parameters:
        None

    Returns:
        dict: List of connection tuples with reasons.

    Initial State:
        Registry must be populated with valid manifests.

    Final State:
        Computed list of agent links is returned.

    Raises:
        HTTPException — on manifest parsing or matching failure.

    Water Cost:
        0
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
    Summary:
        Query all registered agents for their `/metrics` data.

    Parameters:
        None

    Returns:
        dict: Aggregated metrics per agent or error info.

    Initial State:
        Agents must expose `/metrics`.

    Final State:
        Returns latest metrics or fallback error per agent.

    Raises:
        None, handled gracefully per agent.

    Water Cost:
        0 (monitoring is free)
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
    Summary:
        Return raw manifest content for all registered agents.

    Parameters:
        None

    Returns:
        dict: Agent names mapped to their manifest.json content.

    Initial State:
        Registry must contain valid manifests.

    Final State:
        Manifests are returned verbatim.

    Raises:
        None

    Water Cost:
        0
    """
    return {
        name: data["manifest"]
        for name, data in agents_registry.items()
    }

# ----------- Planning & Execution ----------- #
def generate_plan_from_goal(goal: str) -> str:
    """
    Summary:
        Generate an execution plan from a natural language goal using LLM inference.

    Parameters:
        goal (str): Natural language objective to transform into a structured plan.

    Returns:
        str: Multistep plan in numbered text format, one step per line.

    Initial State:
        LICENSE_FILE must exist and contain a valid API key.
        Registry must contain at least one agent with declared capabilities.

    Final State:
        A valid execution plan string is returned.

    Raises:
        RuntimeError — if plan generation fails or returns invalid format.

    Water Cost:
        3 waterdrops (LLM inference and registry scan)
    """
    try:
        plan, water_cost = generate_plan_with_mistral(goal, agents_registry, license_keys)
        increment_aiwaterdrops(water_cost)
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
    Summary:
        Generate a ClearCoreAI execution plan from a given goal string.

    Parameters:
        request (GoalRequest): Must contain a 'goal' key with a natural language objective.

    Returns:
        dict: The original goal and its corresponding structured plan.

    Initial State:
        Same as `generate_plan_from_goal`.

    Final State:
        Returns the computed plan string.

    Raises:
        HTTPException — if goal is missing or plan generation fails.

    Water Cost:
        3 waterdrops (delegates to LLM plan generation)
    """
    goal =  request.get("goal")
    if not goal:
        raise HTTPException(status_code=400, detail="Missing 'goal' field.")
    try:
        plan = generate_plan_from_goal(goal)
        return {"goal": goal, "plan": plan}
    except Exception as planning_error:
        raise HTTPException(status_code=500, detail=str(planning_error))

def execute_plan_string(plan: str) -> dict:
    """
    Summary:
        Execute a structured plan step-by-step and return a full execution trace.

    Parameters:
        plan (str): Multiline execution plan, formatted as "1. agent → capability".

    Returns:
        dict: Contains the full plan, per-step execution trace, and final output context.

    Initial State:
        Agents in the plan must be registered and reachable via /execute.

    Final State:
        Executes each step in sequence, updating shared context progressively.

    Raises:
        None directly — execution errors are embedded per step in the result.

    Water Cost:
        ~0.02 waterdrops fixed + full cost of each /execute call per step (depends on agents)
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

    increment_aiwaterdrops(0.02)
    return {
        "plan": plan,
        "execution": results,
        "final_output": context
    }

@app.post("/execute_plan")
def execute_plan(request: dict):
    """
    Summary:
        Execute a given textual plan and return the results.

    Parameters:
        request (dict): Must contain a 'plan' field with a valid plan string.

    Returns:
        dict: Execution result as returned by `execute_plan_string`.

    Initial State:
        Same requirements as `execute_plan_string`.

    Final State:
        Plan is fully executed or halted on first major error.

    Raises:
        HTTPException — if the 'plan' field is missing.

    Water Cost:
        Pass-through — see `execute_plan_string`
    """
    plan = request.get("plan")
    if not plan:
        raise HTTPException(status_code=400, detail="Missing 'plan' field.")
    return execute_plan_string(plan)

@app.post("/run_goal")
def run_goal(payload: dict):
    """
    Summary:
        End-to-end handler: transforms a natural language goal into a plan and executes it.

    Parameters:
        payload (dict): Must contain a 'goal' string field.

    Returns:
        dict: Full result including goal, generated plan, and execution trace.

    Initial State:
        Same as for plan and execution.

    Final State:
        One-click processing of goal into final output.

    Raises:
        HTTPException — if goal is missing or any part of the process fails.

    Water Cost:
        3 waterdrops (plan) + all waterdrops from plan execution (variable)
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

@app.get("/water/total")
def get_total_water_usage():
    """
    Summary:
        Returns the total waterdrop consumption including orchestrator and all agents.

    Parameters:
        None

    Returns:
        dict: Breakdown of water usage per component and total sum.

    Initial State:
        Orchestrator and agents have stored water usage data.

    Final State:
        Aggregated metrics are computed and returned.

    Raises:
        None

    Water Cost:
        0
    """
    from tools.water import get_aiwaterdrops

    total = get_aiwaterdrops()
    breakdown = {
        "orchestrator": total
    }

    for name, data in agents_registry.items():
        base_url = data.get("base_url")
        try:
            response = requests.get(f"{base_url}/metrics", timeout=3)
            response.raise_for_status()
            agent_data = response.json()
            usage = agent_data.get("aiwaterdrops_consumed", 0.0)
            breakdown[name] = usage
            total += usage
        except Exception as e:
            breakdown[name] = f"error: {str(e)}"

    return {
        "breakdown": breakdown,
        "total_waterdrops": round(total, 3)
    }