"""
Travel Agent API - FastAPI application with Microsoft Agent Framework.
Production deployment for corporate travel assistant with agentic memory.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .services import create_services, ProductionMemoryService, TravelAgentService


# ==================== Models ====================

class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    user_id: Optional[str] = Field(None, description="User ID for personalization")


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    conversation_id: str
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    services: dict


# ==================== Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    services = await create_services()
    app.state.memory = services["memory"]
    app.state.agent = services["agent"]
    app.state.conversation = services["conversation"]
    
    yield
    
    # Shutdown
    pass


# ==================== Application ====================

app = FastAPI(
    title="Travel Agent API",
    description="Corporate travel assistant with agentic memory powered by Microsoft Agent Framework",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Endpoints ====================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Returns status of all memory services.
    """
    memory: ProductionMemoryService = app.state.memory
    health = await memory.health_check()
    
    return HealthResponse(
        status=health["status"],
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=health["services"]
    )


@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe."""
    memory: ProductionMemoryService = app.state.memory
    health = await memory.health_check()
    
    # Ready if at least the core system is working (Foundry)
    if health["services"].get("foundry") not in ["connected", "in-memory"]:
        raise HTTPException(503, "Not ready - LLM unavailable")
    
    return {"status": "ready"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the travel assistant.
    
    The agent uses multiple memory types:
    - Episodic: Past travel experiences
    - Semantic: User preferences and knowledge
    - Procedural: Company policies
    - Shared: Cross-session context
    """
    agent: TravelAgentService = app.state.agent
    conversation = app.state.conversation
    
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    try:
        # Add user message to history
        conversation.add_message(conversation_id, "user", request.message)
        
        # Get response from agent
        response = await agent.chat(request.message, request.user_id)
        
        # Add assistant response to history
        conversation.add_message(conversation_id, "assistant", response)
        
        return ChatResponse(
            response=response,
            conversation_id=conversation_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    except Exception as e:
        raise HTTPException(500, f"Chat error: {str(e)}")


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history."""
    conversation = app.state.conversation
    history = conversation.get_history(conversation_id)
    
    if not history:
        raise HTTPException(404, "Conversation not found")
    
    return {"conversation_id": conversation_id, "messages": history}


@app.delete("/api/conversations/{conversation_id}")
async def clear_conversation(conversation_id: str):
    """Clear conversation history."""
    conversation = app.state.conversation
    conversation.clear(conversation_id)
    return {"status": "cleared", "conversation_id": conversation_id}


@app.get("/api/metrics")
async def get_metrics():
    """Get memory system metrics."""
    memory: ProductionMemoryService = app.state.memory
    return memory.metrics.get_summary()


# ==================== Run ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
