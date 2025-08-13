"""
Module: llm_utils
Component: Orchestrator Tool
Purpose: AI Planning Utility via Mistral API (LLM-first, schema-validated)

Description:
Converts a high-level user goal into an executable plan by leveraging the Mistral LLM.
The function injects a machine-readable catalog of *actual* registered agents/capabilities
and enforces a strict output format. The returned plan is then validated against
the live registry and (if needed) repaired automatically using the declared I/O
specs (input_spec/output_spec) from agent manifests.

Philosophy:
- Rely on the LLM for creative planning, but never trust blindly.
- Validate every step against the registry: agent names, capability names, and I/O compatibility.
- Prefer general, schema-driven reasoning (no keyword dictionaries or agent-specific hacks).
- Return a minimal, executable plan or a clear error if impossible.

Initial State:
- license_keys.json is present and contains a valid Mistral API key
- The orchestrator has at least one registered agent (agents_registry non-vide)
- Each agent’s manifest declares its capabilities and (idéalement) input_spec / output_spec

Final State:
- A syntactically valid plan string is returned (e.g. "1. agent → capability\n2. ...")
- The plan only uses real (agent, capability) pairs from the registry
- The plan passes I/O-compatibility checks or is auto-réparé (fallback) si possible

Version: 0.4.0
Validated by: Olivier Hays
Date: 2025-08-11

Estimated Water Cost:
- 1 waterdrop per planning request (fixed)
"""

# ----------- Imports ----------- #
from __future__ import annotations
import json
import re
from typing import Dict, List, Tuple, Any

import requests


def _is_goal_feasible_with_catalog(goal: str, catalog: Dict[str, Any], license_keys: Dict[str, str]) -> bool:
    """
    Assesses whether the user's goal can reasonably be satisfied with the current catalog
    of agents/capabilities by asking the LLM for a strict JSON verdict.

    Parameters:
        goal (str): User objective in natural language
        catalog (dict): Machine-readable description of registered agents/capabilities
        license_keys (dict): Secrets containing at least the 'mistral' API key

    Returns:
        bool: True if feasible, False if not

    Initial State:
        - 'goal' is a non-empty string
        - 'catalog' was built by _collect_catalog()
        - license_keys['mistral'] is a valid API key

    Final State:
        - Returns a boolean feasibility verdict. No plan is generated here.

    Raises:
        Exception: On API errors or malformed LLM responses

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
        # Be tolerant to minor formatting, but require a JSON object with a 'feasible' boolean.
        verdict = json.loads(content)
        return bool(verdict.get("feasible", False))
    except Exception as e:
        # On any parsing or API error, be conservative: declare not feasible.
        # The caller will surface a clear "no executable steps" error.
        return False


# ----------- Helpers (Internal) ----------- #
def _collect_catalog(agents_registry: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Builds a machine-readable catalog of agents, their capabilities, and I/O specs.
    Backward-compatible: keeps the old 'capabilities' (list of names) and
    adds 'capability_meta' (per-capability short metadata).
    """
    if not agents_registry:
        raise ValueError("No agents registered. Cannot generate meaningful plan.")

    catalog = {"agents": {}}

    for name, data in agents_registry.items():
        manifest = (data.get("manifest") or {})
        raw_caps = manifest.get("capabilities", [])

        # 1) Preserve the previous behavior: a flat list of names
        cap_names: List[str] = []
        # 2) Add a non-blocking meta index
        cap_meta: Dict[str, Dict[str, Any]] = {}

        for c in raw_caps:
            if isinstance(c, dict):
                cname = c.get("name")
                if cname:
                    cap_names.append(cname)
                    # Expose a small subset useful to the LLM (without heavy specs)
                    cap_meta[cname] = {
                        "description": c.get("description"),
                        # if a handler is declared (e.g., audit_trace), mark it
                        "custom_input_handler": c.get("custom_input_handler")
                    }
            elif isinstance(c, str):
                # Manifests that list simple strings
                cap_names.append(c)
                # No meta to expose here, so nothing in cap_meta
            # other types -> silently ignore to remain tolerant

        catalog["agents"][name] = {
            # ⬇️ BACKWARD‑COMPAT — unchanged
            "capabilities": cap_names,
            # ⬇️ NEW — optional, not used by existing code
            "capability_meta": cap_meta,
            # ⬇️ unchanged
            "input_spec": manifest.get("input_spec"),
            "output_spec": manifest.get("output_spec"),
        }

    return catalog


