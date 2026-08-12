#!/usr/bin/env bash
# =============================================================================
#  Razer Axon на Linux — установка одной командой
# =============================================================================
#
#  Что это. Razer Axon — программа «живых обоев» от Razer. Она существует только
#  для Windows. Этот скрипт ставит её на Linux через Wine — прослойку, которая
#  умеет запускать программы для Windows.
#
#  Что делать. Просто запустить:
#
#      ./установить-axon.sh
#
#  Больше ничего вводить не нужно: скрипт не задаёт вопросов и всё делает сам.
#  Займёт примерно 25-40 минут и скачает около 1 ГБ. По ходу он печатает, чем
#  занят. Если прервать на середине — можно запустить ещё раз, уже сделанные
#  шаги будут пропущены.
#
#  Куда всё встанет. В отдельную папку ~/.local/share/openaxon/prefix. Это
#  «свой отсек» для Wine: ничего за его пределами не меняется, а удалить всё
#  можно, просто стерев эту папку.
#
#  Что появится после установки:
#      * пункт «Razer Axon» в меню программ;
#      * команда  razer-axon  в терминале.
#
#  ⚠ Первый запуск. Откроется окно Razer Central с выбором входа. Аккаунт Razer
#  заводить НЕ обязательно — достаточно нажать «Продолжить в качестве гостя»,
#  и каталог обоев откроется целиком.
#
#  Проверено живьём 2026-08-12 на Wine 11.15: Razer Axon 2.9.1.0, Razer Central
#  7.23.0.1220, WebView2 151.0.4129.78. Подробности замеров и разбор каждого
#  шага — в docs/установка_под_wine_2_9_1_0.md.
#
#  Имена переменных здесь латиницей не от хорошей жизни: bash не разрешает
#  кириллицу в именах переменных. Все сообщения и пояснения — по-русски.
# =============================================================================

set -uo pipefail

# --- Что можно поменять через переменные окружения ---------------------------

# Отдельный отсек Wine. Менять не обязательно.
WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
export WINEPREFIX
export WINEARCH="${WINEARCH:-win64}"
export WINEDEBUG="${WINEDEBUG:--all}"

# Куда складывать скачанные установщики, чтобы не качать их повторно.
CACHE="${OPENAXON_CACHE:-$HOME/.cache/openaxon}"

# Если установщики уже лежат на диске — можно указать их напрямую и не качать.
AXON_SETUP="${AXON_SETUP:-}"
CENTRAL_SETUP="${CENTRAL_SETUP:-}"

AXON_URL=""; AXON_MD5=""; CENTRAL_URL=""; CENTRAL_MD5=""

# Каталог Razer, из которого берутся ссылки на установщики и их контрольные суммы.
DISCOVERY_URL='https://discovery3.razerapi.com/api/v1/endpoints?tag=prod'
MANIFEST_QUERY='os=WINDOWS&osver=11&arch=64&mfr=Generic-MFR&model=Generic-MDL0&sku=Generic-SKU&l=en-US'

ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"

# --- Как печатаем сообщения ---------------------------------------------------

C_OK='\033[0;32m'; C_INFO='\033[0;34m'; C_WARN='\033[1;33m'; C_ERR='\033[0;31m'; C_OFF='\033[0m'
step()  { echo -e "${C_OK}==>${C_OFF} $1"; }
note()  { echo -e "${C_INFO}  ·${C_OFF} $1"; }
warn()  { echo -e "${C_WARN}  !${C_OFF} $1"; }
fail()  { echo -e "${C_ERR}  ✗${C_OFF} $1" >&2; }
abort() { fail "$1"; exit 1; }

# --- Пути внутри отсека Wine --------------------------------------------------

axon_dir()     { echo "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"; }
axon_exe()     { echo "$(axon_dir)/RazerAxon.exe"; }
central_dir()  { echo "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Services/Razer Central"; }
central_exe()  { echo "$(central_dir)/RazerCentralService.exe"; }
webview_dir()  { echo "$WINEPREFIX/drive_c/Program Files (x86)/Microsoft/EdgeWebView"; }

