#!/bin/bash
# Razer Axon launcher for Linux (Wine)

set -uo pipefail

export WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
export WINEDEBUG=-all

AXON_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"
AXON_EXE="$AXON_DIR/RazerAxon.exe"
PATCHED_DLL="$(dirname "$(readlink -f "$0")")/patch/RazerAxon.UserManager.dll"

# WebView2 Chromium flags (auxiliary). The real fix for the black/white screen is
# the win7 version for msedgewebview2.exe (see apply_webview2_gpu_fix below): it moves
# frame presentation to GDI BitBlt instead of DirectComposition, which Wine does not support.
# The --disable-gpu-process-crash-limit flag was REMOVED as redundant under win7 (the DComp
# crash loop is fixed at the root; the flag only masked the symptom). This string is WRITTEN TO THE REGISTRY
# (HKCU\Environment) by apply_webview2_gpu_fix so that the flags apply to
# ANY Axon launch (Wine menu, RazerAxon: protocol handler, GUI), not only from here.
WV2_BROWSER_ARGS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --disable-gpu-sandbox --disable-features=RendererCodeIntegrity --disable-crash-reporter --disable-renderer-backgrounding --disable-background-timer-throttling"

# Optional fixed-version WebView2 runtime (more stable than evergreen under Wine).
# If the directory exists and contains msedgewebview2.exe, Axon uses exactly that
# runtime via WEBVIEW2_BROWSER_EXECUTABLE_FOLDER, bypassing evergreen, which under Wine
# crashes the browser process (BrowserProcessExited). See the README section "WebView2".
WV2_FIXED_DIR="${WV2_FIXED_DIR:-$WINEPREFIX/drive_c/webview2-fixed}"

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
        error "$1 not found. Install: $2"
        return 1
    fi
}

check_deps() {
    local missing=0

    check_command wine "sudo pacman -S wine" || missing=1
    check_command xdotool "sudo pacman -S xdotool" || missing=1
    check_command xprop "sudo pacman -S xorg-xprop" || missing=1

    if [ ! -f "$AXON_EXE" ]; then
        error "RazerAxon.exe not found: $AXON_EXE"
        error "Install Razer Axon in Wine: wine RazerAxonSetup.exe"
        missing=1
    fi

    if [ ! -d "$WINEPREFIX" ]; then
        error "WINEPREFIX not found: $WINEPREFIX"
        error "Create it: wineboot -u"
        missing=1
    fi

    # Check WebView2 runtime
    local wv2_dir="$WINEPREFIX/drive_c/Program Files (x86)/Microsoft/EdgeWebView"
    if [ ! -d "$wv2_dir" ]; then
        warn "WebView2 is not installed — login and profile will not work"
        warn "Install: wine MicrosoftEdgeWebview2Setup.exe"
    fi

    return $missing
}

