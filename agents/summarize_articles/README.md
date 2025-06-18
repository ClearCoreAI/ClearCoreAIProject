# ClearCoreAI Agent: summarize_articles

**Version:** 0.2.0  
**Last Updated:** 2025-06-18  
**Validated by:** Olivier Hays  

---

## Overview

`summarize_articles` is a ClearCoreAI-compatible agent that summarizes input articles using the Mistral LLM API.  
It tracks internal mood, reports energy usage (in waterdrops), and exposes a structured capability for orchestrator use.

- LLM summarization via Mistral API  
- Mood state persistence (`mood.json`)  
- Waterdrop consumption tracking  
- Declarative orchestration via `/execute`  
- Structured capability: `structured_text_summarization`

---

## Endpoints

### `GET /health`

Returns agent status and current mood.  
Water cost: 1 waterdrop

---

### `GET /capabilities`

Returns the list of capabilities declared in `manifest.json`.

---

### `GET /metrics`

Returns:

- agent name and version  
- uptime  
- current mood  
- estimated waterdrops consumed

---

### `GET /mood`

Returns:

- current mood  
- last summarized content

---

### `GET /manifest`

Returns the full agent manifest.

---

### `POST /summarize`

Summarizes a list of articles using the Mistral API.  
Payload format:

```json
{
  "articles": [
    {"title": "Optional", "content": "Text to summarize"},
    ...
  ]
}
```

Returns:

```json
{
  "summaries": ["summary1", "summary2", ...],
  "waterdrops_used": <int>
}
```

Water cost: ~2 waterdrops per article

---

### `POST /execute`

Used by the orchestrator to call the main capability.  
Accepted payload:

```json
{
  "capability": "structured_text_summarization",
  "input": { ... }
}
```

Returns:

```json
{
  "summaries": [...],
  "waterdrops_used": <int>
}
```

Water cost: 0.02 fixed + ~2 per article

---

## Capabilities

- `structured_text_summarization`:  
  Summarizes a list of articles provided in either:
  - `articles` field  
  - `collection.items` field  
  Returns a structured JSON response.

---

## Usage

Start agent with Docker Compose:

```bash
docker compose up --build
```

Or manually:

```bash
docker build -t summarize_articles_agent .
docker run -p 8600:8600 summarize_articles_agent
```

---

## Required files

Ensure the following files exist before startup:

- `manifest.json` → capability declaration  
- `mood.json` → persistent agent state  
- `license_keys.json` → must contain valid `mistral` API key  

---

## License

Licensed under the MIT License.

---