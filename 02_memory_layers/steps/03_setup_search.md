# Setting Up Azure AI Search for Procedural Memory

This guide creates the Azure AI Search resource needed for skill/policy indexing in procedural memory.

## 1. Create the Azure AI Search Resource

```bash
# Set variables
RESOURCE_GROUP="rg-agentic-memory"
SEARCH_NAME="search-agentic-memory-$(openssl rand -hex 4)"
LOCATION="eastus2"

# Create resource group (skip if you already have one)
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure AI Search (free tier)
az search service create \
  --name $SEARCH_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku free
```

## 2. Get the Endpoint and Admin Key

```bash
# Get the endpoint
SEARCH_ENDPOINT="https://${SEARCH_NAME}.search.windows.net"
echo "SEARCH_ENDPOINT=$SEARCH_ENDPOINT"

# Get the admin key
SEARCH_KEY=$(az search admin-key show \
  --service-name $SEARCH_NAME \
  --resource-group $RESOURCE_GROUP \
  --query primaryKey -o tsv)
echo "SEARCH_KEY=$SEARCH_KEY"
```

## 3. Update Your `.env`

Add these values to your `.env` file:

```
SEARCH_ENDPOINT=https://your-search.search.windows.net
SEARCH_KEY=your-admin-key
```

## 4. Verify

```bash
# Quick check — should return 200
curl -s -o /dev/null -w "%{http_code}" \
  "$SEARCH_ENDPOINT/indexes?api-version=2024-07-01" \
  -H "api-key: $SEARCH_KEY"
```

## Notes

- **Free tier** allows 1 replica, 3 indexes, 50 MB storage — sufficient for this tutorial.
- The index itself will be created programmatically in the notebook (no manual setup needed).
- Azure AI Search is used here to index travel policies and skill documents for retrieval during procedural memory lookups.
