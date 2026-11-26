# Pipecat Nextbot

A planned phone receptionist for a small restaurant. It will answer calls during service and after hours, answer questions from approved restaurant information, book tables using the same reservation system as staff, and offer optional booking confirmations. Allergy safety questions, large parties, private events, and booking changes or cancellations go to staff or the configured fallback.

**Project status:** a local Pipecat demo is scaffolded with Deepgram speech recognition, an OpenAI language model, and Cartesia speech synthesis. It uses the scaffold's generic assistant prompt and starter evals. Restaurant behaviour, inbound telephony, and live integrations are not implemented.

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

The root `pyproject.toml` also configures mypy and pytest. CI type-checks the bot against its separate `server/` environment and runs pytest when `tests/test_*.py` files exist. No API credentials are needed for static checks.

## Run the local demo

Set `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, and `CARTESIA_API_KEY` in the repository root `.env` or export them in your shell. See [`server/.env.example`](server/.env.example) for optional model and voice overrides. Keep actual keys out of Git.

```sh
cd server
uv sync --locked
uv run --locked bot.py --host 127.0.0.1
```

Open [http://localhost:7860](http://localhost:7860) for the built-in SmallWebRTC client. To run the generated text scenario with the server still running, use a second terminal:

```sh
cd server
uv run --locked pipecat eval run evals/starter_text.yaml -v
```

The starter scenario uses a local Ollama judge by default (`gemma4:12b`). To use a compatible model you already have, copy the scenario and set `judge.eval.service: ollama` and `judge.eval.model` to its name in the copy. Text mode does not verify the speech path. `evals/starter_audio.yaml` exercises that path and may download local speech models on first use.

## Next steps

Start with the read-only restaurant FAQ. [`server/data/west_kirby_kitchen.demo.json`](server/data/west_kirby_kitchen.demo.json) is a local demo snapshot of the restaurant's public info page. The scaffold does not load it yet. It records published opening times, not last kitchen orders. Friday and Saturday dinner is listed as open “until late”; do not infer a closing time. The fixture does not supply holiday hours, parking, accessibility, takeaway, or allergen information. Treat missing facts as unknown. The public email and booking link are reference information, not integration targets.

Wire the FAQ lookup, then add text scenarios for Wednesday closure, Friday dinner hours, and an unknown fact. Use separate synthetic fixtures for booking rules and fake integrations. Before taking live calls or enabling bookings, messages, or transfers, confirm the restaurant information with the owner and follow the pilot release checks in the [agent architecture](docs/architecture/restaurant-receptionist.md). Do not put real caller data in fixtures or eval logs.
