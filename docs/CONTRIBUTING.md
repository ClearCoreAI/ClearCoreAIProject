
# Contributing to ClearCoreAI

First of all — thank you for considering contributing to **ClearCoreAI**! 🚀  
We welcome contributions of all kinds: code, documentation, tests, ideas, discussions.

This document explains how to contribute to the project and how to keep everything consistent and clean.

---

## 🚀 Philosophy

ClearCoreAI is built with the following core principles:

- **Modularity** → Each agent is an independent entity, easily composable.
- **Transparency** → AIWaterdrops tracking, mood/state, memory architecture are fully visible and documented.
- **Autonomy** → Each agent manages its own licenses and tools.
- **Traceability** → Outputs, metrics and resource usage are tracked and auditable.
- **Openness** → We want to encourage contributions from a wide community.

Please respect these principles when contributing. ✨

---

## 📚 Code commenting style — MANDATORY

To ensure **maximum transparency and traceability**, we use a strict code commenting style, inspired by scientific and critical systems engineering.

### 1️⃣ High-level function/class docstrings

Each function and class MUST have a complete docstring using this structure:

"""
Purpose:
    [Brief sentence explaining what this function/class does.]

Initial State:
    [State of the system before executing this function.]

Final State:
    [State of the system after executing this function.]

Inputs:
    param1 (type): description
    param2 (type): description
    ...

Outputs:
    return (type): description

Exceptions:
    - ExceptionType1: when condition1
    - ExceptionType2: when condition2

AIWaterdrops estimation:
    - Estimated Waterdrops per call: X.X
    - Estimated Waterdrops per second (for continuous processes): Y.Y

Version:
    - First implemented in version: x.y.z
    - Last validated in version: x.y.z
    - Validated by: Full Name or GitHub handle
"""

Example:

"""
Purpose:
    Register an agent in the orchestrator's registry.

Initial State:
    Agent is not in the registry.

Final State:
    Agent is added to the registry with its initial mood and metrics.

Inputs:
    agent_name (str): name of the agent to register.

Outputs:
    None

Exceptions:
    - ValueError: if agent_name is empty or invalid.

AIWaterdrops estimation:
    - Estimated Waterdrops per call: 0.05

Version:
    - First implemented in version: 0.1.0
    - Last validated in version: 0.1.0
    - Validated by: John Doe (@johndoe)
"""

### 2️⃣ Inline comments

Inline comments must follow these rules:

✅ One line → starts with #  
✅ Short and precise  
✅ Use full words and avoid abbreviations

Example:

\# Check if agent is already registered
if agent_name in self.registry:
    ...

### 3️⃣ Language

- Comments and docstrings MUST be written in **English**.
- Additional documentation and Manifest can be translated in other languages.

---

## 🚧 Project structure

- orchestrator/ → Main orchestrator (FastAPI), manages agents registry, AIWaterdrops, mood, metrics.
- agents/ → Independent agents (each in their own folder), self-registering to the orchestrator.
- schema/ → Shared memory (Neo4j) schema and samples.
- memory/, logs/, output/ → Are NOT versioned in Git — check .gitignore.

---

## 📚 Commit conventions

We use Conventional Commits — please follow this format for commit messages:

- feat: → New feature (e.g. feat: add /agents/metrics endpoint)
- fix: → Bug fix (e.g. fix: handle missing mood.json gracefully)
- docs: → Documentation only changes (e.g. docs: update README)
- chore: → Build process or auxiliary tool changes (no user impact)
- refactor: → Code changes that neither fixes a bug nor adds a feature
- test: → Adding or correcting tests

Examples:

feat: add initial AIWaterdrops tracking in agent_manager
fix: correct wrong mood state update in fetch_articles agent
docs: add architecture diagram in README

---

## 🚦 Guidelines

- Keep agents **autonomous** → licenses must not be centralized in the orchestrator.
- Do not commit real license_keys.json → only use the provided license_keys.json.template.
- Do not commit personal logs or memory files → they are excluded in .gitignore.
- When adding a new agent:
    - Include a proper agent_manifest.json.
    - Implement /health, /metrics, and at least one useful API endpoint.
    - Document your agent with a README.md.
    - Apply the **mandatory code commenting style** described above to ALL public functions/classes.



## 🗺 Future ideas and discussions

Feel free to open issues and start discussions!  
We welcome ideas about:

- AIWaterdrops evolution → making cost tracking more precise.
- Shared memory architecture → knowledge graph extensions.
- Advanced agent behaviors → more human-like state/mood management.
- Better orchestrator APIs → control, evaluation, reward systems.

---

## Thank you! 🙏

We are building ClearCoreAI as an **open and transparent AI ecosystem**.  
Your contributions help make it stronger and better — and more fun for everyone.

Let's make agents **think**, **trace**, and **collaborate** — the ClearCoreAI way. 🚀