# --- WebView2 GPU-process fix (registry) ---
# ROOT CAUSE of the black screen under Wine: with a Windows version >=8 the Chromium viz process sends
# the presentation of EVERY frame (even a software bitmap) through DirectComposition
# (DCompositionCreateDevice), which Wine does not implement (E_NOTIMPL/0x80004001) ->
# CHECK/0x80000003 -> viz crash -> the frame never reaches the window = a BLACK window. Fixed by
# setting Windows 7 SPECIFICALLY for msedgewebview2.exe (the DComp threshold is win8.1; under win7
# software output goes through GDI BitBlt, without DComp, and actually copies the pixels into the
# HWND). IMPORTANT: win7 is set ONLY for the renderer — the main RazerAxon.exe and the prefix
# stay on win10, otherwise the Razer server returns an empty catalog. Edge HW-accel off +
# env flags are auxiliary. Confirmed live (UI/login render). Sources:
# WineHQ Bug 58921, winetricks #2226, CodeWeavers. Previously win81 was set here by mistake
# (= the DComp threshold) -> that is exactly what caused the black screen.
apply_webview2_gpu_fix() {
    # Idempotent: apply only if not configured yet. Check HW-accel,
    # the presence of the WEBVIEW2_* env variable, AND that msedgewebview2.exe has exactly win7 (NOT win81 —
    # otherwise old prefixes with win81 would not be updated and would stay black).
    local need=0
    grep -aiq '"HardwareAccelerationModeEnabled"=dword:00000000' "$WINEPREFIX/system.reg" 2>/dev/null || need=1
    grep -aiA2 'AppDefaults\\\\msedgewebview2.exe' "$WINEPREFIX/user.reg" 2>/dev/null | grep -qi '"win7"' || need=1
    grep -aiq 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS' "$WINEPREFIX/user.reg" 2>/dev/null || need=1
    [ "$need" = 0 ] && return 0

    log "Applying the WebView2 GPU fix (registry: HW-accel off + win7 for the renderer + env flags for all launches)..."
    local reg
    reg="$(mktemp --suffix=.reg)"
    # \\ in a .reg value = a single backslash; the flags contain no backslashes, so
    # WV2_BROWSER_ARGS is written as is. Wine applies HKCU\Environment to all
    # processes of the prefix at startup -> the fix works from the menu/protocol/GUI, not only
    # from this script.
    cat > "$reg" <<REGEOF
REGEDIT4

[HKEY_LOCAL_MACHINE\\Software\\Policies\\Microsoft\\Edge]
"HardwareAccelerationModeEnabled"=dword:00000000

[HKEY_LOCAL_MACHINE\\Software\\Policies\\Microsoft\\Edge\\WebView2]
"HardwareAccelerationModeEnabled"=dword:00000000

[HKEY_CURRENT_USER\\Software\\Policies\\Microsoft\\Edge]
"HardwareAccelerationModeEnabled"=dword:00000000

[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\msedgewebview2.exe]
"Version"="win7"

[HKEY_CURRENT_USER\\Environment]
"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"="$WV2_BROWSER_ARGS"
REGEOF
    WINEDEBUG=-all wine regedit "$reg" >/dev/null 2>&1 || warn "regedit GPU fix returned an error (check manually)"
    rm -f "$reg"
    wineserver -w 2>/dev/null || true
}

# --- Patched DLL check ---

