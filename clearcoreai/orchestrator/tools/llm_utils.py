"""
Module: llm_utils
Component: Orchestrator Tool
Purpose: AI Planning Utility via Mistral API (LLM-first, schema-validated)

Description:
This module transforms a user goal (natural language) into an executable plan based
on the *actually registered* agents. It sends the LLM (Mistral) a machine-readable
"catalog" of agents/capabilities, enforces a strict numbered format, then validates
and repairs the plan against the live registry (valid agent/capability pairs, I/O
compatibility via input_spec/output_spec).

How it works (end-to-end call flow):
1) Orchestrator calls → generate_plan_with_mistral(goal, agents_registry, license_keys)
   ├─ _collect_catalog(agents_registry)
   │    Builds a JSON catalog (agents, capabilities, metadata, specs).
   ├─ _is_goal_feasible_with_catalog(goal, catalog, license_keys)
   │    Asks the LLM for a strict JSON verdict {"feasible": true|false}.
   │    If false → raises error.
   ├─ Main LLM call (chat.completions) with catalog + numbered-steps instruction
   │    LLM returns text like "1. agent → capability".
   ├─ _parse_llm_plan(text)
   │    Extracts (agent, capability) pairs with regex.
   ├─ _validate_and_repair_plan(steps, catalog)
   │    a) Filters invalid pairs
   │    b) Repairs chain using output_spec -> input_spec
   │    c) Appends a final audit step if available (via _find_audit_capability)
   └─ Returns the final plan as "1. a → c\n2. ..." + water cost

Philosophy:
- Let the LLM do the creative reasoning, but never trust blindly.
- Validate all steps against the registry: agent names, capability names, and I/O compatibility.
- No agent-specific hacks: generic schema-driven reasoning only.
- Return a minimal executable plan, or a clear error if impossible.

Initial State:
- license_keys.json contains a valid Mistral API key
- The registry contains ≥1 agent (agents_registry not empty)
- Manifests declare capabilities and ideally input_spec/output_spec

Final State:
- A syntactically valid plan string is returned: "1. agent → capability\n2. ..."
- Plan uses real (agent, capability) pairs only
- Steps are I/O compatible if specs are provided
- A single final audit step is appended if detected

Version: 0.4.0
Validated by: Olivier Hays
Date: 2025-08-11

Estimated Water Cost:
- 1 waterdrop per planning request (fixed)

----------------------------------------------------------------------
Example (Python):

from tools.llm_utils import generate_plan_with_mistral

goal = "Fetch articles about AI and summarize them with a quality audit"
plan_text, water = generate_plan_with_mistral(goal, agents_registry, license_keys)
print(plan_text)

# Example output:
# 1. fetch_articles → fetch_static_articles
# 2. fetch_articles → generate_article_collection
# 3. summarize_articles → structured_text_summarization
# 4. auditor → audit_trace

----------------------------------------------------------------------
Example (curl) if exposed via an orchestrator endpoint:

curl -s -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{"goal":"Fetch articles about AI and summarize them with a quality audit"}'
----------------------------------------------------------------------
"""

from __future__ import annotations
import json
import re
from typing import Dict, List, Tuple, Any

import requests


