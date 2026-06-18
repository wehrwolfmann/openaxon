#!/usr/bin/env bash
# =============================================================================
# install-axon-linux.sh — установка Razer Axon под Wine «для всех» (OpenAxon)
# =============================================================================
#
# Что делает: создаёт изолированный Wine-префикс, настраивает его так, чтобы
# официальный установщик/каталог Razer работал, скачивает официальный
# RazerAxonSetup из манифеста Razer и ставит Axon в Program Files.
#
# Корень проблемы «доступ к серверу невозможен» / зелёный экран и крах
# WPF-установщика подтверждён живьём (см. docs/axon_installer_wine_diagnosis_*.md):
#   1) Нет настоящего .NET Framework 4.8 -> движок установщика падает до сети.
#   2) Wine=Win7 -> сервер Razer отдаёт пустой каталог (Axon требует Win10+).
#   3) WebView2 Runtime отсутствует -> экран каталога рисуется чёрным.
#   4) WPF UI установщика (Razer.Installer.UI.Language.TextBlockTextPlugin)
#      крашится под Wine на measure/layout TextBlock при переходе с экрана EULA
#      (unhandled 0x80131623), НЕЗАВИСИМО от локали и HW-ускорения WPF.
#
# Обход краха №4: НЕ кликаем по WPF-UI установщика. Манифест Razer честно
# отдаёт прямой download_url официального RazerAxonSetup (Inno Setup), который
# ставится в тихом режиме /VERYSILENT без WPF. Мы качаем именно его и проверяем
# контрольную сумму из манифеста. Установщик НЕ патчится — всё легально.
#
# Идемпотентность: повторный запуск пропускает уже сделанные шаги. dotnet48
# и WebView2 ставятся один раз. Если Axon уже установлен — скрипт выходит.
#
# Проверено живьём: префикс /tmp/axon-verify-prefix, Wine 11.10, RTX 4070.
# RazerAxon.exe установился (Program Files (x86)\Razer\Razer Axon, ~230 МБ,
# 660 файлов, реестр Inno «Razer Axon» 2.6.2.0), приложение стартует и доходит
# до экрана логина. Авторизация (логин Razer) — отдельный runtime-шаг.
# =============================================================================

set -uo pipefail

# --- Настройки (можно переопределить через окружение) ------------------------

# Изолированный префикс (НЕ ~/.wine, чтобы не мешать другим приложениям)
WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
export WINEPREFIX

# Кэш загрузок
CACHE_DIR="${OPENAXON_CACHE:-$HOME/.cache/openaxon}"

# URL онлайн-установщика Razer Axon (bootstrap). Прямой dl-линк Razer (стабильный).
# ВНИМАНИЕ: НЕ использовать https://rzr.to/axon — он 302-редиректит на МАРКЕТИНГОВУЮ
# страницу (HTML), а не на .exe (проверено 2026-05-31 на чистом префиксе → bootstrap
# оказывался HTML → движок не распаковывался → «Манифест с Axon не получен»).
# Правильный короткий линк — rzr.to/axon-download → dl.razerzone.com/.../RazerAxonInstaller.exe
# Можно подсунуть локальный файл через AXON_INSTALLER=/путь/RazerAxonInstaller.exe
AXON_INSTALLER_URL="${AXON_INSTALLER_URL:-https://dl.razerzone.com/drivers/Axon/RazerAxonInstaller.exe}"
AXON_INSTALLER="${AXON_INSTALLER:-}"

# Прямой манифест-URL Axon Setup (Inno). Если задан — пропускаем разбор манифеста
# движком и качаем напрямую (быстрее). Иначе извлекаем из манифеста онлайн-движка.
# ВНИМАНИЕ: этот URL содержит timestamp+random id и со временем протухает —
# актуальный всегда лежит в манифесте, разбираемый автоматически (ветка ниже).
AXON_SETUP_URL="${AXON_SETUP_URL:-}"

# WebView2 Evergreen Standalone (x64), стабильный fwlink Microsoft
WEBVIEW2_URL="${WEBVIEW2_URL:-https://go.microsoft.com/fwlink/?linkid=2124701}"

