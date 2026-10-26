#!/usr/bin/env bash
# razer-token-refresh.sh — silently refresh the Razer Axon JWT and put it where
# the RazerAxon.UserManager.dll patch reads the token from (the Wine prefix).
#
# Uses razer-login.py --refresh: if the Razer ID session cookies are still alive,
# a new token is obtained WITHOUT a login window. Runs periodically (systemd --user
# timer, see systemd/); token_needs_refresh() only refreshes when the token
# expires within an hour — otherwise it is a quick no-op.
set -uo pipefail

DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
SRC="${RAZER_AXON_DIR:-$HOME/.config/razer-axon}/token.json"

dst="$(printf '%s' "$PREFIX"/drive_c/users/*/AppData/Local/Razer/RazerAxon/wine_login_token.json)"

# Respect a manual logout. If the prefix currently holds a GUEST token (isGuest=true),
# the user clicked "Log out", and forcing the account token back in MUST NOT happen
# (otherwise a "log out ⇄ auto-login" collision: it immediately logs back in as RZR_…).
# Refresh ONLY an already logged-in (real) session.
if [ -f "$dst" ] && python3 -c "import json,sys; sys.exit(0 if json.load(open('$dst')).get('isGuest') else 1)" 2>/dev/null; then
    echo "[token-refresh] guest token in the prefix (logged out of the account) — skipping, not forcing a login"
    exit 0
fi

# Silent refresh (exit code != 0 — the session has expired, an interactive login is needed).
python3 "$DIR/razer-login.py" --refresh || {
    echo "[token-refresh] silent refresh failed — run razer-login.py interactively" >&2
    exit 1
}

# Sync the fresh token into the prefix (the location the patched DLL reads).
if [ -f "$SRC" ] && [ -e "$(dirname "$dst")" ]; then
    cp -f "$SRC" "$dst"
    echo "[token-refresh] token refreshed and synced → $dst"
else
    echo "[token-refresh] $SRC or the prefix directory is missing — sync skipped" >&2
fi