def _is_goal_feasible_with_catalog(goal: str,
                                   catalog: Dict[str, Any],
                                   license_keys: Dict[str, str]) -> bool:
    """
    Ask the LLM for a strict feasibility verdict given the catalog.

    Parameters:
        goal (str): User’s natural language objective
        catalog (dict): Machine-readable description of agents/capabilities
        license_keys (dict): Secrets containing at least 'mistral' key

    Returns:
        bool: True if feasible with current catalog, else False

    Initial State:
        - 'goal' is a non-empty string
        - 'catalog' built via _collect_catalog
        - license_keys['mistral'] is valid

    Final State:
        - Returns True/False feasibility verdict only

    Raises:
        Exception: On API errors or malformed LLM output

    Water Cost:
        - ~0.3 waterdrops (counts toward planning budget)
    """
    catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))

    system = (
        "You are a strict feasibility checker for an AI orchestrator. "
        "Given a catalog of real agents/capabilities and a user goal, respond ONLY with JSON "
        'like {"feasible": true} or {"feasible": false}. '
        "Return false if none of the listed capabilities can directly progress the goal."
    )
    user = f"CATALOG_JSON={catalog_json}\nGOAL={goal}\nAnswer strictly with a one-line JSON."

    payload = {
        "model": "mistral-small",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.0
    }
    headers = {
        "Authorization": f"Bearer {license_keys.get('mistral', '')}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()
        verdict = json.loads(content)
        return bool(verdict.get("feasible", False))
    except Exception:
        return False


def _collect_catalog(agents_registry: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a machine-readable catalog of all agents, their capabilities, and I/O specs.
    Backward-compatible: preserves 'capabilities' (list) and adds 'capability_meta'.

    Parameters:
        agents_registry (dict): {agent_name: {base_url, manifest, ...}}

    Returns:
        dict: Catalog JSON:
            { "agents": {
                "<agent>": {
                  "capabilities": [str],
                  "capability_meta": { "<cap>": {"description": str, "custom_input_handler": str|None} },
                  "input_spec": dict|None,
                  "output_spec": dict|None
                } } }

    Raises:
        ValueError: If registry is empty

    Water Cost:
        - 0 (internal)
    """
    if not agents_registry:
        raise ValueError("No agents registered. Cannot generate meaningful plan.")

    catalog = {"agents": {}}

    for name, data in agents_registry.items():
        manifest = (data.get("manifest") or {})
        raw_caps = manifest.get("capabilities", [])

        cap_names: List[str] = []
        cap_meta: Dict[str, Dict[str, Any]] = {}

        for c in raw_caps:
            if isinstance(c, dict):
                cname = c.get("name")
                if cname:
                    cap_names.append(cname)
                    cap_meta[cname] = {
                        "description": c.get("description"),
                        "custom_input_handler": c.get("custom_input_handler")
                    }
            elif isinstance(c, str):
                cap_names.append(c)

        catalog["agents"][name] = {
            "capabilities": cap_names,
            "capability_meta": cap_meta,
            "input_spec": manifest.get("input_spec"),
            "output_spec": manifest.get("output_spec"),
        }

    return catalog


def _are_specs_compatible(out_spec: Dict[str, Any] | None,
                          in_spec: Dict[str, Any] | None) -> bool:
    """
    Check compatibility between output_spec and input_spec.

    Returns:
        bool: True if top-level 'type' matches, else False
    """
    if not out_spec or not in_spec:
        return False
    return out_spec.get("type") == in_spec.get("type")


def _parse_llm_plan(text: str) -> List[Tuple[str, str]]:
    """
    Parse LLM text into (agent, capability) pairs.

    Parameters:
        text (str): Raw LLM output ("N. agent → capability")

    Returns:
        list[tuple[str, str]]: Ordered steps
    """
    steps: List[Tuple[str, str]] = []
    pattern = re.compile(r"^\s*\d+\.\s*([A-Za-z0-9_\-]+)\s*(?:→|->)\s*([A-Za-z0-9_\-]+)\s*$")
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            steps.append((m.group(1), m.group(2)))
    return steps


def _validate_and_repair_plan(steps: List[Tuple[str, str]],
                              catalog: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Validate and repair (agent, capability) steps using the catalog.

    Logic:
    - Filter out non-existent pairs
    - Repair broken links with output_spec->input_spec
    - Append one final audit step if found

    Returns:
        list[tuple[str, str]]: Final executable steps
    """
    agents = catalog["agents"]

    cleaned: List[Tuple[str, str]] = []
    for agent, cap in steps:
        if agent in agents and cap in agents[agent]["capabilities"]:
            cleaned.append((agent, cap))
    if not cleaned:
        return []

    have_specs = any(a.get("input_spec") or a.get("output_spec") for a in agents.values())
    if not have_specs:
        audit_cap = _find_audit_capability(catalog)
        if audit_cap and audit_cap not in cleaned:
            cleaned.append(audit_cap)
        return cleaned

    repaired: List[Tuple[str, str]] = []
    prev_out_spec = None
    for idx, (agent, cap) in enumerate(cleaned):
        curr_in = agents[agent].get("input_spec")
        curr_out = agents[agent].get("output_spec")
        if idx == 0:
            repaired.append((agent, cap))
            prev_out_spec = curr_out
            continue

        if _are_specs_compatible(prev_out_spec, curr_in):
            repaired.append((agent, cap))
            prev_out_spec = curr_out
        else:
            found = False
            for alt_agent, meta in agents.items():
                if (alt_agent, cap) in repaired or alt_agent == agent:
                    continue
                if cap in meta["capabilities"] and _are_specs_compatible(prev_out_spec, meta.get("input_spec")):
                    repaired.append((alt_agent, cap))
                    prev_out_spec = meta.get("output_spec")
                    found = True
                    break
            if not found:
                continue

    audit_cap = _find_audit_capability(catalog)
    if audit_cap and audit_cap not in repaired:
        repaired.append(audit_cap)

    return repaired


def _find_audit_capability(catalog: Dict[str, Any]) -> Tuple[str, str] | None:
    """
    Look for a generic *audit* capability to run as the final step.

    Heuristics:
    - Capability == 'audit_trace'
    - OR metadata.custom_input_handler == 'use_execution_trace'
    - OR capability name contains 'audit'
    """
    agents = catalog.get("agents", {})
    for agent_name, meta in agents.items():
        caps = meta.get("capabilities", []) or []
        cap_meta = meta.get("capability_meta", {}) or {}

        if "audit_trace" in caps:
            return (agent_name, "audit_trace")

        for cname, cmeta in cap_meta.items():
            if isinstance(cmeta, dict) and cmeta.get("custom_input_handler") == "use_execution_trace":
                return (agent_name, cname)

        for cname in caps:
            if isinstance(cname, str) and "audit" in cname.lower():
                return (agent_name, cname)

    return None


def generate_plan_with_mistral(goal: str,
                               agents_registry: Dict[str, Dict[str, Any]],
                               license_keys: Dict[str, str]) -> Tuple[str, int]:
    """
    Generate an execution plan with Mistral, then validate/repair via live manifests.

    Parameters:
        goal (str): User objective in natural language
        agents_registry (dict): Orchestrator registry (agents + manifests)
        license_keys (dict): Secrets containing 'mistral' key

    Returns:
        (str, int): (plan_text, water_cost). plan_text is formatted:
                    "1. agent → capability\n2. ..."

    Raises:
        ValueError: If goal empty or registry empty
        Exception: If API fails or no executable steps found
    """
    if not goal or not isinstance(goal, str):
        raise ValueError("Goal must be a non-empty string.")

    catalog = _collect_catalog(agents_registry)

    feasible = _is_goal_feasible_with_catalog(goal, catalog, license_keys)
    if not feasible:
        raise Exception("No executable steps found for the current registry.")

    catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))

    system_prompt = f"""
    You are a planning assistant for an AI orchestration system.

    Rules:
    - Use ONLY agent and capability names present in the catalog.
    - Prefer minimal, I/O compatible plans.
    - Output ONLY numbered steps like:
      1. agent → capability
      2. agent → capability
    - If an *audit* capability is available, include it ONCE as the final step.
    """.strip()

    payload = {
        "model": "mistral-small",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Goal: {goal}\nReturn only the numbered steps.\nCatalog: {catalog_json}"}
        ],
        "temperature": 0.3
    }
    headers = {
        "Authorization": f"Bearer {license_keys.get('mistral', '')}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Mistral API request failed: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error during plan generation: {e}")

    steps = _parse_llm_plan(raw)

    if steps == [("noop", "noop")]:
        steps = []

    steps = _validate_and_repair_plan(steps, catalog)

    if not steps:
        raise Exception("No executable steps found for the current registry.")

    plan_lines = [f"{i+1}. {a} → {c}" for i, (a, c) in enumerate(steps)]
    plan_text = "\n".join(plan_lines)

    return plan_text, 1