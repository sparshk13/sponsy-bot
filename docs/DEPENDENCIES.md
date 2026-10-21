# Dependencies (the agent maintains this; see CODE-09)

Every direct dependency is checked on pypi.org or npmjs.com and pinned before it is added (SEC-32, SEC-36). Limits: Python at most 15 direct, front-end runtime at most 6.

## Python (backend)
| Package | Pinned version | Why it is needed | Verified on pypi.org (date) | Notes (maintainer, last release) |
|---|---|---|---|---|
| fastapi | 0.143.3 | Web framework and JSON API | 2026-10-18 | Tiangolo, active |
| uvicorn | 0.54.0 | ASGI web server | 2026-10-18 | Encode, active |
| sqlalchemy | 2.1.5 | Database ORM and SQL toolkit | 2026-10-18 | Mike Bayer, active |
| psycopg | 3.3.6 | PostgreSQL 3 driver | 2026-10-18 | Daniele Varrazzo, active |
| psycopg-binary | 3.3.6 | Pre-compiled C extension for psycopg | 2026-10-18 | Daniele Varrazzo, active |
| alembic | 1.20.0 | Database migrations | 2026-10-18 | Mike Bayer, active |
| pydantic-settings | 2.16.0 | Settings management via env | 2026-10-18 | Pydantic team, active |
| argon2-cffi | 25.1.0 | Argon2id password hashing | 2026-10-18 | Hynek Schlawack, active |
| python-multipart | 0.0.32 | Form data and multipart parsing for CSV/uploads | 2026-10-18 | Kludex, active |
| httpx | 0.28.1 | HTTP client for external APIs (Tavily search) | 2026-10-19 | Encode, active |
| google-genai | 2.31.0 | Google Gemini SDK for fact extraction and recommendation | 2026-10-19 | Google, active |
| langgraph | 1.2.16 | Stateful multi-actor orchestration framework for Graph A | 2026-10-19 | LangChain team, active |
| langgraph-checkpoint-sqlite | 3.1.2 | SQLite checkpoint saver for LangGraph | 2026-10-19 | LangChain team, active |
| pyotp | 2.10.0 | TOTP RFC 6238 two-factor authentication (SEC-40) | 2026-10-19 | Andrey Kislyuk, active |



Dev tools (not counted): pytest, ruff, bandit, pip-audit.

## Front end (npm)
| Package | Pinned version | Runtime or dev | Why it is needed | Verified on npmjs.com (date) | Notes |
|---|---|---|---|---|---|
| react | 19.3.1 | Runtime | UI library | 2026-10-18 | Meta, active |
| react-dom | 19.3.1 | Runtime | DOM renderer for React | 2026-10-18 | Meta, active |
| react-router | 7.18.4 | Runtime | Client-side routing | 2026-10-18 | Remix/Shopify, active |
| @tanstack/react-query | 5.104.4 | Runtime | Server state management and caching | 2026-10-18 | Tanner Linsley, active |


Dev tools (not counted): typescript, vite, @vitejs/plugin-react, eslint, typescript-eslint, vitest, @testing-library/react, jsdom, openapi-typescript.

Self-hosted assets with licences kept alongside: the three fonts in `docs/DESIGN.md`.
