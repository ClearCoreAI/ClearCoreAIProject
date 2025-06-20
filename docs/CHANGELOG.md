# Changelog

All notable changes to this project will be documented in this file.  
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.1] – 2025-06-20

**Total waterdrop aggregation, LLM orchestration fixes, and improved developer onboarding**

### Added

- New route `/water/total` in the orchestrator to compute total waterdrop usage across all agents and the orchestrator.
- New `QUICKSTART.txt` to guide testing via `curl`, with example `.txt` articles.
- Support for `/run_goal` endpoint, combining plan generation and execution in one step.
- Automatic file creation logic for `license_keys.json` and `aiwaterdrops.json`.

### Fixed

- Agents now use `get_aiwaterdrops()` instead of `load_aiwaterdrops()` to properly track consumption.
- `summarize_articles` and `fetch_articles` now consistently report and persist water usage.
- LLM system prompt updated to avoid generating hallucinated agent names or capabilities.

### Documentation

- Updated all agent and orchestrator `README.md` files:
  - clarified required folders and files (`memory/`, `license_keys.json`)
  - added endpoint usage examples
  - listed accurate waterdrop costs
- Enhanced clarity on how to run manual tests with expected JSON outputs.

---

## [0.2.0] - 2025-06-18

**Expanded agent capabilities and improved orchestration logic**

### Added

- New capability `structured_output_generation` to `summarize_articles`
- New capability `generate_article_collection` to `fetch_articles`
- Support for multi-capability handling in `/execute` endpoint of both agents
- Full compatibility check between agents via `input_spec` and `output_spec`
- Enhanced traceability in `/execute_plan` with improved execution logging
- Natural language goal-to-plan generation via Mistral LLM API
- New route `/run_goal` to automate planning + execution

### Changed

- Orchestrator now uses `/manifest` instead of `/capabilities` for agent validation
- Updated `manifest_template.json` schema accordingly
- Refined error handling during agent registration and execution

### Documentation

- Updated `README.md` for `fetch_articles`, `summarize_articles`, and the orchestrator with all current capabilities, usage, and endpoints
- Reorganized explanations for better developer onboarding

---

## [0.1.0] - 2025-06-13

**Initial Manifest Ready release**

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

👉 For upcoming features and roadmap, see `docs/ROADMAP.md`.