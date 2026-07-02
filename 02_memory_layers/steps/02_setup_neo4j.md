# Setting Up Neo4j for Semantic Memory

## Neo4j AuraDB Free Tier (Recommended)

AuraDB Free gives you 50K nodes at zero cost — more than enough for
development and all exercises in this repo.

### Step 1: Create Account

1. Go to https://neo4j.com/cloud/aura-free/
2. Sign up with email or Google/GitHub
3. Verify your email

### Step 2: Create Instance

1. Click **New Instance** → **AuraDB Free**
2. Fill in:
   - **Instance name**: `semantic-memory`
   - **Region**: Choose closest to you
3. Click **Create**

### Step 3: Save Credentials

After creation, you'll see a one-time credentials screen:
- **Connection URI**: `neo4j+s://xxxxxx.databases.neo4j.io`
- **Username**: `neo4j`
- **Password**: (auto-generated)

**Save these immediately** — the password is shown only once.

### Step 4: Update .env

Add to your `.env` file:

```env
NEO4J_URI=neo4j+s://xxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-from-step-3
```

### Step 5: Verify

The notebook connects automatically on first run. If you want to verify
manually, open the Neo4j Browser at your instance URL and run:

```cypher
RETURN 1 AS connected
```

## What the Notebook Creates Automatically

The `neo4j-agent-memory` SDK creates its schema (indexes, constraints,
node labels) on first connection. You don't need to set up anything manually.

Nodes created during the exercises:
- **Entity** nodes (Person, Organization, Location, Object)
- **Preference** nodes (category, preference text)
- **Message** nodes (if short-term memory is used)

## Troubleshooting

### "Unable to connect"
- Verify URI starts with `neo4j+s://` (not `bolt://`) for AuraDB
- Check the instance is running in the Aura Console
- Ensure no firewall blocks port 7687

### "Authentication failed"
- Password is case-sensitive
- If lost, reset via Aura Console → Instance → Reset Password

## Cost

AuraDB Free tier includes:
- 50K nodes, 175K relationships
- 1 database per project
- Auto-pause after 3 days of inactivity (resumes on connection)

More than sufficient for all exercises in this repo.
