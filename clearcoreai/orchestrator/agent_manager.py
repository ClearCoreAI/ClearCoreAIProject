"""
Module: agent_manager.py
Class: AgentManager

Description:
Manages the registry of agents in the ClearCoreAI orchestrator.
Stores AgentInfo instances and provides methods to register and retrieve agents.

Version: 0.1.0
Initial State: Empty agent registry.
Final State: Agent registry populated during runtime.

Exceptions handled:
- ValueError — if agent is already registered.

Validation:
- Validated by: Olivier Hays
- Date: 2025-06-13

Estimated Water Cost:
- No direct endpoint, internal calls only.
"""

from models.agent_model import AgentInfo
from datetime import datetime
from typing import Dict

class AgentManager:
    def __init__(self):
        """
        Purpose:
            Initializes an empty agent registry.

        Initial State:
            Empty registry.

        Final State:
            Empty registry ready to accept agents.

        Exceptions handled:
            None

        Validation:
            Validated by: Olivier Hays
            Date: 2025-06-13

        Estimated Water Cost:
            None (initialization).
        """
        self.registry: Dict[str, AgentInfo] = {}

    def register(self, agent_name: str, version: str, url: str):
        """
        Purpose:
            Registers a new agent in the registry.

        Initial State:
            Agent not present in registry.

        Final State:
            Agent added to registry.

        Inputs:
            agent_name (str): Name of the agent.
            version (str): Version of the agent.
            url (str): Base URL of the agent.

        Outputs:
            None

        Exceptions handled:
            ValueError — if agent already registered.

        Validation:
            Validated by: Olivier Hays
            Date: 2025-06-13

        Estimated Water Cost:
            2 waterdrops per call.
        """
        if agent_name in self.registry:
            raise ValueError(f"Agent '{agent_name}' is already registered.")

        agent_info = AgentInfo(
            agent_name=agent_name,
            version=version,
            url=url,
            registered_at=datetime.utcnow(),
            aiwaterdrops_consumed=0.0,
            last_known_mood=None
        )

        self.registry[agent_name] = agent_info

    def get_all_agents(self) -> Dict[str, AgentInfo]:
        """
        Purpose:
            Returns the full agent registry.

        Initial State:
            Registry populated.

        Final State:
            No change.

        Inputs:
            None

        Outputs:
            Dict of agent_name → AgentInfo.

        Exceptions handled:
            None

        Validation:
            Validated by: Olivier Hays
            Date: 2025-06-13

        Estimated Water Cost:
            1 waterdrop per call.
        """
        return self.registry
