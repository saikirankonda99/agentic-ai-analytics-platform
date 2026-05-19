# Troubleshooting

## OpenAI Requests Show `Connection error`

Check proxy environment variables first:

```powershell
Get-ChildItem Env: | Where-Object { $_.Name -like '*PROXY*' }
```

This project disables proxy trust for OpenAI by default through `OPENAI_TRUST_ENV=false`. If a corporate proxy is required, set `OPENAI_TRUST_ENV=true` only after verifying the proxy is reachable.

## OpenAI Requests Show `AuthenticationError`

The request reached OpenAI, but the configured key is invalid or revoked. Replace `OPENAI_API_KEY` in `.env`, Streamlit secrets, or the host environment.

## Verify Runtime Diagnostics

Streamlit shows runtime posture in the `API` section. FastAPI exposes:

```text
GET /health
GET /ready
GET /diagnostics
```

## Export Telemetry

Use the telemetry export buttons in `Monitoring`, `Agents`, or `API` sections. JSON is best for support cases; CSV is best for latency and cost analysis.

## Local Validation Commands

```powershell
python -m ruff check
python -m pytest
python -m streamlit run app.py --server.port 8501 --server.headless true
```
