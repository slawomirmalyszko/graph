# AuraDB seed loader

The canonical seed is stored in Git and projected into AuraDB. The loader is
idempotent: nodes and relationships are matched by canonical identifiers and
updated rather than duplicated.

## Files

- `seed/catalogue-seed.json` contains deterministic synthetic catalogue data.
- `schema/constraints.cypher` contains repeatable constraints and indexes.
- `schema/verification.cypher` contains manual discovery and invariant queries.
- `src/integration_catalogue/seed.py` validates and loads the projection.

## Validate without a database

```powershell
python -m integration_catalogue.seed --validate-only
```

Validation checks required properties, identifiers, enums, relationship
endpoints, platform references, and the exactly-one-source/exactly-one-target
invariant for every integration.

## Load AuraDB

Install the Neo4j driver:

```powershell
python -m pip install -r requirements-auradb.txt
```

Set the AuraDB connection values only in the current shell or an approved
secret store. Never put these values in repository files.

```powershell
$env:NEO4J_URI = "neo4j+s://<database-id>.databases.neo4j.io"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "<password>"
python -m integration_catalogue.seed
```

The loader verifies connectivity before writing, installs the constraints and
indexes, loads nodes before relationships, and then checks the core topology
and platform-reference invariants. It prints final node counts on success.

The loader does not delete records absent from the seed. This protects data
created by future extractors. A separate, explicitly approved reconciliation
operation will be needed if Git is later required to remove stale projections.

## Explore the seed

Run the queries in `schema/verification.cypher` individually in Neo4j Browser
or the Aura console. They include:

- canonical node counts;
- invalid integration topology detection;
- invalid platform reference detection;
- integrations carrying Order information;
- E2E paths interfacing with SAP;
- the directed Salesforce-to-SAP Orders path.

