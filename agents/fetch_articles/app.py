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
import time
import json
import os
from fastapi import FastAPI
import requests

# Initialize variables
ORCHESTRATOR_URL = "http://orchestrator:8000/register_agent"
AGENT_NAME = "fetch_articles"
START_TIME = time.time()

# Load AIWaterdrops from memory
AIWATERDROPS_FILE = "memory/short_term/aiwaterdrops.json"

def load_aiwaterdrops():
    try:
        with open(AIWATERDROPS_FILE, "r") as f:
            data = json.load(f)
            return data.get("aiwaterdrops_consumed", 0.0)
    except FileNotFoundError:
        return 0.0

def save_aiwaterdrops(value):
    with open(AIWATERDROPS_FILE, "w") as f:
        json.dump({"aiwaterdrops_consumed": value}, f)

# Load initial value
aiwaterdrops_consumed = load_aiwaterdrops()

# Load mood
with open("mood.json", "r") as f:
    mood = json.load(f)


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

@app.get("/capabilities")
def get_capabilities():
    """
    Returns the agent's capabilities as declared in its manifest.json.
    Used by the orchestrator to validate and register the agent.

    Version:
        - First implemented: 0.1.1
        - Validated by: Olivier Hays
    """
    try:
        with open("manifest.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "manifest.json not found"}


@app.get("/metrics")
def get_metrics():
    """
    Purpose:
        Returns agent metrics including AIWaterdrops consumption, current mood, uptime, and version.

    Initial State:
        Agent is running.

    Final State:
        No state change.

    Inputs:
        None

    Outputs:
        JSON with agent_name, version, uptime, current_mood, aiwaterdrops_consumed.

    Exceptions:
        None

    AIWaterdrops estimation:
        - Estimated Waterdrops per call: 0.01

    Version:
        - First implemented in version: 0.1.0
        - Last validated in version: 0.1.0
        - Validated by: Olivier Hays
    """
    uptime_seconds = int(time.time() - START_TIME)

    return {
        "agent_name": "fetch_articles",
        "version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "current_mood": mood["current_mood"],
        "aiwaterdrops_consumed": aiwaterdrops_consumed
    }


@app.get("/get_articles")
def get_articles():
    """
    Purpose:
        Returns example articles in JSON format.

    Initial State:
        Agent ready to serve articles.

    Final State:
        AIWaterdrops counter incremented and persisted.

    Inputs:
        None

    Outputs:
        JSON list of articles with title, source, and content.

    Exceptions:
        None

    AIWaterdrops estimation:
        - Estimated Waterdrops per call: 0.05

    Version:
        - First implemented in version: 0.1.0
        - Last validated in version: 0.1.0
        - Validated by: ClearCoreAI Contributors
    """
    global aiwaterdrops_consumed
    aiwaterdrops_consumed += 0.05  # Simulate waterdrop consumption
    save_aiwaterdrops(aiwaterdrops_consumed)

    articles = [
        {
            "title": "AI Revolutionizes Healthcare",
            "source": "Example News",
            "content": "AI technologies are transforming healthcare by enabling faster diagnoses and personalized treatments."
        },
        {
            "title": "Climate Change Update",
            "source": "Example Times",
            "content": "Recent studies show significant progress in renewable energy adoption worldwide."
        },
        {
            "title": "SpaceX Launches New Mission",
            "source": "Space News Daily",
            "content": "SpaceX successfully launched a new mission to deploy communication satellites."
        }
    ]

    return {"articles": articles}

@app.get("/mood")
def get_mood():
    """
    Purpose:
        Returns the current mood and mood history of the agent.

    Initial State:
        Agent running.

    Final State:
        No state change.

    Inputs:
        None

    Outputs:
        JSON with current_mood, last_updated, history.

    Exceptions:
        None

    AIWaterdrops estimation:
        - Estimated Waterdrops per call: 0.01

    Version:
        - First implemented in version: 0.1.0
        - Last validated in version: 0.1.0
        - Validated by: Olivier Hays
    """
    return {
        "current_mood": mood.get("current_mood", "unknown"),
        "last_updated": mood.get("last_updated", "unknown"),
        "history": mood.get("history", [])
    }


