#!/usr/bin/env bash
# =============================================================================
#  Razer Axon on Linux — one-command install
# =============================================================================
#
#  What this is. Razer Axon is Razer's "live wallpaper" app. It exists only for
#  Windows. This script installs it on Linux through Wine, a compatibility layer
#  that can run Windows programs.
#
#  What to do. Just run:
#
#      ./install-axon.sh
#
#  Nothing else needs to be typed: the script asks no questions and does
#  everything by itself. It takes about 25-40 minutes and downloads about 1 GB.
#  It prints what it is doing as it goes. If interrupted halfway, it can simply
#  be run again; steps already done are skipped.
#
#  Where everything goes. Into a separate folder, ~/.local/share/openaxon/prefix.
#  This is Wine's "own compartment": nothing outside it is changed, and
#  everything can be removed by just deleting that folder.
#
#  What appears after installation:
#      * a "Razer Axon" entry in the applications menu;
#      * a  razer-axon  command in the terminal.
#
#  ⚠ First launch. A Razer Central window with sign-in options opens. A Razer
#  account is NOT required — just click "Continue as guest" and the whole
#  wallpaper catalog opens.
#
#  Tested live on 2026-08-13 with Wine 11.15, on a clean prefix from start to
#  finish: Razer Axon 2.9.1.0, Razer Central 7.23.0.1220, WebView2 151.0.4129.78.
#  All final checks are green; a repeat run on a finished compartment completes
#  in 16 seconds. The installed app starts with one command and shows the
#  wallpaper catalog. A breakdown of every step and all measurements is
#  in docs/install-under-wine-2.9.1.0.md (sessions 9-16).
# =============================================================================

set -uo pipefail

# --- What can be changed via environment variables ---------------------------

# A separate Wine compartment. Changing it is optional.
WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
export WINEPREFIX
export WINEARCH="${WINEARCH:-win64}"
export WINEDEBUG="${WINEDEBUG:--all}"

# Where to keep downloaded installers so they are not downloaded again.
CACHE="${OPENAXON_CACHE:-$HOME/.cache/openaxon}"

# If the installers are already on disk, they can be given directly instead of downloading.
AXON_SETUP="${AXON_SETUP:-}"
CENTRAL_SETUP="${CENTRAL_SETUP:-}"

AXON_URL=""; AXON_MD5=""; CENTRAL_URL=""; CENTRAL_MD5=""

# Razer's catalog, which provides the installer links and their checksums.
DISCOVERY_URL='https://discovery3.razerapi.com/api/v1/endpoints?tag=prod'
MANIFEST_QUERY='os=WINDOWS&osver=11&arch=64&mfr=Generic-MFR&model=Generic-MDL0&sku=Generic-SKU&l=en-US'

ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"

# --- How messages are printed -------------------------------------------------

C_OK='\033[0;32m'; C_INFO='\033[0;34m'; C_WARN='\033[1;33m'; C_ERR='\033[0;31m'; C_OFF='\033[0m'
step()  { echo -e "${C_OK}==>${C_OFF} $1"; }
note()  { echo -e "${C_INFO}  ·${C_OFF} $1"; }
warn()  { echo -e "${C_WARN}  !${C_OFF} $1"; }
fail()  { echo -e "${C_ERR}  ✗${C_OFF} $1" >&2; }
abort() { fail "$1"; exit 1; }

# --- Paths inside the Wine compartment ----------------------------------------

axon_dir()     { echo "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"; }
axon_exe()     { echo "$(axon_dir)/RazerAxon.exe"; }
central_dir()  { echo "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Services/Razer Central"; }
central_exe()  { echo "$(central_dir)/RazerCentralService.exe"; }
webview_dir()  { echo "$WINEPREFIX/drive_c/Program Files (x86)/Microsoft/EdgeWebView"; }

# --- Small helpers ------------------------------------------------------------

