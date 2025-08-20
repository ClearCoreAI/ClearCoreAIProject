"""
Module: orchestrator
Component: Central Orchestrator API for ClearCoreAI
Purpose: Register agents, validate manifests, plan with LLM, and execute multi-agent workflows.

Description:
This service is the central coordinator for ClearCoreAI agents. It lets you:
- Register agents (and persist them) after validating their manifest against a schema
- Discover capabilities dynamically from each agent’s manifest
- Generate an executable plan from a natural-language goal via the Mistral LLM
- Execute that plan step-by-step, building a full execution trace
- Aggregate basic metrics and water usage

How it works (end-to-end call flow):
1) Agent Registration
   - Client → POST /register_agent {name, base_url}
   - Orchestrator → GET {base_url}/manifest
   - Normalize capabilities, validate against manifest_template.json
   - Persist to agents.json (registry)

2) Planning
   - Client → POST /plan {goal} or /run_goal {goal}
   - Orchestrator → tools.llm_utils.generate_plan_with_mistral(goal, agents_registry, license_keys)
   - LLM returns numbered steps like "1. agent → capability"
   - Plan text is sanitized to keep only valid (agent, capability) pairs

3) Execution
   - Orchestrator iterates steps and POSTs to each agent’s /execute with:
       { "capability": ..., "input": { previous_context..., "_agent_base_url": agent.base_url } }
   - Collects outputs and errors into a structured execution trace
   - If an agent declares a custom_input_handler == "use_execution_trace", it receives the entire prior trace

4) Auditing (optional in plan)
   - If the plan ends with an audit step (e.g., auditor → audit_trace), the auditor agent will get the whole trace
     including input_used + output for each step, enabling policy-based or LLM-based audits.

Initial State:
- license_keys.json exists and contains a valid Mistral API key
- manifest_template.json exists to validate agent manifests
- agents.json may or may not exist (registry loads empty if absent)

Final State:
- A REST API runs to register agents, generate/execute plans, and surface metrics
- agents.json contains persistent registry
- Execution endpoints return a full trace with per-step inputs/outputs

Exceptions handled:
- FileNotFoundError — missing template/credentials at startup
- HTTPException — invalid inputs, unreachable agents, or unexpected runtime conditions
- ValidationError — manifest schema violations
- RuntimeError — persistence or planning failures

Estimated Water Cost:
- 0.2 waterdrops per registration
- 0.05 waterdrops per listing
- 3 waterdrops per planning (plus execution costs per agent)

Validated by: Olivier Hays
Date: 2025-06-20
Version: 0.3.3

----------------------------------------------------------------------
Quick examples:

# Register an agent
curl -s -X POST http://localhost:8000/register_agent \
  -H "Content-Type: application/json" \
  -d '{"name":"summarize_articles","base_url":"http://summarize_articles:8600"}'

# Plan + Execute a goal in one call
curl -s -X POST http://localhost:8000/run_goal \
  -H "Content-Type: application/json" \
  -d '{"goal":"Fetch articles about AI and summarize them with a quality audit"}' | jq

# Inspect registry
curl -s http://localhost:8000/agents | jq
----------------------------------------------------------------------
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
AIWATERDROPS_FILE = ROOT / "memory" / "short_term" / "aiwaterdrops.json"
VERSION = "0.3.3"

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
aiwaterdrops_consumed = load_aiwaterdrops()
agents_registry = {}

# ----------- Load Template ----------- #
try:
    with TEMPLATE_FILE.open("r", encoding="utf-8") as template_file:
        manifest_template = json.load(template_file)
except FileNotFoundError:
    raise RuntimeError("Missing manifest_template.json file. Cannot start orchestrator.")
except Exception as template_error:
    raise RuntimeError(f"Could not load manifest_template.json: {template_error}")

# -------------- Helper functions -------------#
def safe_json(obj, max_depth=6):
    """
    Produces a JSON-safe, acyclic structure from arbitrary Python objects.

    Parameters:
        obj (Any): Any Python object
        max_depth (int): Hard cap to avoid deep recursion

    Returns:
        Any: A structure composed of dict/list/str/float/int/bool/None

    Initial State:
        - Object may include non-serializable leaves or cycles

    Final State:
        - JSON-safe structure with truncated depth

    Raises:
        None

    Water Cost:
        - 0 (internal)
    """
    if max_depth <= 0:
        return str(obj)
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [safe_json(x, max_depth - 1) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            sk = k if isinstance(k, str) else str(k)
            out[sk] = safe_json(v, max_depth - 1)
        return out
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)

def _load_agents() -> dict:
    """
    Loads the registry of agents from disk if present.

    Parameters:
        None

    Returns:
        dict: Parsed content of agents.json, or {} if not found

    Initial State:
        - agents.json may or may not exist

    Final State:
        - Registry is returned and also assigned to in-memory state by caller

    Raises:
        RuntimeError: If agents.json is malformed/unreadable

    Water Cost:
        - 0 (internal)
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

    Parameters:
        registry (dict): The agent registry to persist

    Returns:
        None

    Initial State:
        - registry is an in-memory dict

    Final State:
        - agents.json is written/overwritten

    Raises:
        RuntimeError: If writing fails

    Water Cost:
        - 0 (internal)
    """
    try:
        with AGENTS_FILE.open("w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
    except Exception as save_error:
        raise RuntimeError(f"Failed to persist registry: {save_error}")

def _load_agent_manifest(agent_name: str) -> dict:
    """
    Loads an agent's manifest.json from agents/<agent_name>/.

    Parameters:
        agent_name (str): Agent folder name

    Returns:
        dict: Parsed manifest content

    Initial State:
        - agents/<agent_name>/manifest.json exists

    Final State:
        - Manifest dict is returned

    Raises:
        FileNotFoundError: If manifest is missing

    Water Cost:
        - 0 (internal)
    """
    manifest_path = AGENT_DIR / agent_name / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found for agent: {agent_name}")
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _are_specs_compatible(output_spec: dict, input_spec: dict) -> bool:
    """
    Checks if the output type of one agent matches the input type of another.

    Parameters:
        output_spec (dict): Producer spec
        input_spec (dict): Consumer spec

    Returns:
        bool: True if both have same top-level 'type'

    Initial State:
        - Specs are dicts with a top-level 'type' (optional in manifests)

    Final State:
        - Boolean compatibility verdict

    Raises:
        None

    Water Cost:
        - 0 (internal)
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
    Returns orchestrator status and the list of registered agents.

    Parameters:
        None

    Returns:
        dict: {status, registered_agents}

    Water Cost:
        - 0
    """
    return {
        "status": "ClearCoreAI Orchestrator is running.",
        "registered_agents": list(agents_registry.keys())
    }

@app.post("/register_agent")
def register_agent(agent: AgentRegistration):
    """
    Registers a new agent by validating its manifest and storing it persistently.

    Parameters:
        agent (AgentRegistration): {name, base_url}

    Returns:
        dict: Confirmation message

    Initial State:
        - Agent exposes GET /manifest with a valid JSON manifest
        - manifest_template.json is loaded

    Final State:
        - Registry stores agent base_url + manifest + normalized capabilities

    Raises:
        HTTPException: If agent is unreachable, manifest invalid, or persistence fails

    Water Cost:
        - 0.2 waterdrops
    """
    try:
        resp = requests.get(f"{agent.base_url}/manifest", timeout=5)
        resp.raise_for_status()
        manifest = resp.json()
    except requests.exceptions.RequestException as req_error:
        raise HTTPException(status_code=400, detail=f"Cannot reach agent at {agent.base_url}: {req_error}")
    except Exception as json_error:
        raise HTTPException(status_code=400, detail=f"Invalid JSON from /manifest: {json_error}")

    # Normalize capabilities: accept ["cap"], [{"name": "cap"}], or { "cap": "desc" }
    raw_caps = manifest.get("capabilities", [])
    normalized_caps = []
    if isinstance(raw_caps, list):
        for cap in raw_caps:
            if isinstance(cap, str):
                normalized_caps.append({"name": cap, "description": ""})
            elif isinstance(cap, dict):
                name = cap.get("name") or cap.get("capability") or cap.get("id")
                desc = cap.get("description", "")
                custom = cap.get("custom_input_handler")
                if name:
                    item = {"name": name, "description": desc}
                    if custom:
                        item["custom_input_handler"] = custom
                    normalized_caps.append(item)
    elif isinstance(raw_caps, dict):
        for k, v in raw_caps.items():
            normalized_caps.append({"name": k, "description": str(v) if v is not None else ""})

    manifest["capabilities"] = normalized_caps

    try:
        validate(instance=manifest, schema=manifest_template)
    except ValidationError as validation_error:
        raise HTTPException(status_code=400, detail=f"Manifest invalid: {validation_error.message}")

    # Build structured capabilities for quick lookup
    capabilities_dict = {}
    for cap in manifest.get("capabilities", []):
        name = cap.get("name")
        if name:
            capabilities_dict[name] = {
                "description": cap.get("description", ""),
                "custom_input_handler": cap.get("custom_input_handler")
            }

    agents_registry[agent.name] = {
        "base_url": agent.base_url,
        "manifest": manifest,
        "capabilities": capabilities_dict
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
    Lists all registered agents with their capabilities.

    Returns:
        dict: { "agents": { name: {base_url, capabilities} } }

    Water Cost:
        - 0.05 waterdrops
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
    Returns the full manifest for a given agent.

    Parameters:
        agent_name (str): Registered agent name

    Returns:
        dict: The manifest JSON

    Raises:
        HTTPException: 404 if agent not found

    Water Cost:
        - 0
    """
    if agent_name not in agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return agents_registry[agent_name]["manifest"]

