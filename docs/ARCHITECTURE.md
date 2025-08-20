# ClearCoreAI – Architecture Overview

**Version:** 0.3.1  
**Last Updated:** 2025-08-20  
**Author:** Olivier Hays  

---

## 1. Philosophy

ClearCoreAI is a modular, transparent AI agent ecosystem where each agent:

- **Declares its capabilities** via a `manifest.json`  
- **Registers dynamically** to a central orchestrator  
- **Exchanges data** strictly according to declared I/O specs  
- **Tracks resource usage** via **AIWaterdrops** accounting  
- Can be **composed dynamically** from natural language goals  
- Provides optional **audit policies** (`audit_policy.json`) to guide trace audits

---

## 2. High-Level Components

### 🧠 Orchestrator (`main.py`)

- Central hub for agent registration, validation, planning, and execution  
- Exposes key routes:
  - `/register_agent`, `/agents`, `/agents/connections`, `/agents/raw`, `/agents/metrics`  
  - `/plan`, `/execute_plan`, `/run_goal`, `/water/total`  
- Uses **Mistral** (via `tools/llm_utils.py`) to generate execution plans from user goals  
- Validates plans: only registered agents/capabilities are allowed; if no match → **NO-PLAN**  

---

### 🔌 Agents (FastAPI microservices)

Each agent:  

- Exposes `/manifest` (+ optional `/capabilities`)  
- Declares `capabilities` and I/O schema  
- Implements `/execute` (or specific endpoints) for orchestrator calls  
- Tracks mood and water usage locally  
- May include **audit_policy.json** to define expected behaviors, constraints, or invariants for auditor checks

**Current agents:**

| Name                 | Capabilities                                                                 |
|----------------------|------------------------------------------------------------------------------|
| `fetch_articles`     | `fetch_static_articles`, `generate_article_collection`                        |
| `summarize_articles` | `structured_text_summarization`                                              |
| `auditor`            | `audit_trace` (LLM-powered); optional: `check_agent_outputs`, `validate_pipeline_consistency` |

---

## 3. Data Flow Example

**User goal:** “Fetch news, summarize them, and audit the pipeline.”  

### Plan generated
```
1. fetch_articles → fetch_static_articles
2. summarize_articles → structured_text_summarization
3. auditor → audit_trace
```

### Execution Flow
1. Orchestrator → `fetch_articles` → returns static articles  
2. Output → `summarize_articles` → returns summaries  
3. Orchestrator converts results into an **execution trace** → `auditor → audit_trace`  
4. Auditor checks the execution against **agent audit policies** (if present)  
5. Final output + audit feedback are returned to the client  

---

## 4. Manifest Contract

Each agent must provide a `manifest.json` with:  

- Metadata: `name`, `version`, `description`, `author`, `license`  
- Capabilities: array of objects with `name`, `description`, optional `input_spec`/`output_spec`  
- Optional: `custom_input_handler` (e.g., `use_execution_trace` for auditor)  
- Top-level `input_spec` / `output_spec` for single-capability agents  
- Operational metadata: `estimate_cost`, `mood_profile`, `memory_profile`, `tools_profile`  
- API model:  
  - `multi_capability_api` → common `/execute` dispatcher, or  
  - Capability-specific endpoints  
- **Audit Policy**: optional `audit_policy.json` defining rules the auditor can use (e.g., “summaries must include source attribution”)  

---

## 5. Waterdrop Accounting

Representative waterdrop costs:  

| Action                              | Cost (waterdrops) |
|-------------------------------------|-------------------|
| Agent registration                  | 0.2               |
| Execution planning (LLM)            | 1.0               |
| Fetch static articles               | 0.05              |
| Summarization (per article, LLM)    | ~2.0              |
| Auditor audit (per trace, LLM)      | ~2.0              |
| Dispatch overhead (`/execute`)      | 0.02              |

Totals can be queried via:  
- Orchestrator → `/water/total`  
- Agents → `/metrics`  

---

## 6. File Structure

```
.
├── main.py                        # Orchestrator
├── tools/
│   └── llm_utils.py               # LLM planning helper
├── agents/
│   ├── fetch_articles/
│   │   ├── app.py
│   │   ├── manifest.json
│   │   └── audit_policy.json
│   ├── summarize_articles/
│   │   ├── app.py
│   │   ├── manifest.json
│   │   └── audit_policy.json
│   └── auditor/
│       ├── app.py
│       ├── tools/llm_utils.py     # LLM audit helper
│       └── manifest.json
└── docs/
    ├── ARCHITECTURE.md
    ├── ROADMAP.md
    ├── CHANGELOG.md
    └── TEST_PLAN.md
```

---

## 7. Future Directions

- Stronger schema validation for inter-agent payloads  
- Graph-based orchestration for non-linear pipelines  
- Richer audit feedback (step-level scoring, anomaly tags)  
- Cost-aware planning (optimize water usage)  
- Pluggable planners/auditors (support multiple LLM providers)  
- **Deeper integration of audit policies**: automated enforcement of per-agent invariants
