# Setting Up Azure Cosmos DB for Persistent Memory

This guide creates the Cosmos DB account and permissions needed for session memory persistence.

## 1. Create the Cosmos DB Account

```bash
# Set variables
RESOURCE_GROUP="rg-agentic-memory"
COSMOS_ACCOUNT="cosmos-agentic-memory-$(openssl rand -hex 4)"
LOCATION="eastus2"

# Create resource group (skip if you already have one)
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Cosmos DB account (NoSQL API) with vector search enabled
az cosmosdb create \
  --name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --default-consistency-level Session \
  --locations regionName=$LOCATION failoverPriority=0 \
  --capabilities EnableNoSQLVectorSearch
```

> **Existing account?** If you already have a Cosmos DB account, enable vector search separately:
> ```bash
> az cosmosdb update \
>   --name $COSMOS_ACCOUNT \
>   --resource-group $RESOURCE_GROUP \
>   --capabilities EnableNoSQLVectorSearch
> ```
> Or in the **Azure Portal**: go to your Cosmos DB account → **Settings** → **Features** → find **Vector Search in Azure Cosmos DB for NoSQL** → click **Enable**. Takes ~1 minute to activate.

## 2. Get the Endpoint

```bash
COSMOS_ENDPOINT=$(az cosmosdb show \
  --name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query documentEndpoint -o tsv)

echo $COSMOS_ENDPOINT
```

Add this to your `.env` file:
```
COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
```

## 3. Configure RBAC (Required for Azure CLI Credential)

The built-in Cosmos DB roles don't cover data-plane operations needed for
container creation. Create a custom role with full data permissions:

```bash
# Get your user's object ID
USER_OID=$(az ad signed-in-user show --query id -o tsv)

# Get the Cosmos account ID
COSMOS_ID=$(az cosmosdb show \
  --name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

# Create a custom role with full data-plane access
az cosmosdb sql role definition create \
  --account-name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --body '{
    "RoleName": "Cosmos Data Contributor",
    "Type": "CustomRole",
    "AssignableScopes": ["/"],
    "Permissions": [{
      "DataActions": [
        "Microsoft.DocumentDB/databaseAccounts/readMetadata",
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*",
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*",
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/*"
      ]
    }]
  }'
```

```bash
# Get the role definition ID (from output of previous command)
ROLE_ID=$(az cosmosdb sql role definition list \
  --account-name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query "[?roleName=='Cosmos Data Contributor'].id" -o tsv)

# Assign the role to your user
az cosmosdb sql role assignment create \
  --account-name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --role-definition-id $ROLE_ID \
  --principal-id $USER_OID \
  --scope "/"
```

## 4. Create the Database

The notebooks create containers automatically, but the **database must exist first**. The `CosmosHistoryProvider` and `SemanticMemoryStore` both expect a database called `travel-memory`:

```bash
az cosmosdb sql database create \
  --account-name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --name travel-memory
```

## 5. Verify

```bash
# Role assignment should show your user
az cosmosdb sql role assignment list \
  --account-name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP
```

## What the Notebooks Create Automatically

The notebooks create these containers on first use (the database must already exist — see step 4):
- **Container**: `chat-history` (partition key: `/session_id`) — used by `CosmosHistoryProvider`
- **Container**: `episodic-events` (partition key: `/user_id`) — used by the episodic memory notebook
- **Container**: `semantic-memory` (partition key: `/user_id`, DiskANN vector index) — used by Modules 2–4 for preferences

You don't need to create the containers manually, but the database `travel-memory` must exist.

## Cost

Cosmos DB free tier includes 1000 RU/s and 25 GB — more than enough for
development and the exercises in this repo.
