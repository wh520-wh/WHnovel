# WHnovel

[![CI](https://github.com/wh520-wh/WHnovel/actions/workflows/ci.yml/badge.svg)](https://github.com/wh520-wh/WHnovel/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An AI interactive fiction platform with streaming chat, structured story state, and configurable model providers.

## Features

- Streaming chat over Server-Sent Events with `delta`, `text_end`, `tail`, and `done` events.
- Two-phase streaming: text body is sent first, then a structured tail (status, tags, highlights) follows as a separate request.
- Archive management: create, export, import, and inline-rename conversation archives.
- Story timeline navigation with clickable plot tags that jump to the matching segment.
- AI image generation driven by a configurable image model, used for cover art and in-chat illustrations.
- Admin panel for configuring chat and image models, prompts, and per-archive options.
- Structured-output governance: a single contract layer (`ai_contracts.py`) defines schemas, validates model JSON, fills defaults, and surfaces uniform error codes.
- Mobile-friendly input bar with virtual-keyboard offset handling managed by a dedicated composable.

## Tech stack

- Frontend: Vue 3, Vite, TypeScript, Pinia, Element Plus.
- Backend: FastAPI, SQLAlchemy, SQLite, Pydantic.
- AI: chat and image models accessed through OpenAI-compatible HTTP APIs.
- Streaming: Server-Sent Events (SSE) with a per-archive generation lock.

## Quick start

Prerequisites:

- Node.js 18+ and npm.
- Python 3.10+.
- On Windows: Git Bash (used by the bundled `start.ps1` helper) or PowerShell.

Clone and run:

```bash
git clone https://github.com/wh520-wh/WHnovel.git
cd WHnovel
```

Backend:

```bash
cd backend
pip install -r requirements.txt
python run.py
```

Frontend (in a second terminal):

```bash
cd frontend
npm install
npm run dev
```

Or from the repository root on Windows, use the bundled launcher:

```bash
./start.ps1
# or
start.bat
```

Stop the dev servers with:

```bash
stop.bat
```

Default local addresses:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

Admin mode is enabled by setting `localStorage.admin_mode = '1'` in the browser console.

## Project structure

```
WHnovel/
├── backend/                FastAPI service, SQLAlchemy models, chat pipeline
│   ├── app/
│   ├── tests/
│   └── run.py
├── frontend/               Vue 3 SPA (Vite + TS)
│   ├── src/
│   │   ├── stores/
│   │   ├── composables/
│   │   ├── views/
│   │   └── api/
│   └── package.json
├── docs/                   Design notes and AI output governance docs
├── scripts/                Repo maintenance scripts
├── start.ps1, start.bat    Local dev launchers (backend + frontend)
├── stop.bat                Stop dev servers
├── LICENSE
├── README.md
├── README.zh.md
└── .github/                Issue and PR templates, code of conduct
```

## Contributing

File issues for bugs and feature ideas, and open a pull request against `main`. Follow `.github/PULL_REQUEST_TEMPLATE.md`, keep changes scoped, and include tests when the change touches backend logic or chat pipeline behavior.

## License

MIT — see [LICENSE](LICENSE).
