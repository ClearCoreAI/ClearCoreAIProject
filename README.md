
# ClearCoreAI Orchestrator

**Version:** 0.1.0  
**Last Updated:** 2025-06-13  
**Validated by:** Olivier Hays  

---

## Overview

The ClearCoreAI Orchestrator is the central component of the ClearCoreAI architecture.  
It provides **transparent and auditable orchestration** of modular AI agents running as independent containers.

**Key features:**

✅ Agent registration & listing  
✅ Agent metrics aggregation  
✅ Global orchestrator metrics  
✅ Global orchestrator mood  
✅ Designed for modularity & security  

---

## Endpoints

### /health

Simple orchestrator health check.

### /register_agent

Registers an AI agent.  
Body must include:

```json
{
    "agent_name": "...",
    "version": "...",
    "url": "http://agent-container:port"
}
```

### /agents

Lists all registered agents.

### /agents/metrics

Aggregates `/metrics` from all registered agents.

### /metrics

Orchestrator own metrics:

- uptime
- registered agents count
- total AIWaterdrops consumed

### /mood

Orchestrator own mood (from `mood.json`).

---

## Usage

Start orchestrator with:

```bash
docker compose up --build
```

Or inside orchestrator folder:

```bash
docker build -t clearcoreai-orchestrator .
docker run -p 8000:8000 clearcoreai-orchestrator
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md).

---

## License

Licensed under MIT License.

---

# 🚀 Let's orchestrate AI agents transparently!  
ClearCoreAI Team
