#!/bin/bash
# Daemon that reactively fixes Razer Axon taskbar visibility
while true; do
    WID=$(xdotool search --name "Razer Axon" 2>/dev/null | head -1)
    if [ -n "$WID" ]; then
        xprop -id "$WID" -remove WM_TRANSIENT_FOR 2>/dev/null
        # Watch for changes reactively - instant response
        xprop -id "$WID" -spy WM_TRANSIENT_FOR 2>/dev/null | while read line; do
            if echo "$line" | grep -q "window id"; then
                xprop -id "$WID" -remove WM_TRANSIENT_FOR 2>/dev/null
            fi
        done
    fi
    sleep 2
done
