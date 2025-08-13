"""
Module: summarize_articles
Component: Agent API
Purpose: Summarize a list of articles using the Mistral LLM

Description:
This ClearCoreAI agent exposes a REST API to receive articles, summarize them using the Mistral API,
and return concise summaries. It supports declarative capability exposure via a manifest, mood tracking,
waterdrop accounting, and full compatibility with the orchestrator’s execution pipeline.

Philosophy:
- Inputs are explicitly validated to ensure content quality and prevent errors.
- Summarization is modular and delegated to a utility layer.
- All state changes (e.g., mood) are saved in JSON for transparency.
- Only declared capabilities are exposed to the orchestrator.
- Execution follows deterministic rules for auditable pipelines.

Initial State:
- `manifest.json` is present and valid
- `mood.json` exists or is initialized to default mood
- `license_keys.json` is present and contains a valid Mistral API key
- The FastAPI server is launched and ready to accept orchestrated or manual requests

Final State:
- Agent responds to all declared endpoints
- Summarization is performed on input content and tracked
- Mood state is updated and persisted
- Waterdrop usage is tracked per summary and exposed via `/metrics`

Version: 0.2.2
Validated by: Olivier Hays
Date: 2025-06-20

Estimated Water Cost:
- 1 waterdrop per /health call
- variable per /summarize and /execute structured summarization (depends on articles)
- 0.02 waterdrops per /execute dispatch
"""

# ----------- Imports ----------- #
import json
import time
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from tools.llm_utils import summarize_with_mistral
from tools.water import increment_aiwaterdrops, load_aiwaterdrops, get_aiwaterdrops

# ----------- Constants ----------- #
AGENT_NAME = "summarize_articles"
VERSION = "0.2.2"

# ----------- Credentials ----------- #
# LLM Key
try:
    with open("license_keys.json", "r") as license_json:
        license_keys = json.load(license_json)
except FileNotFoundError as license_error:
    raise RuntimeError("Missing license_keys.json. Cannot proceed without license.") from license_error

# ----------- App Initialization ----------- #
app = FastAPI(title="Summarize Articles Agent", version=VERSION)
start_time = time.time()

# ----------- State Management ----------- #
# Mood
try:
    with open("mood.json", "r") as mood_json:
        mood = json.load(mood_json)
except FileNotFoundError:
    # Use a single, consistent key across the app: current_mood
    mood = {"current_mood": "neutral", "last_summary": None}

# Current water consumption
aiwaterdrops_consumed = load_aiwaterdrops()

