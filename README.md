# OneShotCourseMate

Google OAuth login/logout with server-side session management, built with React + Vite and Python serverless functions on Vercel.

## Quick Start

```bash
# 1. Install dependencies
npm install
pip install -r requirements.txt

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env — see CLOUD_SETUP.md for how to get each value

# 3. Initialize database
cd api && python create_db.py && cd ..
cd api && DATABASE_URL init_db.py && cd ..

# 4. Run locally
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and click "Sign in with Google".

## Architecture

```
Frontend (React + Vite)          Backend (Python Serverless)       Database (PostgreSQL)
┌─────────────────────┐          ┌──────────────────────┐          ┌──────────────┐
│  App.jsx            │──POST──▶ │  /api/oauth          │──────▶   │  users       │
│  Google Sign-In     │          │  Verify Google JWT   │          │  sessions    │
│  Session in memory  │◀─────── │  Create session      │◀──────   │              │
│                     │          ├──────────────────────┤          └──────────────┘
│  Sign Out button    │──POST──▶ │  /api/logout         │
│                     │          │  Revoke session      │
│                     │          ├──────────────────────┤
│                     │──POST──▶ │  /api/update_address │
│                     │          │  Auth + CSRF required│
└─────────────────────┘          └──────────────────────┘
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_GOOGLE_CLIENT_ID` | Yes | Google OAuth Client ID (frontend) |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth Client ID (backend verification) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SESSION_SECRET` | Yes | Secret for CSRF token signing |
| `ALLOWED_ORIGIN` | Yes | Frontend URL for CORS (e.g., `http://localhost:5173`) |
| `RATE_LIMIT_RPM` | No | Max requests per minute per IP (default: 30) |

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/oauth` | None | Login — verify Google JWT, create user + session |
| POST | `/api/logout` | Bearer token | Logout — revoke server-side session |
| POST | `/api/update_address` | Bearer + CSRF | Update authenticated user's address |

## Security Features

- **Server-side sessions** — sessions stored in DB with expiration and revocation
- **CSRF protection** — HMAC-based tokens tied to sessions for state-changing requests
- **Rate limiting** — per-IP rate limiting on all endpoints
- **Restricted CORS** — configurable allowed origin (not wildcard)
- **Input validation** — sanitization of user inputs with length limits
- **No token leakage** — session tokens stored in React state (not localStorage), filtered from JSON viewer
- **Secure headers** — HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **Connection pooling** — psycopg connection pool for database efficiency
- **Authenticated endpoints** — user identity derived from session, not request body

## Deployment

See [CLOUD_SETUP.md](./CLOUD_SETUP.md) for detailed instructions on:
- Google Cloud Console (OAuth Client ID)
- AWS RDS (PostgreSQL)
- Vercel deployment

## Tech Stack

- **Frontend**: React 19, Vite 7, Tailwind CSS 4
- **Backend**: Python serverless functions (Vercel)
- **Database**: PostgreSQL with psycopg3 + connection pooling
- **Auth**: Google Identity Services (GIS)