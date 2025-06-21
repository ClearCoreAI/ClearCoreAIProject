# 🧪 ClearCoreAI Quickstart Guide (Local Testing)

This quickstart explains how to locally test the **ClearCoreAI Orchestrator** and two agents (`fetch_articles` and `summarize_articles`) using `curl` commands and realistic data.

---

## ✅ Prerequisites

- Docker and Docker Compose installed
- Working directory is the root of your ClearCoreAI project

### Required files before launch:

```
license_keys.json
└── {
      "mistral": "sk-..."
    }

memory/short_term/aiwaterdrops.json (for each agent and orchestrator)
└── {
      "aiwaterdrops_consumed": 0.0
    }

memory/articles/static/sample1.txt
└── "Cats dominate global headlines."

memory/articles/static/sample2.txt
└── "Dogs protest unfair representation in media."
```

---

## 🚀 Launch the stack

```bash
docker compose up --build
```

Wait until all three services are up, and optionally preload your `.txt` files into `input_examples/` before launching:
- `orchestrator` → :8000
- `fetch_articles` → :8500
- `summarize_articles` → :8600

---

## 🧩 Register the agents

```bash
curl -X POST http://localhost:8000/register_agent \
  -H "Content-Type: application/json" \
  -d '{
    "name": "fetch_articles",
    "base_url": "http://fetch_articles_agent:8500"
}' | jq

curl -X POST http://localhost:8000/register_agent \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summarize_articles",
    "base_url": "http://summarize_articles:8600"
}' | jq
```

Expected: confirmation message and 0.2 waterdrop consumed per registration.

---

## 🧠 Generate a plan

```bash
curl -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{"goal": "fetch articles and summarize them"}' | jq
```

Expected output: numbered steps like:
```json
{
  "goal": "fetch articles and summarize them",
  "plan": "1. fetch_articles → fetch_static_articles\n2. summarize_articles → structured_text_summarization"
}
```

---

## ▶️ Run a plan

```bash
curl -X POST http://localhost:8000/execute_plan \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "1. fetch_articles → fetch_static_articles\n2. summarize_articles → structured_text_summarization"
}' | jq
```

Expected: full trace of steps with inputs/outputs and final context.

---

## ⚡ One-shot execution with `run_goal`

```bash
curl -X POST http://localhost:8000/run_goal \
  -H "Content-Type: application/json" \
  -d '{"goal": "fetch articles and summarize them"}' | jq
```

This performs planning and execution in one request. Very useful for demos!

---

## 📊 Check agent water usage

```bash
curl http://localhost:8000/agents/metrics | jq
```

Expected fields:
```json
{
  "fetch_articles": {
    "aiwaterdrops_consumed": 0.58,
    ...
  },
  "summarize_articles": {
    "aiwaterdrops_consumed": 0.6,
    ...
  }
}
```

---

## 📂 Preload sample articles from `input_examples`

By default, the agent `fetch_articles` will copy `.txt` files from `input_examples/` to `memory/long_term/` during container startup via the `entrypoint.sh` script.

You can add more articles to the `input_examples/` folder before launching, and they will be automatically included in the pipeline.

```bash
ls agents/fetch_articles/input_examples/
# Example output:
# 001_healthcare_ai.txt
# 003_spacex_mission.txt
```

After launch, you should see the same files under:

```bash
ls agents/fetch_articles/memory/long_term/
```

If they appear there, the `fetch_static_articles` step will use them in its output.

---

## 💧 Check total water consumption

```bash
curl http://localhost:8000/water/total | jq
```

Expected:
```json
{
  "breakdown": {
    "orchestrator": 6.0,
    "fetch_articles": 0.58,
    "summarize_articles": 0.6
  },
  "total_waterdrops": 7.18
}
```

---

## 🧹 Clean shutdown

```bash
docker compose down
```

---

For further testing or debugging, use:
```bash
curl http://localhost:8000/health | jq
curl http://localhost:8000/agents | jq
curl http://localhost:8000/agents/connections | jq
```