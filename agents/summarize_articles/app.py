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

Version: 0.2.1
Validated by: Olivier Hays
Date: 2025-06-20

Estimated Water Cost:
- 1 waterdrop per /health call
- ~2 waterdrops per /summarize call (variable per article count)
- 0.02 waterdrops per /execute dispatch
"""

# ----------- Imports ----------- #
import json
import time
from fastapi import FastAPI, HTTPException, Request
from tools.llm_utils import summarize_with_mistral
from tools.water import increment_aiwaterdrops, load_aiwaterdrops, get_aiwaterdrops

# ----------- Constants ----------- #
AGENT_NAME = "summarize_articles"
VERSION = "0.2.1"

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
    mood = {"current_mood": "neutral", "last_summary": None}

# Current water consumption
aiwaterdrops_consumed = load_aiwaterdrops()

# ----------- Helper Functions ----------- #
def generate_summaries(payload: dict) -> dict:
    """
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
        - 2 waterdrops per article (fixed estimate)
    """
    articles = payload.get("articles") or payload.get("collection", {}).get("items", [])
    summaries = []
    waterdrops_used = 0

    for article in articles:
        try:
            if not isinstance(article, dict) or "content" not in article:
                raise HTTPException(status_code=400, detail="Invalid article format: missing 'content' field.")

            summary, waterdrops = summarize_with_mistral(
                article.get("content", ""),
                license_keys.get("mistral", "")
            )
        except Exception as summarize_error:
            raise HTTPException(status_code=400, detail=f"Failed to summarize article: {str(summarize_error)}")

        summaries.append(summary)
        waterdrops_used += waterdrops
        increment_aiwaterdrops(waterdrops)

    mood["status"] = "active"
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
    Loads and returns only the list of declared capabilities from the manifest.

    Returns:
        dict: {"capabilities": [...]}

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
        - 2 waterdrops per article
    """
    return generate_summaries(payload)

@app.post("/execute")
async def execute(request: Request) -> dict:
    """
    Executes the agent's main capability: structured text summarization.

    Parameters:
        request (Request): Incoming POST request with 'capability' and 'input' fields

    Returns:
        dict: Structured summaries generated from the input articles

    Initial State:
        - A valid Mistral API key is loaded from license_keys.json
        - The input contains either 'articles' or 'collection.items'

    Final State:
        - Articles are summarized
        - Mood is updated and persisted
        - Waterdrop usage is estimated and returned

    Raises:
        HTTPException: If capability is unrecognized or input is invalid
        HTTPException: If an error occurs during summarization

    Water Cost:
        - ~2 waterdrops per article (LLM usage)
        - +0.02 waterdrops per call (fixed dispatch overhead)
    """
    try:
        payload = await request.json()
        capability = payload.get("capability")
        input_data = payload.get("input", {})

        if capability == "structured_text_summarization":
            return generate_summaries(input_data)

        else:
            raise HTTPException(status_code=400, detail=f"Unknown capability: {capability}")

    except Exception as execution_error:
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
        "current_mood": mood.get("curent_mood", "unknown"),
        "last_summary": mood.get("last_summary")
    }