# WebView2 FIXED-VERSION рантайм (CAB). Под Wine evergreen-рантайм роняет
# browser-процесс (BrowserProcessExited) — нестабильность многопроцессного IPC.
# Идея: pin'нутый Chromium может держаться стабильнее.
#
# ВЕРДИКТ (проверено живьём 2026-06-12, Wine 11.10):
#   * 109.0.1518.78 — несовместим: даёт 'Init webview2 failed', UI не стартует.
#   * 133.0.3065.92 — через WEBVIEW2_BROWSER_EXECUTABLE_FOLDER ТОЖЕ даёт
#     'Init webview2 failed' и Axon выходит. Причина НЕ в версии: env-var
#     заставляет Axon уйти в ветку InitWebview2WithAbsolutePath, которая под
#     Wine падает синхронно. Т.е. сам механизм env-var ломает init.
#   * 133.0.3065.92, развёрнутый как EdgeCore\133.0.3065.92 + registry pv=133
#     (БЕЗ env-var) — init ПРОХОДИТ через рабочую primary-ветку, домашний
#     экран рендерится. НО BrowserProcessExited крашит так же, как 149 (~10 с
#     после init). Стабильности 133 НЕ даёт — корень в Mojo IPC Wine, не в
#     версии рантайма. См. docs/axon_installer_wine_diagnosis_*.md.
#
# По умолчанию ВЫКЛ: env-var-путь ломает init (109 и 133), а registry-путь к 133
# не лечит краш. Evergreen 149 хотя бы рендерит home. Включить (НЕ рекомендуется,
# сломает init): INSTALL_WV2_FIXED=1 — скачивает CAB в drive_c/webview2-fixed;
# razer-axon.sh подхватывает через WEBVIEW2_BROWSER_EXECUTABLE_FOLDER и при
# 'Init webview2 failed' авто-откатывается на evergreen (маркер .wv2-fixed-broken).
INSTALL_WV2_FIXED="${INSTALL_WV2_FIXED:-0}"
WV2_FIXED_URL="${WV2_FIXED_URL:-https://github.com/westinyang/WebView2RuntimeArchive/releases/download/133.0.3065.92/Microsoft.WebView2.FixedVersionRuntime.133.0.3065.92.x64.cab}"

# Применить ли OpenAxon-обход авторизации после установки (DLL-патч)
APPLY_AUTH_PATCH="${APPLY_AUTH_PATCH:-0}"

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

# --- Вывод -------------------------------------------------------------------

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[install-axon]${NC} $1"; }
info() { echo -e "${BLUE}[install-axon]${NC} $1"; }
warn() { echo -e "${YELLOW}[install-axon]${NC} $1"; }
err()  { echo -e "${RED}[install-axon]${NC} $1" >&2; }
die()  { err "$1"; exit 1; }

# --- Пути в префиксе ----------------------------------------------------------

axon_dir()  { echo "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"; }
axon_exe()  { echo "$(axon_dir)/RazerAxon.exe"; }
engine_dir(){ echo "$WINEPREFIX/drive_c/windows/Installer/Razer/Installer2"; }
manifest()  { echo "$(engine_dir)/ManifesetCache/manifest.json"; }
wv2_dir()   { echo "$WINEPREFIX/drive_c/Program Files (x86)/Microsoft/EdgeWebView"; }

# --- Проверка зависимостей ----------------------------------------------------

need() { command -v "$1" &>/dev/null || die "Не найдено: $1. Установите: $2"; }

check_deps() {
    need wine       "sudo pacman -S wine  (или ваш менеджер пакетов)"
    need winetricks "sudo pacman -S winetricks"
    need curl       "sudo pacman -S curl"
    need python3    "sudo pacman -S python"
    # md5sum опционален, но желателен для проверки целостности
    command -v md5sum &>/dev/null || warn "md5sum не найден — пропущу проверку контрольной суммы"
}

# --- Хелпер: добить зависший winetricks (известный баг wineserver -w) ----------

kill_wineserver() { timeout 20 wineserver -k 2>/dev/null || true; }

# --- Шаг 1: создать префикс ---------------------------------------------------