# Check that a required program is installed on the system.
require() {
    command -v "$1" &>/dev/null && return 0
    fail "The program \"$1\" is missing from the system."
    echo "     Install it and run the script again, for example:"
    echo "       Arch / CachyOS / Manjaro:  sudo pacman -S $2"
    echo "       Debian / Ubuntu / Mint:    sudo apt install $2"
    echo "       Fedora:                    sudo dnf install $2"
    exit 1
}

# List the Wine programs running in OUR compartment specifically.
#
# "Our compartment" is determined from the process's environment variable, not
# from its name: other programs with similar names must never be touched.
#
# ⚠ But that check alone is not enough. The script itself also exports
# WINEPREFIX, so by that check it finds ITSELF and its subshells — and, when it
# gets to closing the compartment, kills itself in the middle of installation.
# Hence the second condition: the process must actually be a Wine program. Those
# have either a Windows-style path (C:\…), or are wineserver, or are a Wine
# binary itself.
prefix_pids() {
    local pid owner first
    for pid in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
        # Other users' processes cannot be read — that is normal, skip silently.
        [ -r "/proc/$pid/environ" ] || continue
        owner="$(tr '\0' '\n' 2>/dev/null < "/proc/$pid/environ" | sed -n 's/^WINEPREFIX=//p')"
        [ "$owner" = "$WINEPREFIX" ] || continue
        first="$(tr '\0' '\n' 2>/dev/null < "/proc/$pid/cmdline" | head -1)"
        case "$first" in
            [A-Za-z]:\\*|*/wineserver|*/wine|*/wine64|*/wine-preloader|*/wine64-preloader|*/bin/wine*)
                echo "$pid" ;;
        esac
    done
    return 0
}

# Wait until no programs are left running in the compartment (but no longer than N seconds).
wait_quiet() {
    local limit="${1:-120}" spent=0
    while [ "$spent" -lt "$limit" ]; do
        [ -z "$(prefix_pids)" ] && return 0
        sleep 5; spent=$((spent + 5))
    done
    return 1
}

# Programs that live permanently in the compartment and whose exit is pointless
# to wait for: Wine's service plumbing, the Razer Central service, the .NET
# background compiler (mscorsvw/ngen — stays around after .NET is installed) and
# the Edge updater, which never exits at all (session 8 of the log).
BACKGROUND_NOISE='wineserver|services\.exe|winedevice\.exe|plugplay\.exe|svchost\.exe|rpcss\.exe|explorer\.exe|MicrosoftEdgeUpdate\.exe|RazerCentralService\.exe|conhost\.exe|start\.exe|mscorsvw\.exe|ngen\.exe|ngentask\.exe'

# Wait for an installer to finish. Unlike wait_quiet, it does not wait for the
# everlasting background programs — otherwise every step would idle uselessly
# until the very limit.
wait_installer_done() {
    local limit="${1:-300}" spent=0 pid busy
    while [ "$spent" -lt "$limit" ]; do
        busy=0
        for pid in $(prefix_pids); do
            grep -qzE "$BACKGROUND_NOISE" "/proc/$pid/cmdline" 2>/dev/null && continue
            busy=1; break
        done
        [ "$busy" = 0 ] && return 0
        sleep 5; spent=$((spent + 5))
    done
    return 1
}

# Cleanly close all programs in our compartment — by PID, not by name.
close_prefix() {
    local pid
    for pid in $(prefix_pids); do kill -TERM "$pid" 2>/dev/null; done
    sleep 3
    for pid in $(prefix_pids); do kill -KILL "$pid" 2>/dev/null; done
    return 0
}