# --- Мелкие помощники ---------------------------------------------------------

# Проверить, что нужная программа установлена в системе.
require() {
    command -v "$1" &>/dev/null && return 0
    fail "В системе не хватает программы «$1»."
    echo "     Установите её и запустите скрипт снова, например:"
    echo "       Arch / CachyOS / Manjaro:  sudo pacman -S $2"
    echo "       Debian / Ubuntu / Mint:    sudo apt install $2"
    echo "       Fedora:                    sudo dnf install $2"
    exit 1
}

# Перечислить процессы, работающие ИМЕННО в нашем отсеке Wine.
# Сверяем по переменной окружения процесса, а не по имени: чужие программы
# с похожими именами трогать нельзя ни при каких обстоятельствах.
prefix_pids() {
    local pid owner
    for pid in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
        # Чужие процессы читать не дают — это нормально, молча пропускаем.
        [ -r "/proc/$pid/environ" ] || continue
        owner="$(tr '\0' '\n' 2>/dev/null < "/proc/$pid/environ" | sed -n 's/^WINEPREFIX=//p')"
        [ "$owner" = "$WINEPREFIX" ] && echo "$pid"
    done
    return 0
}

# Дождаться, пока в отсеке не останется работающих программ (но не дольше N секунд).
wait_quiet() {
    local limit="${1:-120}" spent=0
    while [ "$spent" -lt "$limit" ]; do
        [ -z "$(prefix_pids)" ] && return 0
        sleep 5; spent=$((spent + 5))
    done
    return 1
}

# Аккуратно закрыть все программы нашего отсека — по номерам, не по именам.
close_prefix() {
    local pid
    for pid in $(prefix_pids); do kill -TERM "$pid" 2>/dev/null; done
    sleep 3
    for pid in $(prefix_pids); do kill -KILL "$pid" 2>/dev/null; done
    return 0
}

# Скачать файл и сверить контрольную сумму.
fetch() {
    local url="$1" file="$2" md5="${3:-}" title="${4:-файл}" got
    if [ -s "$file" ] && [ -n "$md5" ] && command -v md5sum &>/dev/null; then
        if [ "$(md5sum "$file" | awk '{print $1}')" = "$md5" ]; then
            note "$title уже скачан и проверен — качать не нужно"
            return 0
        fi
        warn "$title в кэше повреждён — качаю заново"
        rm -f "$file"
    elif [ -s "$file" ]; then
        note "$title уже скачан"
        return 0
    fi
    note "Качаю $title …"
    if ! curl -fL --retry 3 --retry-delay 5 -A 'RazerLWI/2.4.0.868' -o "$file" "$url"; then
        rm -f "$file"
        abort "Не удалось скачать $title. Проверьте подключение к интернету."
    fi
    if [ "$(head -c 2 "$file" 2>/dev/null)" != "MZ" ]; then
        rm -f "$file"
        abort "Вместо «$title» скачалось что-то другое (не программа). Проверьте интернет."
    fi
    if [ -n "$md5" ] && command -v md5sum &>/dev/null; then
        got="$(md5sum "$file" | awk '{print $1}')"
        if [ "$got" != "$md5" ]; then
            rm -f "$file"
            abort "$title скачался с ошибкой (контрольная сумма не совпала)."
        fi
        note "Контрольная сумма «$title» совпала — файл подлинный"
    fi
}

# =============================================================================
#  Шаг 1. Проверяем, что в системе есть всё нужное
# =============================================================================

check_system() {
    step "Проверяю, что в системе есть всё необходимое"
    require wine       wine
    require winetricks winetricks
    require curl       curl
    require python3    python3
    command -v md5sum &>/dev/null || warn "Нет md5sum — пропущу проверку подлинности скачанных файлов"
    note "Wine версии $(wine --version 2>/dev/null)"
    note "Отсек Wine: $WINEPREFIX"
}