@app.get("/agents/connections")
def detect_agent_connections():
    """
    Detects compatible input/output connections between registered agents.

    Parameters:
        None

    Returns:
        dict: {"connections": [{"from": str, "to": str, "reason": str}, ...]}

    Initial State:
        - Manifests may provide input_spec/output_spec

    Final State:
        - Returns possible connections based on top-level type match

    Raises:
        HTTPException: 500 if analysis crashes

    Water Cost:
        - 0
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
    Queries all agents for their /metrics snapshot.

    Returns:
        dict: { agent_name: { ...metrics... } | {error}, ... }

    Water Cost:
        - 0 (monitoring)
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
    Returns raw manifest content for all registered agents.

    Returns:
        dict: { name: manifest.json, ... }

    Water Cost:
        - 0
    """
    return {
        name: data["manifest"]
        for name, data in agents_registry.items()
    }

# ----------- Planning & Execution ----------- #
def _extract_step_lines(plan_text: str) -> list:
    """
    Extracts only well-formed step lines like "1. agent → capability".
    Accepts both "→" and "->"; always normalizes to "→".

    Parameters:
        plan_text (str): Raw plan text

    Returns:
        list[str]: Normalized step lines

    Water Cost:
        - 0 (internal)
    """
    lines = []
    for raw in (plan_text or "").splitlines():
        s = raw.strip()
        m = re.match(r"^\s*\d+\.\s*([A-Za-z0-9_]+)\s*(?:→|->)\s*([A-Za-z0-9_\-:]+)\s*$", s)
        if m:
            agent, cap = m.groups()
            lines.append(f"{len(lines)+1}. {agent} → {cap}")
    return lines