# Download a file and verify its checksum.
fetch() {
    local url="$1" file="$2" md5="${3:-}" title="${4:-file}" got
    if [ -s "$file" ] && [ -n "$md5" ] && command -v md5sum &>/dev/null; then
        if [ "$(md5sum "$file" | awk '{print $1}')" = "$md5" ]; then
            note "$title is already downloaded and verified — no need to download"
            return 0
        fi
        warn "$title in the cache is corrupted — downloading again"
        rm -f "$file"
    elif [ -s "$file" ]; then
        note "$title is already downloaded"
        return 0
    fi
    note "Downloading $title …"
    if ! curl -fL --retry 3 --retry-delay 5 -A 'RazerLWI/2.4.0.868' -o "$file" "$url"; then
        rm -f "$file"
        abort "Could not download $title. Check your internet connection."
    fi
    if [ "$(head -c 2 "$file" 2>/dev/null)" != "MZ" ]; then
        rm -f "$file"
        abort "Something other than \"$title\" was downloaded (not a program). Check your internet connection."
    fi
    if [ -n "$md5" ] && command -v md5sum &>/dev/null; then
        got="$(md5sum "$file" | awk '{print $1}')"
        if [ "$got" != "$md5" ]; then
            rm -f "$file"
            abort "$title was downloaded with errors (checksum mismatch)."
        fi
        note "Checksum of \"$title\" matches — the file is genuine"
    fi
}

# =============================================================================
#  Step 1. Check that the system has everything needed
# =============================================================================

check_system() {
    step "Checking that the system has everything needed"
    require wine       wine
    require winetricks winetricks
    require curl       curl
    require python3    python3
    command -v md5sum &>/dev/null || warn "md5sum not found — skipping authenticity checks of downloaded files"
    note "Wine version $(wine --version 2>/dev/null)"
    note "Wine compartment: $WINEPREFIX"
}

# =============================================================================
#  Step 2. Create a separate Wine compartment
# =============================================================================

make_prefix() {
    if [ -f "$WINEPREFIX/system.reg" ]; then
        note "Wine compartment already exists — skipping"
        return
    fi
    step "Creating a separate Wine compartment (the first time takes about a minute)"
    mkdir -p "$(dirname "$WINEPREFIX")" || abort "Cannot create folder $(dirname "$WINEPREFIX")"
    timeout 300 wine wineboot --init >/dev/null 2>&1
    wait_quiet 60
    [ -f "$WINEPREFIX/system.reg" ] \
        || abort "The Wine compartment was not created. Check that the path $WINEPREFIX is inside your home folder."
    note "Compartment created"
}

# =============================================================================
#  Step 3. .NET Framework 4.8
#
#  Razer Central is written in .NET Framework and refuses to install without it:
#  it shows a "Technology Required" window and waits for a button click, which
#  makes the "silent" install hang for good. So .NET is installed beforehand.
#
#  ⚠ The order matters here. The Axon install leaves the Microsoft Edge Update
#  service program running forever in the compartment, and winetricks waits at
#  every step for all programs in the compartment to exit. So .NET is installed
#  FIRST, before Axon; otherwise the .NET install hangs forever.
# =============================================================================

has_dotnet() {
    # .NET 4.8 is marked in the registry by a Release value of 528040 or higher (0x80eb1).
    grep -aqiE '"Release"=dword:0*8[0-9a-f]eb1' "$WINEPREFIX/system.reg" 2>/dev/null
}

install_dotnet() {
    if has_dotnet; then
        note ".NET Framework 4.8 is already installed — skipping"
        return
    fi
    step ".NET Framework 4.8 — the longest step, 10-30 minutes. Feel free to do something else."
    winetricks -q dotnet48 >/dev/null 2>&1
    close_prefix
    has_dotnet || abort ".NET Framework 4.8 was not installed. Run the script again — it will continue from here."
    note ".NET Framework 4.8 installed"
}

# =============================================================================
#  Step 4. Switch back to Windows 10
#
#  Installing .NET changes the reported Windows version to 7 (verified: the
#  registry is left with build 7601). And the Axon installer refuses to run on
#  Windows 7 — Razer ships it only for Windows 10 and newer. Switch back to 10.
# =============================================================================

set_win10() {
    step "Switching back to Windows 10 (the .NET install changes it to 7)"
    timeout 120 wine winecfg -v win10 >/dev/null 2>&1
    close_prefix
    if grep -aqF '"CurrentBuild"="19045"' "$WINEPREFIX/system.reg" 2>/dev/null; then
        note "Reporting Windows 10, build 19045"
    else
        warn "Could not confirm Windows 10 — the Axon installer may refuse to run"
    fi
}

