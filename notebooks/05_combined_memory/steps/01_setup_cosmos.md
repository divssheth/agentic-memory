# Setting Up Persistence Backends

## Cosmos DB NoSQL (Episodic Memory)

If you already created a Cosmos DB account in **Module 2 (Episodic Memory)**, reuse it — no additional setup needed.

Just make sure `COSMOS_ENDPOINT` is set in your `.env` file:

```env
COSMOS_ENDPOINT=https://<your-unique-name>.documents.azure.com:443/
```

If you haven't set up Cosmos DB yet, follow the full guide in [Module 2's setup instructions](../../02_episodic_memory/steps/01_setup_cosmos.md).

## Neo4j (Semantic Memory)

If you already set up Neo4j in **Module 3 (Semantic Memory)**, reuse it — no additional setup needed.

Make sure these variables are set in your `.env` file:

```env
NEO4J_URI=neo4j+s://<your-instance>.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-password>
NEO4J_DATABASE=neo4j
```

If you haven't set up Neo4j yet, follow the full guide in [Module 3's setup instructions](../../03_semantic_memory/steps/01_setup_neo4j.md).