def _filter_registered_steps(step_lines: list, registry: dict) -> list:
    """
    Keeps only steps where agent exists and capability is advertised in that agent’s manifest.

    Parameters:
        step_lines (list[str]): Lines like "N. agent → cap"
        registry (dict): Current agents registry

    Returns:
        list[str]: Filtered/renumbered step lines

    Water Cost:
        - 0 (internal)
    """
    filtered = []
    for s in step_lines:
        s_norm = s.strip().replace("->", "→")
        m = re.match(r"^\d+\.\s*([A-Za-z0-9_]+)\s*→\s*([A-Za-z0-9_\-:]+)$", s_norm)
        if not m:
            continue
        agent, cap = m.groups()
        agent_entry = registry.get(agent)
        if not agent_entry:
            continue
        caps = agent_entry.get("manifest", {}).get("capabilities", [])
        cap_names = {(c["name"] if isinstance(c, dict) and "name" in c else c) for c in caps if isinstance(c, (dict, str))}
        if cap in cap_names:
            filtered.append(f"{len(filtered)+1}. {agent} → {cap}")
    return filtered

def _sanitize_plan_output(raw_plan: str, registry: dict) -> str:
    """
    Normalizes and sanitizes an LLM plan: remove prose, keep valid steps, ensure ≥1 step.

    Parameters:
        raw_plan (str): Raw LLM output
        registry (dict): Agents registry

    Returns:
        str: Clean plan string

    Raises:
        RuntimeError: If no executable steps remain

    Water Cost:
        - 0 (internal)
    """
    steps = _extract_step_lines(raw_plan)
    steps = _filter_registered_steps(steps, registry)
    if not steps:
        raise RuntimeError("No executable steps found for the current registry.")
    return "\n".join(steps)