# =============================================================================
#  Step 5. Ask Razer for the installer URLs
#
#  Razer publishes them itself, in an open catalog, with no authentication at
#  all. The checksums come from there too, to make sure exactly the right file
#  was downloaded, and completely.
# =============================================================================

ask_catalog() {
    if [ -n "$AXON_SETUP" ] && [ -n "$CENTRAL_SETUP" ]; then
        note "Installers given manually — not querying the Razer catalog"
        return
    fi
    step "Asking Razer for the URLs of the latest installers"
    local hash catalog answer
    hash="$(curl -fs --max-time 30 "$DISCOVERY_URL" | grep -oP '"hash":"\K[^"]+' | head -1)"
    [ -n "$hash" ] || abort "The Razer server is not responding. Check your internet connection and try again later."
    catalog="$CACHE/каталог.json"
    mkdir -p "$CACHE"
    curl -fs --max-time 60 -o "$catalog" \
        "https://manifest3.razerapi.com/api/v1/releases/$hash/tags/prod/products?$MANIFEST_QUERY" \
        || abort "Could not fetch the Razer catalog."

    # Extract two entries: Axon itself and Razer Central (Razer calls it Natasha).
    answer="$(python3 - "$catalog" <<'PY'
import json, sys
данные = json.load(open(sys.argv[1], encoding='utf-8'))
найдено = {}
def обойти(узел):
    if isinstance(узел, dict):
        имя = str(узел.get('name', ''))
        if имя in ('Razer Axon', 'Natasha') and узел.get('download_url'):
            найдено[имя] = (узел['download_url'], узел.get('download_file_checksum', ''))
        for значение in узел.values():
            обойти(значение)
    elif isinstance(узел, list):
        for значение in узел:
            обойти(значение)
обойти(данные)
for имя in ('Razer Axon', 'Natasha'):
    адрес, сумма = найдено.get(имя, ('', ''))
    print(адрес); print(сумма)
PY
)" || abort "Could not parse the Razer catalog."

    AXON_URL="$(sed -n '1p' <<<"$answer")";    AXON_MD5="$(sed -n '2p' <<<"$answer")"
    CENTRAL_URL="$(sed -n '3p' <<<"$answer")"; CENTRAL_MD5="$(sed -n '4p' <<<"$answer")"
    [ -n "$AXON_URL" ]    || abort "Razer Axon is missing from the Razer catalog."
    [ -n "$CENTRAL_URL" ] || abort "Razer Central is missing from the Razer catalog."
    note "URLs received"
}

download_installers() {
    mkdir -p "$CACHE"
    if [ -z "$CENTRAL_SETUP" ]; then
        CENTRAL_SETUP="$CACHE/RazerCentral.exe"
        fetch "$CENTRAL_URL" "$CENTRAL_SETUP" "$CENTRAL_MD5" "Razer Central (about 120 MB)"
    fi
    if [ -z "$AXON_SETUP" ]; then
        AXON_SETUP="$CACHE/RazerAxonSetup.exe"
        fetch "$AXON_URL" "$AXON_SETUP" "$AXON_MD5" "Razer Axon (about 60 MB)"
    fi
}

# =============================================================================
#  Step 6. Razer Central
#
#  This is the Razer service component through which Axon signs in to an
#  account. Without it Axon shows no window at all: it waits for a reply from
#  Central and hangs. The installer registers the service itself, as RzActionSvc.
# =============================================================================

has_central() { [ -f "$(central_exe)" ]; }

install_central() {
    if has_central; then
        note "Razer Central is already installed — skipping"
        return
    fi
    step "Installing Razer Central (Axon needs it to sign in) — about 3 minutes"
    timeout 900 wine "$CENTRAL_SETUP" /silent >/dev/null 2>&1
    wait_installer_done 180
    close_prefix
    has_central || abort "Razer Central was not installed. Run the script again."
    note "Razer Central installed"
}

