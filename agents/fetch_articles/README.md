
# ClearCoreAI Agent: fetch_articles

**Version:** 0.1.0  
**Last Updated:** 2025-06-13  
**Validated by:** Olivier Hays  

---

## Overview

`fetch_articles` is an example AI agent for the ClearCoreAI framework.  
It demonstrates:

✅ agent_manifest.json structure  
✅ mood.json support  
✅ AIWaterdrops tracking & persistence  
✅ basic agent endpoints  
✅ registration to orchestrator  

---

## Endpoints

### /health

Simple agent health check.

### /metrics

Returns:

- agent uptime
- current mood
- AIWaterdrops consumed

### /mood

Returns current mood and history from `mood.json`.

### /get_articles

Returns a set of example articles (mock data).  
**Increments AIWaterdrops consumed**.

---

## Usage

Start agent with:

```bash
docker compose up --build
```

Or inside agent folder:

```bash
docker build -t fetch_articles_agent .
docker run -p 8500:8500 fetch_articles_agent
```

---

## Required files

- `agent_manifest.json` → agent metadata
- `mood.json` → agent mood & history
- `license_keys.json.template` → API keys template
- `memory/short_term/aiwaterdrops.json` → AIWaterdrops persistence

---

## License

Licensed under Apache 2.0 License.

---

# 🚀 Let's build auditable and transparent AI agents!  
ClearCoreAI Team
