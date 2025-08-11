# ClearCoreAI – Architecture Overview

**Version:** 0.3.0  
**Last Updated:** 2025-06-18  
**Author:** Olivier Hays

---

## 1. Philosophy

ClearCoreAI is designed as a modular, transparent AI agent ecosystem where each agent:

- **Declares its capabilities** via a `manifest.json`
- **Registers dynamically** to a central orchestrator
- **Exchanges data** based on declared I/O specs
- **Tracks resource usage** via `AIWaterdrops` accounting
- Can be **composed dynamically** via natural language goals

---

## 2. High-Level Components

### 🧠 Orchestrator (`main.py`)

- Central coordination point
- Handles agent registration, validation, planning, and execution
- Exposes routes for:
  - `/register_agent`
  - `/plan`, `/execute_plan`, `/run_goal`
  - `/agents`, `/agents/connections`, `/metrics`, etc.
- Uses `mistral` LLM to generate execution plans from user goals

### 🔌 Agents

Each agent is a self-contained FastAPI service that:

- Exposes a `/manifest` endpoint
- Declares its `capabilities` and I/O schema
- Implements `/execute` for orchestration calls
- Tracks its internal mood and waterdrop consumption

Current agents:

| Name               | Capabilities                                   |
|--------------------|------------------------------------------------|
| `fetch_articles`   | `fetch_static_articles`, `generate_article_collection` |
| `summarize_articles` | `structured_text_summarization`             |

---

## 3. Data Flow Example

**User goal:** “Fetch news and summarize them”

### Plan generated:
```
1. fetch_articles → fetch_static_articles  
2. summarize_articles → structured_text_summarization
```

### Execution Flow:

1. Orchestrator dispatches to `fetch_articles` → returns static articles
2. Output is forwarded to `summarize_articles`
3. Structured summaries are returned to the user

---

## 4. Manifest Contract

Each agent must provide a `manifest.json` with:

- `name`, `description`, `version`
- `capabilities[]`
- `input_spec`, `output_spec`
- Optional: `license_required`, `mood_tracking`

---

## 5. Waterdrop Accounting

Each capability and endpoint has an estimated cost in **AIWaterdrops**:

| Action                          | Cost (waterdrops) |
|---------------------------------|-------------------|
| Agent registration              | 0.2               |
| Static article fetch            | 1                 |
| Summarization (per article)     | ~2                |
| Execution planning              | 3                 |
| Simple dispatch `/execute`      | 0.02              |

---

## 6. File Structure

```
.
├── main.py                 # Orchestrator
├── agents/
│   ├── fetch_articles/
│   └── summarize_articles/
├── docs/
│   ├── ROADMAP.md
│   ├── CHANGELOG.md
│   ├── TEST_PLAN.md
│   └── ...
└── README.md
```

---

## 7. Future Directions

For planned features and future improvements, refer to CONTRIBUTING.md > Future Directions.

# ClearCoreAI – Architecture Overview

**Version:** 0.3.1  
**Last Updated:** 2025-08-11  
**Author:** Olivier Hays

---

## 1. Philosophy

ClearCoreAI is a modular, transparent AI agent ecosystem where each agent:

- **Declares its capabilities** via a `manifest.json`
- **Registers dynamically** to a central orchestrator
- **Exchanges data** strictly according to declared I/O specs
- **Tracks resource usage** via **AIWaterdrops** accounting
- Can be **composed on-the-fly** from natural-language goals

---

## 2. High-Level Components

### 🧠 Orchestrator (`main.py`)

- Central coordinator for registration, validation, planning, and execution
- Exposes routes:
  - `/register_agent`, `/agents`, `/agents/connections`, `/agents/raw`, `/agents/metrics`
  - `/plan`, `/execute_plan`, `/run_goal`, `/water/total`
- Uses **Mistral** (via `tools/llm_utils.py`) to translate user goals into executable plans
- **Plan validation**: the LLM is constrained to use only registered agents/capabilities; if none match, it may return `NO-PLAN` and the orchestrator aborts gracefully

