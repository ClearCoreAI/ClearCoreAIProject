"""
Module: fetch_articles agent
Process: FastAPI agent API

Description:
Example agent for ClearCoreAI: fetch_articles. Registers itself to the orchestrator and provides a simple API.

Version: 0.1.0
Initial State: Agent starts and registers with orchestrator.
Final State: Agent serves API endpoints.

Exceptions handled:
- ConnectionError — if registration to orchestrator fails.

Validation:
- Validated by: Olivier Hays
- Date: 2025-06-11

Estimated Water Cost:
- 1 waterdrop per /health call
- 3 waterdrops per /get_articles call (includes mock processing)
- ~2 waterdrops per agent registration attempt

"""

from fastapi import FastAPI
import requests
import time

ORCHESTRATOR_URL = "http://orchestrator:8000/register_agent"
AGENT_NAME = "fetch_articles"

app = FastAPI(title="Fetch Articles Agent", version="0.1.0")

def register_with_orchestrator():
    """
    Register the agent with the orchestrator.
    """
    time.sleep(2)  # wait for orchestrator to be ready
    try:
        response = requests.post(ORCHESTRATOR_URL, params={"agent_name": AGENT_NAME})
        print(response.json())
    except Exception as e:
        print(f"Error registering agent: {e}")

@app.on_event("startup")
def startup_event():
    register_with_orchestrator()

@app.get("/health")
def health_check():
    """
    Module: fetch_articles agent
    Function: health_check

    Description:
    Returns the current status of the agent.

    Version: 0.1.0
    Initial State: Agent running.
    Final State: No change.

    Exceptions handled:
    - None

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-11

    Estimated Water Cost:
    - 1 waterdrop per call
    """
    return {"status": "Fetch Articles Agent is up and running."}

@app.get("/get_articles")
def get_articles():
    """
    Module: fetch_articles agent
    Function: get_articles

    Description:
    Returns a mock list of articles.

    Version: 0.1.0
    Initial State: Agent running.
    Final State: No change.

    Exceptions handled:
    - None

    Validation:
    - Validated by: Olivier Hays
    - Date: 2025-06-11

    Estimated Water Cost:
    - 3 waterdrops per call
    """
    # Mock response
    return {"articles": ["Article 1", "Article 2", "Article 3"]}