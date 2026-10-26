#!/usr/bin/env bash
# =============================================================================
# install-axon-linux.sh — install Razer Axon under Wine "for everyone" (OpenAxon)
# =============================================================================
#
# What it does: creates an isolated Wine prefix, configures it so that the
# official Razer installer/catalog works, downloads the official
# RazerAxonSetup from the Razer manifest and installs Axon into Program Files.
#
# The root cause of "server access unavailable" / the green screen and the crash
# of the WPF installer was confirmed live (see docs/axon_installer_wine_diagnosis_*.md):
#   1) No real .NET Framework 4.8 -> the installer engine crashes before going online.
#   2) Wine=Win7 -> the Razer server returns an empty catalog (Axon requires Win10+).
#   3) WebView2 Runtime is missing -> the catalog screen is drawn black.
#   4) The installer's WPF UI (Razer.Installer.UI.Language.TextBlockTextPlugin)
#      crashes under Wine in TextBlock measure/layout when leaving the EULA screen
#      (unhandled 0x80131623), REGARDLESS of the locale and WPF HW acceleration.
#
# Workaround for crash #4: we do NOT click through the installer's WPF UI. The Razer
# manifest openly provides a direct download_url for the official RazerAxonSetup
# (Inno Setup), which installs in /VERYSILENT mode without WPF. We download exactly
# that and verify the checksum from the manifest. The installer is NOT patched — all legal.
#
# Idempotency: a repeated run skips steps already done. dotnet48 and WebView2
# are installed once. If Axon is already installed, the script exits.
#
# Verified live: prefix /tmp/axon-verify-prefix, Wine 11.10, RTX 4070.
# RazerAxon.exe got installed (Program Files (x86)\Razer\Razer Axon, ~230 MB,
# 660 files, Inno registry entry "Razer Axon" 2.6.2.0), the app starts and reaches
# the login screen. Authorization (Razer login) is a separate runtime step.
# =============================================================================

set -uo pipefail

# --- Settings (can be overridden via the environment) ------------------------

# Isolated prefix (NOT ~/.wine, so as not to interfere with other applications)
WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
export WINEPREFIX

# Download cache
CACHE_DIR="${OPENAXON_CACHE:-$HOME/.cache/openaxon}"

# URL of the Razer Axon online installer (bootstrap). Direct Razer dl link (stable).
# WARNING: do NOT use https://rzr.to/axon — it 302-redirects to a MARKETING
# page (HTML), not to the .exe (verified 2026-05-31 on a clean prefix → the bootstrap
# turned out to be HTML → the engine did not unpack → "Manifest with Axon not received").
# The correct short link is rzr.to/axon-download → dl.razerzone.com/.../RazerAxonInstaller.exe
# A local file can be supplied via AXON_INSTALLER=/path/RazerAxonInstaller.exe
AXON_INSTALLER_URL="${AXON_INSTALLER_URL:-https://dl.razerzone.com/drivers/Axon/RazerAxonInstaller.exe}"
AXON_INSTALLER="${AXON_INSTALLER:-}"

# Direct manifest URL of Axon Setup (Inno). If set, we skip parsing the manifest
# through the engine and download directly (faster). Otherwise it is extracted from the online engine's manifest.
# WARNING: this URL contains a timestamp+random id and expires over time —
# the current one always lives in the manifest, which is parsed automatically (branch below).
AXON_SETUP_URL="${AXON_SETUP_URL:-}"

# WebView2 Evergreen Standalone (x64), stable Microsoft fwlink
WEBVIEW2_URL="${WEBVIEW2_URL:-https://go.microsoft.com/fwlink/?linkid=2124701}"

