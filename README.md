# Underground Utilities Estimation AI Platform

Welcome to the **Underground Utilities Estimation AI Platform** – an open‑source reference implementation that accompanies the project blueprint you shared. This README is intended to help a new contributor  get a working development environment running quickly.

---

## 1. What you’re building

This application automates the extraction of structured data from civil engineering PDF plans (water, sewer, storm & SWPPP) using **DocuPipe OCR** together with a **custom computer‑vision model**.  A React front‑end provides an interactive overlay viewer where estimators and QA reviewers can validate AI results before exporting them to Excel/CSV.

---

## 2. High‑level architecture

```
┌────────────┐   HTTP    ┌──────────────────┐   events   ┌────────────────┐
│  Frontend  │◀────────▶│   FastAPI REST   │◀──────────▶│    Celery      │
│ React + TS │           │  (Backend API)   │   broker   │  worker pool   │
└────┬───────┘            └────────┬─────────┘            └─────┬──────────┘
     │  signed URLs                       │ results JSON          │
     ▼                                   ▼                       ▼
┌────────────┐                  ┌────────────────┐        ┌──────────────┐
│   AWS S3   │◀────────────────▶│ DocuPipe Cloud │        │  PostgreSQL  │
└────────────┘     PDFs         └────────────────┘        └──────────────┘
                                     ▲
                                     │ vision inference
                                     ▼
                              ┌──────────────────┐
                              │  Custom YOLOv8   │
                              │   (on worker)    │
                              └──────────────────┘
```

* **Frontend** – React + Vite + Tailwind for fast HMR during development.
* **Backend API** – Python 3.11 + FastAPI.
* **Task queue** – Celery workers with RabbitMQ.
* **Storage** – AWS S3 (or MinIO locally) for PDFs & overlays.
* **Database** – PostgreSQL (with an optional second Redis instance for caching).
* **Billing** – Stripe will be wired in Phase 4.

---

## 3. Tech stack summary

| Layer     | Technology                                  |
| --------- | ------------------------------------------- |
| Frontend  | React 18, TypeScript, Tailwind CSS, PDF.js  |
| Backend   | Python 3.11, FastAPI, SQLModel, Pydantic v2 |
| Queue     | Celery 5, RabbitMQ 3                        |
| Database  | PostgreSQL 15                               |
| Storage   | AWS S3 / MinIO                              |
| AI OCR    | DocuPipe SaaS                               |
| AI Vision | YOLOv8 (ultralytics)                        |
| Auth      | JWT (oauthlib), future OAuth 2.0 providers  |
| DevOps    | Docker / docker‑compose, GitHub Actions     |

---

## 4. Local quick‑start (Docker‑Compose)

> **Fastest path** – if you have Docker Desktop installed, this spins up the full stack in one command.

1. Clone the repo:

   ```bash
   git clone https://github.com/your‑org/utility‑ai‑platform.git
   cd utility‑ai‑platform
   ```
2. Copy environment variables:

   ```bash
   cp .env.example .env
   # then edit .env and insert your DocuPipe token, Stripe secret, etc.
   ```
3. Launch the stack:

   ```bash
   docker compose up --build
   ```
4. Open:

   * [**http://localhost:5173**](http://localhost:5173) – React client (Vite dev server)
   * [**http://localhost:8000/docs**](http://localhost:8000/docs) – Interactive FastAPI Swagger docs

### docker‑compose.yml (excerpt)

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [db, rabbitmq]
  worker:
    build: ./worker
    env_file: .env
    command: celery -A worker.main worker -l info
    depends_on: [backend, rabbitmq]
  frontend:
    build: ./frontend
    env_file: .env
    ports: ["5173:5173"]
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: util_ai
      POSTGRES_PASSWORD: util_ai
      POSTGRES_DB: util_ai
  rabbitmq:
    image: rabbitmq:3-management
  minio:
    image: minio/minio
    command: server /data
```

---

## 5. Manual development option (Python venv + Node.js)

1. **Backend**

   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements/dev.txt
   uvicorn app.main:app --reload
   ```
2. **Frontend**

   ```bash
   cd ../frontend
   npm install
   npm run dev
   ```

---

## 6. Suggested repo structure

```
utility‑ai‑platform/
├── backend/          # FastAPI source code
│   ├── app/
│   │   ├── api/      # routers
│   │   ├── core/     # settings, security, helpers
│   │   ├── models/   # SQLModel entities
│   │   └── services/ # DocuPipe, storage, vision, stripe
├── worker/           # Celery tasks that call DocuPipe & YOLO
├── frontend/         # React client (Vite + TS + Tailwind)
├── infra/            # docker‑compose, k8s, Terraform (optional)
├── docs/             # diagrams, ADRs, API docs
└── tests/            # backend unit tests (pytest) & e2e
```

---

## 7. Environment variables reference (`.env.example`)

| Variable                | Example                                        | Purpose                     |
| ----------------------- | ---------------------------------------------- | --------------------------- |
| `DATABASE_URL`          | `postgresql://util_ai:util_ai@db:5432/util_ai` | Postgres connection         |
| `SECRET_KEY`            | `CHANGE_ME`                                    | JWT signing key             |
| `DOCUPIPE_TOKEN`        | `dp_live_********`                             | Auth token for DocuPipe API |
| `AWS_ENDPOINT`          | `http://minio:9000`                            | Local S3 endpoint           |
| `AWS_ACCESS_KEY_ID`     | `minioadmin`                                   |                             |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin`                                   |                             |
| `STRIPE_SECRET_KEY`     | `sk_test_********`                             | Billing (Phase 4)           |

---

## 8. Dev scripts

A simple Makefile provides shortcuts:

```makefile
make up        # docker compose up
make down      # docker compose down
make lint      # ruff + prettier
make test      # pytest & vitest
make migrate   # alembic upgrade head
```

---

## 9. Next milestones

* **Phase 1 ➜ Task 1.2** – build PDF upload UI (Streamlit).
* **Phase 1 ➜ Task 1.3** – wire DocuPipe API and persist JSON.
