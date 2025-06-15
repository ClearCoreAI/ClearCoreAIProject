
ClearCoreAI Orchestrator
=========================

Version: 0.1.0  
Last Updated: 2025-06-15  
Validated by: Olivier Hays  

---

Overview
--------

The ClearCoreAI Orchestrator is the central component of the ClearCoreAI architecture.  
It provides transparent and auditable orchestration of modular AI agents running as independent containers.

Key features:

- Agent registration & discovery
- Dynamic manifest validation
- Dynamic capability & dependency mapping
- Global orchestrator metrics
- Global orchestrator mood tracking
- Designed for modularity, observability & security

---

Endpoints
---------

### /health
Check the orchestrator's health status.

### /register_agent
Register an AI agent.

Request body must include:
{
    "agent_name": "...",
    "version": "...",
    "url": "http://agent-container:port"
}

This endpoint also triggers validation of the agent's manifest against the common template.

### /agents
List all registered agents.

### /agents/metrics
Aggregate /metrics from all registered agents.

### /metrics
Show orchestrator's own metrics:
- Uptime
- Registered agents count
- Total AIWaterdrops consumed

### /mood
Read orchestrator's mood (stored in mood.json).

---

Architecture
------------

The orchestrator:
- Maintains a central registry (`agents.json`)
- Reads and validates agent manifests dynamically
- Aligns each agent's declared capabilities and dependencies with system-level needs
- Uses a unified `manifest_template.json` to ensure conformity and interoperability

---

Usage
-----

To start the orchestrator:

Via Docker Compose:
    docker compose up --build

Or inside the orchestrator folder:
    docker build -t clearcoreai-orchestrator .
    docker run -p 8000:8000 clearcoreai-orchestrator

---

Roadmap
-------

See ROADMAP.md for future features and versioning milestones.

---

License
-------

Licensed under MIT License.

---

Let's orchestrate AI agents transparently and responsibly.  
— ClearCoreAI Team