# =============================================================================
#  Шаг 2. Создаём отдельный отсек Wine
# =============================================================================

make_prefix() {
    if [ -f "$WINEPREFIX/system.reg" ]; then
        note "Отсек Wine уже создан — пропускаю"
        return
    fi
    step "Создаю отдельный отсек Wine (первый раз это занимает около минуты)"
    mkdir -p "$(dirname "$WINEPREFIX")" || abort "Не удаётся создать папку $(dirname "$WINEPREFIX")"
    timeout 300 wine wineboot --init >/dev/null 2>&1
    wait_quiet 60
    [ -f "$WINEPREFIX/system.reg" ] \
        || abort "Отсек Wine не создался. Проверьте, что путь $WINEPREFIX находится в вашей домашней папке."
    note "Отсек создан"
}

# =============================================================================
#  Шаг 3. .NET Framework 4.8
#
#  Razer Central написан на .NET Framework и без него отказывается ставиться:
#  показывает окно «Technology Required» и ждёт нажатия кнопки, из-за чего
#  «тихая» установка встаёт намертво. Ставим .NET заранее.
#
#  ⚠ Порядок здесь важен. Установка Axon оставляет в отсеке вечно работающую
#  служебную программу Microsoft Edge Update, а winetricks на каждом шаге ждёт,
#  пока все программы отсека завершатся. Поэтому .NET ставим ПЕРВЫМ, до Axon,
#  иначе установка .NET зависнет навсегда.
# =============================================================================

has_dotnet() {
    # .NET 4.8 отмечается в реестре числом Release 528040 и выше (0x80eb1).
    grep -aqiE '"Release"=dword:0*8[0-9a-f]eb1' "$WINEPREFIX/system.reg" 2>/dev/null
}

install_dotnet() {
    if has_dotnet; then
        note ".NET Framework 4.8 уже стоит — пропускаю"
        return
    fi
    step ".NET Framework 4.8 — самый долгий шаг, 10-30 минут. Можно заняться своими делами."
    winetricks -q dotnet48 >/dev/null 2>&1
    close_prefix
    has_dotnet || abort ".NET Framework 4.8 не установился. Запустите скрипт ещё раз — он продолжит с этого места."
    note ".NET Framework 4.8 установлен"
}

# =============================================================================
#  Шаг 4. Возвращаем Windows 10
#
#  Установка .NET подменяет заявленную версию Windows на 7 (проверено: в реестре
#  остаётся build 7601). А установщик Axon отказывается работать на Windows 7 —
#  Razer выпускает его только для Windows 10 и новее. Возвращаем 10 обратно.
# =============================================================================

set_win10() {
    step "Возвращаю версию Windows 10 (установка .NET подменяет её на 7)"
    timeout 120 wine winecfg -v win10 >/dev/null 2>&1
    close_prefix
    if grep -aqF '"CurrentBuild"="19045"' "$WINEPREFIX/system.reg" 2>/dev/null; then
        note "Заявлена Windows 10, сборка 19045"
    else
        warn "Не удалось подтвердить Windows 10 — установщик Axon может отказаться работать"
    fi
}

# =============================================================================
#  Шаг 5. Узнаём у Razer адреса установщиков
#
#  Razer публикует их сам, в открытом каталоге, без всякой авторизации. Оттуда же
#  берём контрольные суммы, чтобы убедиться, что скачалось именно то и целиком.
# =============================================================================

