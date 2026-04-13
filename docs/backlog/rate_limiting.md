# Backlog: Edge Rate Limiting via Cloudflare

## Status: In-app done, Cloudflare pending

## Problem

The `/discover` endpoint is expensive per request (~25-60s, 40+ Reddit API calls, 1 LLM call costing ~$0.003). With no rate limiting, anyone who discovers the Cloudflare Tunnel URL can:
- Exhaust the Reddit rate limit (100 req/min shared across all users)
- Run up the Anthropic bill
- Tie up all FastAPI worker threads

## Recommended Approach

**Edge-level rate limiting via Cloudflare** — this is the standard production pattern.

### Why edge, not in-app

| Concern | Edge (Cloudflare) | In-app (slowapi) |
|---------|-------------------|-------------------|
| Malicious traffic reaches server | No — blocked before it hits Python | Yes — request is received, then rejected |
| State across restarts | Persisted in Cloudflare | Lost on restart (in-memory) |
| State across instances | Shared automatically | Needs Redis or external store |
| DDoS / bot detection | Built-in | Not available |
| Setup effort | Dashboard config, no code | Code changes + dependency |

### Implementation Steps

1. **Cloudflare Access (Zero Trust)** — require authentication (GitHub/email) to reach the tunnel. This is the first gate.
2. **Cloudflare Rate Limiting Rule** — on the `/discover` path:
   - 5 requests per minute per IP
   - Action: block with 429 response
   - Configure in Cloudflare Dashboard > Security > WAF > Rate limiting rules
3. **(Optional) slowapi as defense-in-depth** — secondary in-app rate limiter in case edge rules are misconfigured or bypassed.

### Cloudflare Rate Limiting Rule Config

```
Rule name: Discover endpoint rate limit
If: URI Path equals "/discover"
Rate: 5 requests per 1 minute
Per: IP
Action: Block (429)
Duration: 1 minute
```

## Done

- **slowapi defense-in-depth** — `5/minute` per IP on `/discover` endpoint (`api.py`). Returns 429 with JSON `{"detail": "Rate limit exceeded. Try again in a minute."}`. Streamlit UI handles 429 with a user-friendly message.

## Still TODO

- **Cloudflare Rate Limiting Rule** — configure in Dashboard > Security > WAF > Rate limiting rules (see config above). This is the primary gate; slowapi is the backup.
- **(Optional) Cloudflare Access / Zero Trust** — require auth to reach the tunnel.

## Not Doing

- In-app rate limiting as the primary mechanism — doesn't survive restarts, doesn't scale across instances, lets traffic reach the server before rejecting it.
