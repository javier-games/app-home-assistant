#!/usr/bin/with-contenv bashio
# ==============================================================================
# Git Sync app entrypoint
# Reads its configuration directly from /data/options.json (in Python) so this
# launcher stays tiny: it just sets the timezone and hands off to the app.
# ==============================================================================
set -e

bashio::log.info "Starting the Git Sync app..."

# Apply the Home Assistant configured timezone if available, so commit
# timestamps and the scheduler line up with the user's expectations.
if bashio::supervisor.ping > /dev/null 2>&1; then
    TZ_VALUE="$(bashio::info.timezone || true)"
    if bashio::var.has_value "${TZ_VALUE}"; then
        export TZ="${TZ_VALUE}"
        bashio::log.info "Using timezone: ${TZ}"
    fi
fi

exec python3 /app/main.py
