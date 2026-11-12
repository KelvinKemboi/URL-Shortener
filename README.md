# URL Shortener

A small URL shortener API built with FastAPI, SQLite and Redis. I built it to re-learn backend basics: routing, databases, generating unique codes, HTTP redirects, click analytics, expiring links and caching.

## Running it

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/). Redis is optional: without it, the app reads from the database directly.

```bash
uv sync                                  # install dependencies
docker run -d -p 6379:6379 redis         # optional: start Redis
cd src && uv run fastapi dev main.py     # start the server
```

The API runs at http://127.0.0.1:8000, and interactive docs are at http://127.0.0.1:8000/docs. The SQLite file `database.db` is created in the folder you start the server from.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| `POST` | `/shorten` | Creates a short link and returns `short_code` and `short_url` |
| `GET` | `/{short_code}` | Redirects to the original URL (307). Returns 404 if the code doesn't exist, 410 if the link has expired |
| `GET` | `/stats/{short_code}` | Returns the total number of clicks for a link |

Example request body for `POST /shorten` (only `original_url` is required):

```json
{
  "original_url": "https://example.com/some/long/page",
  "custom_alias": "my_link",
  "expiration_date": "2026-12-31T23:59:59Z"
}
```

## Phases

### 1. Database
- I used SQLite with SQLModel, which is built on SQLAlchemy. I chose SQLite because it's a single file, Python supports it out of the box, and I wanted to start simple.
- The `Link` model defines the table. The tables are created when the app starts, using FastAPI's `lifespan`.
- I set `check_same_thread=False` on the engine. SQLite normally only lets the thread that opened a connection use it, and FastAPI can handle a request on a different thread.
- `get_session()` gives each request its own database session through `Depends`.

### 2. Short codes
- Codes are 7 random characters from letters and digits (base62), generated with `secrets`. If a code already exists, a new one is generated.
- Users can choose their own alias instead. Aliases may only contain letters, numbers and `_`, up to 20 characters.
- Shortening a URL that already has a working link returns the existing code.

### 3. Redirects
- The app looks up the short code and redirects to the original URL, or returns 404 if it doesn't exist.
- **Why 307 and not 301:**
  - **307 (temporary):** every visit goes through the server, which is needed for click analytics and expiring links. 302 behaves almost the same.
  - **301 (permanent):** browsers cache the redirect and skip the server on later visits. That's faster and cheaper, but it breaks analytics and expiry.

### 4. Request body validation
- The request body is a Pydantic `BaseModel`, so FastAPI validates it and documents it automatically.
- `original_url` is an `HttpUrl`, so invalid URLs get a 422. It's converted to a string before being saved.

### 5. Click analytics
- A `clicks` table stores one row per redirect, linked to the link's `id`.
- `/stats/{short_code}` counts the rows for that link.

### 6. Expiring links
- Links can have an optional `expiration_date`. It must include a timezone and be in the future.
- Visiting an expired link returns **410 Gone**. 410 means the link existed but is gone for good, while 404 means it never existed.

### 7. Redis cache
- The redirect route checks Redis first. On a miss, it reads from the database and caches the link for one hour.
- The cache stores the link's id and expiry along with the URL. That way, cached visits are still counted and expired links still return 410, without a database read.
- If Redis is down, the app skips the cache and uses the database.
