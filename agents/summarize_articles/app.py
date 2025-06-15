"""
Module: summarize_articles agent
Process: FastAPI agent API

Description:
Agent for ClearCoreAI: summarize_articles. Accepts a list of articles and returns summaries using the Mistral LLM API.
Exposes capabilities via introspection and monitors its internal mood and resource consumption ("waterdrops").

Version: 0.1.1
Initial State: Agent starts with default mood and loads license keys.
Final State: Agent serves HTTP endpoints and updates mood after summarization.

Exceptions handled:
- FileNotFoundError — if mood.json or license_keys.json are missing.
- HTTPException 400 — if summarization fails due to API or logic errors or bad input.

Validation:
- Validated by: Olivier Hays
- Date: 2025-06-15

Estimated Water Cost:
- 1 waterdrop per /health call
- ~4 waterdrops per /summarize call (depends on number of articles)
"""

import json
from fastapi import FastAPI, HTTPException
from tools.llm_utils import summarize_with_mistral

# Internal state tracking (mood, energy)
# Mood represents the current operational state of the agent
try:
    with open("mood.json", "r") as f:
        mood = json.load(f)
except FileNotFoundError:
    mood = {"status": "neutral", "last_summary": None}

# API credentials (license keys)
# Used to authenticate with external services such as the Mistral API
try:
    with open("license_keys.json", "r") as f:
        license_keys = json.load(f)
except FileNotFoundError as e:
    raise RuntimeError("Missing license_keys.json. Cannot proceed without license.") from e

# FastAPI app declaration
app = FastAPI(title="Summarize Articles Agent", version="0.1.1")

@app.get("/capabilities")
def get_capabilities():
    """
    Introspection endpoint.
    Returns the static manifest describing the agent’s inputs, outputs, and functions.
    Enables orchestrator to auto-connect capabilities without hardcoded rules.
    """
    with open("manifest.json", "r") as f:
        return json.load(f)

@app.get("/health")
def health():
    """
    Lightweight healthcheck to ensure the agent is responsive.
    Also returns current mood for monitoring or debugging.
    """
    return {"status": "Summarize Articles Agent is up.", "mood": mood.get("status", "unknown")}

@app.post("/summarize")
def summarize(payload: dict):
    """
    Core endpoint: summarizes a list of articles using the Mistral API.

    Input:
        {
            "articles": [
                {"title": "Optional title", "content": "Text to summarize"},
                ...
            ]
        }

    Output:
        {
            "summaries": ["summary1", "summary2", ...],
            "waterdrops_used": total_waterdrops
        }

    Estimated cost: ~2 waterdrops per article
    """
    articles = payload.get("articles", [])
    summaries = []
    waterdrops_used = 0

    for article in articles:
        try:
            # Minimal input validation
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

    # Update internal state
    mood["status"] = "active"
    mood["last_summary"] = summaries[-1] if summaries else None
    with open("mood.json", "w") as f:
        json.dump(mood, f)

    return {
        "summaries": summaries,
        "waterdrops_used": waterdrops_used
    }