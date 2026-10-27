# Integration Catalogue

An **AI-assisted integration architecture and discovery platform** for enterprise
architects and managers. It builds a canonical integration graph from multiple
platforms and answers natural-language questions through controlled,
read-only Cypher queries.

Initial discovery questions include:

- Show all objects carrying Orders.
- Show all end-to-end flows that interface with SAP.
- Which applications may be affected if an interface changes?

## Status

The local MVP now demonstrates the complete discovery path:

1. Streamlit accepts a natural-language question.
2. Amazon Nova Lite on Bedrock generates parameterized Cypher from the canonical
   Git-controlled schema and reviewed examples.
3. Application safety checks reject unsupported, unbounded, or non-read-only
   queries before execution.
4. AuraDB executes the validated query in a read-only session.
5. The UI presents a summary, normalized table, CSV export, generated Cypher,
   confidence and model metadata, and a graph when Neo4j returns graph entities.

The canonical schema, synthetic seed data, AuraDB load/reset workflows, mock
query mode, and live Bedrock query mode are in place. AWS hosting, authentication,
and source-platform extractors remain later increments.

## Documentation

- [Project charter](docs/project-charter.md)
- [Architecture decisions](docs/decisions.md)
- [Canonical graph schema](docs/canonical-graph-schema.md)
- [External account setup](docs/setup/accounts.md)
- [AWS agent and MCP workflow](docs/setup/aws-agent-workflow.md)
- [Local Streamlit setup](docs/setup/local-streamlit.md)

## Local development

Prerequisites: Python 3.12 or later.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[ai,ui,dev]"
pytest
ruff check .
python -m streamlit run src/integration_catalogue/ui/app.py
```

Never commit credentials or local environment files. AuraDB credentials remain
in the ignored local `.env` file during local development. AWS credentials come
from short-lived `aws login` sessions and are never stored in the repository.
