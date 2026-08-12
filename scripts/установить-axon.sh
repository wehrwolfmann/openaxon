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
# =============================================================================

set -uo pipefail

# --- Что можно поменять через переменные окружения ---------------------------

# Отдельный отсек Wine. Менять не обязательно.
WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/openaxon/prefix}"
export WINEPREFIX
export WINEARCH="${WINEARCH:-win64}"
export WINEDEBUG="${WINEDEBUG:--all}"

# Куда складывать скачанные установщики, чтобы не качать их повторно.
КЭШ="${OPENAXON_CACHE:-$HOME/.cache/openaxon}"

# Если установщики уже лежат на диске — можно указать их напрямую и не качать.
AXON_SETUP="${AXON_SETUP:-}"
CENTRAL_SETUP="${CENTRAL_SETUP:-}"

AXON_URL=""; AXON_MD5=""; CENTRAL_URL=""; CENTRAL_MD5=""

# Каталог Razer, из которого берутся ссылки на установщики и их контрольные суммы.
РАЗВЕДКА_URL='https://discovery3.razerapi.com/api/v1/endpoints?tag=prod'
МАНИФЕСТ_ПАРАМЕТРЫ='os=WINDOWS&osver=11&arch=64&mfr=Generic-MFR&model=Generic-MDL0&sku=Generic-SKU&l=en-US'

КОРЕНЬ="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"

# --- Как печатаем сообщения ---------------------------------------------------

З='\033[0;32m'; С='\033[0;34m'; Ж='\033[1;33m'; К='\033[0;31m'; Н='\033[0m'
шаг()    { echo -e "${З}==>${Н} $1"; }
инфо()   { echo -e "${С}  ·${Н} $1"; }
предупр(){ echo -e "${Ж}  !${Н} $1"; }
ошибка() { echo -e "${К}  ✗${Н} $1" >&2; }
стоп()   { ошибка "$1"; exit 1; }

# --- Пути внутри отсека Wine --------------------------------------------------

папка_axon()    { echo "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"; }
axon_exe()      { echo "$(папка_axon)/RazerAxon.exe"; }
папка_central() { echo "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Services/Razer Central"; }
central_exe()   { echo "$(папка_central)/RazerCentralService.exe"; }
папка_webview() { echo "$WINEPREFIX/drive_c/Program Files (x86)/Microsoft/EdgeWebView"; }

# --- Мелкие помощники ---------------------------------------------------------

# Проверить, что нужная программа установлена в системе.
нужна() {
    command -v "$1" &>/dev/null && return 0
    ошибка "В системе не хватает программы «$1»."
    echo   "     Установите её и запустите скрипт снова, например:"
    echo   "       Arch / CachyOS / Manjaro:  sudo pacman -S $2"
    echo   "       Debian / Ubuntu / Mint:    sudo apt install $2"
    echo   "       Fedora:                    sudo dnf install $2"
    exit 1
}

# Перечислить процессы, работающие ИМЕННО в нашем отсеке Wine.
# Сверяем по переменной окружения процесса, а не по имени: чужие программы
# с похожими именами трогать нельзя ни при каких обстоятельствах.
процессы_отсека() {
    local pid отсек
    for pid in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
        отсек="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | sed -n 's/^WINEPREFIX=//p')"
        [ "$отсек" = "$WINEPREFIX" ] && echo "$pid"
    done
}

# Дождаться, пока в отсеке не останется процессов (но не дольше N секунд).
подождать_тишины() {
    local предел="${1:-120}" прошло=0
    while [ "$прошло" -lt "$предел" ]; do
        [ -z "$(процессы_отсека)" ] && return 0
        sleep 5; прошло=$((прошло + 5))
    done
    return 1
}

# Аккуратно закрыть все процессы нашего отсека — по номерам, не по именам.
закрыть_отсек() {
    local pid
    for pid in $(процессы_отсека); do kill -TERM "$pid" 2>/dev/null; done
    sleep 3
    for pid in $(процессы_отсека); do kill -KILL "$pid" 2>/dev/null; done
}

