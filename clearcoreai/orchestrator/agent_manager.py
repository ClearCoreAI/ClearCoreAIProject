"""
Module: agent_manager.py
Class: AgentManager

Description:
Agent registry manager for ClearCoreAI orchestrator.

Version: 0.1.0
Initial State: Empty agent registry.
Final State: Agents can be registered and queried.

Exceptions handled:
- ValueError — if agent is already registered.

Validation:
- Validated by: Olivier Hays
- Date: 2025-06-11

Estimated Water Cost:
- 1 waterdrop per register() call
- 1 waterdrop per get_agents() call

"""

class AgentManager:
    def __init__(self):
        self.registered_agents = []

    def register(self, agent_name: str):
        """
        Register a new agent.
        """
        if agent_name in self.registered_agents:
            raise ValueError("Agent already registered.")
        self.registered_agents.append(agent_name)

    def get_agents(self):
        """
        Return the list of registered agents.
        """
        return self.registered_agents