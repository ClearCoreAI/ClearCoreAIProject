# Changelog

All notable changes to this project will be documented in this file.  
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2025-06-13

**Initial Manifest Ready release 🚀**

### Added

- Initial orchestrator architecture (FastAPI app)
    - `/health` endpoint
    - `/agents` registry
    - `/register_agent` endpoint
    - `/agents/metrics` endpoint
    - AIWaterdrops basic tracking
    - License manager (orchestrator only)
    - Agent manager (mood, metrics, scoring)

- Initial example agent: `fetch_articles`
    - `agent_manifest.json` with mandatory fields
    - `license_keys.json.template`
    - `mood.json`
    - Memory folders: `short_term`, `long_term`
    - `/health` endpoint
    - `/metrics` endpoint
    - `/get_articles` example endpoint
    - Auto-registration to orchestrator

- Shared memory schema
    - `schema/neo4j_schema.cypher`
    - `schema/sample_data.cypher`

- Initial project documentation
    - `README.md` with project philosophy and architecture
    - `CONTRIBUTING.md` with mandatory code commenting style and commit conventions
    - `LICENSE` (MIT)

- `.gitignore` optimized for Python + PyCharm + VSCode + ClearCoreAI-specific folders

---

## Upcoming

- Advanced orchestrator dashboard
- Web UI for agent management
- Advanced AIWaterdrops calculation and visualisation
- Additional example agents
- Shared memory integration (Neo4j live API)
- Agent orchestration scenarios