# =============================================================================
#  Step 7. Razer Axon itself
#
#  Along the way its installer downloads the WebView2 engine from Microsoft's
#  servers — the entire Axon interface is drawn with it. That is roughly another
#  700 MB and a few minutes.
#
#  The switch that suppresses message boxes is spelled /SUPPRESSMSGBOXES (with
#  two "p"s). Razer's own documentation has a typo, /SUPRESSMSGBOXES — that
#  switch is simply ignored, and on any hiccup the install silently stalls on an
#  invisible window.
# =============================================================================

has_axon() { [ -f "$(axon_exe)" ]; }

install_axon() {
    if has_axon; then
        note "Razer Axon is already installed — skipping"
        return
    fi
    step "Installing Razer Axon and the WebView2 interface engine — about 5 minutes, another ~700 MB to download"
    timeout 1800 wine "$AXON_SETUP" /SP- /VERYSILENT \
        '/DIR=C:\Program Files (x86)\Razer\Razer Axon' \
        /SUPPRESSMSGBOXES /NORESTART >/dev/null 2>&1 &
    local spent=0
    while [ "$spent" -lt 1800 ]; do
        sleep 15; spent=$((spent + 15))
        if has_axon && [ -d "$(webview_dir)/Application" ]; then break; fi
    done
    wait_installer_done 300
    close_prefix
    has_axon || abort "Razer Axon was not installed. Run the script again."
    note "Razer Axon installed"
    if [ -d "$(webview_dir)/Application" ]; then
        note "WebView2 interface engine installed"
    else
        warn "WebView2 not confirmed — the Axon window may stay empty. Check your internet connection and run again."
    fi
}

# =============================================================================
#  Step 8. Rendering setup
#
#  Both Razer programs draw their interface with an embedded browser, and that
#  browser tries to output the picture through a mechanism Wine does not have
#  yet (DirectComposition). Because of this the window stays empty. The fix is
#  to report Windows 7 to the browser subprocesses SPECIFICALLY — on Windows 7
#  they use the old output path, which works in Wine. The Razer programs
#  themselves are still told Windows 10, otherwise they refuse to run.
#
#  Axon's browser is msedgewebview2.exe, Razer Central's is
#  CefSharp.BrowserSubprocess.exe. Both need to be configured.
#
#  A separate problem is the tray icon's context menu. The Razer Central window
#  itself is drawn by the browser, but the tray icon's menu is drawn not by the
#  browser but by WPF — the .NET windowing library. By default WPF renders on
#  the GPU (Direct3D 9); under Wine that path does not work, and the menu window
#  stays a solid black rectangle: right-clicking seems to "do nothing".
#  The fix is WPF's own standard switch — it can render on the CPU.
# =============================================================================

BROWSER_FLAGS='--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --disable-gpu-sandbox --disable-features=RendererCodeIntegrity --disable-crash-reporter --disable-renderer-backgrounding --disable-background-timer-throttling'

setup_rendering() {
    step "Configuring window rendering (without this the windows stay empty)"
    local reg; reg="$(mktemp --suffix=.reg)"
    cat > "$reg" <<REG
REGEDIT4

[HKEY_LOCAL_MACHINE\\Software\\Policies\\Microsoft\\Edge]
"HardwareAccelerationModeEnabled"=dword:00000000

[HKEY_LOCAL_MACHINE\\Software\\Policies\\Microsoft\\Edge\\WebView2]
"HardwareAccelerationModeEnabled"=dword:00000000

[HKEY_CURRENT_USER\\Software\\Policies\\Microsoft\\Edge]
"HardwareAccelerationModeEnabled"=dword:00000000

[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\msedgewebview2.exe]
"Version"="win7"

[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\CefSharp.BrowserSubprocess.exe]
"Version"="win7"

[HKEY_CURRENT_USER\\Environment]
"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"="$BROWSER_FLAGS"

[HKEY_CURRENT_USER\\Software\\Microsoft\\Avalon.Graphics]
"DisableHWAcceleration"=dword:00000001
REG
    timeout 120 wine regedit "$reg" >/dev/null 2>&1
    rm -f "$reg"
    close_prefix
    local ok=1
    grep -aqF 'AppDefaults\\msedgewebview2.exe'             "$WINEPREFIX/user.reg" 2>/dev/null || ok=0
    grep -aqF 'AppDefaults\\CefSharp.BrowserSubprocess.exe' "$WINEPREFIX/user.reg" 2>/dev/null || ok=0
    grep -aqF 'Microsoft\\Avalon.Graphics'                  "$WINEPREFIX/user.reg" 2>/dev/null || ok=0
    if [ "$ok" = 1 ]; then
        note "Rendering configured"
    else
        warn "Could not confirm the rendering setup — windows may be empty"
    fi
}