setup_prefix() {
    if [ -f "$WINEPREFIX/system.reg" ]; then
        info "Префикс уже существует: $WINEPREFIX (пропускаю wineboot)"
        return
    fi
    log "Создаю Wine-префикс: $WINEPREFIX"
    mkdir -p "$(dirname "$WINEPREFIX")"
    # Wine отказывается создавать конфиг-директорию, если РОДИТЕЛЬ префикса не
    # принадлежит текущему пользователю (напр. префикс прямо в /tmp -> root:root).
    # Ловим это явно, иначе падение всплывёт позже невнятной ошибкой dotnet48.
    local parent; parent="$(dirname "$WINEPREFIX")"
    if [ "$(stat -c %u "$parent" 2>/dev/null)" != "$(id -u)" ] && [ ! -d "$WINEPREFIX" ]; then
        warn "Родитель префикса '$parent' не принадлежит вам — Wine может отказать."
        warn "Выберите путь в вашем \$HOME, напр.: WINEPREFIX=\$HOME/.local/share/openaxon/prefix"
    fi
    WINEDEBUG=-all timeout 180 wine wineboot --init 2>/dev/null || true
    timeout 30 wineserver -w 2>/dev/null || true
    kill_wineserver
    [ -f "$WINEPREFIX/system.reg" ] || die "Префикс не инициализировался ($WINEPREFIX/system.reg нет). Часто: путь не в вашем \$HOME или нет прав. Wine: '...is not owned by you'."
}

# --- Шаг 2: .NET Framework 4.8 ------------------------------------------------
# Release 0x80eb1 (528113) = .NET 4.8. Если уже стоит — пропускаем (часы экономии).

dotnet48_installed() {
    # .NET 4.8 -> Release >= 528040 (0x80eb1 = 528113). Достаточно найти маркер 80eb1+.
    grep -aiqE '"Release"=dword:0*8[0-9a-f]eb1' "$WINEPREFIX/system.reg" 2>/dev/null
}

install_dotnet48() {
    if dotnet48_installed; then
        info ".NET Framework 4.8 уже установлен (пропускаю)"
        return
    fi
    log ".NET Framework 4.8 (winetricks dotnet48) — это может занять 10-30 мин..."
    WINEDEBUG=-all winetricks -q dotnet48 || warn "winetricks dotnet48 завершился с ошибкой (часто из-за зависшего wineserver -w — проверяю результат ниже)"
    kill_wineserver
    dotnet48_installed || die ".NET 4.8 не установился. Повторите запуск скрипта."
    log ".NET Framework 4.8 OK"
}

# --- Шаг 3: версия Windows 10 -------------------------------------------------
# ВАЖНО: dotnet48 внутри себя переключает версию обратно на win7 — поэтому
# win10 ВСЕГДА выставляем ПОСЛЕ dotnet48.

set_win10() {
    log "Выставляю версию Windows 10 (иначе сервер отдаёт пустой каталог)"
    WINEDEBUG=-all timeout 90 wine winecfg -v win10 2>/dev/null || true
    kill_wineserver
    if grep -aiq '"CurrentBuild"="19045"' "$WINEPREFIX/system.reg" 2>/dev/null; then
        log "Windows 10 (build 19045) OK"
    else
        warn "Не удалось подтвердить win10 в реестре — продолжаю, но каталог может быть пуст"
    fi
}

# --- Шаг 4: WebView2 Runtime --------------------------------------------------
# Нужен, чтобы UI каталога/Axon не был чёрным.

webview2_installed() {
    [ -d "$(wv2_dir)/Application" ] && \
      find "$(wv2_dir)/Application" -iname 'msedgewebview2.exe' 2>/dev/null | grep -q .
}

install_webview2() {
    if webview2_installed; then
        info "WebView2 Runtime уже установлен (пропускаю)"
        return
    fi
    local wv2="$CACHE_DIR/MicrosoftEdgeWebView2RuntimeInstaller.exe"
    mkdir -p "$CACHE_DIR"
    if [ ! -s "$wv2" ]; then
        log "Скачиваю WebView2 Evergreen Standalone (~190 МБ)..."
        curl -fL -A "Mozilla/5.0" -o "$wv2" "$WEBVIEW2_URL" || die "Не удалось скачать WebView2"
    fi
    log "Устанавливаю WebView2 Runtime в префикс..."
    WINEDEBUG=-all timeout 360 wine "$wv2" /silent /install 2>/dev/null || true
    kill_wineserver
    webview2_installed || warn "WebView2 не подтверждён — UI Axon может быть чёрным"
}

