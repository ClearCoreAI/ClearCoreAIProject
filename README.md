# 🚀 ClearCoreAI — Core Orchestrator

**Version:** 0.3.2  
**Last Updated:** 2025-06-20  
**Validated by:** Olivier Hays  

👉 New here? Check out the [Quickstart Guide](docs/QUICKSTART.md) to get up and running fast.

---

## 🔍 Overview

The **ClearCoreAI Orchestrator** is the beating heart of a modular, explainable and fully auditable AI system.  
It connects and coordinates a swarm of autonomous agents, turning natural language instructions into traceable, multi-step execution plans.

Whether you're building a research prototype or an industrial AI pipeline, ClearCoreAI gives you:

- ✅ Dynamic agent registration & manifest validation  
- 🔁 Automated compatibility checks between agents  
- 🧠 Natural language planning (via Mistral LLM)  
- 📊 Transparent tracking of energy usage (in waterdrops)  
- 📂 Persistent memory for reproducible orchestration  

Built with transparency, modularity and developer joy in mind.  

---

## 🌐 API Endpoints

### `GET /health`  
Check orchestrator status and list current agents.  
Water cost: **0**

---

### `POST /register_agent`  
Register a new agent by validating its `/manifest`.  
Water cost: **0.2**

---

### `GET /agents`  
List all registered agents and their capabilities.  
Water cost: **0.05**

---

### `GET /agent_manifest/{agent_name}`  
Get the full manifest of a specific agent.  
Water cost: **0**

---

### `GET /agents/connections`  
Detect compatible I/O between agents.  
Water cost: **0**

---

### `GET /agents/metrics`  
Collect live `/metrics` from all agents.  
Water cost: **0**

---

### `GET /agents/raw`  
Return raw manifests of all registered agents.  
Water cost: **0**

---

### `POST /plan`  
Generate a multi-step execution plan from a natural language goal.  
Water cost: **3**

---

### `POST /execute_plan`  
Execute a given plan string across agents.  
Water cost: **0.02 + dynamic agent cost**

---

### `POST /run_goal`  
Generate and run a plan in one request (auto pipeline).  
Water cost: **~3**

---

### `GET /water/total`  
Get total waterdrop consumption across orchestrator and agents.  
Water cost: **0**

---

## ▶️ Getting Started

Run locally:

```bash
uvicorn main:app --reload
```

Or using Docker:

```bash
docker build -t clearcore_orchestrator .
docker run -p 8000:8000 clearcore_orchestrator
```

Once running, register agents and launch your goals!

---

## 🧪 Example Usage

**Register an agent:**

```bash
curl -X POST http://localhost:8000/register_agent \
  -H "Content-Type: application/json" \
  -d '{"name": "fetch_articles", "base_url": "http://fetch_articles_agent:8500"}' | jq
```

**Run a full pipeline:**

```bash
curl -X POST http://localhost:8000/run_goal \
  -H "Content-Type: application/json" \
  -d '{"goal": "fetch articles and summarize them"}' | jq
```

---

## 🤝 Contributing

We welcome contributions to make ClearCoreAI even better!

- Fork the repo
- Follow the docstring and commenting conventions
- Respect waterdrop accounting in every route
- Keep it modular and readable

You can also check the [ROADMAP](docs/ROADMAP.md) and [CHANGELOG](CHANGELOG.md) for ideas.

---

## 📄 License

This project is licensed under the MIT License.

---

**Clear orchestration. Auditable agents. Transparent AI.**  
*– The ClearCoreAI Team*