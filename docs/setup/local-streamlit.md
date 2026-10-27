# Local Streamlit setup

The local application connects directly to AuraDB. It does not require or use a
local Neo4j installation or container.

## Install

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[ai,ui,dev]"
Copy-Item .env.example .env
```

Edit `.env` with the connection details downloaded or copied from the AuraDB
console. The file is ignored by Git. Never paste its values into source files,
issues, logs, or pull requests.

The Bedrock adapter uses the standard boto3 credential chain. Do not add AWS
credentials to `.env`; local short-lived AWS authentication will be configured
separately when Bedrock inference access is available.

`QUERY_MODE=mock` is the default. It runs the reviewed example questions without
AWS credentials while still validating and executing their Cypher against AuraDB.
Set `QUERY_MODE=bedrock` only when short-lived AWS credentials are available.
Bedrock failures are shown to the user and never silently fall back to mock mode.

For local Bedrock mode, install AWS CLI 2.32 or later and authenticate with:

```powershell
aws login
```

The project AI dependencies include AWS CRT support so boto3 can consume these
short-lived, auto-rotating login credentials. Do not place credentials in `.env`.
Local login sessions last up to 12 hours and can be renewed by running `aws login`
again.

## Run

```powershell
python -m streamlit run src/integration_catalogue/ui/app.py
```

Open `http://localhost:8501`. The application provides controlled NL-to-Cypher
generation, read-only AuraDB execution, tabular results, generated Cypher, and a
Graph tab when Neo4j returns nodes, relationships, or paths.
