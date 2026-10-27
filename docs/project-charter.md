# Project charter

## Product statement

Integration Catalogue is an **AI-assisted integration architecture and discovery
platform**, with graph modelling and controlled agentic querying as its headline
capabilities.

It is both a learning project and a portfolio project aimed primarily at
enterprise architects and managers.

## Business outcome

The initial outcome is discovery and impact exploration across heterogeneous
integration technologies. Typical questions are:

- Show all objects carrying Orders.
- Show all end-to-end flows that interface with SAP.
- Show how two applications exchange information.

## Domain

The demonstration enterprise is a fictional global pharmaceutical company with
multiple business units. Its data is synthetic but intentionally resembles real
enterprise metadata, including incomplete, ambiguous, and faulty records.

No real corporate data or credentials are used.

## Initial scope

- One DEV environment.
- Approximately 5,000 simulated integrations.
- ServiceNow/APM-inspired application master data.
- Solace and Kong as likely live/demo sources.
- Realistic synthetic exports for platforms that are impractical to provision.
- On-demand and daily extraction through GitHub Actions.
- Neo4j AuraDB as the graph database.
- Python for extractors and application logic.
- Amazon Bedrock for focused natural-language-to-Cypher generation.
- Streamlit for the initial user interface.
- Read-only end-user access; only controlled ingestion writes to the graph.

## Initial user experience

The user enters a natural-language discovery question. The application returns:

1. A plain-language summary.
2. Tabular results where appropriate.
3. CSV export for returned tabular data.
4. A copyable, read-only generated Cypher query with model and confidence metadata.
5. A graph visualization where the result is graph-shaped.

Low-confidence or ambiguous questions are clarified or rejected safely. Follow-up
conversation and suggested questions are later increments, not Sprint 1 scope.

## Delivery principles

- Git is the source of truth for canonical schemas, mappings, examples, and
  reviewed reconciliation decisions.
- AuraDB is a built projection populated only through controlled ingestion.
- Source-specific extraction is separated from canonical normalization.
- Generated Cypher is validated and restricted to read-only operations.
- Technology and AWS service choices are made incrementally and recorded.
- Credentials and secrets are never committed to Git.
