# Setting Up Redis for Shared Memory

This guide covers setting up Redis for the shared memory module.

## Option 1: Azure Cache for Redis (Recommended for Production)

### Create the Service

```bash
# Set variables
RESOURCE_GROUP="rg-agentic-memory"
REDIS_NAME="redis-travel-memory"
LOCATION="eastus"

# Create resource group (if not exists)
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION

# Create Azure Cache for Redis
az redis create \
    --name $REDIS_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Basic \
    --vm-size c0 \
    --enable-non-ssl-port

# Get connection string
az redis show \
    --name $REDIS_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "hostName" -o tsv

az redis list-keys \
    --name $REDIS_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "primaryKey" -o tsv
```

### Configure Environment

```bash
# Add to .env
REDIS_URL=rediss://:<your-key>@<your-redis>.redis.cache.windows.net:6380
```

## Option 2: Local Redis (Development)

### Using Docker

```bash
# Run Redis container
docker run -d \
    --name redis-memory \
    -p 6379:6379 \
    redis:7-alpine

# Verify
docker exec redis-memory redis-cli ping
# Response: PONG
```

### Configure Environment

```bash
# Add to .env
REDIS_URL=redis://localhost:6379
```

## Python Dependencies

```bash
pip install redis
```

## Test Connection

```python
import asyncio
import redis.asyncio as redis

async def test_connection():
    client = redis.from_url("redis://localhost:6379")
    pong = await client.ping()
    print(f"Ping: {pong}")
    await client.close()

asyncio.run(test_connection())
```

## Next Steps

Return to the [notebook](../07_shared_memory.ipynb).
