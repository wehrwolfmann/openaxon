#!/bin/bash
# Razer Axon launcher for Linux (Wine)

set -uo pipefail

export WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
export WINEDEBUG=-all

AXON_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"
AXON_EXE="$AXON_DIR/RazerAxon.exe"
PATCHED_DLL="$(dirname "$(readlink -f "$0")")/patch/RazerAxon.UserManager.dll"

# Chromium-флаги WebView2. --disable-gpu-process-crash-limit — КЛЮЧЕВОЙ: снимает
# фатальный лимит «3 краша», из-за которого browser-процесс под Wine выходит с
# BrowserProcessExited (~16с после старта) и UI-окно закрывается/пустеет («белый
# экран»). Корень крашей — DCompositionCreateDevice E_NOTIMPL (Wine не реализует
# DirectComposition). См. docs/axon_installer_wine_diagnosis_2026_05_31.md.
# ВАЖНО: эта же строка ПИШЕТСЯ В РЕЕСТР (HKCU\Environment) функцией
# apply_webview2_gpu_fix, чтобы фикс действовал при ЛЮБОМ запуске Axon (меню Wine,
# protocol-handler RazerAxon:, GUI), а не только через этот скрипт.
WV2_BROWSER_ARGS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --disable-gpu-sandbox --disable-gpu-process-crash-limit --disable-features=RendererCodeIntegrity --disable-crash-reporter --disable-renderer-backgrounding --disable-background-timer-throttling"

# Опциональный fixed-version WebView2 рантайм (стабильнее evergreen под Wine).
# Если каталог существует и содержит msedgewebview2.exe — Axon использует именно
# его через WEBVIEW2_BROWSER_EXECUTABLE_FOLDER, минуя evergreen, который под Wine
# роняет browser-процесс (BrowserProcessExited). См. README раздел «WebView2».
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

