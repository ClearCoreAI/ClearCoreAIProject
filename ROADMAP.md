
# ClearCoreAI - ROADMAP

**Version:** 0.1.0  
**Last Updated:** 2025-06-13  
**Validated by:** Olivier Hays  

---

## Vision

ClearCoreAI aims to provide a **transparent, robust, modular, and auditable orchestration framework for AI agents**.  
The architecture enables AI agents to be deployed as isolated containers, monitored centrally, and fully traceable (AIWaterdrops tracking, mood, metrics).

---

## v0.1.0 - Initial Public Release

✅ Core orchestrator with:  
- /health  
- /register_agent  
- /agents  
- /agents/metrics  
- /metrics  
- /mood  

✅ Example agent `fetch_articles` with:  
- /health  
- /metrics  
- /mood  
- /get_articles  
- agent_manifest.json  
- mood.json  
- license_keys.json.template  
- AIWaterdrops tracking persisted

✅ Documentation:  
- README.md  
- TEST_PLAN.md  
- CONTRIBUTING.md  

---

## v0.2.0 - Next Iteration

🟡 Orchestrator:  
- [ ] Add `/unregister_agent` endpoint  
- [ ] Add `/update_agent` endpoint (update URL or version)  
- [ ] Add auto-mood calculation for orchestrator mood based on agents state  
- [ ] Add API key / token based security for orchestrator endpoints (optional for enterprise use)

🟡 Agents:  
- [ ] Add `/update_mood` endpoint to agents  
- [ ] Standardize `utils.py` for mood + license + manifest loading  
- [ ] Add example agent with LLM integration (OpenAI or Mistral API)  
- [ ] Add agent status file or database (optional)

🟡 DevOps:  
- [ ] Add CI/CD GitHub Actions basic pipeline (lint, test build)  
- [ ] Provide example production Docker Compose template  
- [ ] Publish first tagged release on GitHub

---

## v0.3.0 - Extended Ecosystem

🟢 Orchestrator:  
- [ ] Dashboard UI basic prototype (VueJS or React) to visualize agents / metrics / mood  
- [ ] Add `global_mood_rules.json` configurable per orchestrator  
- [ ] Multi-tenancy / multi-orchestrator support (design level)  

🟢 Agents:  
- [ ] Add example agent with image generation capabilities  
- [ ] Add example agent with RAG (Retrieval Augmented Generation) support  
- [ ] Provide agent template generator CLI (scaffold new agents)  

🟢 Community & Ecosystem:  
- [ ] Setup GitHub Discussions  
- [ ] Setup GitHub Pages mini site (docs, roadmap, architecture diagram)  
- [ ] Start collecting community-contributed agents  

---

## Longer-Term Ideas

- AI agents with internal memory / personality evolutions  
- Agent-to-agent secure messaging (zero-trust model)  
- AI agents capable of auditing themselves  
- Advanced AIWaterdrops metering (multi-dimension: CPU, GPU, memory, latency)  
- Publish to PyPI: `clearcoreai` framework helpers (orchestrator + agent utilities)  

---

## Summary

ClearCoreAI v0.1.0 sets the foundation for a modular and auditable AI agent orchestration system.  
This roadmap ensures a progressive, community-friendly, transparent evolution of the framework.

---

# 🚀 Let's build it together!  
ClearCoreAI Team
