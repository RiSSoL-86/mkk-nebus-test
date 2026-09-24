# Documentation

## Overview

The service consists of two processes that communicate only through RabbitMQ:

- **backend** (`src/main.py`, FastAPI + uvicorn) — the HTTP API and the outbox
  publisher, which runs as a background task inside the API lifespan.
- **payment_processor** (`services.payment_processor.main:app`, FastStream) — a
  worker that consumes `payments.new` events.

Payment flow:

1. `POST /api/v1/payments` inserts the payment (`pending`) and an outbox event
   `payments.new` in a single transaction and responds with `202 Accepted`.
2. The outbox publisher polls unpublished events
   (`SELECT ... FOR UPDATE SKIP LOCKED`), publishes them to the `payments`
   exchange and marks them as published in the same transaction.
3. The processor consumes the event, waits a random gateway delay, sets the
   status to `succeeded` or `failed` and stores `processed_at`. A gateway
   decline (the 10% "error") is a final business outcome, not a technical
   failure: the payment becomes `failed`, the client gets a webhook and the
   message is not retried.
4. The processor sends a webhook to `webhook_url` and stores
   `webhook_delivered_at` on success.
5. If processing or webhook delivery fails, the message is rerouted to a retry
   queue with exponential backoff; after the last attempt it goes to the DLQ.

Delivery is at-least-once. The processor is idempotent: the status changes only
while the payment is `pending` (conditional `UPDATE`), and a payment whose
webhook is already delivered is skipped. A webhook may still be sent more than
once if storing `webhook_delivered_at` fails after a successful delivery.

## API

All endpoints, including `/health`, require the `X-API-Key` header equal to
`API_KEY`. A missing or wrong key returns `401`.

### Create a payment

`POST /api/v1/payments` → `202 Accepted`

Headers:

- `X-API-Key` — API key.
- `Idempotency-Key` — required, 1–255 characters, not whitespace only.

Body:

| Field         | Type            | Constraints                            |
|---------------|-----------------|----------------------------------------|
| `amount`      | decimal string  | `> 0`, up to 18 digits, 2 decimals     |
| `currency`    | string          | `RUB`, `USD` or `EUR`                  |
| `description` | string          | up to 2000 characters                  |
| `metadata`    | object          | optional, defaults to `{}`             |
| `webhook_url` | URL             | HTTP(S) URL                            |

Response:

```json
{"payment_id": "…", "status": "pending", "created_at": "…"}
```

Idempotency: repeating the request with the same key and the same body returns
the same payment; the same key with a different body returns `409`. Concurrent
requests with the same key create exactly one payment
(`INSERT ... ON CONFLICT DO NOTHING`).

### Get a payment

`GET /api/v1/payments/{payment_id}` → `200 OK`, or `404` if not found.

Response fields: `payment_id`, `amount`, `currency`, `description`, `metadata`,
`webhook_url`, `status` (`pending` / `succeeded` / `failed`), `created_at`,
`processed_at`, `webhook_delivered_at`.

### Webhook

`POST {webhook_url}` with a JSON body:

```json
{
  "payment_id": "…",
  "status": "succeeded",
  "amount": "100.50",
  "currency": "RUB",
  "processed_at": "2026-01-01T00:00:00+00:00"
}
```

Any non-2xx response or network error counts as a failure. The webhook is sent
once per attempt; a failed delivery is retried only through the RabbitMQ retry
queues (see below), so there is a single retry policy. On a retry the gateway
is not called again, only the webhook is resent.

### Examples

```bash
curl -X POST http://localhost:8001/api/v1/payments \
  -H "X-API-Key: ${API_KEY}" \
  -H 'Idempotency-Key: order-42' \
  -H 'Content-Type: application/json' \
  -d '{"amount":"100.50","currency":"RUB","description":"Order 42","metadata":{"order_id":"42"},"webhook_url":"https://example.com/webhook"}'

curl http://localhost:8001/api/v1/payments/PAYMENT_ID \
  -H "X-API-Key: ${API_KEY}"
```

