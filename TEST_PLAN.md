
# ClearCoreAI - TEST PLAN v0.1.0

This document describes how to test the ClearCoreAI orchestrator and agents.

**Version:** 0.1.0  
**Last Updated:** 2025-06-13  
**Validated by:** Olivier Hays  

---

## Testing Environment

- Orchestrator exposed on `http://localhost:8000`
- Agent `fetch_articles` exposed on `http://localhost:8500`
- Containers started with:

```
docker compose up --build
```

---

## 1️⃣ Orchestrator Endpoints

### /health

```
GET http://localhost:8000/health
```

✅ Expect:

```
{ "status": "ClearCoreAI orchestrator is up and running." }
```

---

### /register_agent

```
POST http://localhost:8000/register_agent
Content-Type: application/json

Body:
{
    "agent_name": "fetch_articles",
    "version": "0.1.0",
    "url": "http://fetch_articles_agent:8500"
}
```

✅ Expect:

```
{ "message": "Agent 'fetch_articles' registered successfully." }
```

---

### /agents

```
GET http://localhost:8000/agents
```

✅ Expect: list of registered agents with AgentInfo structure.

---

### /agents/metrics

```
GET http://localhost:8000/agents/metrics
```

✅ Expect: aggregated agents metrics, pulling `/metrics` from each agent.

---

### /metrics (Orchestrator)

```
GET http://localhost:8000/metrics
```

✅ Expect: orchestrator uptime, number of agents, total AIWaterdrops consumed.

---

### /mood (Orchestrator)

```
GET http://localhost:8000/mood
```

✅ Expect: current mood and history from orchestrator `mood.json`.

---

## 2️⃣ Agent `fetch_articles` Endpoints

### /health

```
GET http://localhost:8500/health
```

✅ Expect: agent healthy.

---

### /metrics

```
GET http://localhost:8500/metrics
```

✅ Expect: agent uptime, AIWaterdrops consumed, current mood.

---

### /mood

```
GET http://localhost:8500/mood
```

✅ Expect: agent `mood.json` current mood and history.

---

### /get_articles

```
GET http://localhost:8500/get_articles
```

✅ Expect: list of example articles in JSON.

⚠️ Verify:

- AIWaterdrops consumed increases after each `/get_articles` call.
- Check with `/metrics` before and after `/get_articles`.

---

## Recommended Testing Order

1. Start containers:

```
docker compose up --build
```

2. Verify orchestrator `/health`.
3. Register agent with `/register_agent`.
4. Verify `/agents`.
5. Test `/agents/metrics`.
6. Test `/metrics` and `/mood` orchestrator.
7. Verify agent `/health`, `/metrics`, `/mood`, `/get_articles`.

---

## Notes

✅ This test plan covers functional testing of the ClearCoreAI architecture v0.1.0.  
✅ Advanced features (auto mood update, unregister agent, memory management) planned for future versions.

---

# Happy Testing 🚀  
ClearCoreAI Team
