# Pipecat Nextbot

A planned phone receptionist for a small restaurant. It will answer calls during service and after hours, answer questions from approved restaurant information, book tables using the same reservation system as staff, and offer optional booking confirmations. Allergy safety questions, large parties, private events, and booking changes or cancellations go to staff or the configured fallback.

**Project status:** specification, proposed architecture, and development tooling are in place. The Pipecat bot, restaurant integrations, and conversation evals have not been scaffolded. There is no phone or browser service to start yet.

## Documentation

- [Restaurant receptionist specification](docs/specs/restaurant-receptionist.md) — first-release scope, tool contracts, and acceptance criteria.
- [Agent architecture](docs/architecture/restaurant-receptionist.md) — call pipeline, booking and transfer boundaries, data handling, and verification plan.
- [General receptionist specification](docs/specs/ai-receptionist.md) — the broader product brief.
- [Getting started with a coding agent](GETTING_STARTED.md) — Pipecat and Context Hub guidance.

## Development setup

Install [uv](https://docs.astral.sh/uv/) and use Python 3.11 as pinned in `.python-version`. From the repository root:

```sh
uv sync --locked --all-groups
uv run --locked ruff check .
uv run --locked ruff format --check .
```

The root `pyproject.toml` also configures mypy and pytest. CI passes Python files outside `.venv` to mypy explicitly because recursive discovery can skip helper scripts under `.agents/`. CI runs pytest when `tests/test_*.py` files exist; there is no permanent pytest suite yet. No API credentials are needed for these development checks.

## Before building the agent

Confirm mock demo versus live pilot, telephony and staff transfer, speech and model providers, voice and accent, and hosting. For a live pilot, also confirm the reservation system, restaurant policies, and after-hours fallback. Then scaffold with the Pipecat CLI and eval support. Validate behaviour with synthetic restaurant data before enabling real bookings, messages, or transfers.

Keep credentials in a local `.env` file. Do not commit secret values or put real caller data in fixtures or eval logs.
