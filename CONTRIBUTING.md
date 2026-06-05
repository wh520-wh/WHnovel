# Contributing to WHnovel

Thanks for your interest in improving WHnovel! This guide covers local setup and the checks your change must pass.

## Prerequisites

- Node.js 18+ and npm
- Python 3.10+

## Backend

```bash
cd backend
pip install -r requirements-dev.txt   # runtime + dev tools
ruff check .          # lint
ruff format .         # auto-format
pytest                # tests
```

Runtime-only install uses `requirements.txt`. Copy `backend/.env.example` to `backend/.env` and fill in values as needed (at minimum set `ENCRYPTION_KEY` for portable API-key encryption).

## Frontend

```bash
cd frontend
npm ci
npm run lint          # ESLint
npm run format        # Prettier (write)
npm run type-check    # vue-tsc
npm run test          # vitest
```

## Pull requests

- CI must be green: lint, format check, type-check, and tests run automatically on every PR to `main`.
- Add or update tests when your change touches backend logic or the chat pipeline.
- Keep changes scoped; run the formatters before committing so style is consistent.
- Follow `.github/PULL_REQUEST_TEMPLATE.md`.

## Code style

Style is enforced automatically: Prettier + ESLint (frontend) and Ruff (backend). Don't hand-format — run the tools.
