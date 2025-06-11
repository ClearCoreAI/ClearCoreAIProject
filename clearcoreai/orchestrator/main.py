"""
Module: main.py
Function: main orchestrator API

Description:
Main orchestrator API for ClearCoreAI. Allows agents to register and provides orchestrator health status.

Version: 0.1.0
Initial State: Orchestrator running, empty agent registry.
Final State: Orchestrator running, agents can be registered during runtime.

Exceptions handled:
- HTTPException 500 — if agent already registered.

Validation:
- Validated by: Olivier Hays
- Date: 2025-06-11

Estimated Water Cost:
- 1 waterdrop per /health call
- 2 waterdrops per /register_agent call

"""

from fastapi import FastAPI, HTTPException
from agent_manager import AgentManager

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
    - Date: 2025-06-11

    Estimated Water Cost:
    - 1 waterdrop per call
    """
    return {"status": "ClearCoreAI orchestrator is up and running."}

@app.post("/register_agent")
def register_agent(agent_name: str):
    """
    Module: main.py
    Function: register_agent

    Description:
    Registers a new agent with the orchestrator.

    Version: 0.1.0
    Initial State: Agent not registered.
    Final State: Agent added to registry.

    Exceptions handled:
    - HTTPException 500 — if agent already registered.

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-11

    Estimated Water Cost:
    - 2 waterdrops per call
    """
    try:
        agent_manager.register(agent_name)
        return {"message": f"Agent '{agent_name}' registered successfully."}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))