ask_catalog() {
    if [ -n "$AXON_SETUP" ] && [ -n "$CENTRAL_SETUP" ]; then
        note "Установщики заданы вручную — каталог Razer не опрашиваю"
        return
    fi
    step "Спрашиваю у Razer адреса свежих установщиков"
    local hash catalog answer
    hash="$(curl -fs --max-time 30 "$DISCOVERY_URL" | grep -oP '"hash":"\K[^"]+' | head -1)"
    [ -n "$hash" ] || abort "Сервер Razer не отвечает. Проверьте интернет и попробуйте позже."
    catalog="$CACHE/каталог.json"
    mkdir -p "$CACHE"
    curl -fs --max-time 60 -o "$catalog" \
        "https://manifest3.razerapi.com/api/v1/releases/$hash/tags/prod/products?$MANIFEST_QUERY" \
        || abort "Не удалось получить каталог Razer."

    # Достаём две записи: сам Axon и Razer Central (у Razer он называется Natasha).
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
)" || abort "Не удалось разобрать каталог Razer."

    AXON_URL="$(sed -n '1p' <<<"$answer")";    AXON_MD5="$(sed -n '2p' <<<"$answer")"
    CENTRAL_URL="$(sed -n '3p' <<<"$answer")"; CENTRAL_MD5="$(sed -n '4p' <<<"$answer")"
    [ -n "$AXON_URL" ]    || abort "В каталоге Razer нет Razer Axon."
    [ -n "$CENTRAL_URL" ] || abort "В каталоге Razer нет Razer Central."
    note "Адреса получены"
}

download_installers() {
    mkdir -p "$CACHE"
    if [ -z "$CENTRAL_SETUP" ]; then
        CENTRAL_SETUP="$CACHE/RazerCentral.exe"
        fetch "$CENTRAL_URL" "$CENTRAL_SETUP" "$CENTRAL_MD5" "Razer Central (около 120 МБ)"
    fi
    if [ -z "$AXON_SETUP" ]; then
        AXON_SETUP="$CACHE/RazerAxonSetup.exe"
        fetch "$AXON_URL" "$AXON_SETUP" "$AXON_MD5" "Razer Axon (около 60 МБ)"
    fi
}

# =============================================================================
#  Шаг 6. Razer Central
#
#  Это служебная часть Razer, через которую Axon входит в учётную запись. Без неё
#  Axon не показывает вообще никакого окна: он ждёт ответа от Central и висит.
#  Установщик регистрирует службу сам, под именем RzActionSvc.
# =============================================================================

has_central() { [ -f "$(central_exe)" ]; }

install_central() {
    if has_central; then
        note "Razer Central уже стоит — пропускаю"
        return
    fi
    step "Ставлю Razer Central (нужен Axon для входа) — около 3 минут"
    timeout 900 wine "$CENTRAL_SETUP" /silent >/dev/null 2>&1
    wait_quiet 180
    close_prefix
    has_central || abort "Razer Central не установился. Запустите скрипт ещё раз."
    note "Razer Central установлен"
}

# =============================================================================
#  Шаг 7. Сам Razer Axon
#
#  Его установщик по ходу дела скачивает с серверов Microsoft движок WebView2 —
#  на нём нарисован весь интерфейс Axon. Это ещё около 700 МБ и несколько минут.
#
#  Ключ подавления окон пишется как /SUPPRESSMSGBOXES (с двумя «p»). В своём
#  описании Razer опечатался и пишет /SUPRESSMSGBOXES — такой ключ просто
#  игнорируется, и при любой заминке установка молча встаёт на невидимом окне.
# =============================================================================

has_axon() { [ -f "$(axon_exe)" ]; }

install_axon() {
    if has_axon; then
        note "Razer Axon уже стоит — пропускаю"
        return
    fi
    step "Ставлю Razer Axon и движок интерфейса WebView2 — около 5 минут, качается ещё ~700 МБ"
    timeout 1800 wine "$AXON_SETUP" /SP- /VERYSILENT \
        '/DIR=C:\Program Files (x86)\Razer\Razer Axon' \
        /SUPPRESSMSGBOXES /NORESTART >/dev/null 2>&1 &
    local spent=0
    while [ "$spent" -lt 1800 ]; do
        sleep 15; spent=$((spent + 15))
        if has_axon && [ -d "$(webview_dir)/Application" ]; then break; fi
    done
    wait_quiet 300
    close_prefix
    has_axon || abort "Razer Axon не установился. Запустите скрипт ещё раз."
    note "Razer Axon установлен"
    if [ -d "$(webview_dir)/Application" ]; then
        note "Движок интерфейса WebView2 установлен"
    else
        warn "WebView2 не подтверждён — окно Axon может остаться пустым. Проверьте интернет и повторите запуск."
    fi
}

