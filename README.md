# HOS Trip Planner

Full-stack **Django + React** app for the Spotter AI assessment: plan a truck trip under FMCSA Hours-of-Service assumptions and generate route maps plus printable daily log sheets.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for system design, API contract, and HOS scope.

## Deliverables checklist
- [x] Django + React application  
- [ ] Live hosted version (deploy with steps below)  
- [ ] Loom walkthrough (3–5 min)  
- [ ] GitHub repository  

## Quick start (local)

### Backend
```bash
cd /path/to/spotter-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```
API: http://127.0.0.1:8000/api/health/

Optional: set `OPENROUTESERVICE_API_KEY` in `.env` for real road routing (free at https://openrouteservice.org/). Without it, a built-in mock router is used.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
App: http://127.0.0.1:5173/  
Vite proxies `/api` → `http://127.0.0.1:8000` in development.

### Tests
```bash
source .venv/bin/activate
pytest trips/tests/
```

## Demo scenario
Use **Load sample** in the UI, or:

| Field | Value |
|---|---|
| Current | Chicago, IL |
| Pickup | Dallas, TX |
| Dropoff | Atlanta, GA |
| Cycle used | 12 hrs |
| Shift start | 2026-03-01 06:00 |

Expect multi-day logs with 30-minute breaks, possible 10-hour resets, and fuel stops on long mileage.

## Environment variables

### Backend (`.env`)
| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret |
| `DJANGO_DEBUG` | `true` / `false` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts |
| `CORS_ALLOWED_ORIGINS` | Frontend origins |
| `OPENROUTESERVICE_API_KEY` | Optional directions |
| `DATABASE_URL` | Optional Postgres URL |
| `GEOCODER_USER_AGENT` | Nominatim user agent |

### Frontend
| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Absolute API origin in production (e.g. `https://api.example.com`) |

## Deploy

### API (Render example)
1. New Web Service from this repo  
2. Build: `pip install -r requirements.txt`  
3. Start: `gunicorn config.wsgi:application`  
4. Set env vars above; add a Postgres DB and `DATABASE_URL` if desired  
5. Run release command: `python manage.py migrate`  

A [`Procfile`](./Procfile) is included for platforms that read it.

### Frontend (Vercel)
1. Root directory: `frontend`  
2. Build command: `npm run build`  
3. Output: `dist`  
4. Env: `VITE_API_BASE_URL=https://<your-api-host>`  

[`frontend/vercel.json`](./frontend/vercel.json) enables SPA rewrites.

## Submission links
| Item | URL |
|---|---|
| Hosted app | _TBD_ |
| API | _TBD_ |
| GitHub | _TBD_ |
| Loom | _TBD_ |

## Project structure
```
spotter-ai/
├── ARCHITECTURE.md
├── manage.py
├── config/           # Django settings / URLs
├── trips/            # Models, API, HOS engine, tests
├── frontend/         # React + Vite app
├── requirements.txt
├── Procfile
└── .env.example
```
