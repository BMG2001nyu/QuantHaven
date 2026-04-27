# QuantHaven Technical Assessment

This repository now implements a production-style version of the assessment:

- EMA 9/21 crossover backtest with no-lookahead execution
- FastAPI webhook receiver with validation, idempotency, optional HMAC auth, and SQLite persistence
- Markdown and HTML reporting built from saved backtest artifacts plus logged signals

## Project Layout

- `src/quanthaven/backtest.py`: data loading, EMA strategy, execution engine, metrics export
- `src/quanthaven/api.py`: FastAPI app with webhook, signals, HTML report, and JSON report endpoints
- `src/quanthaven/webhook.py`: request validation, idempotency logic, persistence helpers
- `src/quanthaven/db.py`: SQLite initialization and connection management
- `src/quanthaven/reporting.py`: summary generation plus Markdown and HTML rendering
- `scripts/run_demo.py`: one-command end-to-end demo
- `data/sample_ohlcv.csv`: bundled OHLCV data for offline demos
- `artifacts/`: generated outputs
- `runtime/signals.db`: SQLite store for ingested signals

## Quickstart

Run the full end-to-end demo:

```bash
python3 scripts/run_demo.py
```

That command:

1. runs the backtest
2. posts a sample webhook signal
3. generates Markdown and HTML reports
4. prints all three outputs

## Run The Backtest

```bash
PYTHONPATH=src python3 -m quanthaven.backtest --data-file data/sample_ohlcv.csv
```

Optional free Stooq data:

```bash
PYTHONPATH=src python3 -m quanthaven.backtest --symbol aapl.us
```

Output:

- `artifacts/backtest_results.json`

## Run The API

```bash
PYTHONPATH=src uvicorn quanthaven.api:app --reload
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/webhook/signal \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","side":"buy","qty":"10","price":"202.5","client_order_id":"demo-1"}'
```

Available endpoints:

- `POST /webhook/signal`
- `GET /signals`
- `GET /report`
- `GET /report.json`

## Generate Reports

```bash
PYTHONPATH=src python3 -m quanthaven.reporting
```

Outputs:

- `artifacts/report.md`
- `artifacts/report.html`

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Auth

Webhook authentication is disabled by default for local review. To enable HMAC verification:

```bash
export QUANTHAVEN_DISABLE_AUTH=false
export QUANTHAVEN_WEBHOOK_SECRET="your-secret"
```

Then send `X-Webhook-Signature: sha256=<digest>` using the raw request body.