# --- WebView2 GPU-process fix (реестр) ---
# КОРЕНЬ чёрного экрана под Wine: viz-процесс Chromium при Windows-версии >=8 гонит
# презентацию КАЖДОГО кадра (даже software-bitmap) через DirectComposition
# (DCompositionCreateDevice), которого Wine не реализует (E_NOTIMPL/0x80004001) →
# CHECK/0x80000003 → краш viz → кадр не доходит до окна = ЧЁРНОЕ окно. Лечится
# версией Windows 7 ИМЕННО для msedgewebview2.exe (порог DComp — win8.1; под win7
# software-output идёт через GDI BitBlt, без DComp, и реально копирует пиксели в
# HWND). ВАЖНО: win7 ставится ТОЛЬКО рендереру — основное RazerAxon.exe и префикс
# остаются win10, иначе сервер Razer отдаёт пустой каталог. HW-accel Edge off +
# env-флаги — вспомогательные. Подтверждено живьём (UI/логин рисуются). Источники:
# WineHQ Bug 58921, winetricks #2226, CodeWeavers. Раньше тут ошибочно стоял win81
# (= порог DComp) → именно он давал чёрный экран.
apply_webview2_gpu_fix() {
    # Идемпотентно: применяем только если ещё не настроено. Проверяем HW-accel,
    # env-флаг crash-limit, И что у msedgewebview2.exe именно win7 (НЕ win81 —
    # иначе старые префиксы с win81 не обновятся и останутся чёрными).
    local need=0
    grep -aiq '"HardwareAccelerationModeEnabled"=dword:00000000' "$WINEPREFIX/system.reg" 2>/dev/null || need=1
    grep -aiA2 'AppDefaults\\\\msedgewebview2.exe' "$WINEPREFIX/user.reg" 2>/dev/null | grep -qi '"win7"' || need=1
    grep -aiq 'disable-gpu-process-crash-limit' "$WINEPREFIX/user.reg" 2>/dev/null || need=1
    [ "$need" = 0 ] && return 0

    log "Применяю WebView2 GPU-fix (реестр: HW-accel off + win7 рендереру + env crash-limit для всех запусков)..."
    local reg
    reg="$(mktemp --suffix=.reg)"
    # \\ в .reg-значении = одиночный бэкслеш; флаги бэкслешей не содержат, так что
    # WV2_BROWSER_ARGS пишем как есть. Wine применяет HKCU\Environment ко всем
    # процессам префикса при старте → фикс работает из меню/protocol/GUI, не только
    # из этого скрипта.
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
    WINEDEBUG=-all wine regedit "$reg" >/dev/null 2>&1 || warn "regedit GPU-fix вернул ошибку (проверьте вручную)"
    rm -f "$reg"
    wineserver -w 2>/dev/null || true
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

    # Применить реестр-фикс GPU-процесса (идемпотентно). Главный рычаг против
    # BrowserProcessExited — отключение HW-ускорения Edge через реестр.
    apply_webview2_gpu_fix

    # WebView2 flags. Под Wine viz/GPU-процесс Chromium поднимается даже при
    # --disable-gpu (софтверный композитинг), падает 0x80000003 на
    # DCompositionCreateDevice (E_NOTIMPL в Wine, см. chrome_debug.log) и после
    # 3 крашей browser фаталится «GPU process isn't usable. Goodbye» →
    # BrowserProcessExited. Реестр-политика HardwareAccelerationModeEnabled=0
    # (apply_webview2_gpu_fix) сама по себе цикл не останавливает.
    # --disable-gpu-process-crash-limit — ключевой: снимает лимит «3 краша»,
    # browser живёт при цикличном перезапуске viz (проверено 2026-06-12:
    # >5.5 мин, fatal=0; без флага смерть на ~11с). --disable-gpu-sandbox
    # убирает ещё один путь breakpoint при init GPU-sandbox.
    export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="$WV2_BROWSER_ARGS"

    # Если установлен fixed-version рантайм — используем его (стабильнее evergreen),
    # НО только если он совместим с Axon. Несовместимый рантайм (напр. слишком
    # старый 109) роняет CreateCoreWebView2Environment → UI вообще не стартует.
    # Лаунчер детектит 'Init webview2 failed' в логе и при повторном запуске
    # автоматически откатывается на evergreen (маркер .wv2-fixed-broken).
    local wv2_broken_marker="$WV2_FIXED_DIR/.wv2-fixed-broken"
    if [ -f "$WV2_FIXED_DIR/msedgewebview2.exe" ] && [ ! -f "$wv2_broken_marker" ]; then
        export WEBVIEW2_BROWSER_EXECUTABLE_FOLDER="$WV2_FIXED_DIR"
        log "WebView2: fixed-version рантайм $(basename "$WV2_FIXED_DIR")"
    elif [ -f "$wv2_broken_marker" ]; then
        warn "WebView2: fixed-version помечен несовместимым — использую evergreen"
    else
        warn "WebView2: evergreen-рантайм (fixed-version не найден в $WV2_FIXED_DIR)"
    fi

    # Принудительно software-EGL (Mesa), чтобы NVIDIA EGL под XWayland не сыпал
    # 'failed to create dri2 screen' и не дёргал GPU-процесс WebView2.
    export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
    export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"
    if [ -f /usr/share/glvnd/egl_vendor.d/50_mesa.json ]; then
        export __EGL_VENDOR_LIBRARY_FILENAMES="${__EGL_VENDOR_LIBRARY_FILENAMES:-/usr/share/glvnd/egl_vendor.d/50_mesa.json}"
    fi

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

    # Авто-детект несовместимости fixed-version: если он был активен и WebView2
    # не смог инициализироваться — пометить, чтобы в следующий раз взять evergreen.
    if [ -n "${WEBVIEW2_BROWSER_EXECUTABLE_FOLDER:-}" ]; then
        local axon_log="$WINEPREFIX/drive_c/users/$USER/AppData/Local/Razer/RazerAxon/Log/RazerAxon.log"
        if [ -f "$axon_log" ] && tail -80 "$axon_log" 2>/dev/null | grep -q "Init webview2 failed"; then
            warn "fixed-version WebView2 несовместим (Init webview2 failed) — помечаю и откатываюсь на evergreen"
            touch "$WV2_FIXED_DIR/.wv2-fixed-broken" 2>/dev/null
        fi
    fi

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
