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
