# ClearCoreAI Core Orchestrator

Version: 0.3.1  
Last Updated: 2025-06-20  
Validated by: Olivier Hays  

---

## Overview

The ClearCoreAI orchestrator acts as the central controller of the agent ecosystem.  
It manages agent registration, capability discovery, compatibility analysis, plan generation, and multi-agent execution.

Features:

- Agent registration and manifest validation  
- Dynamic compatibility checks between agents  
- Natural language goal → execution plan (via Mistral LLM)  
- Traceable execution of multi-step plans  
- Internal memory and persistent agent registry  
- Waterdrop metering for energy transparency

---

## Endpoints

### GET /health  
Returns basic orchestrator status and list of registered agents.  
Water cost: free

### POST /register_agent  
Registers a new agent by validating its /manifest.  
Water cost: 0.2 waterdrops

### GET /agents  
Returns all registered agents and their declared capabilities.  
Water cost: 0.05 waterdrops

### GET /agent_manifest/{agent_name}  
Returns the full manifest for a specific agent.  
Useful for debugging or capability checks.  
Water cost: free

### GET /agents/connections  
Analyzes I/O compatibility between agents.  
Water cost: free (uses internal manifests)

### GET /agents/metrics  
Fetches live /metrics data from each agent.  
Useful for centralized monitoring.  
Water cost: free

### GET /agents/raw  
Returns all raw manifests currently stored.  
Water cost: free

### POST /plan  
Generates a step-by-step execution plan from a user goal.  
Internally uses the Mistral LLM API.  
Water cost: 3 waterdrops

### POST /execute_plan  
Executes a provided plan string across agents sequentially.  
Returns full trace of execution with context forwarding.  
Water cost: 0.02 base + dynamic per agent execution

### POST /run_goal  
Generates a plan and executes it in one shot.  
Water cost: ~3 waterdrops (same as /plan + /execute_plan)

### GET /water/total  
Returns the total waterdrop consumption across orchestrator and all registered agents.  
Breaks down usage per component.  
Water cost: free

---

## File Structure

- main.py → orchestrator API server  
- agents.json → persistent memory of registered agents  
- manifest_template.json → schema used for manifest validation  
- license_keys.json → contains API keys (e.g. for Mistral)  
- memory/short_term/aiwaterdrops.json → orchestrator water usage log

---

## Usage

Run the orchestrator locally:

    uvicorn main:app --reload

Or with Docker:

    docker build -t clearcore_orchestrator .
    docker run -p 8000:8000 clearcore_orchestrator

---

## License

Licensed under the MIT License.

---

Clear orchestration. Auditable agents. Transparent AI.  
ClearCoreAI Team