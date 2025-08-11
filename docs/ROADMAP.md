# ClearCoreAI Orchestrator – Roadmap

**Current Version:** 0.3.0  
**Maintainer:** Olivier Hays  
**Last Updated:** 2025-08-11

---

## ✅ Completed Milestones

- Agent registration and manifest validation
- Capability discovery via `/capabilities`
- Planning via LLM (Mistral)
- NO-PLAN detection for unsupported goals
- LLM-powered agent auditing (Auditor agent with Mistral integration)
- Sequential execution across agents
- Context propagation between steps
- Waterdrop-based energy accounting
- Mood and metric tracking
- Agent introspection and orchestration readiness
- FastAPI-based modular orchestrator

---

## 🧭 Upcoming Features

### 🔍 Reduce Hallucinations
- Constraint-based planning using schemas and hard type-checking
- LLM guardrails and manifest-only reasoning (also apply to auditor outputs)
- Add validation layers pre- and post-agent calls

### 📚 Automated Documentation
- Auto-generate `README.md` and inline docstrings from manifests and code
- CLI tool: `ccai docgen`
- Support multilingual comments

### 🧪 Agent Auditor
- Dedicated agent to verify execution outputs from other agents
- Auditor now uses LLM-based deep analysis; future work will expand heuristics and advanced consistency checks
- Compares declared vs. observed behaviors
- Provides audit trails and exception scoring

### 🔀 Non-Linear Pipelines (Graph Execution)
- Support for DAG-style agent workflows
- Visual editor for agent graphs
- Intelligent routing based on capabilities and data types

### 📈 Performance Tracing
- End-to-end latency and cost reporting
- Per-agent and per-capability stats
- Audit scoring metrics
- Optional logging to external tools (e.g., Prometheus, OpenTelemetry)

### 🔐 Encrypted Inter-Agent Communication
- Encrypt data payloads exchanged between agents
- Support both symmetric and asymmetric encryption
- Configurable per agent or per pipeline

### 💧 Improved AIWaterdrops Calculation
- Refine granularity of waterdrop estimation per capability
- Track cumulative and peak consumption per agent and per session
- Introduce configurable cost models (e.g., based on payload size, latency, or token usage)
- Include audit and planning costs
- Expose detailed consumption via /metrics and optional billing module

### 🌐 Agent Visualization UI
- Web dashboard showing:
  - Active agents
  - Live executions
  - Graph-based pipeline view
  - Mood, metrics, and waterdrop usage

### 🧠 Autonomous Agent Generation
- High-level goal → agent scaffold
- Auto-generate manifest, endpoints, stubs
- Use LLMs and context-aware templates

---

## 📌 Notes

- All features will respect the ClearCoreAI design principles:
  - Transparency
  - Auditable behaviors
  - Declarative orchestration
  - Modular, agent-based architecture

---

# 🛠 Help us build the future of explainable orchestration  
ClearCoreAI Team
