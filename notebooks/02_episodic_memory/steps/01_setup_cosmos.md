# Setting Up Azure Cosmos DB

The notebook creates the database and containers automatically — you just need the account and RBAC.

## Prerequisites

- Azure subscription
- Azure CLI installed (`az --version`)
- Logged in to Azure (`az login`)

## Step 1: Create Resource Group (if needed)

```bash
az group create \
  --name rg-agentic-memory \
  --location eastus
```

## Step 2: Create Cosmos DB Account

Choose a globally unique name (e.g. append your initials or a random suffix):

```bash
az cosmosdb create \
  --name <your-unique-name> \
  --resource-group rg-agentic-memory \
  --default-consistency-level Session \
  --enable-free-tier true
```

This takes 5-10 minutes to provision.

> **Note**: The notebook creates the `travel-memory` database and all containers programmatically. You don't need to create them manually.

## Step 3: Get Connection Details

```bash
az cosmosdb show \
  --name <your-unique-name> \
  --resource-group rg-agentic-memory \
  --query documentEndpoint \
  --output tsv
```

## Step 4: Assign Data Plane RBAC

The notebook uses `AzureCliCredential` and creates databases/containers programmatically. This requires a custom RBAC role with full data plane permissions (the built-in "Data Contributor" role only covers item read/write, not database or container creation).

### Create the custom role

```bash
az cosmosdb sql role definition create \
  --account-name <your-unique-name> \
  --resource-group rg-agentic-memory \
  --body '{
    "RoleName": "Cosmos DB Full Access",
    "Type": "CustomRole",
    "AssignableScopes": ["/"],
    "Permissions": [{
      "DataActions": [
        "Microsoft.DocumentDB/databaseAccounts/readMetadata",
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*",
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*",
        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/*"
      ]
    }]
  }'
```

Note the `id` (GUID) from the output — you'll need it in the next command.

### Assign the role to your identity

```bash
USER_ID=$(az ad signed-in-user show --query id -o tsv)

az cosmosdb sql role assignment create \
  --account-name <your-unique-name> \
  --resource-group rg-agentic-memory \
  --principal-id $USER_ID \
  --role-definition-id "<role-definition-id-from-above>" \
  --scope "/"
```

> **PowerShell users**: Replace `$(...)` with variable assignment syntax, e.g. `$USER_ID = az ad signed-in-user show --query id -o tsv`.

## Step 5: Update .env File

Add to your `.env`:

```env
COSMOS_ENDPOINT=https://<your-unique-name>.documents.azure.com:443/
```

## Troubleshooting

### "Resource Not Found"
- Verify the endpoint URL matches your account name
- The notebook creates the database/containers — run the setup cells first

### "Forbidden" (403)
- The built-in "Cosmos DB Built-in Data Contributor" role is not sufficient — it doesn't cover database/container creation. Make sure you created and assigned the custom role from Step 4.
- Ensure you're logged in with the same identity: `az account show`
