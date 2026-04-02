"""
Service layer for production travel agent.
Uses Microsoft Agent Framework with production memory system.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add parent for production_memory import
sys.path.insert(0, str(Path(__file__).parent.parent))

from production_memory import (
    MemoryConfig,
    MemorySystem,
    MemoryMetrics,
    PRODUCTION_AGENT_INSTRUCTIONS,
    create_production_system
)
from .config import settings


class ProductionMemoryService:
    """Production memory service wrapper for FastAPI."""
    
    _instance: Optional["ProductionMemoryService"] = None
    _memory_system: Optional[MemorySystem] = None
    _metrics: Optional[MemoryMetrics] = None
    
    @classmethod
    async def get_instance(cls) -> "ProductionMemoryService":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance.initialize()
        return cls._instance
    
    async def initialize(self):
        """Initialize the memory system."""
        config = MemoryConfig(
            foundry_endpoint=settings.FOUNDRY_PROJECT_ENDPOINT,
            model_deployment=settings.FOUNDRY_MODEL_DEPLOYMENT_NAME,
            cosmos_endpoint=settings.COSMOS_ENDPOINT,
            cosmos_database=settings.COSMOS_DATABASE,
            neo4j_uri=settings.NEO4J_URI,
            neo4j_username=settings.NEO4J_USERNAME,
            neo4j_password=settings.NEO4J_PASSWORD,
            search_endpoint=settings.AZURE_SEARCH_ENDPOINT,
            search_index=settings.AZURE_SEARCH_INDEX,
            redis_url=settings.REDIS_URL,
        )
        
        self._memory_system = MemorySystem(config)
        await self._memory_system.initialize()
        self._metrics = MemoryMetrics()
    
    @property
    def memory_system(self) -> MemorySystem:
        """Get the memory system."""
        if self._memory_system is None:
            raise RuntimeError("Memory service not initialized")
        return self._memory_system
    
    @property
    def metrics(self) -> MemoryMetrics:
        """Get the metrics collector."""
        if self._metrics is None:
            raise RuntimeError("Memory service not initialized")
        return self._metrics
    
    async def health_check(self) -> dict:
        """Run health check on all services."""
        return await self.memory_system.health_check()


class TravelAgentService:
    """Service for interacting with the travel agent."""
    
    def __init__(self, memory_service: ProductionMemoryService):
        self.memory_service = memory_service
    
    def create_agent(self, instructions: str = None):
        """Create a travel agent with memory tools."""
        return self.memory_service.memory_system.create_agent(
            name="ProductionTravelAssistant",
            instructions=instructions or PRODUCTION_AGENT_INSTRUCTIONS
        )
    
    async def chat(self, message: str, user_id: str = None) -> str:
        """Chat with the travel agent."""
        import time
        start_time = time.time()
        
        agent = self.create_agent()
        
        try:
            async with agent:
                stream = await agent.run(message, stream=True)
                response = await stream.get_final_response()
                
                # Track metrics
                latency = (time.time() - start_time) * 1000
                self.memory_service.metrics.record_call("chat", latency, True)
                
                return response
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.memory_service.metrics.record_call("chat", latency, False)
            raise


class ConversationService:
    """Service for managing conversation history."""
    
    def __init__(self, memory_service: ProductionMemoryService):
        self.memory_service = memory_service
        self.conversations: dict[str, list] = {}
    
    def add_message(self, conversation_id: str, role: str, content: str):
        """Add a message to conversation history."""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        self.conversations[conversation_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def get_history(self, conversation_id: str) -> list:
        """Get conversation history."""
        return self.conversations.get(conversation_id, [])
    
    def clear(self, conversation_id: str):
        """Clear conversation history."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]


# Factory function for creating services
async def create_services():
    """Create all production services."""
    memory_service = await ProductionMemoryService.get_instance()
    
    return {
        "memory": memory_service,
        "agent": TravelAgentService(memory_service),
        "conversation": ConversationService(memory_service),
    }