# --- Шаг 4b (опц.): fixed-version WebView2 рантайм (стабильность под Wine) ------
# Распаковывается в drive_c/webview2-fixed; razer-axon.sh подхватывает его через
# WEBVIEW2_BROWSER_EXECUTABLE_FOLDER. Снижает частоту BrowserProcessExited.

wv2_fixed_dir() { echo "$WINEPREFIX/drive_c/webview2-fixed"; }

install_webview2_fixed() {
    [ "$INSTALL_WV2_FIXED" = "1" ] || { info "Fixed-version WebView2 пропущен (INSTALL_WV2_FIXED=0)"; return; }
    if [ -f "$(wv2_fixed_dir)/msedgewebview2.exe" ]; then
        info "Fixed-version WebView2 уже установлен (пропускаю)"
        return
    fi
    command -v cabextract &>/dev/null || { warn "cabextract не найден (sudo pacman -S cabextract) — fixed-version пропущен"; return; }
    local cab="$CACHE_DIR/wv2-fixed-x64.cab"
    mkdir -p "$CACHE_DIR"
    if [ ! -s "$cab" ]; then
        log "Скачиваю fixed-version WebView2 рантайм (~200 МБ)..."
        curl -fL --retry 3 -o "$cab" "$WV2_FIXED_URL" || { warn "Не удалось скачать fixed-version — останется evergreen"; return; }
    fi
    log "Распаковываю fixed-version WebView2..."
    local tmp="$CACHE_DIR/wv2-fixed-extract"
    rm -rf "$tmp"; mkdir -p "$tmp"
    cabextract -q -d "$tmp" "$cab" || { warn "cabextract упал — останется evergreen"; return; }
    # CAB кладёт всё в подкаталог Microsoft.WebView2.FixedVersionRuntime.*.x64/
    local exe; exe="$(find "$tmp" -iname msedgewebview2.exe 2>/dev/null | head -1)"
    [ -n "$exe" ] || { warn "msedgewebview2.exe не найден в CAB — останется evergreen"; return; }
    rm -rf "$(wv2_fixed_dir)"
    mkdir -p "$(dirname "$(wv2_fixed_dir)")"
    cp -a "$(dirname "$exe")" "$(wv2_fixed_dir)"
    rm -rf "$tmp"
    [ -f "$(wv2_fixed_dir)/msedgewebview2.exe" ] \
        && log "Fixed-version WebView2 установлен: $(wv2_fixed_dir)" \
        || warn "Установка fixed-version не подтверждена — останется evergreen"
}

# --- Шаг 4c: WebView2 GPU-process fix (реестр) --------------------------------
# КОРЕНЬ чёрного экрана под Wine: viz-процесс Chromium при Windows-версии >=8.1
# презентует кадр (даже software) через DirectComposition (Wine не реализует →
# E_NOTIMPL/0x80004001 → CHECK/0x80000003 → краш viz → кадр не доходит в окно =
# ЧЁРНОЕ). Лечится версией Windows 7 ИМЕННО для msedgewebview2.exe: под win7
# software-output идёт через GDI BitBlt (без DComp) и копирует пиксели в HWND.
# win7 — ТОЛЬКО рендереру; RazerAxon.exe и префикс остаются win10 (иначе сервер
# Razer отдаёт пустой каталог). HW-accel Edge off — вспомогательное. Подтверждено
# живьём. Раньше тут стоял win81 (= порог DComp), что и давало чёрный экран.
# Детали: docs/axon_installer_wine_diagnosis_2026_05_31.md, раздел «КОРЕНЬ ПЕРЕУСТАНОВЛЕН».
# Вспомогательные флаги (настоящий фикс — win7 для msedgewebview2.exe выше).
# Пишутся в реестр (HKCU\Environment), чтобы действовать при ЛЮБОМ запуске Axon
# (меню Wine, protocol-handler RazerAxon:, GUI), а не только через razer-axon.sh.
# Флаг --disable-gpu-process-crash-limit УБРАН как избыточный при win7 (он лишь
# маскировал краш-цикл DComp, а win7 устраняет его в корне).
WV2_BROWSER_ARGS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --disable-gpu-sandbox --disable-features=RendererCodeIntegrity --disable-crash-reporter --disable-renderer-backgrounding --disable-background-timer-throttling"

