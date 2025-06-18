# ClearCoreAI Agent: fetch_articles

**Version:** 0.2.2  
**Last Updated:** 2025-06-18  
**Validated by:** Olivier Hays  

---

## Overview

`fetch_articles` is a ClearCoreAI-compatible agent that serves static news content and tracks resource usage using AIWaterdrops.

It features:

- dynamic capability declaration (`/capabilities`)
- internal mood state tracking and persistence (`mood.json`)
- AIWaterdrops metering via `aiwaterdrops.json`
- orchestrator-compatible execution via `/execute`
- automatic self-registration to the orchestrator at startup

---

## Endpoints

### `GET /health`

Basic health check to verify that the agent is up.  
Water cost: 1 waterdrop

---

### `GET /capabilities`

Returns the declared capabilities, as defined in `manifest.json`.  
Water cost: 0

---

### `GET /manifest`

Returns the agent manifest.  
Useful for orchestrator registration and auditing.  
Water cost: 0

---

### `GET /metrics`

Returns runtime metrics:

- agent name and version  
- uptime in seconds  
- current mood  
- total waterdrops consumed  

Water cost: 0

---

### `GET /mood`

Returns:

- current mood  
- last mood update timestamp  
- historical mood changes  

Water cost: 0

---

### `GET /get_articles`

Returns a predefined list of static news articles stored in the `memory/long_term/` folder.  
Water cost: 3 waterdrops

---

### `POST /execute`

Main endpoint for orchestrator-controlled execution.  
Dispatches requests based on the `capability` declared.

Example payloads:

```json
{
  "capability": "fetch_static_articles",
  "input": {}
}
```

```json
{
  "capability": "generate_article_collection",
  "input": {
    "articles": [
      {"title": "Sample 1", "content": "Text", "source": "Demo"}
    ]
  }
}
```

Water cost: 0.02 waterdrops per call

---

## Capabilities

### `fetch_static_articles`

Fetches and returns a list of static articles from `.txt` files stored under `memory/long_term/`.

Each article follows the structure:

```json
{
  "title": "First line of file",
  "source": "Local file",
  "content": "Rest of the file"
}
```

---

### `generate_article_collection`

Converts a raw list of articles (e.g. from `fetch_static_articles`) into a normalized format:

```json
{
  "collection": {
    "count": 3,
    "items": [
      { "title": "...", "source": "...", "content": "..." }
    ]
  }
}
```

This is particularly useful for downstream agents expecting a `collection` schema.

---

## Usage

### Docker Compose

```bash
docker compose up --build
```

### Manual Run

```bash
docker build -t fetch_articles_agent .
docker run -p 8500:8500 fetch_articles_agent
```

---

## Required Files

Before launching the agent, ensure the following files exist:

- `manifest.json`: capability declarations and metadata  
- `mood.json`: stores mood and timestamps  
- `memory/short_term/aiwaterdrops.json`: created if missing  
- `.txt` article files in `memory/long_term/`  

To initialize the memory:

```bash
mkdir -p memory/short_term memory/long_term
echo '{"aiwaterdrops_consumed": 0}' > memory/short_term/aiwaterdrops.json
```

---

## License

This project is licensed under the MIT License.