# WebView2 FIXED-VERSION runtime (CAB). Under Wine the evergreen runtime crashes
# the browser process (BrowserProcessExited) — instability of multi-process IPC.
# Idea: a pinned Chromium might hold up more stably.
#
# VERDICT (verified live 2026-06-12, Wine 11.10):
#   * 109.0.1518.78 — incompatible: gives 'Init webview2 failed', the UI does not start.
#   * 133.0.3065.92 — via WEBVIEW2_BROWSER_EXECUTABLE_FOLDER ALSO gives
#     'Init webview2 failed' and Axon exits. The cause is NOT the version: the env var
#     makes Axon take the InitWebview2WithAbsolutePath branch, which under
#     Wine fails synchronously. I.e. the env-var mechanism itself breaks init.
#   * 133.0.3065.92 deployed as EdgeCore\133.0.3065.92 + registry pv=133
#     (WITHOUT the env var) — init PASSES via the working primary branch, the home
#     screen renders. BUT BrowserProcessExited crashes the same way as 149 (~10 s
#     after init). 133 gives NO stability — the root is in Wine's Mojo IPC, not in the
#     runtime version. See docs/axon_installer_wine_diagnosis_*.md.
#
# OFF by default: the env-var path breaks init (109 and 133), and the registry path to 133
# does not cure the crash. Evergreen 149 at least renders home. To enable (NOT recommended,
# it will break init): INSTALL_WV2_FIXED=1 — downloads the CAB into drive_c/webview2-fixed;
# razer-axon.sh picks it up via WEBVIEW2_BROWSER_EXECUTABLE_FOLDER and on
# 'Init webview2 failed' automatically falls back to evergreen (marker .wv2-fixed-broken).
INSTALL_WV2_FIXED="${INSTALL_WV2_FIXED:-0}"
WV2_FIXED_URL="${WV2_FIXED_URL:-https://github.com/westinyang/WebView2RuntimeArchive/releases/download/133.0.3065.92/Microsoft.WebView2.FixedVersionRuntime.133.0.3065.92.x64.cab}"

# Whether to apply the OpenAxon authorization workaround after installation (DLL patch)
APPLY_AUTH_PATCH="${APPLY_AUTH_PATCH:-0}"

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

# --- Output ------------------------------------------------------------------

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[install-axon]${NC} $1"; }
info() { echo -e "${BLUE}[install-axon]${NC} $1"; }
warn() { echo -e "${YELLOW}[install-axon]${NC} $1"; }
err()  { echo -e "${RED}[install-axon]${NC} $1" >&2; }
die()  { err "$1"; exit 1; }

# --- Paths inside the prefix --------------------------------------------------

axon_dir()  { echo "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"; }
axon_exe()  { echo "$(axon_dir)/RazerAxon.exe"; }
engine_dir(){ echo "$WINEPREFIX/drive_c/windows/Installer/Razer/Installer2"; }
manifest()  { echo "$(engine_dir)/ManifesetCache/manifest.json"; }
wv2_dir()   { echo "$WINEPREFIX/drive_c/Program Files (x86)/Microsoft/EdgeWebView"; }

# --- Dependency check ---------------------------------------------------------

need() { command -v "$1" &>/dev/null || die "Not found: $1. Install it: $2"; }

check_deps() {
    need wine       "sudo pacman -S wine  (or your package manager)"
    need winetricks "sudo pacman -S winetricks"
    need curl       "sudo pacman -S curl"
    need python3    "sudo pacman -S python"
    # md5sum is optional but desirable for the integrity check
    command -v md5sum &>/dev/null || warn "md5sum not found — skipping the checksum check"
}

# --- Helper: finish off a hung winetricks (known wineserver -w bug) ------------

kill_wineserver() { timeout 20 wineserver -k 2>/dev/null || true; }

# --- Step 1: create the prefix ------------------------------------------------

setup_prefix() {
    if [ -f "$WINEPREFIX/system.reg" ]; then
        info "Prefix already exists: $WINEPREFIX (skipping wineboot)"
        return
    fi
    log "Creating Wine prefix: $WINEPREFIX"
    mkdir -p "$(dirname "$WINEPREFIX")"
    # Wine refuses to create the config directory if the prefix's PARENT is not
    # owned by the current user (e.g. a prefix directly in /tmp -> root:root).
    # Catch this explicitly, otherwise the failure surfaces later as an obscure dotnet48 error.
    local parent; parent="$(dirname "$WINEPREFIX")"
    if [ "$(stat -c %u "$parent" 2>/dev/null)" != "$(id -u)" ] && [ ! -d "$WINEPREFIX" ]; then
        warn "The prefix parent '$parent' is not owned by you — Wine may refuse."
        warn "Choose a path inside your \$HOME, e.g.: WINEPREFIX=\$HOME/.local/share/openaxon/prefix"
    fi
    WINEDEBUG=-all timeout 180 wine wineboot --init 2>/dev/null || true
    timeout 30 wineserver -w 2>/dev/null || true
    kill_wineserver
    [ -f "$WINEPREFIX/system.reg" ] || die "The prefix did not initialize ($WINEPREFIX/system.reg is missing). Usually: the path is not inside your \$HOME or there are no permissions. Wine: '...is not owned by you'."
}

