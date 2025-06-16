"""
Module: summarize_articles
Component: Agent API
Purpose: Summarize a list of articles using the Mistral LLM

Description:
This ClearCoreAI agent exposes a FastAPI interface to receive articles,
summarize them using the Mistral API, and return concise summaries.
It reports its capabilities to the orchestrator and tracks internal
mood and energy consumption via the metaphor of "waterdrops".

Philosophy:
- Inputs are validated explicitly (presence of article content).
- Summarization is delegated to a dedicated utility function.
- State persistence (mood) is simple but traceable.
- Capabilities are declared via manifest introspection.
- Execution is modular and interoperable with orchestration.

Initial State:
- `mood.json` exists or is initialized to default
- `license_keys.json` contains a valid Mistral API key
- `manifest.json` is present and valid

Final State:
- Agent responds to HTTP endpoints (/health, /capabilities, /summarize, /execute)
- Mood is updated after summarization
- Water usage is tracked and reported

Version: 0.2.0
Validated by: Olivier Hays
Date: 2025-06-16

Estimated Water Cost:
- 1 waterdrop per /health call
- ~4 waterdrops per /summarize call (depends on number of articles)
- 0.02 waterdrops per /execute dispatch
"""

# ----------- Imports ----------- #
import json
from fastapi import FastAPI, HTTPException, Request
from tools.llm_utils import summarize_with_mistral

# ----------- Internal State / License Loading ----------- #
try:
    with open("mood.json", "r") as f:
        mood = json.load(f)
except FileNotFoundError:
    mood = {"status": "neutral", "last_summary": None}

try:
    with open("license_keys.json", "r") as f:
        license_keys = json.load(f)
except FileNotFoundError as e:
    raise RuntimeError("Missing license_keys.json. Cannot proceed without license.") from e

# ----------- App Initialization ----------- #
app = FastAPI(title="Summarize Articles Agent", version="0.2.0")

# ----------- API Endpoints ----------- #
@app.get("/capabilities")
def get_capabilities():
    """
    Returns the agent's manifest for orchestrator introspection.

    Initial State:
        - `manifest.json` is present and valid

    Final State:
        - Returns the parsed manifest as a dict

    Raises:
        FileNotFoundError: if manifest.json is missing
    """
    with open("manifest.json", "r") as f:
        return json.load(f)


@app.get("/health")
def health():
    """
    Healthcheck endpoint.

    Initial State:
        - Agent is booted and `mood` is loaded

    Final State:
        - Returns basic status and mood

    Water Cost:
        - 1 waterdrop
    """
    return {"status": "Summarize Articles Agent is up.", "mood": mood.get("status", "unknown")}


@app.post("/summarize")
def summarize(payload: dict):
    """
    Summarizes a list of articles using the Mistral API.

    Parameters:
        payload (dict): must contain a list of article dicts with a "content" field

    Returns:
        dict: summaries and total waterdrops consumed

    Initial State:
        - Valid Mistral API key loaded
        - Input contains at least one valid article with text content

    Final State:
        - Summaries are returned
        - Mood is updated and persisted
        - Waterdrops are accumulated

    Raises:
        HTTPException 400: if input is malformed or summarization fails

    Water Cost:
        - ~2 waterdrops per article
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
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to summarize article: {str(e)}")

        summaries.append(summary)
        waterdrops_used += waterdrops

    # Update mood state
    mood["status"] = "active"
    mood["last_summary"] = summaries[-1] if summaries else None

    with open("mood.json", "w") as f:
        json.dump(mood, f)

    return {
        "summaries": summaries,
        "waterdrops_used": waterdrops_used
    }


@app.post("/execute")
async def execute(request: Request):
    """
    Dispatcher endpoint for orchestrator execution.

    Parameters:
        request (Request): JSON with a 'capability' and 'input' field

    Returns:
        dict: Result of dispatched capability

    Initial State:
        - Input payload contains valid capability and input
        - Optional: summaries already precomputed (for structured output)

    Final State:
        - Dispatches to the correct internal capability function
        - Returns structured result

    Raises:
        HTTPException 400: if unknown capability or invalid input
        HTTPException 500: for internal execution errors

    Water Cost:
        - 0.02 base + cost of underlying function
    """
    try:
        payload = await request.json()
        capability = payload.get("capability")
        input_data = payload.get("input", {})

        if capability == "text_summarization":
            return summarize(input_data)

        elif capability == "structured_output_generation":
            summaries = input_data.get("summaries")
            if not summaries:
                raise HTTPException(status_code=400, detail="Missing 'summaries' in input for structured output.")

            return {
                "summaries_structured": [
                    {"summary": s, "format": "simple_text"} for s in summaries
                ]
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown capability: {capability}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")