# =============================================================================
#  Step 9. Fonts for Russian and other non-Latin labels
#
#  Razer draws its labels with its own RazerF5 typeface. It has 229 glyphs —
#  Latin letters and punctuation, and that is all. It has no Cyrillic letters at
#  all.
#
#  On real Windows this is not a problem: if a font lacks a letter, .NET takes
#  it from a fallback font. The fallback list lives in a file of .NET itself
#  (GlobalUserInterface.CompositeFont), and for the whole range from Latin to
#  Cyrillic it lists three names: Segoe UI, Segoe UI Symbol, Ebrima. These are
#  Windows system fonts.
#
#  Wine has no fonts with those names and cannot have them — they are not free.
#  Ordinary Windows programs do not mind: ask Wine for "Segoe UI" directly and it
#  silently substitutes a similar system font. But .NET asks differently — it
#  first asks whether a font with that name EXISTS. The answer is "no", and the
#  whole fallback list breaks off at the very first step: the letter is drawn
#  with nothing, and an empty rectangle is left in its place. That is how the
#  Russian items of the tray icon menu turned into little boxes.
#
#  The fix is a standard Wine feature: it can expose an existing font under
#  another name as well. Below we say that "Segoe UI" is a font that actually
#  exists on the system. The list is separator-delimited: Wine takes the first
#  one it finds, so the entry works on any distribution. Tahoma at the end ships
#  with Wine itself and is always there.
#
#  If a real font with that name appears in the compartment (say, some program
#  brings it along), Wine silently drops the substitution — that is its own
#  rule, nothing to break.
# =============================================================================

# What covers Latin, Cyrillic and Greek.
FONT_FALLBACK='Noto Sans|DejaVu Sans|Liberation Sans|Arial|Tahoma'
# What covers arrows, check marks and other symbols.
FONT_FALLBACK_SYM='DejaVu Sans|Noto Sans|Liberation Sans|Arial|Tahoma'

setup_fonts() {
    step "Configuring fonts for non-Latin (e.g. Russian) labels"
    local name
    for name in "Segoe UI" "Ebrima"; do
        timeout 60 wine reg add 'HKCU\Software\Wine\Fonts\Replacements' \
            /v "$name" /t REG_MULTI_SZ /s '|' /d "$FONT_FALLBACK" /f >/dev/null 2>&1
    done
    timeout 60 wine reg add 'HKCU\Software\Wine\Fonts\Replacements' \
        /v 'Segoe UI Symbol' /t REG_MULTI_SZ /s '|' /d "$FONT_FALLBACK_SYM" /f >/dev/null 2>&1
    close_prefix
    if grep -aqF 'Wine\\Fonts\\Replacements' "$WINEPREFIX/user.reg" 2>/dev/null; then
        note "Fonts configured"
    else
        warn "Could not confirm the font setup — non-Latin labels may still show as boxes"
    fi
}

# =============================================================================
#  Step 10. Menu entry and the razer-axon command
# =============================================================================

