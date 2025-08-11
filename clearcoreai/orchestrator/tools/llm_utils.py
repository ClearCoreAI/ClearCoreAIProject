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
- The orchestrator's waterdrop counter is incremented

Version: 0.3.0
Validated by: Olivier Hays
Date: 2025-06-20

Estimated Water Cost:
- 1 waterdrop per planning request (fixed)
"""

# ----------- Imports ----------- #
import requests
from typing import Tuple

# ----------- Core Function ----------- #
def generate_plan_with_mistral(goal: str, agents_registry: dict, license_keys: dict) -> Tuple[str, int]:
    """
    Summary:
        Generates an execution plan to fulfill a user-defined goal using registered agents,
        by calling the Mistral API and returning a structured plan.

    Parameters:
        goal (str): A clear description of the user's objective.
        agents_registry (dict): Agent metadata including names and capabilities.
        license_keys (dict): API credentials containing the Mistral key.

    Returns:
        Returns:
        tuple[str, int]: Either a numbered plan or a single line starting with
                         'UNSUPPORTED | <reason>'. Second item is waterdrops cost.

    Initial State:
        - 'goal' is a non-empty string
        - 'agents_registry' is a non-empty dictionary of agents with valid manifests
        - A valid Mistral API key is loaded from license_keys.json

    Final State:
        - A deterministic plan is returned in textual form (e.g., "1. agent → capability")
        - The plan exclusively uses declared agents and capabilities
        - The plan is ready to be parsed and executed by the orchestrator
        - 1 waterdrop is consumed and recorded

    Raises:
        ValueError — If inputs are malformed or no agents are available.
        Exception — For network or API-related failures.

    Water Cost:
        - Fixed cost of 1 waterdrop per planning.
    """
    # ----------- Input Validation ----------- #
    if not goal or not isinstance(goal, str):
        raise ValueError("Goal must be a non-empty string.")

    if not agents_registry:
        raise ValueError("No agents registered. Cannot generate meaningful plan.")

    # ----------- Agent Context Formatting ----------- #
    agent_list = []
    for name, data in agents_registry.items():
        manifest = data.get("manifest", {})
        capabilities = manifest.get("capabilities", [])
        caps = [c["name"] if isinstance(c, dict) and "name" in c else str(c) for c in capabilities]
        agent_list.append(f"- {name}: {', '.join(caps)}")
    agent_description = "\n".join(agent_list) if agent_list else "(no agents registered)"

    # ----------- Prompt Construction ----------- #
    system_prompt = f"""
    You are a planning assistant for an AI orchestration system.
    You must generate a plan using ONLY the available agents/capabilities listed.

    Available agents:
    {agent_description}

    Rules:
    - Use ONLY agents/capabilities listed above.
    - Exact syntax per step: "<agent> → <capability>".
    - One step per line, numbered: "1. ...", "2. ...", etc.
    - Do NOT add prose or comments around the plan.
    - If the goal CANNOT be satisfied strictly with the available capabilities,
      reply with EXACTLY ONE LINE in this format (no numbering):
      UNSUPPORTED | short reason in the user's language.
    """
    user_prompt = f"Goal: {goal}\nRespond either with a numbered plan OR 'UNSUPPORTED | reason'."

    # ----------- API Request ----------- #

    payload = {
        "model": "mistral-small",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }
    headers = {
        "Authorization": f"Bearer {license_keys.get('mistral', '')}",
        "Content-Type": "application/json"
    }

    headers = {
        "Authorization": f"Bearer {license_keys.get('mistral', '')}",
        "Content-Type": "application/json"
    }

    # ----------- Remote Call + Water Accounting ----------- #
    try:
        resp = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()

        # Allow explicit UNSUPPORTED signal from the LLM
        if content.upper().startswith("UNSUPPORTED"):
            # keep cost at 1 waterdrop for the planning call
            return content, 1

        return content, 1
    except requests.exceptions.RequestException as e:
        raise Exception(f"Mistral API request failed: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error during plan generation: {e}")