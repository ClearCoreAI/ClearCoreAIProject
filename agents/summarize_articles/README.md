# ClearCoreAI Agent: summarize_articles

**Version:** 0.1.0  
**Last Updated:** 2025-06-15  
**Validated by:** Olivier Hays  

---

## Overview

The `summarize_articles` agent is part of the ClearCoreAI modular architecture.  
It is responsible for **summarizing text-based articles** using a language model like **Mistral AI**.

**Key features:**

✅ LLM-based article summarization  
✅ Dynamic API powered by FastAPI  
✅ Waterdrop consumption tracking  
✅ Mood status tracking with `mood.json`  
✅ Designed for plug-and-play with ClearCoreAI Orchestrator  

---

## Endpoints

### /health

Returns the current health and mood status of the summarize agent.

### /summarize

Accepts a JSON payload of articles and returns a list of summaries.  
Example:

```json
{
  "articles": [
    "First article full text goes here...",
    "Second article full text goes here..."
  ]
}
```

Returns:

```json
{
  "summaries": ["Summary 1", "Summary 2"],
  "waterdrops_used": 7
}
```

---

## Usage

Start the agent with:

```bash
docker compose up --build
```

Or manually:

```bash
docker build -t ClearCoreAIProject-summarize .
docker run -p 8001:8000 ClearCoreAIProject-summarize
```

---

## Agent Configuration

This agent requires:

- A valid API key in `license_keys.json`
- An initial `mood.json` configuration
- LLM utilities under `tools/llm_utils.py`

---

## License

Licensed under MIT License.

---

# ✨ Empower your AI pipeline with summarization!
ClearCoreAI Team