make_launcher() {
    step "Creating the applications menu entry and the razer-axon command"

    local launcher="$HOME/.local/bin/razer-axon"
    mkdir -p "$(dirname "$launcher")"
    cat > "$launcher" <<LAUNCHER
#!/usr/bin/env bash
# Launches Razer Axon under Wine. Created by the install script; no need to edit.
export WINEPREFIX="$WINEPREFIX"
export WINEDEBUG=-all
# Render on the CPU: Razer's embedded browser cannot cope with attempts to use
# the GPU through Wine and crashes its rendering process without this.
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="$BROWSER_FLAGS"

# "razer-axon --stop" — fully shut down Axon and everything it started.
# A wallpaper app runs in the background and does not exit by itself: closing
# the window only minimizes it. Kill the whole Wine session of this
# compartment, leaving other programs alone.
case "\${1:-}" in
    --стоп|--stop)
        wineserver -k 2>/dev/null
        echo "Razer Axon has been shut down."
        exit 0
        ;;
esac

# Keep the Wine session open: the Razer Central service lives exactly as long as
# the session does, and without this it dies within a few seconds.
wineserver -p 2>/dev/null

# Start the Razer Central service. If it is already running, Wine just says so
# and nothing breaks.
wine sc start RzActionSvc >/dev/null 2>&1
sleep 6

# The sign-in window is drawn by Razer Central with its embedded browser. The
# service starts it WITHOUT the --no-sandbox switch, and under Wine the Chromium
# sandbox does not work: the render subprocesses never start, and the window
# stays white. So the instance started by the service is closed and our own is
# started, with the right switches.
CENTRAL_DIR="\$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Services/Razer Central"
if [ -d "\$CENTRAL_DIR" ]; then
    for pid in \$(ls /proc 2>/dev/null | grep -E '^[0-9]+\$'); do
        [ -r "/proc/\$pid/environ" ] || continue
        [ "\$(tr '\\0' '\\n' 2>/dev/null < "/proc/\$pid/environ" | sed -n 's/^WINEPREFIX=//p')" = "\$WINEPREFIX" ] || continue
        case "\$(tr '\\0' ' ' 2>/dev/null < "/proc/\$pid/cmdline")" in
            *"Razer Central.exe"*|*CefSharp.BrowserSubprocess.exe*) kill -TERM "\$pid" 2>/dev/null ;;
        esac
    done
    sleep 2
    ( cd "\$CENTRAL_DIR" && setsid wine "Razer Central.exe" /Client \\
        --no-sandbox --disable-gpu --disable-gpu-compositing \\
        --disable-features=RendererCodeIntegrity >/dev/null 2>&1 & )
fi

cd "\$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon" || exit 1
exec wine RazerAxon.exe -showui "\$@"
LAUNCHER
    chmod +x "$launcher"
    note "Command: $launcher"

    # Take the icon from the repository if the script is run from it.
    local icon=""
    if [ -f "$ROOT_DIR/axon.png" ]; then
        icon="$HOME/.local/share/icons/razer-axon.png"
        mkdir -p "$(dirname "$icon")"
        cp -f "$ROOT_DIR/axon.png" "$icon"
    fi

    local desktop="$HOME/.local/share/applications/razer-axon.desktop"
    mkdir -p "$(dirname "$desktop")"
    cat > "$desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=Razer Axon
GenericName=Live wallpapers
GenericName[ru]=Живые обои
Comment=Live desktop wallpapers by Razer
Comment[ru]=Живые обои рабочего стола от Razer
Exec=$launcher
Icon=${icon:-razer-axon}
Terminal=false
Categories=Settings;DesktopSettings;
Keywords=wallpaper;live wallpaper;background;desktop;Razer;Axon;
Keywords[ru]=обои;живые обои;фон;рабочий стол;Razer;Axon;wallpaper;
StartupWMClass=razeraxon.exe
DESKTOP
    command -v update-desktop-database &>/dev/null \
        && update-desktop-database "$(dirname "$desktop")" 2>/dev/null
    note "Menu entry: $desktop"

    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) warn "~/.local/bin is not in PATH — the razer-axon command will work after you log in again" ;;
    esac
}

