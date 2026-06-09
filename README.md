# NeuroDb

NeuroDb is a local neuroscience data and agent-workflow platform. The primary UI
is the FastAPI + React workbench.

## Primary UI

Run the API and React frontend from separate terminals:

```bash
uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
cd frontend && npm run dev
```

Open the Vite URL printed by the frontend server.

## Deprecated Streamlit UI

The old Streamlit app is deprecated and retained only as a legacy compatibility
surface. New UI workflows and fixes should target FastAPI + React.

To run the legacy UI:

```bash
uv sync --extra legacy-ui
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```
