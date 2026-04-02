# Setting Up Neo4j for Semantic Memory

## Option 1: Neo4j AuraDB (Recommended)

### Step 1: Create Free Account

1. Go to https://neo4j.com/cloud/aura/
2. Sign up for free tier (AuraDB Free)

### Step 2: Create Instance

Click **Create Instance** and fill in the details:

| Field | Value |
|-------|-------|
| **Instance name** | `semantic-memory` |
| **Neo4j version** | `2026.02.2` (or latest) |
| **Database user** | `neo4j` |
| **Password** | Choose a password (min 8 characters) |

Click **Create**. This also creates a database automatically.

### Step 3: Download Credentials

After creation, you'll be prompted to **download a credentials file** (`.txt`). Do this immediately — the connection URI and password are shown only once.

The file contains:
- **NEO4J_URI**: `neo4j+s://xxxxxx.databases.neo4j.io`
- **NEO4J_USERNAME**: `neo4j`
- **NEO4J_PASSWORD**: your password
- **AURA_INSTANCENAME**: `semantic-memory`

### Step 4: Update .env

Open the downloaded credentials file and copy the values into your `.env`:

```env
NEO4J_URI=neo4j+s://xxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-from-credentials-file
```

## Option 2: Neo4j Desktop (Local Download)

### Step 1: Download Neo4j

1. Go to https://neo4j.com/download/
2. Download **Neo4j Desktop** for your OS
3. Install and launch

### Step 2: Create a Local Instance

1. In the left sidebar under **Data services**, click **Local instances**
2. Click **Create Instance**
3. Fill in the instance details (instance name, Neo4j version, database user, password)
4. Click **Create** — the instance starts automatically

### Step 3: Update .env

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

## Option 3: Local Docker (Development)

### Step 1: Run Neo4j Container

```bash
docker run -d \
  --name neo4j-memory \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:5
```

### Step 2: Update .env

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

## Troubleshooting

### "Unable to connect"
- Check URI format (`neo4j+s://` for Aura, `bolt://` for local/Docker)
- Verify network connectivity and firewall rules
- For local/Docker, ensure the instance is running

### "Authentication failed"
- Verify username and password (case-sensitive for Aura)