# =============================================================================
#  Step 11. Clean up
#
#  The WebView2 install leaves Microsoft Edge Update service programs running.
#  They never exit on their own and get in the way of repeat runs. They are
#  killed together with the whole compartment — strictly by the PIDs of our
#  compartment's processes.
# =============================================================================

cleanup() {
    step "Cleaning up"
    close_prefix
    note "Done"
}

# =============================================================================
#  Step 12. Check that everything is in place
# =============================================================================

FAILED=0

verify() {
    step "Checking what got installed"
    FAILED=0
    # The first argument is the item description, the rest is the command to run.
    check() {
        local title="$1"; shift
        if "$@" >/dev/null 2>&1; then
            echo -e "  ${C_OK}✓${C_OFF} $title"
        else
            echo -e "  ${C_ERR}✗${C_OFF} $title"; FAILED=$((FAILED + 1))
        fi
    }
    in_registry() { grep -aqF "$2" "$WINEPREFIX/$1"; }

    check "Razer Axon is in place"                     test -f "$(axon_exe)"
    check "Razer Central is in place"                  test -f "$(central_exe)"
    check "WebView2 interface engine is in place"      test -d "$(webview_dir)/Application"
    check ".NET Framework 4.8 is installed"            has_dotnet
    check "Windows 10 is reported"                     in_registry system.reg '"CurrentBuild"="19045"'
    check "Razer Central service is registered"        in_registry system.reg 'RzActionSvc'
    check "rendering configured for Axon"              in_registry user.reg 'AppDefaults\\msedgewebview2.exe'
    check "rendering configured for Razer Central"     in_registry user.reg 'AppDefaults\\CefSharp.BrowserSubprocess.exe'
    check "tray icon menu renders"                     in_registry user.reg 'Microsoft\\Avalon.Graphics'
    check "non-Latin labels are not boxes"             in_registry user.reg 'Wine\\Fonts\\Replacements'
    check "razer-axon command created"                 test -x "$HOME/.local/bin/razer-axon"
    check "menu entry created"                         test -f "$HOME/.local/share/applications/razer-axon.desktop"

    echo
    if [ "$FAILED" -eq 0 ]; then
        echo -e "${C_OK}Done. Razer Axon is installed.${C_OFF}"
        echo
        echo "  To launch: the \"Razer Axon\" entry in the applications menu"
        echo "             or the  razer-axon  command in a terminal"
        echo
        echo -e "  ${C_WARN}On first launch${C_OFF} a Razer Central window opens."
        echo "  You do not need a Razer account — click"
        echo "  \"Continue as guest\" and the whole wallpaper catalog opens."
        echo
        echo "  The first window takes a while to fill: give it half a minute."
        echo
        echo "  To shut it down completely (a wallpaper app runs in the background;"
        echo "  closing the window only minimizes it):  razer-axon --stop"
        echo
        echo "  To remove everything:"
        echo "    rm -rf \"$WINEPREFIX\" \\"
        echo "           \"$HOME/.local/bin/razer-axon\" \\"
        echo "           \"$HOME/.local/share/applications/razer-axon.desktop\""
    else
        fail "$FAILED item(s) from the list above are missing."
        echo "     Run the script again — it will skip what is done and finish the rest."
        exit 1
    fi
}

# =============================================================================

main() {
    echo
    echo "  Razer Axon for Linux — installation"
    echo "  ───────────────────────────────────"
    echo "  Takes 25-40 minutes and downloads about 1 GB. No questions will be asked."
    echo

    check_system
    make_prefix
    install_dotnet      # must come BEFORE Axon, otherwise winetricks hangs forever
    set_win10           # must come AFTER .NET, which changes the version to 7
    ask_catalog
    download_installers
    install_central     # must come BEFORE Axon: Razer queues it first
    install_axon
    setup_rendering
    setup_fonts
    make_launcher
    cleanup
    verify
}

main "$@"