# =============================================================================
#  Шаг 8. Настройка отрисовки
#
#  Обе программы Razer рисуют интерфейс встроенным браузером, а тот пытается
#  выводить картинку через способ, которого в Wine пока нет (DirectComposition).
#  Из-за этого окно остаётся пустым. Лечится тем, что ИМЕННО браузерным
#  подпрограммам заявляется Windows 7 — на ней используется старый способ вывода,
#  который в Wine работает. Самим программам Razer при этом по-прежнему заявлена
#  Windows 10, иначе они откажутся работать.
#
#  У Axon браузер называется msedgewebview2.exe, у Razer Central —
#  CefSharp.BrowserSubprocess.exe. Настраивать нужно оба.
# =============================================================================

BROWSER_FLAGS='--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --disable-gpu-sandbox --disable-features=RendererCodeIntegrity --disable-crash-reporter --disable-renderer-backgrounding --disable-background-timer-throttling'

setup_rendering() {
    step "Настраиваю отрисовку окон (без этого окна остаются пустыми)"
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
REG
    timeout 120 wine regedit "$reg" >/dev/null 2>&1
    rm -f "$reg"
    close_prefix
    local ok=1
    grep -aqF 'AppDefaults\\msedgewebview2.exe'             "$WINEPREFIX/user.reg" 2>/dev/null || ok=0
    grep -aqF 'AppDefaults\\CefSharp.BrowserSubprocess.exe' "$WINEPREFIX/user.reg" 2>/dev/null || ok=0
    if [ "$ok" = 1 ]; then
        note "Отрисовка настроена"
    else
        warn "Настройку отрисовки подтвердить не удалось — окна могут быть пустыми"
    fi
}

# =============================================================================
#  Шаг 9. Ярлык в меню и команда razer-axon
# =============================================================================

make_launcher() {
    step "Создаю пункт в меню программ и команду razer-axon"

    local launcher="$HOME/.local/bin/razer-axon"
    mkdir -p "$(dirname "$launcher")"
    cat > "$launcher" <<LAUNCHER
#!/usr/bin/env bash
# Запуск Razer Axon под Wine. Создан скриптом установки, править не нужно.
export WINEPREFIX="$WINEPREFIX"
export WINEDEBUG=-all
# Рисуем силами процессора: встроенный браузер Razer не переносит попыток
# работать с видеокартой через Wine и без этого роняет свой процесс вывода.
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="$BROWSER_FLAGS"

# Держим сеанс Wine открытым: служба Razer Central живёт ровно столько,
# сколько живёт сеанс, и без этого гаснет через несколько секунд.
wineserver -p 2>/dev/null

# Поднимаем службу Razer Central. Если она уже работает — Wine просто скажет
# об этом и ничего не сломается.
wine sc start RzActionSvc >/dev/null 2>&1

cd "\$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon" || exit 1
exec wine RazerAxon.exe -showui "\$@"
LAUNCHER
    chmod +x "$launcher"
    note "Команда: $launcher"

    # Значок берём из репозитория, если скрипт запущен из него.
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
GenericName=Живые обои
GenericName[en]=Live wallpapers
Comment=Живые обои рабочего стола от Razer
Comment[en]=Live desktop wallpapers by Razer
Exec=$launcher
Icon=${icon:-razer-axon}
Terminal=false
Categories=Graphics;Settings;DesktopSettings;
Keywords=обои;живые обои;фон;рабочий стол;Razer;Axon;wallpaper;
StartupWMClass=razeraxon.exe
DESKTOP
    command -v update-desktop-database &>/dev/null \
        && update-desktop-database "$(dirname "$desktop")" 2>/dev/null
    note "Пункт меню: $desktop"

    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) warn "Папки ~/.local/bin нет в PATH — команда razer-axon заработает после перезахода в систему" ;;
    esac
}