def generate_plan_from_goal(goal: str) -> str:
    """
    Generates a numbered execution plan from a natural-language goal.

    Parameters:
        goal (str): Objective to transform into a step plan

    Returns:
        str: Multiline plan "1. agent → capability\n2. ..."

    Initial State:
        - license_keys.json contains a valid Mistral key
        - Registry has ≥1 agent with capabilities

    Final State:
        - A sanitized plan string is returned; LLM water is accounted

    Raises:
        HTTPException(422): If LLM declares the goal unsupported
        RuntimeError: If plan generation or sanitization fails

    Water Cost:
        - ~3 waterdrops (delegates to LLM + scan)
    """
    try:
        plan, water_cost = generate_plan_with_mistral(goal, agents_registry, license_keys)
        increment_aiwaterdrops(water_cost)

        # Optional: allow explicit unsupported marker from LLM ("UNSUPPORTED | reason")
        upper = plan.strip().upper()
        if upper.startswith("UNSUPPORTED"):
            reason = plan.split("|", 1)[1].strip() if "|" in plan else "Goal unsupported by current agents."
            raise HTTPException(status_code=422, detail=f"Unsupported goal: {reason}")

        # Coerce to string and sanitize
        if isinstance(plan, list):
            plan = "\n".join(map(str, plan))
        elif not isinstance(plan, str):
            raise RuntimeError(f"Invalid plan format: expected str or list, got {type(plan)}")

        clean_plan = _sanitize_plan_output(plan, agents_registry)
        return clean_plan
    except HTTPException:
        raise
    except Exception as plan_error:
        raise RuntimeError(f"Plan generation failed: {plan_error}")

@app.post("/plan")
def plan_goal(payload: dict):
    """
    Generates a plan from a goal and (for convenience) immediately executes it.

    Parameters:
        payload (dict): {"goal": str}

    Returns:
        dict: {"goal": str, "plan": str, "result": <execution result>}

    Raises:
        HTTPException: 400 if goal missing, 422 if unsupported, 500 on failure

    Water Cost:
        - ~3 waterdrops (planning) + execution costs
    """
    goal = payload.get("goal")
    if not goal:
        raise HTTPException(status_code=400, detail="Missing 'goal' field.")
    try:
        plan = generate_plan_from_goal(goal)
        result = execute_plan_string(plan)
        return {"goal": goal, "plan": plan, "result": result}
    except HTTPException as http_err:
        raise http_err
    except Exception as run_error:
        raise HTTPException(status_code=500, detail=str(run_error))