# --- Step 2: .NET Framework 4.8 -----------------------------------------------
# Release 0x80eb1 (528113) = .NET 4.8. If it is already installed, skip (saves hours).

dotnet48_installed() {
    # .NET 4.8 -> Release >= 528040 (0x80eb1 = 528113). Finding the 80eb1+ marker is enough.
    grep -aiqE '"Release"=dword:0*8[0-9a-f]eb1' "$WINEPREFIX/system.reg" 2>/dev/null
}

install_dotnet48() {
    if dotnet48_installed; then
        info ".NET Framework 4.8 already installed (skipping)"
        return
    fi
    log ".NET Framework 4.8 (winetricks dotnet48) — this may take 10-30 min..."
    WINEDEBUG=-all winetricks -q dotnet48 || warn "winetricks dotnet48 finished with an error (often because of a hung wineserver -w — checking the result below)"
    kill_wineserver
    dotnet48_installed || die ".NET 4.8 was not installed. Run the script again."
    log ".NET Framework 4.8 OK"
}

# --- Step 3: Windows 10 version -----------------------------------------------
# IMPORTANT: dotnet48 internally switches the version back to win7 — that is why
# win10 is ALWAYS set AFTER dotnet48.

set_win10() {
    log "Setting the Windows version to 10 (otherwise the server returns an empty catalog)"
    WINEDEBUG=-all timeout 90 wine winecfg -v win10 2>/dev/null || true
    kill_wineserver
    if grep -aiq '"CurrentBuild"="19045"' "$WINEPREFIX/system.reg" 2>/dev/null; then
        log "Windows 10 (build 19045) OK"
    else
        warn "Could not confirm win10 in the registry — continuing, but the catalog may be empty"
    fi
}

# --- Step 4: WebView2 Runtime -------------------------------------------------
# Needed so that the catalog/Axon UI is not black.

webview2_installed() {
    [ -d "$(wv2_dir)/Application" ] && \
      find "$(wv2_dir)/Application" -iname 'msedgewebview2.exe' 2>/dev/null | grep -q .
}

install_webview2() {
    if webview2_installed; then
        info "WebView2 Runtime already installed (skipping)"
        return
    fi
    local wv2="$CACHE_DIR/MicrosoftEdgeWebView2RuntimeInstaller.exe"
    mkdir -p "$CACHE_DIR"
    if [ ! -s "$wv2" ]; then
        log "Downloading WebView2 Evergreen Standalone (~190 MB)..."
        curl -fL -A "Mozilla/5.0" -o "$wv2" "$WEBVIEW2_URL" || die "Could not download WebView2"
    fi
    log "Installing WebView2 Runtime into the prefix..."
    WINEDEBUG=-all timeout 360 wine "$wv2" /silent /install 2>/dev/null || true
    kill_wineserver
    webview2_installed || warn "WebView2 not confirmed — the Axon UI may be black"
}

# --- Step 4b (optional): fixed-version WebView2 runtime (stability under Wine) ---
# Unpacked into drive_c/webview2-fixed; razer-axon.sh picks it up via
# WEBVIEW2_BROWSER_EXECUTABLE_FOLDER. Reduces the frequency of BrowserProcessExited.

wv2_fixed_dir() { echo "$WINEPREFIX/drive_c/webview2-fixed"; }

