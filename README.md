# MKK Nebus — asynchronous payment processing

A service that accepts payments over HTTP and processes them asynchronously.
The API stores a payment and its `payments.new` event in PostgreSQL in one
transaction (transactional outbox). A background publisher relays the event to
RabbitMQ. A separate `payment_processor` worker (FastStream) emulates the payment
gateway, sends a webhook with the result and retries failures, moving
exhausted messages to a DLQ.

Stack: Python 3.14, FastAPI, SQLAlchemy 2 (asyncpg), PostgreSQL 16,
FastStream/RabbitMQ 4, Alembic, uv.

## Quick start

```bash
cp src/.env.example src/.env  # fill in the values first
make up
make migrate
```

- Swagger: http://localhost:8001/docs (port from `UVICORN_PORT`; set the API key
  via Authorize).
- RabbitMQ Management: http://localhost:15672 (credentials from `src/.env`).

## API at a glance

| Method | Path                         | Description                   |
|--------|------------------------------|-------------------------------|
| POST   | `/api/v1/payments`           | Create a payment, returns 202 |
| GET    | `/api/v1/payments/{id}`      | Get a payment                 |
| GET    | `/health`                    | Health check                  |

Every endpoint requires the `X-API-Key` header. `POST` also requires an
`Idempotency-Key` header.

Full documentation: [`docs/README.md`](docs/README.md).