def _are_specs_compatible(out_spec: Dict[str, Any] | None,
                          in_spec: Dict[str, Any] | None) -> bool:
    """
    Validates I/O compatibility between two JSON-schema-like specs (very conservative).

    Parameters:
        out_spec (dict|None): Producer's output_spec
        in_spec (dict|None): Consumer's input_spec

    Returns:
        bool: True if compatible (same top-level "type"), False otherwise or if missing

    Initial State:
        - Specs may be missing or partial

    Final State:
        - A boolean compatibility verdict is returned

    Raises:
        None

    Water Cost:
        - 0 (internal)
    """
    if not out_spec or not in_spec:
        return False
    return out_spec.get("type") == in_spec.get("type")


def _parse_llm_plan(text: str) -> List[Tuple[str, str]]:
    """
    Parses LLM text into a list of (agent, capability) steps.

    Parameters:
        text (str): Raw LLM output

    Returns:
        list[tuple[str, str]]: Ordered steps as (agent, capability)

    Initial State:
        - text is a string from the LLM

    Final State:
        - Steps are extracted with a strict regex

    Raises:
        None (returns empty list on failure)

    Water Cost:
        - 0 (internal)
    """
    steps: List[Tuple[str, str]] = []
    # Accept both "→" and "->" just in case
    pattern = re.compile(
        r"^\s*\d+\.\s*([A-Za-z0-9_\-]+)\s*(?:→|->)\s*([A-Za-z0-9_\-]+)\s*$"
    )
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            steps.append((m.group(1), m.group(2)))
    return steps


