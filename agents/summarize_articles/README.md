# ClearCoreAI Agent: summarize_articles

**Version:** 0.2.2  
**Last Updated:** 2025-06-20  
**Validated by:** Olivier Hays  

---

## Overview

`summarize_articles` is a ClearCoreAI-compatible agent that summarizes input articles using the Mistral LLM API.  
It tracks internal mood, reports energy usage (in waterdrops), and exposes a structured capability for orchestrator use.

Features:

- Summarization using Mistral API  
- Mood persistence in `mood.json`  
- Waterdrop tracking per usage  
- Declarative orchestration via `/execute`  
- Structured capability: `structured_text_summarization`

---

## Endpoints

### `GET /health`

Returns the agent’s status and current mood.  
**Water cost:** 0

---

### `GET /capabilities`

Returns the list of capabilities from `manifest.json`.  
**Water cost:** 0

---

### `GET /metrics`

Returns:
- Agent name and version  
- Uptime (seconds)  
- Current mood  
- Estimated waterdrops consumed  
**Water cost:** 0

---

### `GET /mood`

Returns:
- Current mood  
- Last summarized content  
**Water cost:** 0

---

### `GET /manifest`

Returns the complete agent manifest.  
**Water cost:** 0

---

### `POST /summarize`

Manual endpoint to summarize a list of articles.  

**Payload example:**
```json
{
  "articles": [
    {
      "title": "Optional",
      "content": "Text to summarize"
    }
  ]
}
```

**Returns:**
```json
{
  "summaries": ["summary1", "summary2", "..."],
  "waterdrops_used": 4
}
```

**Water cost:** ~2 waterdrops per article

---

### `POST /execute`

Main orchestrator endpoint.  

**Payload:**
```json
{
  "capability": "structured_text_summarization",
  "input": {
    "articles": [
      {
        "title": "Title",
        "content": "Article content"
      }
    ]
  }
}
```

**Returns:**
```json
{
  "summaries": "[...]",
  "waterdrops_used": 4
}
```

**Water cost:** 0.02 fixed overhead + ~2 per article

---

## Capabilities

### `structured_text_summarization`

Summarizes a list of articles provided via:

- `articles` field  
- or `collection.items` field

Returns structured summaries suitable for downstream agents.

---

## Usage

**With Docker Compose:**
```bash
docker compose up --build
```

**Or manually:**
```bash
docker build -t summarize_articles_agent .
docker run -p 8600:8600 summarize_articles_agent
```

---

## Required Files

Before starting the agent, ensure the following files exist:

- `manifest.json` → capability declaration  
- `mood.json` → stores agent state  
- `license_keys.json` → must contain a valid "mistral" API key  
- `memory/short_term/aiwaterdrops.json` → must exist with content:
```json
{
  "aiwaterdrops_consumed": 0.0
}
```

To initialize memory folders:
```bash
mkdir -p memory/short_term
echo '{"aiwaterdrops_consumed": 0.0}' > memory/short_term/aiwaterdrops.json
```

---

## License

Licensed under the MIT License.