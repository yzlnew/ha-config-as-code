# The Daily — Live HA Dashboard

Newspaper-style HA dashboard. Static HTML + JS served from HA's `/local/`,
backed by a Python composer that fetches HA states + FreshRSS items every
5 min and writes a `data.json` snapshot.

```
dev 机                                HA 实例
─────────────                         ────────────────────
scripts/the_daily/                    /config/www/the-daily/
  ├─ compose.py        ──── SCP ───→     ├─ index.html
  └─ deploy.py                            ├─ style.css
                                          ├─ app.js
                                          └─ data.json   ← rewritten every 5 min
                                       Lovelace dashboard:
                                          / sidebar entry → panel-iframe
```

## Files

- `compose.py` — orchestrator; pulls HA states, calendar events, FreshRSS items, todo lists; writes `/root/ha/www/the-daily/data.json`.
- `deploy.py` — SCP all assets to HA `/config/www/the-daily/`; first run also registers a Lovelace panel-iframe dashboard at `/the-daily/main`.
- `sources.py` — per-section fetchers (house lights, climate, air quality, energy, calendar, tasks, bulletin, today prose).
- `freshrss_bridge.py` — imports `/root/wiki/scripts/update_freshrss.py` and returns top-N filtered items for the Wire's Headlines slot.
- `_ws.py` — small WebSocket client (auth + request/response by id).
- `_bootstrap.py` — sets sys.path so `import ha_api` works; loads `/root/ha/.env`.

## One-time setup

1. Create the bulletin todo list in HA UI:
   *Settings → Devices & services → Helpers → Add → Local to-do list*, name `Bulletin`. Should produce entity `todo.bulletin`.
2. Confirm `.env` has: `HA_URL`, `HA_TOKEN`, `HA_SSH_HOST/USER/PASSWORD`.
3. Confirm `/root/wiki/.env.freshrss.local` has: `FRESHRSS_BASE_URL`, `FRESHRSS_USERNAME`, `FRESHRSS_API_PASSWORD` (already set).

## First deploy

```bash
cd /root/ha
set -a && source .env && set +a
.venv/bin/python scripts/the_daily/compose.py            # writes www/the-daily/data.json
.venv/bin/python scripts/the_daily/deploy.py             # SCP all 4 files + register Lovelace panel
```

After this, open `https://<HA_URL>/the-daily/main` in a browser. The dashboard
should also appear in the HA sidebar as **The Daily** (newspaper icon).

## Refresh loop

Add to root crontab on the dev machine:

```cron
*/5 * * * * cd /root/ha && set -a && . ./.env && set +a && \
  /root/ha/.venv/bin/python /root/ha/scripts/the_daily/compose.py && \
  /root/ha/.venv/bin/python /root/ha/scripts/the_daily/deploy.py --data-only \
  >> /var/log/the-daily.log 2>&1
```

Browser polls `data.json` every 30s. With cron at 5 min, freshness is 0–6 min.

## CLI

```bash
# preview JSON without writing
.venv/bin/python scripts/the_daily/compose.py --dry-run

# only push data.json (no HTML/CSS/JS, no dashboard register)
.venv/bin/python scripts/the_daily/deploy.py --data-only

# push assets but skip Lovelace registration (e.g. testing static)
.venv/bin/python scripts/the_daily/deploy.py --skip-dashboard
```

## Bulletin items

`todo.bulletin` items render in The Wire's third column. Format the summary as:

- Single line: `"五一带母亲去苏州"`
- With sub-line, separate by ` | `: `"五一带母亲去苏州 | 需确认高铁票，4/30 21:00 前"`

The optional `due` date appears in the `by` corner of each card.

## Failure modes

| What breaks | What you see |
|---|---|
| HA token expired | Header dot turns red; tile values become em-dashes; composer exits non-zero |
| FreshRSS unreachable | Wire Headlines column shows "No items today." |
| `todo.bulletin` doesn't exist | Wire Bulletin column shows the helper-creation hint |
| Calendar empty for next 24h | Calendar card shows "No events in the next 24 hours." |
| Browser can't fetch data.json | Header dot red; last-known render preserved |
| `generated_at` > 10 min old | Submeta `refreshed Nm ago` turns red (`body[data-state="stale"]`) |

## Phase 2 backlog (not in MVP)

- **Social Pulse slot** — currently hidden via `data-bind-hidden="wire.social_count"`. Wire up HN front page (public CORS API) or Bluesky public feed.
- **Real Energy bars** — query `/api/history/period` for the last 12h of the energy sensor, bucket into hourly bars, encode as `bars: [{h, kind}]`.
- **Real Thread mesh tile** — would need Matter Server addon WebSocket; replaced with Air Quality for now.
- **HA-internal trigger** — replace dev cron with HA `shell_command` + `automation` time-pattern trigger.