def execute_plan_string(plan: str) -> dict:
    """
    Executes the plan step-by-step and returns a full execution trace.

    Parameters:
        plan (str): "N. agent → capability" per line

    Returns:
        dict: {
            "trace": [ {step, agent, capability, input_used, output, error}... ],
            "final_output": <last business output or last output>,
            "total_waterdrops_used": <float from final_output.waterdrops_used or 0.0>
        }

    Initial State:
        - All agents in the plan are registered and reachable via /execute

    Final State:
        - Each step is invoked; context is passed along; trace is accumulated

    Raises:
        None (errors captured per-step in the trace)

    Water Cost:
        - 0.02 (fixed) + per-agent execution costs downstream
    """
    def _capabilities_for(agent_name: str) -> set:
        caps = agents_registry.get(agent_name, {}).get("manifest", {}).get("capabilities", [])
        names = set()
        for c in caps:
            if isinstance(c, dict) and "name" in c:
                names.add(c["name"])
            elif isinstance(c, str):
                names.add(c)
        return names

    def _clean_input(ctx):
        if isinstance(ctx, dict):
            return {k: v for k, v in ctx.items() if k not in ("waterdrops_used",)}
        return ctx

    results = []
    context = None
    business_context = None

    for raw in plan.splitlines():
        step_line = raw.strip()
        if not step_line or step_line.startswith("#"):
            continue

        step_line = step_line.replace("->", "→")
        m = re.match(r"^\d+\.\s*([A-Za-z0-9_]+)\s*→\s*([A-Za-z0-9_]+)$", step_line)
        if not m:
            results.append({"step": step_line, "error": "Unrecognized format"})
            continue

        agent_name, capability = m.groups()
        agent = agents_registry.get(agent_name)
        if not agent:
            results.append({"step": step_line, "error": f"Agent '{agent_name}' not registered"})
            continue

        available = _capabilities_for(agent_name)
        if capability not in available:
            results.append({
                "step": step_line,
                "agent": agent_name,
                "capability": capability,
                "skipped": True,
                "reason": "Capability not advertised by agent manifest"
            })
            continue

        try:
            payload_input = _clean_input(context)

            # Detect meta-capability via custom_input_handler
            manifest_caps = agents_registry[agent_name]["manifest"].get("capabilities", [])
            cap_obj = next((c for c in manifest_caps if isinstance(c, dict) and c.get("name") == capability), None)
            custom_handler = cap_obj.get("custom_input_handler") if isinstance(cap_obj, dict) else None

            if custom_handler == "use_execution_trace":
                payload_input = {
                    "steps": [
                        {
                            "agent": r.get("agent"),
                            "input": r.get("input_used"),
                            "output": r.get("output"),
                            "error": r.get("error"),
                        }
                        for r in results
                        if "agent" in r
                    ]
                }

            if not isinstance(payload_input, dict) and payload_input is not None:
                payload_input = {"_value": payload_input}
            if payload_input is None:
                payload_input = {}

            # Attach base_url hint for downstream audit agents
            payload_input["_agent_base_url"] = agent["base_url"]

            url = f"{agent['base_url']}/execute"
            payload = {"capability": capability, "input": payload_input}
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            out = resp.json()

            if isinstance(out, dict):
                out.setdefault("_agent_base_url", agent["base_url"])

            results.append({
                "step": step_line,
                "agent": agent_name,
                "capability": capability,
                "input_used": payload_input if payload_input is not None else {},
                "output": out,
                "error": None
            })

            context = out
            if custom_handler != "use_execution_trace":
                business_context = out

        except Exception as e:
            results.append({
                "step": step_line,
                "agent": agent_name,
                "capability": capability,
                "input_used": payload_input if 'payload_input' in locals() else None,
                "output": None,
                "error": str(e)
            })
            break

    increment_aiwaterdrops(0.02)

    final_context = business_context if business_context is not None else context

    return {
        "trace": results,
        "final_output": final_context,
        "total_waterdrops_used": final_context.get("waterdrops_used", 0.0) if isinstance(final_context, dict) else 0.0
    }

@app.post("/execute_plan")
def execute_plan(request: dict):
    """
    Executes a given plan string and returns the execution result.

    Parameters:
        request (dict): {"plan": str}

    Returns:
        dict: Execution result from execute_plan_string

    Raises:
        HTTPException: 400 if 'plan' missing

    Water Cost:
        - Pass-through (see execute_plan_string)
    """
    plan = request.get("plan")
    if not plan:
        raise HTTPException(status_code=400, detail="Missing 'plan' field.")
    return execute_plan_string(plan)

@app.post("/run_goal")
def run_goal(payload: dict):
    """
    End-to-end handler: plan + execute from a goal.

    Parameters:
        payload (dict): {"goal": str}

    Returns:
        dict: {"goal": str, "plan": str, "result": <trace>}

    Raises:
        HTTPException: 400 missing goal, 500 other failures

    Water Cost:
        - ~3 (planning) + execution variable
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
    Returns the total waterdrop consumption including orchestrator + all agents.

    Parameters:
        None

    Returns:
        dict: {"breakdown": {component: usage|error}, "total_waterdrops": float}

    Initial State:
        - Agents expose /metrics with aiwaterdrops_consumed

    Final State:
        - Totals aggregated and rounded

    Raises:
        None (per-agent errors are embedded)

    Water Cost:
        - 0
    """
    total = get_aiwaterdrops()
    breakdown = {"orchestrator": total}

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

    return {"breakdown": breakdown, "total_waterdrops": round(total, 3)}