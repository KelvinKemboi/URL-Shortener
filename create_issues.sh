#!/usr/bin/env bash
# Creates GitHub issues for the URL Shortener learning roadmap.
# Requires the GitHub CLI: `brew install gh && gh auth login`
set -euo pipefail

REPO="KelvinKemboi/URL-Shortener"

# Labels (ignore errors if they already exist)
gh label create "core"     --repo "$REPO" --color "0E8A16" --description "Core shortener features" 2>/dev/null || true
gh label create "advanced" --repo "$REPO" --color "1D76DB" --description "Extra features"          2>/dev/null || true

issue() {
  gh issue create --repo "$REPO" --title "$1" --label "$2" --body "$3"
  echo "Created: $1"
}

# ---------- Core ----------

issue "Set up database table for links" "core" \
"Add a database (SQLite is fine to start) with a \`links\` table.

- [ ] Columns: \`id\`, \`short_code\` (unique), \`original_url\`, \`created_at\`
- [ ] Use SQLAlchemy (or SQLModel) and create tables on startup
- [ ] Add a DB session dependency for routes"

issue "Generate unique short codes" "core" \
"Write a function that generates a short code for a URL.

- [ ] Random base62 string (e.g. 6–7 chars) or base62-encode the row id
- [ ] Handle collisions (retry if code already exists)
- [ ] Bonus: allow an optional custom alias"

issue "POST /shorten endpoint" "core" \
"Create a link from a long URL.

- [ ] Request body validated with Pydantic (\`HttpUrl\`)
- [ ] Save to DB, return the short code and full short URL
- [ ] Return 422 for invalid URLs"

issue "GET /{code} redirect endpoint" "core" \
"Redirect a short code to its original URL.

- [ ] Look up the code in the DB
- [ ] Return \`RedirectResponse\` (try 307 vs 301 and note the difference)
- [ ] Return 404 if the code doesn't exist"

# ---------- Advanced ----------

issue "Click analytics" "advanced" \
"Track how often each link is used.

- [ ] Add a \`clicks\` table (\`link_id\`, \`clicked_at\`, optional \`user_agent\`/\`referrer\`)
- [ ] Record a click on every redirect
- [ ] \`GET /{code}/stats\` returning total clicks (and maybe clicks per day)"

issue "Expiring links" "advanced" \
"Let links expire after a set time.

- [ ] Add nullable \`expires_at\` column
- [ ] Accept optional expiry in \`POST /shorten\`
- [ ] Return 410 Gone when an expired link is visited"

issue "Redis cache for hot links" "advanced" \
"Cache code → URL lookups in Redis so popular links skip the DB.

- [ ] Run Redis locally (Docker: \`docker run -p 6379:6379 redis\`)
- [ ] Check cache first in the redirect route, fall back to DB and populate cache
- [ ] Set a TTL (respect \`expires_at\` if set)
- [ ] Make sure click analytics still records cached hits"

echo "All issues created."