`API_KEY` must contain the key from `src/.env`. The amount is sent as a string
and stored as `NUMERIC(18, 2)`.

## RabbitMQ topology

All exchanges are direct and durable. The whole topology is declared on startup
by both the backend and the processor.

| Exchange         | Queue                     | Purpose                              |
|------------------|---------------------------|--------------------------------------|
| `payments`       | `payments.new`            | new payment events                   |
| `payments.retry` | `payments.new.retry.{N}`  | delay queue for retry attempt `N`    |
| `payments.dlq`   | `payments.new.dlq`        | messages that exhausted all attempts |

- Messages are published as persistent, so they survive a broker restart.
- The processor limits in-flight messages with `RABBITMQ_PREFETCH_COUNT`.
- The attempt number is carried in the `x-retry-count` header.
- Each retry attempt has its own queue with
  `x-message-ttl = RETRY_BACKOFF_BASE_SECONDS * 2^(N-1)`; on expiry the message
  is dead-lettered back to `payments.new`. Separate queues keep short delays
  from waiting behind longer ones.
- After `RETRY_MAX_ATTEMPTS` failed attempts the message is published to the
  DLQ. With the defaults: 3 attempts, delays of 2 s and 4 s.
- `payments.new` has a dead-letter exchange, so messages rejected by the
  consumer (e.g. an invalid payload) also end up in the DLQ.

## Project structure

```text
src/
  main.py                        # FastAPI app, routers, lifespan (broker + outbox publisher)
  conftest.py                    # test settings and migrations before tests
  app_settings/                  # settings from environment / src/.env
    brokers/                     # RabbitMQ connection settings
    processing/                  # gateway, webhook, outbox and retry settings
  core/
    common/                      # base model, repository and service
      broker/                    # broker, producer and consumer abstractions
    brokers/
      rabbitmq/                  # RabbitMQ implementation
        broker.py                # RabbitMQBroker: connection with retries + .producer / .consumer
        producer.py              # publish, retry, dead-letter
        consumer.py              # payments.new subscription
        topology.py              # exchanges and queues
    database/                    # engine and session factory
    payments/                    # ORM model, entities, enums, event types, repository, errors
    outbox/                      # ORM model and repository of outbox events
  services/
    api/
      urls.py                    # /api/v1 router
      common/                    # API key dependency
      payments/
        urls.py                  # payments routes
        handlers.py              # HTTP handlers
        schemas.py               # response schemas
        services/                # create / get use cases
    outbox_publisher/
      main.py                    # OutboxPublisher: background polling task
      services/publisher.py      # publishes a batch of outbox events
    payment_processor/
      main.py                    # FastStream app entry point
      handlers.py                # payments.new handler
      schemas.py                 # broker event schemas
      errors.py                  # webhook delivery error
      services/                  # processing, webhook sending, rerouting
  alembic/                       # migrations
```

Layering: a handler receives a session via `Depends` and passes it to a
service; the service creates a repository with that session and calls it.
Repositories contain SQL and manage their transactions (`session.begin()`) and
return entities. The outbox publisher service opens the transaction itself so
that publishing and marking events as published happen under the same row lock.

## Configuration

All settings are read from environment variables and `src/.env`
(`ENV_FILE` overrides the path). `src/.env.example` lists the required
variables with empty values.

| Variable                                   | Description                          |
|--------------------------------------------|--------------------------------------|
| `PROJECT_NAME`                             | API title                            |
| `DEBUG`                                    | FastAPI debug and SQL echo           |
| `API_KEY`                                  | static API key, required             |
| `UVICORN_HOST`, `UVICORN_PORT`             | HTTP server address                  |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | PostgreSQL |
| `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`, `RABBITMQ_HOST`, `RABBITMQ_PORT` | RabbitMQ |

Credentials are URL-encoded automatically when the RabbitMQ URL is built.

Optional processing and broker settings (defaults shown):

