#!/bin/bash
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu --disable-gpu-sandbox --in-process-gpu --disable-features=RendererCodeIntegrity"
export WINEDEBUG=-all

AXON_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"

# If already running, just show the window
WID=$(xdotool search --name "Razer Axon" 2>/dev/null | head -1)
if [ -n "$WID" ]; then
    xprop -id "$WID" -remove WM_TRANSIENT_FOR 2>/dev/null
    xdotool windowactivate --sync "$WID" 2>/dev/null
    exit 0
fi

cd "$AXON_DIR"
wine RazerAxon.exe -showui "$@" &>/dev/null &

# Wait for window and fix taskbar
while true; do
    WID=$(xdotool search --name "Razer Axon" 2>/dev/null | head -1)
    if [ -n "$WID" ]; then
        sleep 2
        xprop -id "$WID" -remove WM_TRANSIENT_FOR 2>/dev/null
        xdotool windowactivate "$WID" 2>/dev/null
        break
    fi
    sleep 1
done