install_webview2_fixed() {
    [ "$INSTALL_WV2_FIXED" = "1" ] || { info "Fixed-version WebView2 skipped (INSTALL_WV2_FIXED=0)"; return; }
    if [ -f "$(wv2_fixed_dir)/msedgewebview2.exe" ]; then
        info "Fixed-version WebView2 already installed (skipping)"
        return
    fi
    command -v cabextract &>/dev/null || { warn "cabextract not found (sudo pacman -S cabextract) — fixed-version skipped"; return; }
    local cab="$CACHE_DIR/wv2-fixed-x64.cab"
    mkdir -p "$CACHE_DIR"
    if [ ! -s "$cab" ]; then
        log "Downloading the fixed-version WebView2 runtime (~200 MB)..."
        curl -fL --retry 3 -o "$cab" "$WV2_FIXED_URL" || { warn "Could not download the fixed-version — evergreen stays"; return; }
    fi
    log "Unpacking fixed-version WebView2..."
    local tmp="$CACHE_DIR/wv2-fixed-extract"
    rm -rf "$tmp"; mkdir -p "$tmp"
    cabextract -q -d "$tmp" "$cab" || { warn "cabextract failed — evergreen stays"; return; }
    # The CAB puts everything into the subdirectory Microsoft.WebView2.FixedVersionRuntime.*.x64/
    local exe; exe="$(find "$tmp" -iname msedgewebview2.exe 2>/dev/null | head -1)"
    [ -n "$exe" ] || { warn "msedgewebview2.exe not found in the CAB — evergreen stays"; return; }
    rm -rf "$(wv2_fixed_dir)"
    mkdir -p "$(dirname "$(wv2_fixed_dir)")"
    cp -a "$(dirname "$exe")" "$(wv2_fixed_dir)"
    rm -rf "$tmp"
    [ -f "$(wv2_fixed_dir)/msedgewebview2.exe" ] \
        && log "Fixed-version WebView2 installed: $(wv2_fixed_dir)" \
        || warn "Fixed-version installation not confirmed — evergreen stays"
}

# --- Step 4c: WebView2 GPU-process fix (registry) -----------------------------
# The ROOT of the black screen under Wine: with a Windows version >=8.1 Chromium's viz
# process presents the frame (even software) via DirectComposition (Wine does not implement it →
# E_NOTIMPL/0x80004001 → CHECK/0x80000003 → viz crash → the frame never reaches the window =
# BLACK). Cured by Windows 7 version SPECIFICALLY for msedgewebview2.exe: under win7
# software output goes through GDI BitBlt (no DComp) and copies the pixels into the HWND.
# win7 is ONLY for the renderer; RazerAxon.exe and the prefix stay win10 (otherwise the
# Razer server returns an empty catalog). Edge HW-accel off is auxiliary. Confirmed
# live. Previously win81 was set here (= the DComp threshold), which is what gave the black screen.
# Details: docs/axon_installer_wine_diagnosis_2026_05_31.md, section "ROOT CAUSE REVISED".
# Auxiliary flags (the real fix is win7 for msedgewebview2.exe above).
# They are written to the registry (HKCU\Environment) so that they apply on ANY Axon launch
# (Wine menu, RazerAxon: protocol handler, GUI), not only via razer-axon.sh.
# The --disable-gpu-process-crash-limit flag was REMOVED as redundant with win7 (it only
# masked the DComp crash loop, while win7 eliminates it at the root).
WV2_BROWSER_ARGS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --disable-gpu-sandbox --disable-features=RendererCodeIntegrity --disable-crash-reporter --disable-renderer-backgrounding --disable-background-timer-throttling"

apply_webview2_gpu_fix() {
    log "Registry: Edge HW acceleration off + win7 for the renderer + env flags (GPU fix for all launches)"
    local reg; reg="$(mktemp --suffix=.reg)"
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
    WINEDEBUG=-all wine regedit "$reg" >/dev/null 2>&1 || warn "regedit for the GPU fix returned an error"
    rm -f "$reg"
    kill_wineserver
    if grep -aiq '"HardwareAccelerationModeEnabled"=dword:00000000' "$WINEPREFIX/system.reg" 2>/dev/null \
       && grep -aiq 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS' "$WINEPREFIX/user.reg" 2>/dev/null; then
        log "GPU fix applied (HW-accel=0 + env flags in the registry)"
    else
        warn "GPU fix NOT confirmed in the registry — WebView2 may crash in a loop"
    fi
}

# --- Step 5: get the online installer (bootstrap) ------------------------------

