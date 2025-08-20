# ClearCoreAI

**Version:** 0.4.0  
**Last Updated:** 2025-08-12  
**Author:** Olivier Hays  

---

## 🌌 Overview

**ClearCoreAI** is an experimental framework for building, orchestrating, and auditing modular AI agents.  
Think of it as a **brain for AI microservices**: each agent declares its capabilities, registers with the orchestrator, and can be composed dynamically to solve natural language goals.

Highlights:

- **Modular architecture** – plug in any agent as a standalone FastAPI microservice.  
- **Dynamic orchestration** – user goals are translated into execution plans via LLMs.  
- **Auditing built-in** – every pipeline can be verified for consistency with the **Auditor Agent**.  
- **Resource tracking** – all calls are accounted in **AIWaterdrops**, a simple resource currency.  
- **Transparency first** – manifests and policies make agent behavior explicit and auditable.  

ClearCoreAI is **research-driven**: an open lab where we experiment with LLM-based planning, auditing, and governance of AI workflows.  
We welcome contributors who want to **push the limits of AI orchestration**.  

---

## 🚀 QuickStart

### Requirements
- Python 3.10+
- Docker & Docker Compose (recommended)
- A Mistral API key (for orchestration planning & auditing)

### Setup

Clone the repo:
```bash
git clone https://github.com/ClearCoreAI/ClearCoreAIProject.git
cd ClearCoreAIProject
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Launch orchestrator + agents with Docker:
```bash
docker compose up --build
```

Or run locally:
```bash
uvicorn main:app --reload --port 8000
```

---

## 🧩 Current Agents

- **fetch_articles** → fetch static demo articles, normalize collections  
- **summarize_articles** → generate structured summaries via LLM  
- **auditor** → audit execution traces & verify consistency  

Each agent has its own `README.md` in `agents/<name>/`.

---

## 📊 Architecture

```
orchestrator (main.py)
   ├── fetch_articles → static/news input
   ├── summarize_articles → summarization
   └── auditor → audit & consistency checks
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full breakdown.  

---

## 🛠 Example Goal Execution

```
POST /run_goal
{
  "goal": "Fetch news, summarize them, then audit the pipeline"
}
```

Example execution plan:
```
1. fetch_articles → fetch_static_articles
2. summarize_articles → structured_text_summarization
3. auditor → audit_trace
```

The orchestrator will automatically chain these agents, run the pipeline, and return results + audit.

---

## 📑 Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) – High-level overview  
- [ROADMAP.md](docs/ROADMAP.md) – Future directions (graph-based orchestration, cost-aware planning, auto-generated agents)  
- [TEST_PLAN.md](docs/TEST_PLAN.md) – Validation and QA framework  

Each agent also ships with:
- `manifest.json` – declares capabilities & I/O specs  
- `audit_policy.json` – defines validation rules  

---

## 🤝 Contributing

We believe in **open experimentation**.  
Contributions are welcome whether you’re into:

- 🚀 Designing new agents  
- 📐 Improving manifest / schema contracts  
- 🔍 Building better audit policies  
- 🎨 Visualization & UI for orchestrator pipelines  
- 🧠 Research on LLM orchestration  

To get started:
1. Fork the repo  
2. Explore `agents/` and add your own agent  
3. Submit a PR with a new capability or improvement  

Check [CONTRIBUTING.md](docs/CONTRIBUTING.md) for full guidelines.  

---

## 📜 License

ClearCoreAI is open-source under the **MIT License**.  
See [LICENSE](LICENSE) for details.  

---

💡 *ClearCoreAI is not a finished product. It’s an ongoing experiment.  
If you’re excited about the future of AI orchestration, join us on this journey.*  