apply_webview2_gpu_fix() {
    log "Реестр: HW-ускорение Edge off + win7 рендереру + env-флаги (GPU-fix для всех запусков)"
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
    WINEDEBUG=-all wine regedit "$reg" >/dev/null 2>&1 || warn "regedit GPU-fix вернул ошибку"
    rm -f "$reg"
    kill_wineserver
    if grep -aiq '"HardwareAccelerationModeEnabled"=dword:00000000' "$WINEPREFIX/system.reg" 2>/dev/null \
       && grep -aiq 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS' "$WINEPREFIX/user.reg" 2>/dev/null; then
        log "GPU-fix применён (HW-accel=0 + env-флаги в реестре)"
    else
        warn "GPU-fix НЕ подтверждён в реестре — WebView2 может циклически крашить"
    fi
}

# --- Шаг 5: получить онлайн-установщик (bootstrap) -----------------------------

fetch_installer() {
    if [ -n "$AXON_INSTALLER" ] && [ -s "$AXON_INSTALLER" ]; then
        info "Использую локальный установщик: $AXON_INSTALLER"
        return
    fi
    AXON_INSTALLER="$CACHE_DIR/RazerAxonInstaller.exe"
    mkdir -p "$CACHE_DIR"
    if [ -s "$AXON_INSTALLER" ]; then
        info "Онлайн-установщик уже скачан: $AXON_INSTALLER"
        return
    fi
    log "Скачиваю онлайн-установщик Razer Axon ($AXON_INSTALLER_URL)..."
    curl -fL -A "RazerLWI/2.4.0.868" -o "$AXON_INSTALLER" "$AXON_INSTALLER_URL" \
        || die "Не удалось скачать установщик. Укажите файл через AXON_INSTALLER=/путь.exe"
    # Проверяем, что это настоящий PE (MZ), а не HTML-лендинг (как у rzr.to/axon).
    if [ "$(head -c 2 "$AXON_INSTALLER" 2>/dev/null)" != "MZ" ]; then
        rm -f "$AXON_INSTALLER"
        die "Скачан не .exe (вероятно HTML-страница). Проверьте AXON_INSTALLER_URL — нужен прямой линк на RazerAxonInstaller.exe (напр. https://dl.razerzone.com/drivers/Axon/RazerAxonInstaller.exe)."
    fi
}

# --- Шаг 6: получить манифест каталога Razer ----------------------------------
# Запускаем bootstrap-установщик: он распаковывает движок и СКАЧИВАЕТ manifest.json
# (с осей win10 — полный каталог с Axon). Мы НЕ кликаем по его WPF-UI (он крашится),
# а через ~60с убиваем процесс — манифест к этому моменту уже на диске.

obtain_manifest() {
    if [ -s "$(manifest)" ] && grep -aiq 'RazerAxonSetup' "$(manifest)" 2>/dev/null; then
        info "Манифест каталога с Axon уже есть (пропускаю запуск bootstrap)"
        return
    fi
    log "Запускаю bootstrap-установщик для получения манифеста (UI игнорируем)..."
    export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-features=RendererCodeIntegrity"
    WINEDEBUG=-all wine "$AXON_INSTALLER" &>/dev/null &
    local pid=$!
    # Ждём появления манифеста с Axon (до ~120с)
    local ok=0
    for _ in $(seq 1 24); do
        sleep 5
        if [ -s "$(manifest)" ] && grep -aiq 'RazerAxonSetup' "$(manifest)" 2>/dev/null; then ok=1; break; fi
    done
    # Глушим bootstrap и его WPF-движок (он бесполезен дальше и крашится в UI)
    kill "$pid" 2>/dev/null || true
    pkill -f RazerInstaller 2>/dev/null || true
    pkill -f RazerAxonInstaller 2>/dev/null || true
    kill_wineserver
    [ "$ok" = 1 ] || die "Манифест с Axon не получен. Проверьте сеть к *.razerapi.com и осверсию win10."
    log "Манифест каталога получен (содержит Razer Axon)"
}

# --- Шаг 7: извлечь download_url + checksum для Axon из манифеста --------------

