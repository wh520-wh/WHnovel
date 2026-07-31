<div align="center">

# 📖 WHnovel

**Chat your way through a story. Pick one, talk to the AI, and the plot moves forward.**

Self-hosted AI interactive fiction — a story hall, a chat window, and an AI that actually
remembers what happened three chapters ago.

[![CI](https://github.com/wh520-wh/WHnovel/actions/workflows/ci.yml/badge.svg)](https://github.com/wh520-wh/WHnovel/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Vue 3](https://img.shields.io/badge/Frontend-Vue%203%20%2B%20TypeScript-42b883.svg)]()
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20SQLite-009688.svg)]()
[![OpenAI-compatible](https://img.shields.io/badge/Models-OpenAI%20compatible%20API-412991.svg)]()

[English](README.md) · [中文](README.zh.md)

</div>

---

## Why WHnovel?

Existing AI roleplay tools are either **power-user frontends with no story layer** (SillyTavern-style),
**closed chat apps with no narrative structure** (Character.AI-style), or **cloud-locked subscription games**
(AI Dungeon-style). WHnovel is the one that treats the **story** as the product:

- 🕰️ **A story timeline** — plot tags become a clickable timeline; jump back to any beat of the story
- 🧩 **Structured story output** — the AI writes the prose first, then *asynchronously* writes back a
  structured tail (plot state, tags, highlighted words), keeping the story coherent across hundreds of turns
- 🔑 **Your model, your data** — bring any OpenAI-compatible API key (chat *and* image models);
  everything runs on your own machine, no cloud lock-in

## ✨ Features

**Story-first** — the parts competitors don't have:

- **Two-phase output**: prose streams in first, then a structured tail (plot state, tags, highlighted words) is written back asynchronously — the narrative stays readable even at model speed
- **Story timeline**: click any tag to jump to that beat of the plot; the whole arc stays navigable
- **AI illustrations**: cover art and in-chat images share one configurable image model
- **Save system**: create, export to JSON, import, inline rename — your stories are portable

**Chat that feels good**:

- **SSE streaming** with typing indicator and smart auto-scroll (follows the story, never yanks the page)
- **Plot state persistence** woven into prompts so the AI remembers earlier chapters

**Yours to run**:

- Self-hosted: FastAPI + SQLite, zero external services
- Admin panel: configure chat/image models, edit prompts, manage story options
- Mobile-friendly: virtual-keyboard offset, 44px minimum touch targets, notch-safe areas

## 📸 Screenshots

> TODO: add real screenshots under `docs/screenshots/` (e.g. `story-hall.png`, `chat-timeline.png`).

## ⚡ Quick Start

Requires Node.js 18+ and Python 3.10+.

```bash
git clone https://github.com/wh520-wh/WHnovel.git
cd WHnovel
```

**Backend:**

```bash
cd backend
pip install -r requirements.txt
python run.py
```

**Frontend (in another terminal):**

```bash
cd frontend
npm install
npm run dev
```

Windows users can also run `start.ps1` or `start.bat` (stop with `stop.bat`).

Default addresses: frontend `http://localhost:5173`, backend `http://localhost:8000`.

> Admin panel: type `localStorage.admin_mode = '1'` in the browser console, then refresh.

## 🧰 Tech Stack

| Layer | Tech |
| --- | --- |
| Frontend | Vue 3 · Vite · TypeScript · Pinia · Element Plus |
| Backend | FastAPI · SQLAlchemy · SQLite |
| AI | Any OpenAI-compatible API (chat + image models) · SSE streaming |

## 🧭 Product Direction

Positioning and roadmap come from a competitor research report:
[docs/research/2026-07-31-competitive-research.md](docs/research/2026-07-31-competitive-research.md).

Highlights: open story-state database (world/character/relationship lines), Character Card v2/v3 import
from the SillyTavern ecosystem, branch/replay from any timeline node, and long-conversation auto-summaries.

## 🛠 Development

Backend — Ruff + pytest:

```bash
cd backend
pip install -r requirements-dev.txt
ruff check .          # lint
ruff format .         # format
pytest                # tests
```

Frontend — ESLint + Prettier + vitest:

```bash
cd frontend
npm ci
npm run lint          # ESLint
npm run format        # Prettier
npm run type-check    # TypeScript
npm run test          # tests
```

CI runs all checks on every PR.

## 📁 Structure

```
WHnovel/
├── backend/             FastAPI service
│   ├── app/             routes, models, chat pipeline, crypto
│   ├── tests/           pytest suite
│   └── run.py           entry point
├── frontend/            Vue 3 SPA
│   ├── src/
│   │   ├── stores/      Pinia state
│   │   ├── composables/ streaming chat, scroll, images
│   │   ├── views/       pages
│   │   └── api/         HTTP + SSE clients
│   └── package.json
├── .github/workflows/   CI
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report issues, open PRs against `main`, and add tests for backend changes.

## 📄 License

MIT — see [LICENSE](LICENSE).