# Скачать файл и сверить контрольную сумму.
скачать() {
    local адрес="$1" файл="$2" сумма="${3:-}" имя="${4:-файл}"
    if [ -s "$файл" ] && [ -n "$сумма" ] && command -v md5sum &>/dev/null; then
        if [ "$(md5sum "$файл" | awk '{print $1}')" = "$сумма" ]; then
            инфо "$имя уже скачан и проверен — качать не нужно"
            return 0
        fi
        предупр "$имя в кэше повреждён — качаю заново"
        rm -f "$файл"
    elif [ -s "$файл" ]; then
        инфо "$имя уже скачан"
        return 0
    fi
    инфо "Качаю $имя …"
    if ! curl -fL --retry 3 --retry-delay 5 -A 'RazerLWI/2.4.0.868' -o "$файл" "$адрес"; then
        rm -f "$файл"
        стоп "Не удалось скачать $имя. Проверьте подключение к интернету."
    fi
    [ "$(head -c 2 "$файл" 2>/dev/null)" = "MZ" ] \
        || { rm -f "$файл"; стоп "Вместо $имя скачалось что-то другое (не программа). Проверьте интернет."; }
    if [ -n "$сумма" ] && command -v md5sum &>/dev/null; then
        local получено; получено="$(md5sum "$файл" | awk '{print $1}')"
        [ "$получено" = "$сумма" ] \
            || { rm -f "$файл"; стоп "$имя скачался с ошибкой (контрольная сумма не совпала)."; }
        инфо "Контрольная сумма $имя совпала — файл подлинный"
    fi
}

# =============================================================================
#  Шаг 1. Проверяем, что в системе есть всё нужное
# =============================================================================

проверить_систему() {
    шаг "Проверяю, что в системе есть всё необходимое"
    нужна wine       wine
    нужна winetricks winetricks
    нужна curl       curl
    нужна python3    python3
    command -v md5sum &>/dev/null || предупр "Нет md5sum — пропущу проверку подлинности скачанных файлов"
    инфо "Wine версии $(wine --version 2>/dev/null)"
    инфо "Отсек Wine: $WINEPREFIX"
}

# =============================================================================
#  Шаг 2. Создаём отдельный отсек Wine
# =============================================================================