# ----------- Helper Functions ----------- #
def _coerce_articles(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Summary:
        Extract articles from supported input shapes.

    Parameters:
        payload (dict): Incoming input dict from the orchestrator.

    Returns:
        list[dict]: List of article objects with at least a 'content' field.

    Notes:
        - Supports:
          * {"articles": [ {title?, content, ...}, ... ]}
          * {"collection": {"items": [ ... ]}}
    """
    if isinstance(payload, dict):
        if isinstance(payload.get("articles"), list):
            return payload["articles"]
        collection = payload.get("collection")
        if isinstance(collection, dict) and isinstance(collection.get("items"), list):
            return collection["items"]
    return []


def generate_summaries(payload: dict) -> dict:
    """
    Summary:
        Generates summaries for a batch of articles using the Mistral LLM.

    Parameters:
        payload (dict): A dictionary with either `articles` or `collection.items`

    Returns:
        dict: A dictionary containing the summaries and total waterdrops used

    Initial State:
        - Valid Mistral API key loaded
        - Input articles are provided in the expected format

    Final State:
        - Each article is summarized
        - Mood is updated and saved

    Raises:
        HTTPException: If input is invalid or summarization fails

    Water Cost:
        - variable (returned by summarize_with_mistral per article)
    """
    articles = _coerce_articles(payload)
    if not isinstance(articles, list):
        raise HTTPException(status_code=422, detail="Input must contain 'articles' (list) or 'collection.items' (list).")

    summaries: List[str] = []
    waterdrops_used: float = 0.0

    for article in articles:
        if not isinstance(article, dict) or "content" not in article:
            raise HTTPException(status_code=400, detail="Invalid article format: missing 'content' field.")
        try:
            summary, waterdrops = summarize_with_mistral(
                article.get("content", ""),
                license_keys.get("mistral", "")
            )
        except Exception as summarize_error:
            raise HTTPException(status_code=400, detail=f"Failed to summarize article: {str(summarize_error)}")

        summaries.append(summary)
        waterdrops_used += float(waterdrops or 0)
        increment_aiwaterdrops(float(waterdrops or 0))

    # Update mood consistently
    mood["current_mood"] = "active"
    mood["last_summary"] = summaries[-1] if summaries else None

    with open("mood.json", "w") as file_out:
        json.dump(mood, file_out)

    return {
        "summaries": summaries,
        "waterdrops_used": waterdrops_used
    }


# ----------- API Endpoints ----------- #

@app.get("/manifest")
def get_manifest() -> dict:
    """
    Returns the full agent manifest.

    Returns:
        dict: The full manifest as declared in `manifest.json`

    Initial State:
        - manifest.json file is present and readable

    Final State:
        - The manifest is loaded and returned unchanged

    Raises:
        HTTPException: If the file is missing or unreadable

    Water Cost:
        - 0
    """
    try:
        with open("manifest.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="manifest.json not found")


@app.get("/health")
def health() -> dict:
    """
    Returns the health status of the agent.

    Returns:
        dict: Health status and current mood

    Initial State:
        - Mood is loaded from internal state

    Final State:
        - Returns static health check message

    Water Cost:
        - 0 waterdrop per call
    """
    return {"status": "Summarize Articles Agent is up and running."}


@app.get("/capabilities")
def get_capabilities() -> dict:
    """
    Loads and returns only the list of declared capabilities from the manifest (update manifest to remove basic path if you want the orchestrator to stop planning it).

    Returns:
        dict: {"capabilities": [...]}
        Reads from the manifest.json file.

    Initial State:
        - manifest.json is present

    Final State:
        - Extracted list of capabilities is returned

    Raises:
        FileNotFoundError: If manifest is missing

    Water Cost:
        - 0
    """
    with open("manifest.json", "r") as manifest_json:
        manifest = json.load(manifest_json)
    return {"capabilities": manifest.get("capabilities", [])}


@app.post("/summarize")
def summarize(payload: dict) -> dict:
    """
    Executes direct summarization endpoint for manual testing or client use.

    Parameters:
        payload (dict): Articles to summarize

    Returns:
        dict: Summaries and waterdrops used

    Initial State:
        - Valid API key and content present

    Final State:
        - Summarization performed and mood updated

    Water Cost:
        - variable per article
    """
    return generate_summaries(payload)


@app.post("/execute")
async def execute(request: Request) -> dict:
    """
    Executes declared capabilities for the agent.

    Parameters:
        request (Request): Incoming POST request with 'capability' and 'input' fields

    Returns:
        dict: Result structure defined by the capability

    Initial State:
        - A valid Mistral API key is loaded from license_keys.json for LLM-backed ops
        - The input contains either 'articles' or 'collection.items'

    Final State:
        - Structured LLM summarization is executed
        - Mood and water usage are updated accordingly

    Raises:
        HTTPException: If capability is unrecognized or input is invalid

    Water Cost:
        - ~2 waterdrops per article for structured LLM summarization
        - +0.02 waterdrops per call (fixed dispatch overhead)
    """
    try:
        payload = await request.json()
        capability = payload.get("capability")
        input_data = payload.get("input", {}) or {}

        # Fixed dispatch overhead
        increment_aiwaterdrops(0.02)

        if capability == "structured_text_summarization":
            return generate_summaries(input_data)

        raise HTTPException(status_code=400, detail=f"Unknown or disabled capability: {capability}. Only 'structured_text_summarization' is enabled.")

    except HTTPException:
        # Re-raise FastAPI HTTP errors unchanged
        raise
    except Exception as execution_error:
        # Wrap any unexpected exception
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(execution_error)}")


@app.get("/metrics")
def get_metrics() -> dict:
    """
    Returns runtime and usage metrics.

    Returns:
        dict: Agent version, uptime, mood, and estimated water usage

    Initial State:
        - Mood and uptime are tracked

    Final State:
        - Metrics report returned

    Water Cost:
        - 0
    """
    uptime = int(time.time() - start_time)
    return {
        "agent": AGENT_NAME,
        "version": VERSION,
        "uptime_seconds": uptime,
        "current_mood": mood.get("current_mood", "unknown"),
        "aiwaterdrops_consumed": get_aiwaterdrops()
    }


@app.get("/mood")
def get_mood() -> dict:
    """
    Retrieves current mood and last summary from memory.

    Returns:
        dict: Mood and last summary state

    Initial State:
        - mood.json loaded at startup

    Final State:
        - Mood data returned without change

    Water Cost:
        - 0
    """
    return {
        "current_mood": mood.get("current_mood", "unknown"),
        "last_summary": mood.get("last_summary")
    }

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