# =============================================================================
#  Шаг 10. Убираем за собой
#
#  Установка WebView2 оставляет работающими служебные программы Microsoft Edge
#  Update. Сами они не завершаются никогда и мешают повторным запускам. Гасим их
#  вместе со всем отсеком — строго по номерам процессов нашего отсека.
# =============================================================================

cleanup() {
    step "Убираю за собой"
    close_prefix
    note "Готово"
}

# =============================================================================
#  Шаг 11. Проверяем, что всё на месте
# =============================================================================

FAILED=0

verify() {
    step "Проверяю, что установилось"
    FAILED=0
    # Первый довод — описание пункта, остальное — команда, которую надо выполнить.
    check() {
        local title="$1"; shift
        if "$@" >/dev/null 2>&1; then
            echo -e "  ${C_OK}✓${C_OFF} $title"
        else
            echo -e "  ${C_ERR}✗${C_OFF} $title"; FAILED=$((FAILED + 1))
        fi
    }
    in_registry() { grep -aqF "$2" "$WINEPREFIX/$1"; }

    check "Razer Axon на месте"                   test -f "$(axon_exe)"
    check "Razer Central на месте"                test -f "$(central_exe)"
    check "движок интерфейса WebView2 на месте"   test -d "$(webview_dir)/Application"
    check ".NET Framework 4.8 установлен"         has_dotnet
    check "заявлена Windows 10"                   in_registry system.reg '"CurrentBuild"="19045"'
    check "служба Razer Central зарегистрирована" in_registry system.reg 'RzActionSvc'
    check "отрисовка настроена для Axon"          in_registry user.reg 'AppDefaults\\msedgewebview2.exe'
    check "отрисовка настроена для Razer Central" in_registry user.reg 'AppDefaults\\CefSharp.BrowserSubprocess.exe'
    check "команда razer-axon создана"            test -x "$HOME/.local/bin/razer-axon"
    check "пункт меню создан"                     test -f "$HOME/.local/share/applications/razer-axon.desktop"

    echo
    if [ "$FAILED" -eq 0 ]; then
        echo -e "${C_OK}Готово. Razer Axon установлен.${C_OFF}"
        echo
        echo "  Запустить: пункт «Razer Axon» в меню программ"
        echo "             или команда  razer-axon  в терминале"
        echo
        echo -e "  ${C_WARN}При первом запуске${C_OFF} откроется окно Razer Central."
        echo "  Заводить учётную запись Razer не нужно — нажмите"
        echo "  «Продолжить в качестве гостя», и каталог обоев откроется целиком."
        echo
        echo "  Первое окно наполняется не сразу: дайте ему полминуты."
        echo
        echo "  Удалить всё:"
        echo "    rm -rf \"$WINEPREFIX\" \\"
        echo "           \"$HOME/.local/bin/razer-axon\" \\"
        echo "           \"$HOME/.local/share/applications/razer-axon.desktop\""
    else
        fail "Не хватает $FAILED пунктов из списка выше."
        echo "     Запустите скрипт ещё раз — сделанное он пропустит и доделает остальное."
        exit 1
    fi
}

# =============================================================================

main() {
    echo
    echo "  Razer Axon для Linux — установка"
    echo "  ────────────────────────────────"
    echo "  Займёт 25-40 минут и скачает около 1 ГБ. Вопросов не будет."
    echo

    check_system
    make_prefix
    install_dotnet      # обязательно ДО Axon, иначе winetricks зависнет навсегда
    set_win10           # обязательно ПОСЛЕ .NET, он подменяет версию на 7
    ask_catalog
    download_installers
    install_central     # обязательно ДО Axon: у Razer он в очереди раньше
    install_axon
    setup_rendering
    make_launcher
    cleanup
    verify
}

main "$@"
