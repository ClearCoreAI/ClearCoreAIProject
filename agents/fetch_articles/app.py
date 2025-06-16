"""
Module: fetch_articles
Component: Agent API
Purpose: Serve static news articles and expose orchestration-compatible capabilities

Description:
This ClearCoreAI agent registers itself to the orchestrator and exposes multiple endpoints:
- fetch static articles
- transform articles into a collection format
- monitor mood and track water usage
It supports orchestrator-driven execution via a generic `/execute` endpoint.

Philosophy:
- All capabilities must be declared via a manifest
- State (mood and water usage) is persisted and observable
- Agents must self-register on startup and support orchestration without tight coupling

Initial State:
- mood.json is present and loaded
- aiwaterdrops.json file may exist or is initialized to 0
- manifest.json describes declared capabilities

Final State:
- Agent is registered to orchestrator
- Static articles are retrievable
- Water usage and mood are updated on each call

Version: 0.2.0
Validated by: Olivier Hays
Date: 2025-06-16

Estimated Water Cost:
- 1 waterdrop per /health call
- 3 waterdrops per /get_articles call
- 0.02 waterdrops per /execute call
"""

# ----------- Imports ----------- #
import time
import json
import os
from fastapi import FastAPI, HTTPException, Request
import requests

# ----------- Constants ----------- #
ORCHESTRATOR_URL = "http://orchestrator:8000/register_agent"
AGENT_NAME = "fetch_articles"
START_TIME = time.time()
AIWATERDROPS_FILE = "memory/short_term/aiwaterdrops.json"

# ----------- Internal State / Registry ----------- #
with open("mood.json", "r") as f:
    mood = json.load(f)

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

aiwaterdrops_consumed = load_aiwaterdrops()

# ----------- App Initialization ----------- #
app = FastAPI(title="Fetch Articles Agent", version="0.2.0")

# ----------- Helper Functions ----------- #
def fetch_static_articles():
    """
    Returns a fixed set of example news articles.

    Initial State:
        - No external input required

    Final State:
        - A list of article dicts with title, source, and content

    Water Cost:
        - ~3 waterdrops (charged in /get_articles)
    """
    return {
        "articles": [
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
    }

def generate_article_collection(data):
    """
    Converts a raw list of articles into a collection format with count.

    Parameters:
        data (dict): contains key "articles": list of dicts

    Returns:
        dict: {"collection": {"count": int, "items": [...] }}

    Initial State:
        - data includes a valid "articles" list

    Final State:
        - A normalized structure is returned

    Water Cost:
        - Charged in /execute (0.02)
    """
    articles = data.get("articles", [])
    return {
        "collection": {
            "count": len(articles),
            "items": articles
        }
    }

# ----------- Startup Logic ----------- #
def register_with_orchestrator():
    """
    Registers this agent to the central orchestrator via HTTP POST.

    Initial State:
        - Orchestrator is running and reachable at ORCHESTRATOR_URL

    Final State:
        - Agent appears in orchestrator’s registry with declared capabilities

    Raises:
        ConnectionError: If orchestrator is not available
    """
    time.sleep(2)  # Ensure orchestrator is ready
    try:
        response = requests.post(ORCHESTRATOR_URL, params={"agent_name": AGENT_NAME})
        print(response.json())
    except Exception as e:
        print(f"Error registering agent: {e}")

@app.on_event("startup")
def startup_event():
    register_with_orchestrator()

# ----------- API Endpoints ----------- #
@app.get("/health")
def health_check():
    """
    Health check endpoint.

    Returns:
        dict: status string

    Water Cost:
        - 1 waterdrop
    """
    return {"status": "Fetch Articles Agent is up and running."}

@app.get("/capabilities")
def get_capabilities():
    """
    Returns the agent’s declared capabilities.

    Raises:
        FileNotFoundError: if manifest.json is missing
    """
    try:
        with open("manifest.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "manifest.json not found"}

@app.get("/metrics")
def get_metrics():
    """
    Returns live metrics for monitoring.

    Includes:
        - agent version
        - uptime
        - mood
        - water consumption
    """
    uptime_seconds = int(time.time() - START_TIME)
    return {
        "agent_name": AGENT_NAME,
        "version": "0.2.0",
        "uptime_seconds": uptime_seconds,
        "current_mood": mood["current_mood"],
        "aiwaterdrops_consumed": aiwaterdrops_consumed
    }

@app.get("/get_articles")
def get_articles():
    """
    Serves static articles and tracks water usage.

    Final State:
        - aiwaterdrops_consumed is incremented and saved

    Water Cost:
        - 3 waterdrops
    """
    global aiwaterdrops_consumed
    aiwaterdrops_consumed += 3
    save_aiwaterdrops(aiwaterdrops_consumed)
    return fetch_static_articles()

@app.get("/mood")
def get_mood():
    """
    Exposes internal agent mood for monitoring/debugging.
    """
    return {
        "current_mood": mood.get("current_mood", "unknown"),
        "last_updated": mood.get("last_updated", "unknown"),
        "history": mood.get("history", [])
    }

@app.post("/execute")
async def execute(request: Request):
    """
    Dispatcher endpoint for orchestrator execution.

    Parameters:
        request (Request): JSON with "capability" and optional "input" field

    Returns:
        dict: Result of capability execution

    Initial State:
        - capability is one of the known agent functions

    Final State:
        - Called function is executed
        - Water usage is incremented and saved

    Raises:
        HTTPException 400: if unknown capability
        HTTPException 500: if execution fails

    Water Cost:
        - 0.02 waterdrops base + underlying cost if applicable
    """
    global aiwaterdrops_consumed

    try:
        payload = await request.json()
        capability = payload.get("capability")
        input_data = payload.get("input", {})

        if capability == "fetch_static_articles":
            aiwaterdrops_consumed += 0.02
            save_aiwaterdrops(aiwaterdrops_consumed)
            return fetch_static_articles()

        elif capability == "generate_article_collection":
            aiwaterdrops_consumed += 0.02
            save_aiwaterdrops(aiwaterdrops_consumed)
            return generate_article_collection(input_data)

        else:
            raise HTTPException(status_code=400, detail=f"Unknown capability: {capability}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")