# ClearCoreAI Agent: auditor

**Version:** 0.2.0  
**Last Updated:** 2025-08-20  
**Validated by:** Olivier Hays  

---

## Overview

`auditor` is a ClearCoreAI-compatible agent that performs audits on execution traces and agent outputs.  
Its purpose is to **verify consistency, correctness, and quality** of pipelines orchestrated by ClearCoreAI.

It features:

- audit of execution traces and outputs  
- anomaly and inconsistency detection  
- quality scoring of agent workflows  
- final audit report generation  
- orchestrator-compatible execution via `/execute`  
- automatic self-registration to the orchestrator at startup  

---

## Endpoints

### `GET /health`

Basic health check to verify that the agent is running.  
Water cost: 0

---

### `GET /capabilities`

Returns declared capabilities, as defined in `manifest.json`.  
Water cost: 0

---

### `GET /manifest`

Returns the full manifest.  
Useful for orchestrator registration and auditing.  
Water cost: 0

---

### `GET /metrics`

Returns runtime metrics **specific to this agent**:

- agent name and version  
- uptime in seconds  
- total waterdrops consumed  

Water cost: 0

---

### `POST /execute`

Main endpoint for orchestrator-controlled execution.  
Dispatches requests based on the requested `capability`.

Example payload:

```json
{
  "capability": "audit_trace",
  "input": {
    "steps": [
      {
        "agent": "fetch_articles",
        "capability": "fetch_static_articles",
        "input": {},
        "output": {"articles": [...]}
      },
      {
        "agent": "summarize_articles",
        "capability": "structured_output_generation",
        "input": {"articles": [...]},
        "output": {"summary": "..."}
      }
    ]
  }
}
```

Water cost: 0.05 waterdrops + 0.01 per step analyzed  

---

## Capabilities

### `audit_trace`

Analyzes a full execution trace (steps, inputs, outputs, errors).  

Produces a structured audit report such as:

```json
{
  "report": {
    "steps_analyzed": 5,
    "issues_found": 1,
    "quality_score": 0.82,
    "comments": ["Step 3 output inconsistent with declared schema."]
  }
}
```

---

### `verify_output_consistency`

Checks multiple runs of the same pipeline to detect inconsistencies.  

Returns:

```json
{
  "consistency": {
    "runs_compared": 3,
    "inconsistencies": 0,
    "verdict": "stable"
  }
}
```

---

### `generate_audit_report`

Aggregates findings from previous capabilities into a human-readable report.  

---

## Usage

### Docker Compose

```bash
docker compose up --build
```

### Manual Run

```bash
docker build -t auditor_agent .
docker run -p 8600:8600 auditor_agent
```

---

## Required Files

Before launching the agent, ensure the following files exist:

- `manifest.json`: capability declarations and metadata  
- `memory/short_term/aiwaterdrops.json`: created if missing  

To initialize memory:

```bash
mkdir -p memory/short_term
echo '{"aiwaterdrops_consumed": 0}' > memory/short_term/aiwaterdrops.json
```

---

## Self-Registration

The agent attempts to register itself to the orchestrator at startup via `/manifest`.  
If the orchestrator is not available, it logs the error but continues running.

---

## License

This project is licensed under the MIT License.