| Variable                        | Default | Description                         |
|---------------------------------|---------|-------------------------------------|
| `GATEWAY_MIN_DELAY_SECONDS`     | `2.0`   | min emulated gateway delay          |
| `GATEWAY_MAX_DELAY_SECONDS`     | `5.0`   | max emulated gateway delay          |
| `GATEWAY_SUCCESS_RATE`          | `0.9`   | probability of `succeeded`          |
| `WEBHOOK_TIMEOUT_SECONDS`       | `5.0`   | webhook request timeout             |
| `OUTBOX_POLL_INTERVAL_SECONDS`  | `0.5`   | outbox polling interval             |
| `OUTBOX_BATCH_SIZE`             | `50`    | events per outbox batch             |
| `RETRY_MAX_ATTEMPTS`            | `3`     | message processing attempts         |
| `RETRY_BACKOFF_BASE_SECONDS`    | `2.0`   | retry queue TTL base                |
| `RABBITMQ_PREFETCH_COUNT`       | `10`    | max unacked messages per consumer   |
| `RABBITMQ_CONNECT_ATTEMPTS`     | `10`    | startup connection attempts         |
| `RABBITMQ_CONNECT_RETRY_DELAY_SECONDS` | `3.0` | delay between connection attempts |

## Running with Docker

```bash
cp src/.env.example src/.env  # fill in the values first
make up
make migrate
```

On PowerShell use `Copy-Item src/.env.example src/.env`.

Compose starts PostgreSQL, RabbitMQ, `backend` and `payment_processor`. Both
services wait for RabbitMQ on startup (`RABBITMQ_CONNECT_ATTEMPTS`), so they
survive starting before the broker is ready.

- `make up` builds and starts the containers; `make up.nobuild` skips the build.
- `make migrate` applies migrations inside the running backend container.
- `make down` stops everything.

Notes:

- All containers read `src/.env` and use `network_mode: host`, so set
  `POSTGRES_HOST` and `RABBITMQ_HOST` to local addresses.
- PostgreSQL listens on `POSTGRES_PORT`; RabbitMQ uses its default ports
  (`5672`, management `15672`).
- The backend runs `uvicorn main:app --reload`; `./src` is mounted into
  `/app/src`, the virtual environment lives in `/app/.venv`.
- Data is kept in the `postgres_data` and `rabbitmq_data` volumes.

Endpoints:

- Swagger: http://localhost:8001/docs (port from `UVICORN_PORT`).
- RabbitMQ Management: http://localhost:15672.

## Development

```bash
make install             # uv sync --locked
make pre-commit.install  # gitlint, ruff, ruff-format, mypy hooks
make lint                # ruff check, ruff format --check, mypy (strict)
make test                # pytest with coverage report
```

Migrations (run inside the backend container):

```bash
make migrations m="description"  # autogenerate a revision
make migrate                     # upgrade head
make downgrade                   # downgrade -1
make migrations.check            # fail if models and migrations differ
```

## Tests

Tests do not read `src/.env`: `conftest.py` sets test settings and applies
migrations (`alembic upgrade head` + `alembic check`) before the session.
RabbitMQ is replaced with FastStream's in-memory `TestRabbitBroker`, so only
PostgreSQL is needed.

Integration tests expect PostgreSQL at `127.0.0.1:5433` with database
`mkk_nebus_test` owned by `test_user` / `test_password`. For example, with the
Compose database running on port 5433:

```bash
docker compose --env-file src/.env -f compose.dev.yml exec db \
  sh -c 'psql -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "CREATE USER test_user WITH PASSWORD '\''test_password'\'';" \
    -c "CREATE DATABASE mkk_nebus_test OWNER test_user;"'
make test
```

Integration tests use unique keys, so they can run against a non-empty database.
They cover concurrent creation, idempotency conflicts, outbox rollback,
`SKIP LOCKED` behaviour and exactly-once status transition.

CI (GitHub Actions) starts its own PostgreSQL service and runs ruff, mypy and
pytest.

## References

- [uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/)
- [FastStream CLI](https://faststream.ag2.ai/latest/getting-started/cli/)
