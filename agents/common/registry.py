"""Agent Registry for Agora v4.0.

Provides a Firestore-backed registry for discovering A2A agents dynamically.
"""

import os
import structlog
from typing import Any, List, Optional
from agents.common.a2a import AgentCard

logger = structlog.get_logger(__name__)

class AgentRegistry:
    """Firestore-backed Agent Registry."""

    def __init__(self):
        self.project_id = os.environ.get("GCP_PROJECT", "gen-lang-client-0625573011")
        self._db = None
        try:
            from google.cloud import firestore
            self._db = firestore.AsyncClient(project=self.project_id)
        except Exception as e:
            logger.warning("firestore_registry_init_failed", error=str(e))
            self._db = None

    async def register_agent(self, card: AgentCard) -> None:
        """Register an agent's A2A card in Firestore."""
        if not self._db:
            logger.warning("firestore_registry_offline", action="register_agent", agent=card.name)
            return

        try:
            doc_ref = self._db.collection("agora_agents").document(card.name)
            await doc_ref.set(card.model_dump())
            logger.info("agent_registered", agent=card.name, url=card.url)
        except Exception as e:
            logger.error("agent_registration_failed", agent=card.name, error=str(e))
            raise

    async def get_agent(self, name: str) -> Optional[AgentCard]:
        """Discover an agent's URL and capabilities by name."""
        if not self._db:
            logger.warning("firestore_registry_offline", action="get_agent", agent=name)
            return None

        try:
            doc = await self._db.collection("agora_agents").document(name).get()
            if doc.exists:
                return AgentCard(**doc.to_dict())
            return None
        except Exception as e:
            logger.error("agent_lookup_failed", agent=name, error=str(e))
            return None

    async def list_agents(self) -> List[AgentCard]:
        """List all registered agents."""
        if not self._db:
            logger.warning("firestore_registry_offline", action="list_agents")
            return []

        try:
            agents = []
            docs = self._db.collection("agora_agents").stream()
            async for doc in docs:
                agents.append(AgentCard(**doc.to_dict()))
            return agents
        except Exception as e:
            logger.error("agent_list_failed", error=str(e))
            return []
