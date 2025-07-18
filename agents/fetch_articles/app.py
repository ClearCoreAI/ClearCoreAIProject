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

Version: 0.2.3
Validated by: Olivier Hays
Date: 2025-06-20

Estimated Water Cost:
- 1 waterdrop per /health call
- 1 waterdrops per /get_articles call
- 0.02 waterdrops per /execute call
"""

# ----------- Imports ----------- #
import os
import time
import json
import requests
from fastapi import FastAPI, HTTPException, Request
from pathlib import Path
from tools.water import increment_aiwaterdrops, load_aiwaterdrops, get_aiwaterdrops

# ----------- Constants ----------- #
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000/register_agent")
AGENT_NAME = "fetch_articles"
START_TIME = time.time()
AIWATERDROPS_FILE = Path("memory/short_term/aiwaterdrops.json")
ARTICLES_DIR = Path("memory/long_term/")
VERSION = "0.2.3"

# ----------- App Initialization ----------- #
app = FastAPI(title="Fetch Articles Agent", version=VERSION)

# ----------- State Management ----------- #
# Mood
try:
    with open("mood.json", "r") as mood_json:
        mood = json.load(mood_json)
except FileNotFoundError:
    mood = {"current_mood": "happy", "last_summary": None}
# Current water consumption
aiwaterdrops_consumed = load_aiwaterdrops()

# ----------- Capabilities ----------- #
def fetch_static_articles() -> dict:
    """
    Loads static article files and returns structured list.

    Returns:
        dict: {"articles": list of article dicts}

    Initial State:
        - One or more .txt files in memory/long_term

    Final State:
        - Structured articles are returned

    Water Cost:
        - 1 (in /get_articles) or 0.02 (in /execute)
    """
    articles = []
    for file_path in sorted(ARTICLES_DIR.glob("*.txt")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")
                if not lines:
                    continue
                title = lines[0].strip() if len(lines) > 1 else file_path.stem.replace("_", " ").capitalize()
                content = "\n".join(lines[1:]).strip() if len(lines) > 1 else lines[0].strip()
                articles.append({
                    "title": title,
                    "source": "Local file",
                    "content": content
                })
        except Exception as e:
            print(f"⚠️ Failed to load article from {file_path}: {e}")
            continue
    increment_aiwaterdrops(0.05 + len(articles) * 0.1)
    return {"articles": articles}

def generate_article_collection(data: dict) -> dict:
    """
    Converts article list into structured collection.

    Parameters:
        data (dict): Contains key "articles"

    Returns:
        dict: {"collection": {"count": int, "items": [...] }}

    Initial State:
        - Valid articles list exists in input

    Final State:
        - Normalized collection returned

    Water Cost:
        - 0.02 per call
    """
    articles = data.get("articles", [])
    increment_aiwaterdrops(0.2)
    return {
        "collection": {
            "count": len(articles),
            "items": articles
        }
    }

# ----------- API Endpoints ----------- #
@app.get("/health")
def health_check() -> dict:
    """
    Returns basic status message confirming the agent is operational.

    Returns:
        dict: Status confirmation message

    Initial State:
        - Agent is initialized

    Final State:
        - Health status returned

    Water Cost:
        - 0
    """
    return {"status": "Fetch Articles Agent is up and running."}

@app.get("/capabilities")
def get_capabilities() -> dict:
    """
    Returns the list of declared capabilities from the manifest.

    Returns:
        dict: {"capabilities": [...]}

    Initial State:
        - manifest.json must be present

    Final State:
        - List of capabilities returned

    Raises:
        HTTPException: If manifest is missing

    Water Cost:
        - 0
    """
    try:
        with open("manifest.json", "r") as f:
            manifest = json.load(f)
        return {"capabilities": manifest.get("capabilities", [])}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")

@app.get("/manifest")
def get_manifest() -> dict:
    """
    Returns the full manifest file content.

    Returns:
        dict: Full manifest

    Initial State:
        - manifest.json must exist

    Final State:
        - Manifest returned or 404

    Raises:
        HTTPException: If file not found

    Water Cost:
        - 0
    """
    try:
        with open("manifest.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")

@app.get("/metrics")
def get_metrics() -> dict:
    """
    Returns agent uptime, version, mood and water usage metrics.

    Returns:
        dict: Agent metrics including uptime and waterdrops

    Initial State:
        - mood and uptime tracked

    Final State:
        - Metrics snapshot returned

    Water Cost:
        - 0
    """
    uptime_seconds = int(time.time() - START_TIME)
    return {
        "agent_name": AGENT_NAME,
        "version": "0.2.2",
        "uptime_seconds": uptime_seconds,
        "current_mood": mood.get("current_mood", "unknown"),
        "aiwaterdrops_consumed": get_aiwaterdrops()
    }

@app.get("/get_articles")
def get_articles() -> dict:
    """
    Returns the list of static articles and tracks water usage.

    Returns:
        dict: {"articles": [...]}

    Initial State:
        - Files available in ARTICLES_DIR

    Final State:
        - Articles returned and water usage incremented

    Water Cost:
        - 1 waterdrop
    """
    increment_aiwaterdrops(1)
    return fetch_static_articles()

@app.get("/mood")
def get_mood() -> dict:
    """
    Returns the current mood and mood history.

    Returns:
        dict: Current mood, last update, and history

    Initial State:
        - mood.json loaded

    Final State:
        - Mood data returned

    Water Cost:
        - 0
    """
    return {
        "current_mood": mood.get("current_mood", "unknown"),
        "last_updated": mood.get("last_updated", "unknown"),
        "history": mood.get("history", [])
    }

@app.post("/execute")
async def execute(request: Request) -> dict:
    """
    Dispatches an orchestrator execution call based on declared capability.

    Parameters:
        request (Request): Incoming request with 'capability' and 'input' payload

    Returns:
        dict: Result from the called capability

    Initial State:
        - Request payload contains a valid capability

    Final State:
        - Capability is executed and response is returned

    Raises:
        HTTPException: If capability is unknown or execution fails

    Water Cost:
        - 0.02 waterdrops per call
    """
    global aiwaterdrops_consumed
    try:
        payload = await request.json()
        capability = payload.get("capability")
        input_data = payload.get("input", {})

        if capability == "fetch_static_articles":
            increment_aiwaterdrops(0.02)
            return fetch_static_articles()
        elif capability == "generate_article_collection":
            increment_aiwaterdrops(0.02)
            return generate_article_collection(input_data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown capability: {capability}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")