check_patch() {
    local installed_dll="$AXON_DIR/RazerAxon.UserManager.dll"
    local orig_dll="$AXON_DIR/RazerAxon.UserManager.dll.orig"

    if [ -f "$PATCHED_DLL" ] && [ -f "$installed_dll" ]; then
        if ! cmp -s "$PATCHED_DLL" "$installed_dll"; then
            warn "The patched DLL differs from the installed one"
            if [ ! -f "$orig_dll" ]; then
                log "Saving the original: $orig_dll"
                cp "$installed_dll" "$orig_dll"
            fi
            log "Updating the DLL..."
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
    local line=""
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
        error "Not all dependencies are installed, exiting."
        exit 1
    fi

    # If already running, activate existing window
    local existing_wid
    existing_wid=$(find_window)
    if [ -n "$existing_wid" ]; then
        log "Razer Axon is already running, activating the window..."
        activate_window "$existing_wid"
        exit 0
    fi

    # Start the Razer Central service. Without it RazerAxon.exe hangs in TryLoginAsync
    # and creates NO window at all (measured: docs/install-under-wine-2.9.1.0.md, session 9).
    # The service is called RzActionSvc — that is how Razer's own installer registers it.
    # wineserver -p keeps the session open: the service lives exactly as long as the session.
    if [ -f "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Services/Razer Central/RazerCentralService.exe" ]; then
        wineserver -p 2>/dev/null
        WINEDEBUG=-all wine sc start RzActionSvc >/dev/null 2>&1
    else
        warn "Razer Central is not installed — the Axon window will not appear. Install it: scripts/install-axon.sh"
    fi

    # Check and update patched DLL
    check_patch

    # Apply the GPU-process registry fix (idempotent). The main lever against
    # BrowserProcessExited is disabling Edge HW acceleration via the registry.
    apply_webview2_gpu_fix

    # WebView2 flags. Under Wine the Chromium viz/GPU process starts even with
    # --disable-gpu (software compositing), crashes with 0x80000003 on
    # DCompositionCreateDevice (E_NOTIMPL in Wine, see chrome_debug.log) and after
    # 3 crashes the browser dies with "GPU process isn't usable. Goodbye" ->
    # BrowserProcessExited. The real solution is win7 for msedgewebview2.exe
    # (apply_webview2_gpu_fix): viz stops calling DComp, the crash loop goes away.
    # Hence --disable-gpu-process-crash-limit was REMOVED (it only masked the
    # symptom; not needed under win7). --disable-gpu-sandbox is kept — it removes
    # one more breakpoint path during GPU-sandbox init.
    export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="$WV2_BROWSER_ARGS"

    # If a fixed-version runtime is installed, use it (more stable than evergreen),
    # BUT only if it is compatible with Axon. An incompatible runtime (e.g. the too
    # old 109) crashes CreateCoreWebView2Environment -> the UI does not start at all.
    # The launcher detects 'Init webview2 failed' in the log and on the next launch
    # automatically falls back to evergreen (marker .wv2-fixed-broken).
    local wv2_broken_marker="$WV2_FIXED_DIR/.wv2-fixed-broken"
    if [ -f "$WV2_FIXED_DIR/msedgewebview2.exe" ] && [ ! -f "$wv2_broken_marker" ]; then
        export WEBVIEW2_BROWSER_EXECUTABLE_FOLDER="$WV2_FIXED_DIR"
        log "WebView2: fixed-version runtime $(basename "$WV2_FIXED_DIR")"
    elif [ -f "$wv2_broken_marker" ]; then
        warn "WebView2: fixed-version is marked incompatible — using evergreen"
    else
        warn "WebView2: evergreen runtime (fixed-version not found in $WV2_FIXED_DIR)"
    fi

    # Force software EGL (Mesa) so that NVIDIA EGL under XWayland does not spam
    # 'failed to create dri2 screen' and does not poke the WebView2 GPU process.
    export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
    export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"
    if [ -f /usr/share/glvnd/egl_vendor.d/50_mesa.json ]; then
        export __EGL_VENDOR_LIBRARY_FILENAMES="${__EGL_VENDOR_LIBRARY_FILENAMES:-/usr/share/glvnd/egl_vendor.d/50_mesa.json}"
    fi

    # Launch
    log "Starting Razer Axon..."
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

    # Auto-detect fixed-version incompatibility: if it was active and WebView2
    # failed to initialize, mark it so that evergreen is used next time.
    if [ -n "${WEBVIEW2_BROWSER_EXECUTABLE_FOLDER:-}" ]; then
        local axon_log="$WINEPREFIX/drive_c/users/$USER/AppData/Local/Razer/RazerAxon/Log/RazerAxon.log"
        if [ -f "$axon_log" ] && tail -80 "$axon_log" 2>/dev/null | grep -q "Init webview2 failed"; then
            warn "fixed-version WebView2 is incompatible (Init webview2 failed) — marking it and falling back to evergreen"
            touch "$WV2_FIXED_DIR/.wv2-fixed-broken" 2>/dev/null
        fi
    fi

    if [ -z "$wid" ]; then
        error "The window did not appear within ${timeout}s. Check Wine."
        error "Run manually: cd \"$AXON_DIR\" && wine RazerAxon.exe -showui"
        exit 1
    fi

    log "Window found (${elapsed}s)"
    sleep 1
    activate_window "$wid"
    taskbar_fix "$wid"

    log "Done"
}

main "$@"