def _validate_and_repair_plan(steps: List[Tuple[str, str]],
                              catalog: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Validates (agent, capability) steps and repairs the plan using I/O specs if possible.

    Parameters:
        steps (list[tuple[str, str]]): LLM-proposed plan
        catalog (dict): Output of _collect_catalog

    Returns:
        list[tuple[str, str]]: A final, executable step list

    Initial State:
        - steps may contain unknown agents/caps or be I/O incompatible

    Final State:
        - Non-existent pairs are removed
        - If the chain is broken, we try to re-link compatible agents using specs
        - If everything breaks, returns an empty list

    Raises:
        None

    Water Cost:
        - 0 (internal)
    """
    agents = catalog["agents"]

    # 1) Keep only real (agent, capability)
    cleaned: List[Tuple[str, str]] = []
    for agent, cap in steps:
        if agent in agents and cap in agents[agent]["capabilities"]:
            cleaned.append((agent, cap))

    if not cleaned:
        return []

    # 2) If no specs available anywhere, accept as-is
    have_specs = any(a.get("input_spec") or a.get("output_spec") for a in agents.values())
    if not have_specs:
        # Ensure a single terminal audit step if available and not already present
        audit_cap = _find_audit_capability(catalog)
        if audit_cap and audit_cap not in cleaned:
            cleaned.append(audit_cap)
        return cleaned

    # 3) Try to ensure adjacency compatibility based on output_spec -> input_spec
    # We assume each agent has a *single* global output_spec/input_spec in manifest.
    repaired: List[Tuple[str, str]] = []
    prev_out_spec = None
    for idx, (agent, cap) in enumerate(cleaned):
        curr_in = agents[agent].get("input_spec")
        curr_out = agents[agent].get("output_spec")
        if idx == 0:
            # First step: no input constraint, accept it
            repaired.append((agent, cap))
            prev_out_spec = curr_out
            continue

        # For the rest: check compatibility from previous agent's out -> current agent's in
        if _are_specs_compatible(prev_out_spec, curr_in):
            repaired.append((agent, cap))
            prev_out_spec = curr_out
        else:
            # Try to find any other agent that *is* compatible (soft repair)
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
                # Drop incompatible step
                continue

    # Ensure a single terminal audit step if available and not already present
    audit_cap = _find_audit_capability(catalog)
    if audit_cap and audit_cap not in repaired:
        repaired.append(audit_cap)
    return repaired


def _find_audit_capability(catalog: Dict[str, Any]) -> Tuple[str, str] | None:
    """
    Searches the catalog for a generic *audit* capability that should run at the end of the plan.

    Heuristics (generic, not agent-specific):
    - Capability name equals 'audit_trace' (common convention), OR
    - The capability metadata includes a key 'custom_input_handler' with value 'use_execution_trace', OR
    - Capability name contains the substring 'audit' (case-insensitive) as a fallback.

    Parameters:
        catalog (dict): Output of _collect_catalog()

    Returns:
        tuple[str, str] | None: (agent_name, capability_name) if found, else None

    Water Cost:
        - 0 (internal)
    """
    agents = catalog.get("agents", {})
    for agent_name, meta in agents.items():
        caps = meta.get("capabilities", []) or []
        cap_meta = meta.get("capability_meta", {}) or {}
        # 1) Exact match common name
        if "audit_trace" in caps:
            return (agent_name, "audit_trace")
        # 2) Look for custom_input_handler marker
        for cname, cmeta in cap_meta.items():
            if (isinstance(cmeta, dict) and cmeta.get("custom_input_handler") == "use_execution_trace"):
                return (agent_name, cname)
        # 3) Soft fallback: any capability whose name contains 'audit'
        for cname in caps:
            if isinstance(cname, str) and "audit" in cname.lower():
                return (agent_name, cname)
    return None


# ----------- Core Function ----------- #
def generate_plan_with_mistral(goal: str,
                               agents_registry: Dict[str, Dict[str, Any]],
                               license_keys: Dict[str, str]) -> Tuple[str, int]:
    """
    Generates an execution plan from a natural language goal using the Mistral LLM,
    then validates and repairs the plan using live agent manifests (schema-first).

    Parameters:
        goal (str): Natural language objective provided by the user
        agents_registry (dict): Orchestrator registry with agents and their manifests
        license_keys (dict): Secrets containing at least the 'mistral' API key

    Returns:
        tuple[str, int]: (plan_text, water_cost). plan_text is multiline:
                         "1. agent → capability\n2. agent → capability\n..."

    Initial State:
        - 'goal' is a non-empty string
        - 'agents_registry' contains at least one registered agent
        - license_keys["mistral"] holds a valid API key

    Final State:
        - A syntactically valid plan string is returned
        - The plan only uses real (agent, capability) pairs
        - If possible, steps are I/O compatible thanks to schema-based repair

    Raises:
        ValueError: If inputs are malformed or registry is empty
        Exception: On Mistral API failures or unexpected response shapes

    Water Cost:
        - 1 waterdrop per planning (fixed)
    """
    if not goal or not isinstance(goal, str):
        raise ValueError("Goal must be a non-empty string.")

    catalog = _collect_catalog(agents_registry)

    # -------- Feasibility Gate (LLM) --------
    feasible = _is_goal_feasible_with_catalog(goal, catalog, license_keys)
    if not feasible:
        # No valid path with current agents; surface a clear error to the caller.
        raise Exception("No executable steps found for the current registry.")

    # Build a compact JSON catalog to inject into the prompt (keeps it generic)
    catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))

    system_prompt = f"""
    You are a planning assistant for an AI orchestration system.

    Your job is twofold:
    1) Determine if the goal can be achieved using ONLY the agents and capabilities in the provided catalog (JSON below).
    2) If feasible, produce a minimal, valid execution plan in the required numbered format.

    If the goal is NOT feasible with the given catalog, output exactly:
    1. noop → noop

    Catalog (JSON):
    {catalog_json}

    VERY IMPORTANT RULES:
    - Use ONLY agent names and capability names present in the catalog.
    - Prefer minimal plans that are likely executable based on I/O compatibility between steps.
    - Output each step EXACTLY like this (one per line):
      1. agent_name → capability_name
      2. agent_name → capability_name
      3. agent_name → capability_name
    - Do not add commentary, justifications, or any extra text before or after the steps.
    - If the catalog includes any *quality audit* capability (e.g., capability name == 'audit_trace',
      or metadata.custom_input_handler == 'use_execution_trace', or name contains 'audit'),
      you MUST include exactly ONE audit step as the FINAL step of the plan.
    - Ensure no duplicate audit steps appear.
    """

    payload = {
        "model": "mistral-small",
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": f"Goal: {goal}\nReturn only the numbered steps."}
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

    # Parse + validate + repair
    steps = _parse_llm_plan(raw)

    # Filter out explicit noop if LLM gave up
    if steps == [("noop", "noop")]:
        steps = []

    steps = _validate_and_repair_plan(steps, catalog)


    if not steps:
        # Surface a clear error so the orchestrator can react (e.g., tell the user it's impossible)
        raise Exception("No executable steps found for the current registry.")

    # Serialize back to the expected textual format
    plan_lines = [f"{i+1}. {a} → {c}" for i, (a, c) in enumerate(steps)]
    plan_text = "\n".join(plan_lines)

    # Fixed cost for planning
    return plan_text, 1