# FlockSpace

**Find your flock. Study together. Build your nest.**

A collaborative study platform: study rooms with independent Pomodoro cycles, a shared workspace (chat, resources, AI notes, tasks, an AI study agent), a personal halfway quiz, a competitive Nest Race, twigs, Golden Nests, bird and nest customization, buddy matching, meetings, analytics with streaks, and a reporting and review system.

- `backend/`: FastAPI, SQLAlchemy and SQLite, a WebSocket hub, a background worker for AI jobs, and a server-clock ticker
- `frontend/`: Vue 3, Vite, Vue Router and Pinia, with hand-built SVG birds, nests and charts

## Run it

```bash
# backend (Python 3.12)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # macOS/Linux: .venv/bin/pip
cp .env.example .env                               # then fill in GROQ_API_KEY and a long random JWT_SECRET
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# frontend (Node 20+)
cd frontend
npm install
npm run dev                                         # http://localhost:5173 (forwards /api and /ws to :8000)
```

- **Sample data**: run `cd backend && .venv/Scripts/python -m app.seed.demo` once to add sample students, live and upcoming rooms, chat, buddies, meetings and three weeks of study history. Every sample room gets mock quiz questions from the starter bank (`backend/app/seed/bank.json`), and two of them get sample documents. Sign in as `demo@flockspace.app` / `flockspace`. Run it again any time: it re-creates sample rooms that have ended, so there are always live rooms. With `DEV_MODE=true`, five sample students show as online, studying or on a break (see `services/demo_presence.py`). This never counts as study time.
- **Offline demo**: if the frontend can't reach the backend when it loads, it switches to a demo that runs entirely in the browser. It has its own sample data, saved in `localStorage`, and an "Offline demo" pill in the header. Rooms, chat, the focus timer, checklists, buddies, meetings, profile, bird and settings all work there. AI, uploads, quizzes and races need the server. Add `?demo=1` to the URL to force the demo or `?demo=0` to go back. Reset it under **Settings → Demo data**.
- **Prototype extras**: rooms can be created with documents attached. My bird has a Student ID upload that shows a *Verified student* badge; this is a demo, the card stays in the browser and is approved automatically. Accounts with no study history see clearly labelled example charts.
- **Email**: without SMTP settings and with `DEV_MODE=true`, verification and reset codes are printed in the backend console, and the verify page fills in your own verification code for you. Reset codes are never shown in the browser.
- **Reviewers**: put reviewer emails in `ADMIN_EMAILS`. Those accounts get a **Review** page for reports, flags and appeals.
- **Tests**: run `cd backend && .venv/Scripts/python -m pytest`. That runs 31 tests covering the full journey and the safety rules, with a fake AI client.
- **Database upgrades**: the schema upgrades itself on startup. Missing tables and columns are added, and nothing is ever dropped.
- **No AI key?** If Groq isn't configured, AI actions return a clear error and the rest of the app keeps working.

## Rules (also in the code next to the logic)

| Area | Rule | Where |
|---|---|---|
| Room timing | The server owns the clock: scheduled → studying → race → finished. Pomodoro cycles are per student and are capped at the room's end. | `services/rooms.py`, `services/ticker.py` |
| Study credit | A focus block counts only if the server confirms it ran its planned length and lasted at least 10 minutes. Being online never counts. | `services/rooms.py` |
| Streaks | A day counts when completed focus minutes reach the daily goal, using local calendar days in the profile's timezone (DST-safe). | `services/analytics.py` |
| Halfway quiz | Unlocks at 50% of topics. One attempt; answers are saved as you go. Correct answers are hidden until the race ends. | `services/quiz.py` |
| Nest Race | The rules lock at creation. Same questions for everyone, shuffled per person, with server-checked deadlines. The deterministic ranking is in the module docstring. | `services/race.py` |
| Winners | More than 5 eligible racers → top 3 win; otherwise only 1st. Golden Nests are unique per race. Placement bonuses are kept in a separate ledger. | `services/race.py` |
| Fairness | The room creator can see the answer key, so they race and quiz for practice only. Unverified accounts race unranked. | `services/race.py` |
| Rewards | The twig ledger uses unique dedupe keys. Only quizzes create twigs; AI, chat, uploads and time online never do. | `services/rewards.py` |
| Matching | `40C + 25T + 15G + 10A + 10P` with explicit missing-data rules, plus a Beta(2,2) pair model capped at ±30 points. | `services/matching.py` |
| Blocking | Enforced on the server for follows, requests, nudges, invites, profiles, discovery and chat delivery. | `services/relations.py` |
| Safety | Flags are review signals, never verdicts. Only reviewers restrict accounts, every restriction can be appealed, and earned rewards are never removed. | `services/safety.py`, `api/safety.py` |
| AI | Backend-only key, a persisted job queue, quotas and idempotency, prompt-injection guards, recorded sources, and drafts until a person shares them. | `services/ai_jobs.py`, `services/prompts.py` |
