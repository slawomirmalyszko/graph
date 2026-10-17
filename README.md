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

The project is in its foundation phase. The current focus is repository,
account, security, and development-environment setup. The first functional
vertical slice will follow after the graph model is agreed.

## Documentation

- [Project charter](docs/project-charter.md)
- [Architecture decisions](docs/decisions.md)
- [External account setup](docs/setup/accounts.md)

## Local development

Prerequisites: Python 3.12 or later.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
ruff check .
```

Never commit credentials or local environment files. Service credentials will
be documented only by variable name and stored in an appropriate secret store.
