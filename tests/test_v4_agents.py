import pytest
import asyncio
from agents.hilbert.agent import HilbertAgent
from agents.einstein.agent import EinsteinAgent
from agents.common.registry import AgentRegistry
from agents.common.a2a import AgentCard, A2AClient
from alexandrie.hub import AlexandrieHub

@pytest.mark.asyncio
async def test_t9_hilbert_core():
    agent = HilbertAgent()
    assert agent.config.name == "hilbert"
    
@pytest.mark.asyncio
async def test_t10_einstein_core():
    agent = EinsteinAgent()
    assert agent.config.name == "einstein"

def test_t8_alexandrie_hub_mock():
    hub = AlexandrieHub()
    assert hub is not None

@pytest.mark.asyncio
async def test_t4_agent_card_registry():
    registry = AgentRegistry()
    card = AgentCard(
        name="hilbert",
        description="Formal Mathematician",
        url="https://mock-url.run.app"
    )
    assert card.name == "hilbert"

def test_t15_pubsub_fallback():
    client = A2AClient("https://mock")
    assert hasattr(client, "delegate_task_pubsub")
