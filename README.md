# jamr.io

Music chat rooms for people with similar taste. Log in with Spotify, pick the genres you're into, and jamr.io ranks rooms by how well they match you, shows which of your top artists the people in each room also love, and lets everyone chat in real time and listen together through a shared Spotify Jam.

![Discover page](docs/screenshots/discover.png)

| Landing | Room |
| --- | --- |
| ![Landing page](docs/screenshots/landing.png) | ![Room page](docs/screenshots/room.png) |

## Features

- **Spotify login** (OAuth), with sessions in HTTP-only cookies and Spotify tokens encrypted at rest (Fernet)
- **Taste matching**: rooms are ranked by how well their genres match the genres you picked. Close genres (e.g. hip-hop and R&B) count partially
- **Shared artists**: each room shows which of your Spotify top artists its members, chatters and owner also have
- **Real-time chat** over Socket.IO: messages, who's here now, join/leave notices
- **Listen together**: share a Spotify Jam link with the room
- Chat rate limiting (10 messages per 10 seconds per user)

> **Why pick genres manually?** Spotify no longer gives development-mode apps
> artist genres or audio features, so taste can't be derived automatically.
> Top artists are still available, which is what shared-artist matching uses.

## Tech stack

- **Backend:** FastAPI, python-socketio, SQLAlchemy, Alembic, PostgreSQL, httpx
- **Frontend:** plain HTML, CSS and JavaScript (no build step), served by FastAPI
- **Tests:** pytest, Hypothesis (property-based tests)

## Running it locally

### Prerequisites

- Python 3.12 (e.g. via [uv](https://docs.astral.sh/uv/))
- Docker (for PostgreSQL), or any PostgreSQL 14+
- A **Spotify Premium** account. Since February 2026, Spotify only allows Premium accounts to use the Web API from development-mode apps.

### 1. Install dependencies

```bash
uv venv -p 3.12 venv
source venv/bin/activate          # fish: source venv/bin/activate.fish
uv pip install -r requirements.txt
```

### 2. Start PostgreSQL

```bash
docker run -d --name jamr-db \
  -e POSTGRES_USER=jamr -e POSTGRES_PASSWORD=jamr -e POSTGRES_DB=jamr_io \
  -p 5432:5432 postgres:16
```

After a reboot, start it again with `docker start jamr-db`.

### 3. Create a Spotify app

1. Go to the [Spotify developer dashboard](https://developer.spotify.com/dashboard) and click **Create app**.
2. Set the redirect URI to exactly `http://127.0.0.1:8000/auth/callback`. Spotify no longer accepts `localhost`.
3. Tick **Web API** and save.
4. In **Settings → User Management**, add the Spotify email of everyone who will log in (up to 5 in development mode).

### 4. Configure `.env`

```bash
cp .env.example .env
```

Then fill in:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `postgresql://jamr:jamr@localhost:5432/jamr_io` |
| `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | From your Spotify app's settings |
| `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SESSION_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

`python check_setup.py` checks the configuration.

### 5. Run

```bash
./start_dev.sh
```

This checks the database connection, runs migrations and starts the server with auto-reload. Open **http://127.0.0.1:8000**. Use `127.0.0.1`, not `localhost`, so the login cookie matches the Spotify redirect.

To try live chat, open the same room in a private window logged in as a second Spotify account.

## Tests

```bash
pytest
```

Tests use a temporary SQLite database, so they don't need PostgreSQL or Spotify. The full suite takes about 3 minutes, mostly property-based tests.

## Project structure

```
backend/
  main.py                  FastAPI app, page routes, middleware, startup
  auth.py                  Spotify OAuth, sessions, /auth/me, favorite genres
  rooms.py                 Room REST API, recommendations, shared artists
  socketio_server.py       Real-time events: join/leave, messages, Jam links
  recommendation_engine.py Genre vectors, genre match score, shared artists
  models.py                SQLAlchemy models
  serializers.py           Safe API representations of models
  validators.py            Input validation
  rate_limiter.py          Sliding-window rate limiter
alembic/versions/          Database migrations
frontend/                  index.html, discover.html, room.html, css/, js/
tests/                     pytest suite
```

## API

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/auth/spotify` | | Start Spotify login |
| GET | `/auth/callback` | | Spotify OAuth callback |
| POST | `/auth/logout` | ✓ | Log out |
| GET | `/auth/me` | ✓ | Current user |
| PUT | `/auth/me/genres` | ✓ | Set 1-5 favorite genres |
| GET | `/api/rooms` | ✓ | Rooms ranked for the current user (`?search=`, `?genres=`) |
| GET | `/api/rooms/featured` | | Public room summaries and stats for the landing page |
| POST | `/api/rooms` | ✓ | Create a room |
| GET | `/api/rooms/{id}` | ✓ | Room details |
| GET | `/api/rooms/{id}/messages` | ✓ | Latest 50 messages |
| PUT | `/api/rooms/{id}/jam-link` | ✓ | Set the room's Spotify Jam link |

Socket.IO (at `/socket.io/`, authenticated by the session cookie) handles `join_room`, `leave_room`, `send_message` and `update_jam_link`. It broadcasts `new_message`, `user_joined`, `user_left`, `user_count_updated`, `active_users_updated` and `jam_link_updated`.

## Known limitations

- Socket.IO connection state and rate limits live in memory, so run a single server process. Scaling out would need Redis.
- Spotify development mode allows at most 5 users per app. Opening it up needs Spotify's extended quota approval.
- Top artists are refreshed only when a user logs in.
