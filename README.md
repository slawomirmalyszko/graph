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

The canonical graph schema and repeatable AuraDB seed process are in place. A
local Streamlit chat shell now provides read-only AuraDB connectivity; controlled
natural-language-to-Cypher generation is the next functional increment.

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
python -m pip install -e ".[ui,dev]"
pytest
ruff check .
python -m streamlit run src/integration_catalogue/ui/app.py
```

Never commit credentials or local environment files. Service credentials will
be documented only by variable name and stored in an appropriate secret store.
