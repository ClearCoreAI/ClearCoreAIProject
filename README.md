# ClearCoreAI Core Orchestrator

**Version:** 0.3.0  
**Last Updated:** 2025-06-18  
**Validated by:** Olivier Hays  

---

## Overview

The ClearCoreAI orchestrator acts as the central controller of the agent ecosystem.  
It manages agent registration, capability discovery, compatibility analysis, plan generation, and multi-agent execution.

- agent registration and manifest validation  
- dynamic compatibility checks between agents  
- natural language goal → execution plan (via Mistral LLM)  
- traceable execution of multi-step plans  
- internal memory and persistent agent registry  

---

## Endpoints

### `GET /health`
Returns basic orchestrator status and list of registered agents.  
Water cost: free

---

### `POST /register_agent`
Registers a new agent by validating its `/manifest`.  
Water cost: 0.2 waterdrops

---

### `GET /agents`
Returns all registered agents and their declared capabilities.  
Water cost: 0.05 waterdrops

---

### `GET /agent_manifest/{agent_name}`
Returns the full manifest for a specific agent.  
Useful for debugging or capability checks.

---

### `GET /agents/connections`
Analyzes I/O compatibility between agents.  
Water cost: free (uses internal manifests)

---

### `GET /agents/metrics`
Fetches live `/metrics` data from each agent.  
Useful for centralized monitoring.

---

### `GET /agents/raw`
Returns all raw manifests currently stored.  
Water cost: free

---

### `POST /plan`
Generates a step-by-step execution plan from a user goal.  
Internally uses the Mistral LLM API.  
Water cost: 3 waterdrops

---

### `POST /execute_plan`
Executes a provided plan string across agents sequentially.  
Returns full trace of execution with context forwarding.

---

### `POST /run_goal`
Generates a plan and executes it in one shot.  
Water cost: 3 waterdrops

---

## File Structure

- `main.py` → orchestrator API server  
- `agents.json` → persistent memory of registered agents  
- `manifest_template.json` → schema used for manifest validation  
- `license_keys.json` → contains API keys (e.g. for Mistral)  

---

## Usage

Run the orchestrator locally:

```bash
uvicorn main:app --reload
```

Or with Docker:

```bash
docker build -t clearcore_orchestrator .
docker run -p 8000:8000 clearcore_orchestrator
```

---

## License

Licensed under the MIT License.

---

Clear orchestration. Auditable agents. Transparent AI.  
ClearCoreAI Team