создать_отсек() {
    if [ -f "$WINEPREFIX/system.reg" ]; then
        инфо "Отсек Wine уже создан — пропускаю"
        return
    fi
    шаг "Создаю отдельный отсек Wine (первый раз это занимает около минуты)"
    mkdir -p "$(dirname "$WINEPREFIX")" || стоп "Не удаётся создать папку $(dirname "$WINEPREFIX")"
    timeout 300 wine wineboot --init >/dev/null 2>&1
    подождать_тишины 60
    [ -f "$WINEPREFIX/system.reg" ] || стоп "Отсек Wine не создался. Проверьте, что путь $WINEPREFIX находится в вашей домашней папке."
    инфо "Отсек создан"
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

dotnet_стоит() {
    # .NET 4.8 отмечается в реестре числом Release 528040 и выше (0x80eb1).
    grep -aqiE '"Release"=dword:0*8[0-9a-f]eb1' "$WINEPREFIX/system.reg" 2>/dev/null
}

поставить_dotnet() {
    if dotnet_стоит; then
        инфо ".NET Framework 4.8 уже стоит — пропускаю"
        return
    fi
    шаг ".NET Framework 4.8 — самый долгий шаг, 10-30 минут. Можно заняться своими делами."
    winetricks -q dotnet48 >/dev/null 2>&1
    закрыть_отсек
    dotnet_стоит || стоп ".NET Framework 4.8 не установился. Запустите скрипт ещё раз — он продолжит с этого места."
    инфо ".NET Framework 4.8 установлен"
}

# =============================================================================
#  Шаг 4. Возвращаем Windows 10
#
#  Установка .NET подменяет заявленную версию Windows на 7 (проверено: в реестре
#  остаётся build 7601). А установщик Axon отказывается работать на Windows 7 —
#  Razer выпускает его только для Windows 10 и новее. Возвращаем 10 обратно.
# =============================================================================

вернуть_windows10() {
    шаг "Возвращаю версию Windows 10 (установка .NET подменяет её на 7)"
    timeout 120 wine winecfg -v win10 >/dev/null 2>&1
    закрыть_отсек
    if grep -aq '"CurrentBuild"="19045"' "$WINEPREFIX/system.reg" 2>/dev/null; then
        инфо "Заявлена Windows 10, сборка 19045"
    else
        предупр "Не удалось подтвердить Windows 10 — установщик Axon может отказаться работать"
    fi
}

# =============================================================================
#  Шаг 5. Узнаём у Razer адреса установщиков
#
#  Razer публикует их сам, в открытом каталоге, без всякой авторизации. Оттуда же
#  берём контрольные суммы, чтобы убедиться, что скачалось именно то и целиком.
# =============================================================================

спросить_каталог() {
    if [ -n "$AXON_SETUP" ] && [ -n "$CENTRAL_SETUP" ]; then
        инфо "Установщики заданы вручную — каталог Razer не опрашиваю"
        return
    fi
    шаг "Спрашиваю у Razer адреса свежих установщиков"
    local хеш
    хеш="$(curl -fs --max-time 30 "$РАЗВЕДКА_URL" | grep -oP '"hash":"\K[^"]+' | head -1)"
    [ -n "$хеш" ] || стоп "Сервер Razer не отвечает. Проверьте интернет и попробуйте позже."
    local каталог="$КЭШ/каталог.json"
    mkdir -p "$КЭШ"
    curl -fs --max-time 60 -o "$каталог" \
        "https://manifest3.razerapi.com/api/v1/releases/$хеш/tags/prod/products?$МАНИФЕСТ_ПАРАМЕТРЫ" \
        || стоп "Не удалось получить каталог Razer."

    # Достаём две записи: сам Axon и Razer Central (у Razer он называется Natasha).
    local выписка
    выписка="$(python3 - "$каталог" <<'PY'
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
)" || стоп "Не удалось разобрать каталог Razer."

    AXON_URL="$(sed -n '1p' <<<"$выписка")";     AXON_MD5="$(sed -n '2p' <<<"$выписка")"
    CENTRAL_URL="$(sed -n '3p' <<<"$выписка")";  CENTRAL_MD5="$(sed -n '4p' <<<"$выписка")"
    [ -n "$AXON_URL" ]    || стоп "В каталоге Razer нет Razer Axon."
    [ -n "$CENTRAL_URL" ] || стоп "В каталоге Razer нет Razer Central."
    инфо "Адреса получены"
}

скачать_установщики() {
    mkdir -p "$КЭШ"
    if [ -z "$CENTRAL_SETUP" ]; then
        CENTRAL_SETUP="$КЭШ/RazerCentral.exe"
        скачать "$CENTRAL_URL" "$CENTRAL_SETUP" "${CENTRAL_MD5:-}" "Razer Central (около 120 МБ)"
    fi
    if [ -z "$AXON_SETUP" ]; then
        AXON_SETUP="$КЭШ/RazerAxonSetup.exe"
        скачать "$AXON_URL" "$AXON_SETUP" "${AXON_MD5:-}" "Razer Axon (около 60 МБ)"
    fi
}

# =============================================================================
#  Шаг 6. Razer Central
#
#  Это служебная часть Razer, через которую Axon входит в учётную запись. Без неё
#  Axon не показывает вообще никакого окна: он ждёт ответа от Central и висит.
#  Установщик регистрирует службу сам, под именем RzActionSvc.
# =============================================================================

central_стоит() { [ -f "$(central_exe)" ]; }

поставить_central() {
    if central_стоит; then
        инфо "Razer Central уже стоит — пропускаю"
        return
    fi
    шаг "Ставлю Razer Central (нужен Axon для входа) — около 3 минут"
    timeout 900 wine "$CENTRAL_SETUP" /silent >/dev/null 2>&1
    подождать_тишины 180
    закрыть_отсек
    central_стоит || стоп "Razer Central не установился. Запустите скрипт ещё раз."
    инфо "Razer Central установлен"
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

axon_стоит() { [ -f "$(axon_exe)" ]; }

поставить_axon() {
    if axon_стоит; then
        инфо "Razer Axon уже стоит — пропускаю"
        return
    fi
    шаг "Ставлю Razer Axon и движок интерфейса WebView2 — около 5 минут, качается ещё ~700 МБ"
    timeout 1800 wine "$AXON_SETUP" /SP- /VERYSILENT \
        '/DIR=C:\Program Files (x86)\Razer\Razer Axon' \
        /SUPPRESSMSGBOXES /NORESTART >/dev/null 2>&1 &
    local ждём=0
    while [ "$ждём" -lt 1800 ]; do
        sleep 15; ждём=$((ждём + 15))
        if axon_стоит && [ -d "$(папка_webview)/Application" ]; then break; fi
    done
    подождать_тишины 300
    закрыть_отсек
    axon_стоит || стоп "Razer Axon не установился. Запустите скрипт ещё раз."
    инфо "Razer Axon установлен"
    [ -d "$(папка_webview)/Application" ] \
        && инфо "Движок интерфейса WebView2 установлен" \
        || предупр "WebView2 не подтверждён — окно Axon может остаться пустым. Проверьте интернет и повторите запуск."
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

ФЛАГИ_БРАУЗЕРА='--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --disable-gpu-sandbox --disable-features=RendererCodeIntegrity --disable-crash-reporter --disable-renderer-backgrounding --disable-background-timer-throttling'

настроить_отрисовку() {
    шаг "Настраиваю отрисовку окон (без этого окна остаются пустыми)"
    local правки; правки="$(mktemp --suffix=.reg)"
    cat > "$правки" <<REG
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
"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"="$ФЛАГИ_БРАУЗЕРА"
REG
    timeout 120 wine regedit "$правки" >/dev/null 2>&1
    rm -f "$правки"
    закрыть_отсек
    local хорошо=1
    grep -aqF 'AppDefaults\\msedgewebview2.exe'             "$WINEPREFIX/user.reg" 2>/dev/null || хорошо=0
    grep -aqF 'AppDefaults\\CefSharp.BrowserSubprocess.exe' "$WINEPREFIX/user.reg" 2>/dev/null || хорошо=0
    [ "$хорошо" = 1 ] && инфо "Отрисовка настроена" || предупр "Настройку отрисовки подтвердить не удалось — окна могут быть пустыми"
}

# =============================================================================
#  Шаг 9. Ярлык в меню и команда razer-axon
# =============================================================================

сделать_ярлык() {
    шаг "Создаю пункт в меню программ и команду razer-axon"

    local запуск="$HOME/.local/bin/razer-axon"
    mkdir -p "$(dirname "$запуск")"
    cat > "$запуск" <<ЗАПУСК
#!/usr/bin/env bash
# Запуск Razer Axon под Wine. Создан скриптом установки, править не нужно.
export WINEPREFIX="$WINEPREFIX"
export WINEDEBUG=-all
# Рисуем силами процессора: встроенный браузер Razer не переносит попыток
# работать с видеокартой через Wine и без этого роняет свой процесс вывода.
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="$ФЛАГИ_БРАУЗЕРА"

# Держим сеанс Wine открытым: служба Razer Central живёт ровно столько,
# сколько живёт сеанс, и без этого гаснет через несколько секунд.
wineserver -p 2>/dev/null

# Поднимаем службу Razer Central. Если она уже работает — Wine просто скажет
# об этом и ничего не сломается.
wine sc start RzActionSvc >/dev/null 2>&1

cd "\$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon" || exit 1
exec wine RazerAxon.exe -showui "\$@"
ЗАПУСК
    chmod +x "$запуск"
    инфо "Команда: $запуск"

    # Значок берём из репозитория, если скрипт запущен из него.
    local значок=""
    if [ -f "$КОРЕНЬ/axon.png" ]; then
        значок="$HOME/.local/share/icons/razer-axon.png"
        mkdir -p "$(dirname "$значок")"
        cp -f "$КОРЕНЬ/axon.png" "$значок"
    fi

    local ярлык="$HOME/.local/share/applications/razer-axon.desktop"
    mkdir -p "$(dirname "$ярлык")"
    cat > "$ярлык" <<ЯРЛЫК
[Desktop Entry]
Type=Application
Version=1.0
Name=Razer Axon
GenericName=Живые обои
GenericName[en]=Live wallpapers
Comment=Живые обои рабочего стола от Razer
Comment[en]=Live desktop wallpapers by Razer
Exec=$запуск
Icon=${значок:-razer-axon}
Terminal=false
Categories=Graphics;Settings;DesktopSettings;
Keywords=обои;живые обои;фон;рабочий стол;Razer;Axon;wallpaper;
StartupWMClass=razeraxon.exe
ЯРЛЫК
    command -v update-desktop-database &>/dev/null \
        && update-desktop-database "$(dirname "$ярлык")" 2>/dev/null
    инфо "Пункт меню: $ярлык"

    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) предупр "Папки ~/.local/bin нет в PATH — команда razer-axon заработает после перезахода в систему" ;;
    esac
}

# =============================================================================
#  Шаг 10. Убираем за собой
#
#  Установка WebView2 оставляет работающими служебные программы Microsoft Edge
#  Update. Сами они не завершаются никогда и мешают повторным запускам. Гасим их
#  вместе со всем отсеком — строго по номерам процессов нашего отсека.
# =============================================================================

прибраться() {
    шаг "Убираю за собой"
    закрыть_отсек
    инфо "Готово"
}

# =============================================================================
#  Шаг 11. Проверяем, что всё на месте
# =============================================================================

проверить_итог() {
    шаг "Проверяю, что установилось"
    ПРОВАЛОВ=0
    # Первый довод — описание пункта, остальное — команда, которую надо выполнить.
    проверка() {
        local описание="$1"; shift
        if "$@" >/dev/null 2>&1; then
            echo -e "  ${З}✓${Н} $описание"
        else
            echo -e "  ${К}✗${Н} $описание"; ПРОВАЛОВ=$((ПРОВАЛОВ + 1))
        fi
    }
    в_реестре() { grep -aqF "$2" "$WINEPREFIX/$1"; }

    проверка "Razer Axon на месте"                   test -f "$(axon_exe)"
    проверка "Razer Central на месте"                test -f "$(central_exe)"
    проверка "движок интерфейса WebView2 на месте"   test -d "$(папка_webview)/Application"
    проверка ".NET Framework 4.8 установлен"         dotnet_стоит
    проверка "заявлена Windows 10"                   в_реестре system.reg '"CurrentBuild"="19045"'
    проверка "служба Razer Central зарегистрирована" в_реестре system.reg 'RzActionSvc'
    проверка "отрисовка настроена для Axon"          в_реестре user.reg 'AppDefaults\\msedgewebview2.exe'
    проверка "отрисовка настроена для Razer Central" в_реестре user.reg 'AppDefaults\\CefSharp.BrowserSubprocess.exe'
    проверка "команда razer-axon создана"            test -x "$HOME/.local/bin/razer-axon"
    проверка "пункт меню создан"                     test -f "$HOME/.local/share/applications/razer-axon.desktop"
    local провалов="$ПРОВАЛОВ"

    echo
    if [ "$провалов" -eq 0 ]; then
        echo -e "${З}Готово. Razer Axon установлен.${Н}"
        echo
        echo "  Запустить: пункт «Razer Axon» в меню программ"
        echo "             или команда  razer-axon  в терминале"
        echo
        echo -e "  ${Ж}При первом запуске${Н} откроется окно Razer Central."
        echo "  Заводить учётную запись Razer не нужно — нажмите"
        echo "  «Продолжить в качестве гостя», и каталог обоев откроется целиком."
        echo
        echo "  Первое окно наполняется не сразу: дайте ему полминуты."
        echo
        echo "  Удалить всё: rm -rf \"$WINEPREFIX\" \\"
        echo "                     \"$HOME/.local/bin/razer-axon\" \\"
        echo "                     \"$HOME/.local/share/applications/razer-axon.desktop\""
    else
        ошибка "Не хватает $провалов пунктов из списка выше."
        echo   "     Запустите скрипт ещё раз — сделанное он пропустит и доделает остальное."
        exit 1
    fi
}

# =============================================================================

главное() {
    echo
    echo "  Razer Axon для Linux — установка"
    echo "  ────────────────────────────────"
    echo "  Займёт 25-40 минут и скачает около 1 ГБ. Вопросов не будет."
    echo

    проверить_систему
    создать_отсек
    поставить_dotnet        # обязательно ДО Axon, иначе winetricks зависнет навсегда
    вернуть_windows10       # обязательно ПОСЛЕ .NET, он подменяет версию на 7
    спросить_каталог
    скачать_установщики
    поставить_central       # обязательно ДО Axon: у Razer он в очереди раньше
    поставить_axon
    настроить_отрисовку
    сделать_ярлык
    прибраться
    проверить_итог
}

главное "$@"
