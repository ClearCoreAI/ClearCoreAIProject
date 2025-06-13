
# ClearCoreAI

**Transparent & robust orchestration of modular AI agents**  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)  
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](CHANGELOG.md)

---

## 🌟 Philosophy

ClearCoreAI is an open-source framework to orchestrate modular, autonomous AI agents with full transparency and robust architecture.

**Core principles**:

- 🧩 Modularity → Agents are treated as independent thinking entities
- 🔍 Transparency → All processes are auditable and documented (AIWaterdrops, memory, mood)
- 🤝 Autonomy → Agents manage their own tools and licenses
- 📜 Traceability → Metrics, moods, resource usage and outputs are fully tracked
- 🌍 Openness → The architecture is designed for community contributions and extensibility

---

## 🚀 Architecture

User → Orchestrator → Agents (Dockerized) → External APIs / LLMs / Memory  
↑  
AIWaterdrops tracking  
Mood + Metrics collection  

**Orchestrator**:

- Agents registry
- Mood and scoring tracking
- AIWaterdrops management
- License management (internal)
- Memory (optional) and metrics collection

**Agents**:

- Independent Docker containers
- Own Manifest MCP
- Own mood, metrics, tools and licenses
- Short-term and long-term memory
- Self-register to orchestrator

**Shared Memory**:

- Optional shared knowledge graph (Neo4j)

---

## 💧 AIWaterdrops

ClearCoreAI introduces the concept of **AIWaterdrops**:

- 1 Waterdrop = estimated cost of an operation (LLM call, DB query, processing...)
- All agents report their AIWaterdrops consumption
- The orchestrator tracks global and per-agent consumption
- This provides an **auditable and transparent cost tracking system** for AI operations.

---

## 🧩 Project structure

- orchestrator/ → Main orchestrator (FastAPI), manages agents registry, AIWaterdrops, mood, metrics.
- agents/ → Independent agents (each in their own folder), self-registering to the orchestrator.
- schema/ → Shared memory (Neo4j) schema and samples.
- memory/, logs/, output/ → Are NOT versioned in Git — see .gitignore.

---

## 🏃‍♂️ How to run locally

### 1️⃣ Prerequisites

- Docker and Docker Compose installed on your system.

### 2️⃣ Launch ClearCoreAI

```bash
docker compose up --build
```

### 3️⃣ Test orchestrator

http://localhost:8000/health  
http://localhost:8000/agents  

### 4️⃣ Test example agent

http://localhost:8500/health  
http://localhost:8500/get_articles  
http://localhost:8500/metrics  

---

## ✏️ Code style and commenting conventions

We use a **strict code commenting style** for maximum transparency and traceability.  
All public functions/classes must include a complete docstring following this structure:

Purpose:  
Initial State:  
Final State:  
Inputs:  
Outputs:  
Exceptions:  
AIWaterdrops estimation:  
Version:  

👉 See [CONTRIBUTING.md](CONTRIBUTING.md) for full details and example.

---

## 🤝 Contributing

We welcome contributions from all backgrounds and skill levels!  
Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting pull requests.

When adding a new agent:

- Include a agent_manifest.json
- Implement /health, /metrics and at least one useful endpoint
- Follow the mandatory code commenting style
- Respect the project’s core principles (modularity, transparency, autonomy, traceability)

---

## 📜 License

This project is licensed under the MIT License — see [LICENSE](LICENSE).

---

## 🚧 Roadmap

- Advanced orchestrator dashboard (web UI)
- Better AIWaterdrops visualisation and tracking
- Shared memory live integration (Neo4j API)
- Advanced agent evaluation and orchestration
- Support for complex orchestration scenarios (multi-agent workflows)

---

## 🚀 Join the movement

ClearCoreAI is built with ❤️ to promote **transparent, auditable, modular AI architectures**.  
Join us and contribute your own agents!  

Let’s make agents **think**, **trace**, and **collaborate** — the ClearCoreAI way. 🚀
