"""
Configuration settings for production deployment.
Uses Microsoft Agent Framework with AzureAIClient.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # Azure AI Foundry (Microsoft Agent Framework)
    FOUNDRY_PROJECT_ENDPOINT: str
    FOUNDRY_MODEL_DEPLOYMENT_NAME: str = "gpt-4o"
    
    # Cosmos DB (Episodic Memory)
    COSMOS_ENDPOINT: Optional[str] = None
    COSMOS_DATABASE: str = "travel-memory"
    COSMOS_CONTAINER: str = "episodic"
    
    # Neo4j (Semantic Memory)
    NEO4J_URI: Optional[str] = None
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: Optional[str] = None
    
    # Azure AI Search (Procedural Memory)
    AZURE_SEARCH_ENDPOINT: Optional[str] = None
    AZURE_SEARCH_INDEX: str = "travel-policies"
    
    # Redis (Shared Memory)
    REDIS_URL: Optional[str] = None
    
    # Application Insights
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional[str] = None
    
    # API Settings
    CORS_ORIGINS: list[str] = ["*"]
    DEBUG: bool = False
    
    # Memory settings
    DEFAULT_MEMORY_TTL: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
