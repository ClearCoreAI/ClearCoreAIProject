"""
Module: main.py
Function: main orchestrator API

Description:
Main orchestrator API for ClearCoreAI.
Allows agents to register and provides orchestrator health status.
Agents are registered using AgentRegistrationRequest and stored as AgentInfo instances.

Version: 0.1.0
Initial State: Orchestrator running, empty agent registry.
Final State: Orchestrator running, agents can be registered during runtime.

Exceptions handled:
- HTTPException 500 — if agent already registered.

Validation:
- Validated by: Olivier Hays
- Date: 2025-06-13

Estimated Water Cost:
- 1 waterdrop per /health call
- 2 waterdrops per /register_agent call
"""

from fastapi import FastAPI, HTTPException
from agent_manager import AgentManager
from models.agent_model import AgentRegistrationRequest
import requests
import time, json

START_TIME = time.time()

# Load orchestrator mood
with open("mood.json", "r") as f:
    orchestrator_mood = json.load(f)
app = FastAPI(title="ClearCoreAI Orchestrator", version="0.1.0")

agent_manager = AgentManager()

@app.get("/health")
def health_check():
    """
    Module: main.py
    Function: health_check

    Description:
    Returns the current status of the orchestrator.

    Version: 0.1.0
    Initial State: Orchestrator running.
    Final State: No change, status returned.

    Exceptions handled:
    - None

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-13

    Estimated Water Cost:
    - 1 waterdrop per call
    """
    return {"status": "ClearCoreAI orchestrator is up and running."}

@app.post("/register_agent")
def register_agent(request: AgentRegistrationRequest):
    """
    Module: main.py
    Function: register_agent

    Description:
    Registers a new agent with the orchestrator using an AgentRegistrationRequest.

    Version: 0.1.0
    Initial State: Agent not registered.
    Final State: Agent added to registry.

    Exceptions handled:
    - HTTPException 500 — if agent already registered.

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-13

    Estimated Water Cost:
    - 2 waterdrops per call
    """
    try:
        agent_manager.register(
            agent_name=request.agent_name,
            version=request.version,
            url=request.url
        )
        return {"message": f"Agent '{request.agent_name}' registered successfully."}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
def list_agents():
    """
    Module: main.py
    Function: list_agents

    Description:
    Returns the list of registered agents with their information.

    Version: 0.1.0
    Initial State: Agents may be registered.

    Final State: No change.

    Exceptions handled:
    - None

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-13

    Estimated Water Cost:
    - 1 waterdrop per call.
    """
    agents_dict = agent_manager.get_all_agents()
    # Convert AgentInfo objects to dicts for JSON serialization
    agents_list = [agent.dict() for agent in agents_dict.values()]
    return {"registered_agents": agents_list}

@app.get("/agents/metrics")
def get_agents_metrics():
    """
    Module: main.py
    Function: get_agents_metrics

    Description:
    Returns aggregated metrics of all registered agents.
    Calls each agent's /metrics endpoint and collects the results.

    Version: 0.1.0
    Initial State: Agents may be registered.

    Final State: No change.

    Exceptions handled:
    - HTTPException 500 — if an agent's /metrics endpoint is unreachable.

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-13

    Estimated Water Cost:
    - 3 waterdrops per call (1 per agent queried).
    """
    agents_dict = agent_manager.get_all_agents()
    aggregated_metrics = []

    for agent_name, agent_info in agents_dict.items():
        try:
            metrics_url = f"{agent_info.url}/metrics"
            response = requests.get(metrics_url, timeout=3)
            response.raise_for_status()
            metrics = response.json()
            aggregated_metrics.append({
                "agent_name": agent_name,
                "metrics": metrics
            })
        except requests.RequestException as e:
            # Handle agent not reachable or /metrics error
            aggregated_metrics.append({
                "agent_name": agent_name,
                "error": f"Could not retrieve metrics: {str(e)}"
            })

    return {"aggregated_agents_metrics": aggregated_metrics}

@app.get("/metrics")
def orchestrator_metrics():
    """
    Module: main.py
    Function: orchestrator_metrics

    Description:
    Returns metrics of the orchestrator itself:
    - uptime
    - number of agents
    - total AIWaterdrops consumed (sum of all agents).

    Version: 0.1.0
    Initial State: Orchestrator running.

    Final State: No change.

    Exceptions handled:
    - None

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-13

    Estimated Water Cost:
    - 1 waterdrop per call.
    """
    uptime_seconds = int(time.time() - START_TIME)
    agents_dict = agent_manager.get_all_agents()
    total_agents = len(agents_dict)
    total_aiwaterdrops = sum(agent.aiwaterdrops_consumed for agent in agents_dict.values())

    return {
        "orchestrator_version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "registered_agents": total_agents,
        "total_aiwaterdrops_consumed": total_aiwaterdrops
    }

@app.get("/mood")
def get_orchestrator_mood():
    """
    Module: main.py
    Function: get_orchestrator_mood

    Description:
    Returns the current mood and mood history of the orchestrator.

    Version: 0.1.0
    Initial State: Orchestrator running.

    Final State: No change.

    Exceptions handled:
    - None

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-13

    Estimated Water Cost:
    - 1 waterdrop per call.
    """
    return {
        "current_mood": orchestrator_mood.get("current_mood", "unknown"),
        "last_updated": orchestrator_mood.get("last_updated", "unknown"),
        "history": orchestrator_mood.get("history", [])
    }