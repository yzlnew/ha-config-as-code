#!/usr/bin/env bash
# Push Claude Code usage data to Home Assistant via webhook.
# Designed to run as a cron job on the machine where Claude Code is installed.
set -euo pipefail

CREDENTIALS_FILE="$HOME/.claude/.credentials.json"
HA_WEBHOOK_URL="http://192.168.50.154:8123/api/webhook/claude_code_usage"

# Read OAuth token from Claude Code credentials
if [[ ! -f "$CREDENTIALS_FILE" ]]; then
  echo "ERROR: credentials file not found: $CREDENTIALS_FILE" >&2
  exit 1
fi

ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('$CREDENTIALS_FILE'))['claudeAiOauth']['accessToken'])")

# Fetch usage from Anthropic API
USAGE=$(curl -sf "https://api.anthropic.com/api/oauth/usage" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "anthropic-beta: oauth-2025-04-20")

if [[ -z "$USAGE" ]]; then
  echo "ERROR: failed to fetch usage data" >&2
  exit 1
fi

# Parse and build payload for HA
PAYLOAD=$(python3 -c "
import json, sys
d = json.loads('''$USAGE''')
out = {}
if d.get('five_hour'):
    out['five_hour_utilization'] = d['five_hour']['utilization']
    out['five_hour_resets_at'] = d['five_hour']['resets_at']
if d.get('seven_day'):
    out['seven_day_utilization'] = d['seven_day']['utilization']
    out['seven_day_resets_at'] = d['seven_day']['resets_at']
if d.get('extra_usage'):
    out['extra_usage_enabled'] = d['extra_usage'].get('is_enabled', False)
    out['extra_usage_monthly_limit'] = d['extra_usage'].get('monthly_limit', 0)
    out['extra_usage_used_credits'] = d['extra_usage'].get('used_credits', 0)
print(json.dumps(out))
")

# Push to HA webhook
curl -sf -X POST "$HA_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"

echo "OK: pushed usage data to HA"