fetch_installer() {
    if [ -n "$AXON_INSTALLER" ] && [ -s "$AXON_INSTALLER" ]; then
        info "Using the local installer: $AXON_INSTALLER"
        return
    fi
    AXON_INSTALLER="$CACHE_DIR/RazerAxonInstaller.exe"
    mkdir -p "$CACHE_DIR"
    if [ -s "$AXON_INSTALLER" ]; then
        info "Online installer already downloaded: $AXON_INSTALLER"
        return
    fi
    log "Downloading the Razer Axon online installer ($AXON_INSTALLER_URL)..."
    curl -fL -A "RazerLWI/2.4.0.868" -o "$AXON_INSTALLER" "$AXON_INSTALLER_URL" \
        || die "Could not download the installer. Point to a file via AXON_INSTALLER=/path.exe"
    # Check that this is a real PE (MZ) and not an HTML landing page (like rzr.to/axon).
    if [ "$(head -c 2 "$AXON_INSTALLER" 2>/dev/null)" != "MZ" ]; then
        rm -f "$AXON_INSTALLER"
        die "What was downloaded is not an .exe (probably an HTML page). Check AXON_INSTALLER_URL — it must be a direct link to RazerAxonInstaller.exe (e.g. https://dl.razerzone.com/drivers/Axon/RazerAxonInstaller.exe)."
    fi
}

# --- Step 6: get the Razer catalog manifest -----------------------------------
# We run the bootstrap installer: it unpacks the engine and DOWNLOADS manifest.json
# (with OS version win10 — the full catalog including Axon). We do NOT click through its WPF UI (it crashes),
# and after ~60 s we kill the process — by then the manifest is already on disk.

obtain_manifest() {
    if [ -s "$(manifest)" ] && grep -aiq 'RazerAxonSetup' "$(manifest)" 2>/dev/null; then
        info "Catalog manifest with Axon already present (skipping the bootstrap run)"
        return
    fi
    log "Running the bootstrap installer to obtain the manifest (ignoring the UI)..."
    export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-features=RendererCodeIntegrity"
    WINEDEBUG=-all wine "$AXON_INSTALLER" &>/dev/null &
    local pid=$!
    # Wait for the manifest with Axon to appear (up to ~120 s)
    local ok=0
    for _ in $(seq 1 24); do
        sleep 5
        if [ -s "$(manifest)" ] && grep -aiq 'RazerAxonSetup' "$(manifest)" 2>/dev/null; then ok=1; break; fi
    done
    # Shut down the bootstrap and its WPF engine (useless from here on, and it crashes in the UI).
    # IMPORTANT: only our own process by PID and our OWN whole prefix via wineserver -k.
    # Killing by name (pkill -f RazerInstaller) is not allowed: another prefix on the same
    # machine may be running under the same name, and we would kill someone else's program.
    kill "$pid" 2>/dev/null || true
    kill_wineserver
    [ "$ok" = 1 ] || die "Manifest with Axon not received. Check network access to *.razerapi.com and the win10 OS version."
    log "Catalog manifest obtained (contains Razer Axon)"
}

# --- Step 7: extract download_url + checksum for Axon from the manifest --------

parse_axon_setup() {
    if [ -n "$AXON_SETUP_URL" ]; then
        AXON_SETUP_CHECKSUM=""
        AXON_SETUP_PARAMS='/SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART'
        info "Using the given AXON_SETUP_URL"
        return
    fi
    log "Parsing the manifest: looking for the direct URL of the official Axon Setup..."
    local out
    out="$(python3 - "$(manifest)" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
found = {}
def rec(o):
    if isinstance(o, dict):
        if str(o.get('name','')) == 'Razer Axon':
            found.update(o)
        for v in o.values(): rec(v)
    elif isinstance(o, list):
        for v in o: rec(v)
rec(d)
url = found.get('download_url','')
md5 = found.get('download_file_checksum','')
prm = found.get('install_parameters','/SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART')
print(url); print(md5); print(prm)
PY
)" || die "Manifest parsing error"
    AXON_SETUP_URL="$(echo "$out"   | sed -n '1p')"
    AXON_SETUP_CHECKSUM="$(echo "$out" | sed -n '2p')"
    AXON_SETUP_PARAMS="$(echo "$out" | sed -n '3p')"
    [ -n "$AXON_SETUP_URL" ] || die "The manifest has no download_url for Axon"
    info "Axon Setup URL: $AXON_SETUP_URL"
    info "Install parameters: $AXON_SETUP_PARAMS"
}

