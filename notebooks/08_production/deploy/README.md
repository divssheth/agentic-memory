# Deployment Guide

This guide walks through deploying the Travel Agent to Azure.

## Prerequisites

- Azure subscription
- Azure CLI installed (`az`)
- Azure Developer CLI installed (`azd`)
- Docker installed

## Quick Deploy with azd

The fastest way to deploy is using Azure Developer CLI:

```bash
# Login to Azure
azd auth login

# Initialize (first time only)
azd init

# Deploy everything
azd up
```

This will:
1. Create all Azure resources (Bicep)
2. Build and push Docker image
3. Deploy to Container Apps
4. Configure all environment variables

## Manual Deployment

If you prefer manual deployment:

### Step 1: Create Resource Group

```bash
az group create --name rg-travel-agent --location eastus
```

### Step 2: Deploy Infrastructure

```bash
az deployment group create \
    --resource-group rg-travel-agent \
    --template-file deploy/main.bicep \
    --parameters environment=dev
```

### Step 3: Build and Push Docker Image

```bash
# Get ACR login server from deployment output
ACR_LOGIN_SERVER=$(az deployment group show \
    --resource-group rg-travel-agent \
    --name main \
    --query properties.outputs.ACR_LOGIN_SERVER.value -o tsv)

# Login to ACR
az acr login --name ${ACR_LOGIN_SERVER%%.*}

# Build and push
docker build -t ${ACR_LOGIN_SERVER}/travel-agent:latest .
docker push ${ACR_LOGIN_SERVER}/travel-agent:latest
```

### Step 4: Create Azure AI Search Index

```python
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SearchField
)
from azure.core.credentials import AzureKeyCredential

endpoint = "https://your-search.search.windows.net"
key = "your-admin-key"

client = SearchIndexClient(endpoint, AzureKeyCredential(key))

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SimpleField(name="memory_type", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="employee_id", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="destination", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="date", type=SearchFieldDataType.String),
    SimpleField(name="rating", type=SearchFieldDataType.Int32),
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=1536,
        vector_search_profile_name="my-profile"
    )
]

vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(name="my-hnsw")
    ],
    profiles=[
        VectorSearchProfile(
            name="my-profile",
            algorithm_configuration_name="my-hnsw"
        )
    ]
)

index = SearchIndex(
    name="travel-memories",
    fields=fields,
    vector_search=vector_search
)

client.create_or_update_index(index)
print("Index created!")
```

## Verify Deployment

### Check Container App Status

```bash
az containerapp show \
    --name ca-travelagent* \
    --resource-group rg-travel-agent \
    --query properties.runningStatus
```

### Get Application URL

```bash
az containerapp show \
    --name ca-travelagent* \
    --resource-group rg-travel-agent \
    --query properties.configuration.ingress.fqdn -o tsv
```

### Test Health Endpoint

```bash
APP_URL=$(az containerapp show ... --query properties.configuration.ingress.fqdn -o tsv)
curl https://${APP_URL}/health
```

## Environment Variables Reference

| Variable | Description | Source |
|----------|-------------|--------|
| `AZURE_AI_PROJECT_ENDPOINT` | Azure OpenAI endpoint | Bicep output |
| `COSMOS_ENDPOINT` | Cosmos DB endpoint | Bicep output |
| `COSMOS_DATABASE` | Database name | `travel-memory` |
| `COSMOS_CONTAINER` | Container name | `memories` |
| `AZURE_SEARCH_ENDPOINT` | Search service URL | Bicep output |
| `AZURE_SEARCH_ADMIN_KEY` | Search admin key | Secret |
| `AZURE_SEARCH_INDEX` | Index name | `travel-memories` |
| `REDIS_HOST` | Redis hostname | Bicep output |
| `REDIS_PORT` | Redis port | `6380` |
| `REDIS_PASSWORD` | Redis key | Secret |
| `REDIS_SSL` | Enable SSL | `true` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights | Secret |

## Troubleshooting

### Container fails to start

Check logs:
```bash
az containerapp logs show \
    --name ca-travelagent* \
    --resource-group rg-travel-agent \
    --follow
```

### Authentication errors

Verify managed identity roles:
```bash
az role assignment list \
    --assignee <managed-identity-principal-id> \
    --output table
```

### Cosmos DB connection issues

Test connection:
```python
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient

credential = DefaultAzureCredential()
client = CosmosClient(endpoint, credential=credential)
list(client.list_databases())
```

## Cost Optimization

For development/testing:

1. **Cosmos DB**: Use serverless (included in Bicep)
2. **Redis**: Basic C0 tier
3. **Container Apps**: Scale to zero when not in use
4. **AI Search**: Basic tier

For production:
- Consider reserved capacity
- Set up auto-scaling limits
- Use Azure Monitor alerts for cost tracking
