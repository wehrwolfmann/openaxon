#!/bin/bash
# Razer Axon launcher for Linux (Wine)

set -uo pipefail

export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
export WINEDEBUG=-all

AXON_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"
AXON_EXE="$AXON_DIR/RazerAxon.exe"
PATCHED_DLL="$(dirname "$(readlink -f "$0")")/patch/RazerAxon.UserManager.dll"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[axon]${NC} $1"; }
warn()  { echo -e "${YELLOW}[axon]${NC} $1"; }
error() { echo -e "${RED}[axon]${NC} $1" >&2; }

# --- Dependency checks ---

check_command() {
    if ! command -v "$1" &>/dev/null; then
        error "$1 не найден. Установите: $2"
        return 1
    fi
}

check_deps() {
    local missing=0

    check_command wine "sudo pacman -S wine" || missing=1
    check_command xdotool "sudo pacman -S xdotool" || missing=1
    check_command xprop "sudo pacman -S xorg-xprop" || missing=1

    if [ ! -f "$AXON_EXE" ]; then
        error "RazerAxon.exe не найден: $AXON_EXE"
        error "Установите Razer Axon в Wine: wine RazerAxonSetup.exe"
        missing=1
    fi

    if [ ! -d "$WINEPREFIX" ]; then
        error "WINEPREFIX не найден: $WINEPREFIX"
        error "Создайте: wineboot -u"
        missing=1
    fi

    # Check WebView2 runtime
    local wv2_dir="$WINEPREFIX/drive_c/Program Files (x86)/Microsoft/EdgeWebView"
    if [ ! -d "$wv2_dir" ]; then
        warn "WebView2 не установлен — логин и профиль не будут работать"
        warn "Установите: wine MicrosoftEdgeWebview2Setup.exe"
    fi

    return $missing
}

# --- Patched DLL check ---

check_patch() {
    local installed_dll="$AXON_DIR/RazerAxon.UserManager.dll"
    local orig_dll="$AXON_DIR/RazerAxon.UserManager.dll.orig"

    if [ -f "$PATCHED_DLL" ] && [ -f "$installed_dll" ]; then
        if ! cmp -s "$PATCHED_DLL" "$installed_dll"; then
            warn "Патченная DLL отличается от установленной"
            if [ ! -f "$orig_dll" ]; then
                log "Сохраняю оригинал: $orig_dll"
                cp "$installed_dll" "$orig_dll"
            fi
            log "Обновляю DLL..."
            cp "$PATCHED_DLL" "$installed_dll"
        fi
    fi
}

# --- Window management ---

find_window() {
    xdotool search --name "Razer Axon" 2>/dev/null | head -1
}

activate_window() {
    local wid="$1"
    xprop -id "$wid" -remove WM_TRANSIENT_FOR 2>/dev/null
    xdotool windowactivate --sync "$wid" 2>/dev/null
}

# Fix Wine taskbar bug: reactively remove WM_TRANSIENT_FOR
taskbar_fix() {
    local wid="$1"
    while xprop -id "$wid" -spy WM_TRANSIENT_FOR 2>/dev/null | read -r line; do
        if echo "$line" | grep -q "window id"; then
            xprop -id "$wid" -remove WM_TRANSIENT_FOR 2>/dev/null
        fi
    done &
}

# --- Main ---

main() {
    # Check dependencies
    if ! check_deps; then
        error "Не все зависимости установлены, выход."
        exit 1
    fi

    # If already running, activate existing window
    local existing_wid
    existing_wid=$(find_window)
    if [ -n "$existing_wid" ]; then
        log "Razer Axon уже запущен, активирую окно..."
        activate_window "$existing_wid"
        exit 0
    fi

    # Check and update patched DLL
    check_patch

    # WebView2 flags
    export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu --disable-gpu-sandbox --in-process-gpu --disable-features=RendererCodeIntegrity"

    # Launch
    log "Запуск Razer Axon..."
    cd "$AXON_DIR"
    wine RazerAxon.exe -showui "$@" &>/dev/null &
    local wine_pid=$!

    # Wait for window (timeout 60s)
    local timeout=60
    local elapsed=0
    local wid=""
    while [ -z "$wid" ] && [ $elapsed -lt $timeout ]; do
        sleep 1
        elapsed=$((elapsed + 1))
        wid=$(find_window)
    done

    if [ -z "$wid" ]; then
        error "Окно не появилось за ${timeout}с. Проверьте Wine."
        error "Запустите вручную: cd \"$AXON_DIR\" && wine RazerAxon.exe -showui"
        exit 1
    fi

    log "Окно найдено (${elapsed}с)"
    sleep 1
    activate_window "$wid"
    taskbar_fix "$wid"

    log "Готово"
}

main "$@"
