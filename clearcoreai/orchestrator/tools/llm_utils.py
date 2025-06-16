"""
Module: llm_utils
Component: Orchestrator Tool
Purpose: AI Planning Utility via Mistral API

Description:
This utility module enables the ClearCoreAI orchestrator to convert
a high-level user goal into an executable plan by leveraging the
Mistral LLM API. It introspects the available agents and guides the
language model to generate a coherent sequence of actions.

Philosophy:
- Inputs must be validated early to ensure safety.
- Outputs must be simple, reliable, and traceable.
- The metaphor of 'waterdrops' is used to quantify energy/resource usage.
- The LLM must only use real agents known to the orchestrator.
- No speculative output or hallucinated agents are accepted.

Initial State:
- license_keys.json is present and contains a valid Mistral API key
- At least one agent is registered in the orchestrator with a valid manifest
- A user-defined goal is provided as a non-empty string

Final State:
- A deterministic and syntactically valid plan is returned as a string
- Only real agents and capabilities from the registry are used
- The plan can be parsed and executed step-by-step by the orchestrator

Version: 0.2.1
Validated by: Olivier Hays
Date: 2025-06-15

Estimated Water Cost:
- 1 waterdrop per planning request (fixed)
"""

import requests
import json
from pathlib import Path
from typing import Tuple

# --------- License Key Loading --------- #
LICENSE_PATH = Path("license_keys.json")
try:
    with open(LICENSE_PATH, "r") as f:
        license_keys = json.load(f)
except Exception as e:
    raise RuntimeError("Missing license_keys.json. Cannot call Mistral API.") from e


# --------- Core Function: Plan Generation --------- #
def generate_plan_with_mistral(goal: str, agents_registry: dict) -> Tuple[str, int]:
    """
    Generates a plan to achieve a user-defined goal using registered agents.

    Parameters:
        goal (str): A clear description of the user's objective.
        agents_registry (dict): Agent metadata including names and capabilities.

    Returns:
        tuple[str, int]: A step-by-step plan and its energy cost (in waterdrops).

    Initial State:
        - 'goal' is a non-empty string
        - 'agents_registry' is a non-empty dictionary of agents with valid manifests
        - A valid Mistral API key is loaded from license_keys.json

    Final State:
        - A deterministic plan is returned in textual form (e.g., "1. agent → capability")
        - The plan exclusively uses declared agents and capabilities
        - The plan is ready to be parsed and executed by the orchestrator
        - 1 waterdrop is consumed

    Raises:
        ValueError: If inputs are malformed or no agents are available.
        Exception: For API or unexpected errors.

    Water Cost:
        - Fixed cost of 1 waterdrop per planning.
    """
    # --------- Input Validation --------- #
    if not goal or not isinstance(goal, str):
        raise ValueError("Goal must be a non-empty string.")

    if not agents_registry:
        raise ValueError("No agents registered. Cannot generate meaningful plan.")

    # --------- Agent Capability Context --------- #
    agent_list = []
    for name, data in agents_registry.items():
        manifest = data.get("manifest", {})
        capabilities = manifest.get("capabilities", [])
        caps = [c["name"] if isinstance(c, dict) and "name" in c else str(c) for c in capabilities]
        agent_list.append(f"- {name}: {', '.join(caps)}")
    agent_description = "\n".join(agent_list)

    # --------- System Prompt Construction --------- #
    system_prompt = f"""
    You are a planning assistant for an AI orchestration system.
    Your task is to generate a **strictly step-by-step execution plan** to fulfill a user goal using ONLY the available agents listed below.

    🧠 Available agents:
    {agent_description}

    ⚠️ Very important:
    - Do NOT mention code.
    - Do NOT suggest using external tools.
    - Do NOT add explanations.
    - Your entire response must ONLY be the plan steps using the agent names and capabilities.
    - Refer to the agents by their **exact name** and their capabilities.

    🎯 Format:
    1. AgentName → capability_name
    2. AgentName → capability_name
    """

    # --------- Mistral API Call --------- #
    payload = {
        "model": "mistral-small",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Goal: {goal}\n\nRespond strictly in the format above."}
        ],
        "temperature": 0.5
    }

    headers = {
        "Authorization": f"Bearer {license_keys.get('mistral', '')}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        plan = result["choices"][0]["message"]["content"].strip()
        return plan, 1  # ~1 waterdrop used
    except requests.exceptions.RequestException as e:
        raise Exception(f"Mistral API request failed: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error during plan generation: {e}")

