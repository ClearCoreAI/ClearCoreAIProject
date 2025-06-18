# ClearCoreAI Orchestrator – Test Plan

**Version:** 0.3.0  
**Last Updated:** 2025-06-18  
**Validated by:** Olivier Hays  

---

## 🧪 Objectives

- Ensure reliability of agent registration and validation
- Verify compatibility detection between agents
- Confirm correct execution of multi-step plans
- Monitor robustness against invalid input and offline agents
- Validate API stability and consistent waterdrop tracking
- Ensure structured outputs and cost estimates align with agent specs

---

## 🔁 Test Scenarios

### ✅ Agent Registration

**Endpoint:** `POST /register_agent`  
- [ ] Valid manifest registers correctly  
- [ ] Invalid manifest is rejected  
- [ ] Offline agent triggers connection error  
- [ ] Duplicate agent names overwrite or raise conflict  

---

### ✅ Capability Discovery

**Endpoint:** `GET /agents`, `GET /agent_manifest/{agent_name}`  
- [ ] Registered agent exposes correct capabilities  
- [ ] Manifest matches agent's declared capabilities  
- [ ] Raw manifests are correctly served via `/agents/raw`  
- [ ] 404 is returned for unknown agent name  

---

### ✅ Plan Generation

**Endpoint:** `POST /plan`  
- [ ] Valid goal returns non-empty plan  
- [ ] Invalid goal or empty agent list returns error  
- [ ] LLM output follows strict step-by-step format  
- [ ] Only registered agents and capabilities appear  
- [ ] Water cost is recorded as 3 waterdrops  

---

### ✅ Plan Execution

**Endpoint:** `POST /execute_plan`  
- [ ] All agents in plan are reachable  
- [ ] Unknown agents trigger structured error  
- [ ] Execution trace includes all steps and outputs  
- [ ] Final output is returned and conforms to `output_spec`  
- [ ] Per-agent `waterdrops_used` values match manifest cost  

---

### ✅ Combined Execution

**Endpoint:** `POST /run_goal`  
- [ ] Generates and executes plan in one shot  
- [ ] Waterdrop cost and full trace are returned  
- [ ] Output includes summaries and optional structured summaries  
- [ ] Error trace is returned if any step fails  

---

### ✅ Health and Monitoring

**Endpoint:** `GET /health`, `GET /metrics`  
- [ ] Returns orchestrator status and agent list  
- [ ] Metrics from agents are correctly aggregated  
- [ ] Handles slow or non-responsive agents gracefully  

---

## ⚠️ Edge Cases

- [ ] Manifest file missing or corrupted  
- [ ] Agent changes capabilities after registration  
- [ ] Agent manifest lacks required input/output spec  
- [ ] LLM returns malformed plan  
- [ ] Agent returns invalid JSON or fails mid-plan  
- [ ] Circular dependencies in future DAGs (non-linear plans)  

---

## 🧾 Reporting

- All test results should be logged in `tests/results/`  
- Failures must include HTTP code, error message, and offending input  
- Include waterdrop accounting per test to detect leaks  
- Validate per-agent runtime behavior against declared manifest  

---

## ✅ Coverage Target

Minimum 90% for:

- Agent lifecycle  
- API responses  
- Error handling  
- Plan consistency  
- Compliance with manifest specs  

---

# 🔬 Let’s ensure the orchestrator is as reliable as it is transparent.  
ClearCoreAI QA Team