parse_axon_setup() {
    if [ -n "$AXON_SETUP_URL" ]; then
        AXON_SETUP_CHECKSUM=""
        AXON_SETUP_PARAMS='/SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART'
        info "Использую заданный AXON_SETUP_URL"
        return
    fi
    log "Разбираю манифест: ищу прямой URL официального Axon Setup..."
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
)" || die "Ошибка разбора манифеста"
    AXON_SETUP_URL="$(echo "$out"   | sed -n '1p')"
    AXON_SETUP_CHECKSUM="$(echo "$out" | sed -n '2p')"
    AXON_SETUP_PARAMS="$(echo "$out" | sed -n '3p')"
    [ -n "$AXON_SETUP_URL" ] || die "В манифесте нет download_url для Axon"
    info "Axon Setup URL: $AXON_SETUP_URL"
    info "Параметры установки: $AXON_SETUP_PARAMS"
}

# --- Шаг 8: скачать и проверить официальный Axon Setup (Inno) ------------------

download_axon_setup() {
    AXON_SETUP="$CACHE_DIR/RazerAxonSetup.exe"
    mkdir -p "$CACHE_DIR"
    log "Скачиваю официальный Razer Axon Setup (~88 МБ)..."
    curl -fL -A "RazerLWI/2.4.0.868" -o "$AXON_SETUP" "$AXON_SETUP_URL" \
        || die "Не удалось скачать Axon Setup (URL мог протухнуть — перезапустите для свежего манифеста)"
    if [ -n "${AXON_SETUP_CHECKSUM:-}" ] && command -v md5sum &>/dev/null; then
        local got; got="$(md5sum "$AXON_SETUP" | awk '{print $1}')"
        if [ "$got" = "$AXON_SETUP_CHECKSUM" ]; then
            log "Контрольная сумма MD5 совпала ($got) — файл подлинный"
        else
            die "MD5 не совпал! ожид. $AXON_SETUP_CHECKSUM, получено $got"
        fi
    fi
}

# --- Шаг 9: тихая установка Axon (Inno Setup, без WPF) -------------------------

install_axon() {
    log "Устанавливаю Razer Axon (тихий режим Inno Setup)..."
    export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-features=RendererCodeIntegrity"
    # shellcheck disable=SC2086
    WINEDEBUG=-all wine "$AXON_SETUP" $AXON_SETUP_PARAMS \
        '/DIR=C:\Program Files (x86)\Razer\Razer Axon' &>/dev/null &
    local pid=$!
    # Ждём появления RazerAxon.exe (до ~180с)
    for _ in $(seq 1 36); do
        sleep 5
        [ -f "$(axon_exe)" ] && break
    done
    wait "$pid" 2>/dev/null || true
    kill_wineserver
    [ -f "$(axon_exe)" ] || die "RazerAxon.exe не появился — установка не завершилась"
    local sz; sz="$(du -sh "$(axon_dir)" 2>/dev/null | awk '{print $1}')"
    log "Установка завершена: $(axon_exe) (папка $sz)"
}

# --- Шаг 10 (опц.): применить обход авторизации OpenAxon -----------------------

apply_auth() {
    [ "$APPLY_AUTH_PATCH" = "1" ] || { info "Авторизация (DLL-патч) пропущена. Запуск: razer-axon.sh"; return; }
    local patch="$SCRIPT_DIR/patch/RazerAxon.UserManager.dll"
    local target="$(axon_dir)/RazerAxon.UserManager.dll"
    if [ -f "$patch" ] && [ -f "$target" ]; then
        [ -f "$target.orig" ] || cp "$target" "$target.orig"
        cp "$patch" "$target"
        log "Применён OpenAxon DLL-патч авторизации"
    else
        warn "DLL-патч или целевой файл не найден — пропущено"
    fi
}

# --- Главная ------------------------------------------------------------------

main() {
    info "OpenAxon — установка Razer Axon под Wine"
    info "Префикс: $WINEPREFIX"
    check_deps

    # Идемпотентность: уже установлено?
    if [ -f "$(axon_exe)" ]; then
        log "Razer Axon уже установлен: $(axon_exe)"
        install_webview2_fixed
        apply_webview2_gpu_fix
        apply_auth
        log "Готово. Запуск: WINEPREFIX=\"$WINEPREFIX\" $SCRIPT_DIR/razer-axon.sh"
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
    log " Razer Axon установлен в:"
    log "   $(axon_dir)"
    log " Запуск (с авторизацией):"
    log "   WINEPREFIX=\"$WINEPREFIX\" $SCRIPT_DIR/razer-axon.sh"
    log "=========================================================="
}

main "$@"
