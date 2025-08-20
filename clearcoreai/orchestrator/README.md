# ClearCoreAI Orchestrator

The **ClearCoreAI Orchestrator** is the central API that coordinates ClearCoreAI agents.  
It handles agent registration, manifest validation, LLM-based planning (Mistral API), and step-by-step workflow execution.

---

## Features

- Register agents and validate their manifests
- Discover capabilities dynamically
- Generate execution plans from natural language goals
- Execute multi-step workflows across agents
- Monitor waterdrop usage across the system

---

## Quickstart

### Requirements
- Python 3.10+
- FastAPI, Requests, jsonschema
- `license_keys.json` with a valid Mistral API key

### Install
```bash
git clone git@github.com:ClearCoreAI/ClearCoreAIProject.git
cd ClearCoreAIProject/orchestrator
pip install -r requirements.txt
```

### Run
```bash
uvicorn main:app --reload --port 8000
```

---

## API Reference

- `GET /health` → Orchestrator status  
- `POST /register_agent` → Register a new agent  
- `GET /agents` → List registered agents  
- `POST /plan` → Generate plan from a goal  
- `POST /execute_plan` → Execute a plan string  
- `POST /run_goal` → One-shot goal → plan → execution  
