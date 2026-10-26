# Local Streamlit setup

The local application connects directly to AuraDB. It does not require or use a
local Neo4j installation or container.

## Install

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[ui,dev]"
Copy-Item .env.example .env
```

Edit `.env` with the connection details downloaded or copied from the AuraDB
console. The file is ignored by Git. Never paste its values into source files,
issues, logs, or pull requests.

## Run

```powershell
python -m streamlit run src/integration_catalogue/ui/app.py
```

Open `http://localhost:8501`. The first increment provides the chat shell and a
fixed, read-only AuraDB catalogue summary. Natural-language-to-Cypher generation
and graph rendering are intentionally separate follow-up increments.
