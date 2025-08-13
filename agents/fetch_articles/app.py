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

# ----------- Audit Policy Endpoint (generic) ----------- #
import json
import os
from pathlib import Path
from fastapi import HTTPException

AUDIT_POLICY_FILE = Path("audit_policy.json")
# Petit cache en mémoire pour éviter de relire le disque à chaque appel
_AUDIT_POLICY_CACHE = {"mtime": None, "data": None}


def _validate_audit_policy(policy: dict) -> None:
    """
    Validates a minimal schema for the agent's audit policy file.

    Parameters:
        policy (dict): Parsed JSON policy to validate.

    Returns:
        None: The function returns None if the policy is valid.

    Initial State:
        - `policy` is a Python dict obtained from audit_policy.json
        - The dict may contain "rules", "scoring", and "meta" sections

    Final State:
        - The policy is guaranteed to include minimally valid structures
          required by the auditor (e.g., a list of rules with ids/targets/asserts)

    Raises:
        HTTPException: 500 when the structure is invalid (missing keys or wrong types)

    Water Cost:
        - 0 waterdrops (pure in-memory checks)
    """
    if not isinstance(policy, dict):
        raise HTTPException(status_code=500, detail="audit_policy.json must be a JSON object")

    rules = policy.get("rules")
    if not isinstance(rules, list) or len(rules) == 0:
        raise HTTPException(status_code=500, detail="audit_policy.json: 'rules' must be a non-empty array")

    # Validate each rule has minimal shape
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise HTTPException(status_code=500, detail=f"Rule #{idx} must be an object")
        if "id" not in rule or not isinstance(rule["id"], str) or not rule["id"].strip():
            raise HTTPException(status_code=500, detail=f"Rule #{idx} missing non-empty 'id'")
        if "target" not in rule or not isinstance(rule["target"], str) or not rule["target"].strip():
            raise HTTPException(status_code=500, detail=f"Rule #{idx} missing non-empty 'target'")
        if "assert" not in rule or not isinstance(rule["assert"], dict):
            raise HTTPException(status_code=500, detail=f"Rule #{idx} missing 'assert' object")

    # Optional scoring block (when present)
    scoring = policy.get("scoring")
    if scoring is not None:
        if not isinstance(scoring, dict):
            raise HTTPException(status_code=500, detail="'scoring' must be an object when present")

    # Optional meta block (free-form)
    meta = policy.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise HTTPException(status_code=500, detail="'meta' must be an object when present")


def _load_audit_policy() -> dict:
    """
    Loads and returns the agent's audit policy from disk with light validation and caching.

    Parameters:
        None

    Returns:
        dict: The parsed and validated audit policy JSON.

    Initial State:
        - `audit_policy.json` exists next to the agent's app.py
        - File is UTF-8 and contains valid JSON

    Final State:
        - A valid policy dict is returned
        - In-memory cache is populated for subsequent calls

    Raises:
        HTTPException: 404 if the file is missing
        HTTPException: 500 on JSON decode error or schema validation error

    Water Cost:
        - 0 waterdrops (I/O only, no LLM)
    """
    if not AUDIT_POLICY_FILE.exists():
        raise HTTPException(status_code=404, detail="audit_policy.json not found")

    try:
        mtime = AUDIT_POLICY_FILE.stat().st_mtime
        # Return cached version if unchanged
        if _AUDIT_POLICY_CACHE["mtime"] == mtime and _AUDIT_POLICY_CACHE["data"] is not None:
            return _AUDIT_POLICY_CACHE["data"]

        with AUDIT_POLICY_FILE.open("r", encoding="utf-8") as f:
            policy = json.load(f)

        _validate_audit_policy(policy)

        _AUDIT_POLICY_CACHE["mtime"] = mtime
        _AUDIT_POLICY_CACHE["data"] = policy
        return policy

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in audit_policy.json: {str(e)}")
    except HTTPException:
        # Propager les erreurs déjà formées ci-dessus
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load audit_policy.json: {str(e)}")


@app.get("/audit_policy")
def get_audit_policy() -> dict:
    """
    Returns the agent-specific audit policy for the external auditor.

    Parameters:
        None

    Returns:
        dict: The validated content of `audit_policy.json`.

    Initial State:
        - `audit_policy.json` file is present alongside this app
        - File content follows the minimal policy schema (rules[], optional scoring/meta)

    Final State:
        - A JSON policy is returned to the caller
        - Policy content may be served from an in-memory cache when unchanged

    Raises:
        HTTPException: 404 if `audit_policy.json` is missing
        HTTPException: 500 if JSON is invalid or schema checks fail

    Water Cost:
        - 0 waterdrops per call
    """
    return _load_audit_policy()