# --- Step 8: download and verify the official Axon Setup (Inno) ----------------

download_axon_setup() {
    AXON_SETUP="$CACHE_DIR/RazerAxonSetup.exe"
    mkdir -p "$CACHE_DIR"
    log "Downloading the official Razer Axon Setup (~88 MB)..."
    curl -fL -A "RazerLWI/2.4.0.868" -o "$AXON_SETUP" "$AXON_SETUP_URL" \
        || die "Could not download Axon Setup (the URL may have expired — rerun for a fresh manifest)"
    if [ -n "${AXON_SETUP_CHECKSUM:-}" ] && command -v md5sum &>/dev/null; then
        local got; got="$(md5sum "$AXON_SETUP" | awk '{print $1}')"
        if [ "$got" = "$AXON_SETUP_CHECKSUM" ]; then
            log "MD5 checksum matches ($got) — the file is authentic"
        else
            die "MD5 mismatch! expected $AXON_SETUP_CHECKSUM, got $got"
        fi
    fi
}

# --- Step 9: silent Axon installation (Inno Setup, without WPF) ----------------

install_axon() {
    log "Installing Razer Axon (Inno Setup silent mode)..."
    export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-features=RendererCodeIntegrity"
    # shellcheck disable=SC2086
    WINEDEBUG=-all wine "$AXON_SETUP" $AXON_SETUP_PARAMS \
        '/DIR=C:\Program Files (x86)\Razer\Razer Axon' &>/dev/null &
    local pid=$!
    # Wait for RazerAxon.exe to appear (up to ~180 s)
    for _ in $(seq 1 36); do
        sleep 5
        [ -f "$(axon_exe)" ] && break
    done
    wait "$pid" 2>/dev/null || true
    kill_wineserver
    [ -f "$(axon_exe)" ] || die "RazerAxon.exe did not appear — the installation did not complete"
    local sz; sz="$(du -sh "$(axon_dir)" 2>/dev/null | awk '{print $1}')"
    log "Installation complete: $(axon_exe) (folder $sz)"
}

# --- Step 10 (optional): apply the OpenAxon authorization workaround -----------

apply_auth() {
    [ "$APPLY_AUTH_PATCH" = "1" ] || { info "Authorization (DLL patch) skipped. Launch: razer-axon.sh"; return; }
    local patch="$SCRIPT_DIR/patch/RazerAxon.UserManager.dll"
    local target="$(axon_dir)/RazerAxon.UserManager.dll"
    if [ -f "$patch" ] && [ -f "$target" ]; then
        [ -f "$target.orig" ] || cp "$target" "$target.orig"
        cp "$patch" "$target"
        log "OpenAxon authorization DLL patch applied"
    else
        warn "DLL patch or target file not found — skipped"
    fi
}

# --- Main ---------------------------------------------------------------------

main() {
    info "OpenAxon — installing Razer Axon under Wine"
    info "Prefix: $WINEPREFIX"
    check_deps

    # Idempotency: already installed?
    if [ -f "$(axon_exe)" ]; then
        log "Razer Axon already installed: $(axon_exe)"
        install_webview2_fixed
        apply_webview2_gpu_fix
        apply_auth
        log "Done. Launch: WINEPREFIX=\"$WINEPREFIX\" $SCRIPT_DIR/razer-axon.sh"
        exit 0
    fi

    setup_prefix
    install_dotnet48
    set_win10
    install_webview2
    install_webview2_fixed
    apply_webview2_gpu_fix
    fetch_installer
    obtain_manifest
    parse_axon_setup
    download_axon_setup
    install_axon
    apply_auth

    echo
    log "=========================================================="
    log " Razer Axon installed in:"
    log "   $(axon_dir)"
    log " Launch (with authorization):"
    log "   WINEPREFIX=\"$WINEPREFIX\" $SCRIPT_DIR/razer-axon.sh"
    log "=========================================================="
}

main "$@"