### 🔌 Agents (FastAPI microservices)

Each agent:

- Exposes a `/manifest` endpoint (and optional `/capabilities`)  
- Declares `capabilities` and I/O schema (top-level and/or per-capability)  
- Implements `/execute` (or a capability-specific endpoint) for orchestration  
- Tracks mood and water usage via local JSON files

Current agents:

| Name                 | Capabilities                                                                 |
|----------------------|------------------------------------------------------------------------------|
| `fetch_articles`     | `fetch_static_articles`, `generate_article_collection`                        |
| `summarize_articles` | `structured_text_summarization`                                              |
| `auditor`            | `audit_trace` (LLM-powered); optional: `check_agent_outputs`, `validate_pipeline_consistency` |

> The **auditor** now supports LLM-based trace evaluation and is invoked with a normalized execution trace.

---

## 3. Data Flow Example

**User goal:** “Fetch news and summarize them, then audit the pipeline”

### Plan generated
```
1. fetch_articles → fetch_static_articles
2. summarize_articles → structured_text_summarization
3. auditor → audit_trace
```

### Execution Flow

1. Orchestrator dispatches to `fetch_articles` → returns static articles
2. Output is forwarded to `summarize_articles` → returns summaries (via Mistral)
3. Orchestrator converts the step-by-step results into an **execution trace** and calls `auditor → audit_trace` (LLM-powered)  
4. Final output + audit are returned to the client

If the goal cannot be met with available capabilities, planning returns **NO-PLAN** and the API responds with a helpful error.

---

## 4. Manifest Contract

Each agent provides a `manifest.json` containing:

- `name`, `version`, `description`, `author`, `license`
- `capabilities`: array of capability objects:
  - `name`, `description`
  - optional: `input_spec`, `output_spec`
  - optional: `custom_input_handler` (e.g., `use_execution_trace`)
- Optional **top-level** `input_spec` / `output_spec` (for single-capability agents)
- Operational metadata: `estimate_cost`, `mood_profile`, `memory_profile`, `tools_profile`
- API declaration: either
  - `multi_capability_api` → common `/execute` dispatcher, **or**
  - capability-specific endpoints (e.g., auditor’s `/run` for `audit_trace`)

The orchestrator stores the full manifest and extracts a normalized capability map for routing.

---

## 5. Waterdrop Accounting

Representative costs (may vary by implementation):

| Action                              | Cost (waterdrops) |
|-------------------------------------|-------------------|
| Agent registration                  | 0.2               |
| **Execution planning (LLM)**        | 1.0               |
| Fetch static articles               | 0.05              |
| Summarization (per article, LLM)    | ~2.0              |
| Dispatch overhead per `/execute`    | 0.02              |
| Auditor LLM audit per `/run`        | ~2.0              |

Totals are exposed via `/water/total` (orchestrator) and `/metrics` (agents).

---

## 6. File Structure

```
.
├── main.py                        # Orchestrator API
├── tools/
│   └── llm_utils.py               # Mistral planning helper (orchestrator)
├── agents/
│   ├── fetch_articles/
│   │   ├── app.py
│   │   └── manifest.json
│   ├── summarize_articles/
│   │   ├── app.py
│   │   └── manifest.json
│   └── auditor/
│       ├── app.py
│       ├── tools/llm_utils.py     # LLM audit helper (auditor agent)
│       └── manifest.json
└── docs/
    ├── README.md
    ├── ARCHITECTURE.md
    ├── CHANGELOG.md
    └── ...
```

---

## 7. Future Directions

- Stronger schema contracts and typed inter-agent payloads
- Capability matchmaking based on `input_spec`/`output_spec` compatibility graphs
- Richer audit signals (e.g., reliability tags, constraints checks, step-local scores)
- Cost-aware planning (optimize waterdrops under constraints)
- Pluggable planners/auditors (support multiple LLM providers)