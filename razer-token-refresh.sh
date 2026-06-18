#!/usr/bin/env bash
# razer-token-refresh.sh — тихо обновить JWT Razer Axon и положить его туда,
# откуда патч RazerAxon.UserManager.dll читает токен (Wine-префикс).
#
# Использует razer-login.py --refresh: если session-cookie Razer ID ещё живы,
# новый токен берётся БЕЗ окна входа. Запускается периодически (systemd --user
# timer, см. systemd/), token_needs_refresh() обновляет только когда токен
# истекает в течение часа — иначе быстрый no-op.
set -uo pipefail

DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
SRC="${RAZER_AXON_DIR:-$HOME/.config/razer-axon}/token.json"

# Тихий refresh (код выхода !=0 — сессия истекла, нужен интерактивный вход).
python3 "$DIR/razer-login.py" --refresh || {
    echo "[token-refresh] silent refresh не удался — нужен интерактивный razer-login.py" >&2
    exit 1
}

# Синхронизируем свежий токен в префикс (location, которую читает патч-DLL).
dst="$(printf '%s' "$PREFIX"/drive_c/users/*/AppData/Local/Razer/RazerAxon/wine_login_token.json)"
if [ -f "$SRC" ] && [ -e "$(dirname "$dst")" ]; then
    cp -f "$SRC" "$dst"
    echo "[token-refresh] токен обновлён и синхронизирован → $dst"
else
    echo "[token-refresh] нет $SRC или каталога префикса — синк пропущен" >&2
fi
