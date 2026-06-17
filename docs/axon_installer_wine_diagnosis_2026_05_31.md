# Razer Axon — диагностика ОНЛАЙН-УСТАНОВЩИКА под Wine: «доступ к серверу невозможен» (2026-05-31)

Автор работ: Wehrwolfmann. Документ — отдельный от
`openaxon_wine_axon_install_2026_05_31.md` (тот про запуск УЖЕ установленного app).
Здесь — почему НЕ ПРОХОДИТ сам онлайн-установщик `RazerAxonInstaller.exe` у новых
пользователей под Wine, и как сделать установку рабочей «для всех».

## TL;DR (результат, подтверждено живьём)

Зелёный экран «ДОСТУП К СЕРВЕРУ НЕВОЗМОЖЕН / Услуга отключена / Проверьте» вызывается
**ДВУМЯ независимыми причинами**, обе на стороне Wine-конфигурации, не сервера:

1. **Нет настоящего .NET Framework 4.8.** `RazerAxonInstaller.exe` — это DotNetZip-SFX,
   который распаковывает оффлайн в `C:\windows\Installer\Razer\Installer2\App\` настоящий
   движок `RazerInstaller.exe` (.NET Framework **v4.8**, не .NET Core). На голом Wine с
   wine-mono движок **падает ещё до сети** (`mscoree:LoadLibraryShim error reading registry
   key for installroot` + mono assertion `gmisc-win32.c:138 'filename != NULL'`). Сеть даже
   не начинается.

2. **Wine представляется как Windows 7 → сервер легитимно отдаёт пустой каталог.** После
   установки `winetricks dotnet48` движок запускается и УСПЕШНО ходит по HTTPS (TLS ok, HTTP
   200), НО шлёт `osver=7`. Сервер Razer на `osver=7` возвращает **пустой список продуктов**
   `{"data":{"items":[]}}` (Axon требует Win10+). Установщик трактует пустой каталог как
   «услуга недоступна» → ТОТ ЖЕ зелёный экран, несмотря на HTTP 200.

**Фикс «для всех» (путь A, проверен живьём):**
`winetricks dotnet48` + `winetricks win10` в префиксе. После этого установщик шлёт
`osver=10`, получает полный каталог (Synapse 4, Chroma, Cortex, **Razer Axon**), грузит
карточки продуктов (`Axon/logo.png`, `Axon/media_*.mp4` и т.д., 89× HTTP 200) и показывает
нормальный экран «RAZER GAMING SOFTWARE / Идёт подготовка…». **Зелёный экран ошибки
исчез.** Уверенность ~90% (см. границы в конце).

Это НЕ баг Wine — Wine ведёт себя корректно (TLS/winhttp/secur32 работают, сертификаты
проходят `netconn_verify_cert returning 0`). Это вопрос **конфигурации префикса**.

---

## (1) Точка падения установщика — что именно, где, лог-цитаты

Тест-префикс: `~/.cache/axon-test-prefix` (НЕ рабочий `~/.wine`). Wine 11.10.
Все запуски с таймаутами 90–150с. Рабочий префикс и Rexon-код не трогались.

### Архитектура установщика (RE)
- `~/Загрузки/RazerAxonInstaller.exe` = **DotNetZip Command-Line Self Extractor** (native
  i386 stub). При запуске:
  - быстрый `wininet:InternetOpenW` (проверка связи, успешно),
  - **распаковывает 84 файла / ~40 МБ оффлайн** в
    `C:\windows\Installer\Razer\Installer2\App\` — это движок `RazerInstaller.exe` +
    AWS Kinesis (телеметрия) + BLE/dongle модули + конфиги. **Самого Axon в SFX НЕТ** —
    он докачивается с сервера.
  - запускает `RazerInstaller.exe` через `mscoree` (.NET).
- `RazerInstaller.exe` — PE32 **Mono/.NET assembly**, рядом лежит
  `RazerInstaller.exe.config` с жёстким требованием:
  `<supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.8" />`.
- Endpoint'ы — в распакованном `App/InstallerConfiguration.xml` (открытым текстом):
  ```xml
  <DiscoveryServerRoot>discovery3.razerapi.com</DiscoveryServerRoot>
  <DiscoveryEndpointName>prod</DiscoveryEndpointName>
  <ManifestServerRoot>manifest3.razerapi.com</ManifestServerRoot>
  ```

### Падение №1 — на голом Wine (wine-mono), ДО сети
```
00ec:err:mscoree:LoadLibraryShim error reading registry key for installroot
/builds/mono/wine-mono/.../mono/eglib/gmisc-win32.c:138: assertion 'filename != NULL' failed
```
Движок не исполняется → пустой `ManifesetCache/manifest.json` (`{"items":[]}`), нулевой
`DownloadCache` → зелёный экран. Это первое, что видит новый пользователь.

### Падение №2 — после `dotnet48`, но Wine=Win7
С настоящим .NET 4.8 движок запускается и реально работает по сети. Лог
(`+winhttp,+secur32`) показывает успешные вызовы:
```
winhttp:send_request full request:
  GET /api/v1/endpoints  Host: discovery3.razerapi.com  UserAgent: RazerLWI/2.4.0.868
secur32:schan_handshake Handshake completed
winhttp:netconn_verify_cert returning 0           <- сертификат принят
read_reply ... status code [L"200"]               <- discovery 200
  -> тело: {"data":{"items":[{"hash":"8TQEz6XZ","name":"prod"}]}}

  GET /api/v1/releases/8TQEz6XZ/tags/prod/products?os=WINDOWS&osver=7&arch=64&mfr=HP
      &model=OMEN%20by%20HP%2016.1%20inch0&sku=8L370EA  Host: manifest3.razerapi.com
  -> status 200, Content-Length: 21  ->  {"data":{"items":[]}}   <- ПУСТО из-за osver=7
```
То есть **сервер доступен, TLS работает, HTTP 200** — но `osver=7` → пустой каталог →
установщик считает «услуга отключена» → опять зелёный экран (подтверждено скриншотом
`/tmp/axon_inst_shot.png`).

---

## (2) Механизм связи: ПРЯМОЙ HTTPS (не Central Service IPC)

Однозначно **прямой HTTPS через WinHttp**, без локального Razer Central Service / named-pipe.
Установщик использует `System.Net.Http.WinHttpHandler` → Wine `winhttp` → `secur32`
(Schannel поверх GnuTLS). Трасса показала всю цепочку запросов:

1. `GET https://discovery3.razerapi.com/api/v1/endpoints` → `{hash:"8TQEz6XZ", name:"prod"}`.
2. `GET https://manifest3.razerapi.com/api/v1/releases/8TQEz6XZ/tags/prod/products?os=WINDOWS&osver=<N>&arch=64&mfr=...&sku=...`
   → каталог продуктов (зависит от osver!).
3. `GET https://bespoke-analytics.razerapi.com/api/v1/lwi/app-rating-statistics` (рейтинги).
4. Ассеты карточек: `https://manifest-assets.razersynapse.com/Axon/logo.png`, `media_*.mp4`…
5. AWS телеметрия: `https://u05srooyhc.execute-api.us-east-1.amazonaws.com/sts` (Kinesis).

Реальные пакеты приложений докачиваются по URL из манифеста (assets/S3, с random-хэшами —
см. research). До этой фазы в тесте установщик не доводился (нужен клик «Установить» в UI).

**Вывод:** чинибельно на уровне Wine-конфигурации (winhttp/TLS/osver), а НЕ через заглушку
сервиса. Подход «заглушка UserManager.dll» здесь НЕ нужен и НЕ применим (это другой бинарник,
другой этап — установщик, а не запуск app).

### Доказательство, что сервер исправен и под Wine, и нативно
| Запрос | Нативно (curl) | Под Wine (winhttp) |
|---|---|---|
| discovery `/api/v1/endpoints` | 200, выдаёт hash `8TQEz6XZ` | 200 |
| manifest products `osver=7` | 200, `items:[]` | 200, `items:[]` → зелёный экран |
| manifest products `osver=10` | 200, **11597 байт, есть RAZER AXON** | 200, грузит Axon-ассеты, 89×200 |

(Запросы к голым корням `discovery3/manifest3` дают 503/404/500 — это нормально, реальные
пути с hash/params отдают 200. «Сервер 503» — ложный след, если бить корень `/`.)

---

## (3) Research: WineHQ / сообщество / обходы

- **Подтверждение симптома** (Razer Insider / Level1Techs): пользователи Synapse 4 под
  Bottles/Lutris ловят «installer wants to download additional data from Razer and isn't
  granted access» — тот же класс. Причина у них та же: .NET и/или osver/сеть.
- **Архитектура Razer-инсталляторов** (Bioruebe/UniExtract2 #165): первичный .exe — лишь
  bootstrap; реальный движок `RazerInstaller.exe` ложится в `C:\Windows\Installer\Razer\…`;
  он создаёт XML с пакетами и download-URL; пакеты — 7-Zip Solid SFX; download-URL содержат
  timestamp + random id (намеренно не шарятся → «честный» оффлайн-инсталлер невозможен без
  сохранения уже скачанных файлов). Совпадает с тем, что мы видим.
- **`discovery.razerapi.com/manifest.razerapi.com` — Akamai CDN**, endpoint'ы живы.
- **WineHQ AppDB по Razer Axon** — содержательных записей нет (нишевое ПО) → есть смысл
  завести.
- Альтернатива для драйверов мышей/клав — OpenRazer+Polychromatic, но это НЕ про
  wallpaper-app Axon (нерелевантно нашей задаче).

Источники: razer.com/software/axon; Razer Insider «Server Access Unavailable» (Synapse 3/4);
Level1Techs Synapse-on-Linux; GitHub Bioruebe/UniExtract2 #165; Winetricks issues #1792/#2367
(dotnet48 под Wine/Proton).

---

## (4) Проверенные в тест-префиксе гипотезы (что помогло / нет)

| # | Гипотеза | Результат | Доказательство |
|---|---|---|---|
| H1 | Голый Wine (mono) запустит установщик | **НЕТ** | mscoree/mono краш до сети |
| H2 | Сервер недоступен под Wine (TLS/сертификаты) | **ОПРОВЕРГНУТО** | `Handshake completed`, `verify_cert returning 0`, HTTP 200 |
| H3 | `winetricks dotnet48` чинит запуск | **ДА (частично)** | движок стартует, идёт по сети, HTTP 200 |
| H4 | Под Win7 каталог пустой → зелёный экран | **ДА, это 2-я причина** | `osver=7` → `items:[]`; скриншот зелёного экрана |
| H5 | `winetricks win10` + dotnet48 = рабочий установщик | **ДА (главный фикс)** | `osver=10`, каталог 11597Б с Axon, 89×HTTP 200, экран «RAZER GAMING SOFTWARE / Идёт подготовка», зелёного экрана НЕТ |

Замечания по процессу:
- `winetricks -q dotnet48` ставит .NET 4.8 (рег. `NDP\v4\Full` Release=`0x80eb1`=528113,
  mono удалён), но **деадлочится на финальном `wineserver -w`** (известный баг winetricks).
  Сама установка при этом успешна; достаточно убить зависший `wineserver -k`.
- `winetricks win10` ставит `CurrentBuild=19045`; установщик корректно начал слать `osver=10`.
- Чистый CA-bundle/системные сертификаты НЕ потребовались — secur32+GnuTLS приняли цепочку
  Razer как есть.

---

## (5) РЕКОМЕНДАЦИЯ «для всех»

### Путь A — Wine-конфигурация (РЕКОМЕНДУЕТСЯ, проверен живьём)
Это не патч исходников Wine (баг не в Wine), а воспроизводимый рецепт префикса. Для
контрибуции — **WineHQ AppDB test report для Razer Axon** + готовый скрипт-обёртка OpenAxon,
который делает префикс правильно. Минимальные шаги:

```bash
export WINEPREFIX="$HOME/.local/share/openaxon/prefix"   # отдельный, не ~/.wine
wineboot --init
winetricks -q dotnet48          # ОБЯЗАТЕЛЬНО: .NET Framework 4.8 (mono установщик не тянет)
winetricks -q win10             # ОБЯЗАТЕЛЬНО: иначе osver=7 → пустой каталог → зелёный экран
# (winetricks может зависнуть на 'wineserver -w' — добить: WINEPREFIX=... wineserver -k)
wine ~/Загрузки/RazerAxonInstaller.exe   # теперь доходит до каталога и ставит Axon
```
Опционально под WebView2-окна Axon (уже в нашем razer-axon.sh):
`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu --in-process-gpu --disable-features=RendererCodeIntegrity"`.

Реализация «для всех» = добавить в OpenAxon скрипт `openaxon-install.sh`, который:
1. создаёт изолированный префикс, ставит `dotnet48`+`win10` (с обходом winetricks-деадлока),
2. запускает оригинальный `RazerAxonInstaller.exe` (его никто не патчит — он легально качает
   Axon с сервера Razer),
3. после установки применяет наш существующий обход авторизации запуска (DLL-патч/
   токен-инжектор из `openaxon_wine_axon_install_2026_05_31.md`) и ставит ярлык.

Плюсы: ничего проприетарного не модифицируем на этапе установки; пользователь получает
официальные файлы Axon; воспроизводимо на чистой машине. Это и есть «контрибутируемый фикс».

### Путь B — оффлайн-бандл OpenAxon (запасной, НЕ рекомендуется как основной)
Скопировать установленный каталог Axon + наш DLL-патч и раскладывать в обход установщика.
Минусы (по research Bioruebe): download-URL пакетов содержат timestamp+random id, не шарятся;
бандлить чужие бинарники Razel — юр-риск (см. правила clean-room/не-бандлить-чужое в MEMORY).
Поэтому B — только если у пользователя НЕТ интернета к Razer; иначе путь A честнее и проще.

**Итог: путь A.** Он устраняет ОБА корня (dotnet48 + win10) и проверен до экрана каталога
с Axon. B оставить как fallback для оффлайна, без бандла чужих бинарников в продукт.

---

## (6) Что нужно от Wehrwolfmann

1. **Дотестировать путь A до конца установки**: в тест-префиксе установщик доведён до экрана
   каталога/подготовки (Axon-карточки грузятся), но клик «Установить Axon» → фактическая
   докачка пакетов и запись в `Program Files` в headless-прогоне не доводились. Нужно
   прокликать UI вживую (или подтвердить, что мне можно автоматизировать клики через
   xdotool/spectacle в тест-префиксе) и проверить, что пакет Axon реально скачивается и
   ставится под Wine (фаза 7-Zip SFX / возможный запуск под-инсталлеров).
2. **Razer-логин/токен для каталога обоев** — отдельный шаг, к ошибке установщика отношения
   НЕ имеет (нужен уже после установки, для контента; см. `razer-login.py`). Свежий JWT
   нужен, т.к. прежний истёк 2026-04-08.
3. Решение: оформлять ли **WineHQ AppDB запись** для Razer Axon (рейтинг + test report с
   рецептом dotnet48+win10) — это и есть «контрибуция для всех».

---

## Файлы и артефакты
- Этот док: `~/Projects/openaxon/docs/axon_installer_wine_diagnosis_2026_05_31.md`
- Смежный (запуск app): `~/Projects/openaxon/docs/openaxon_wine_axon_install_2026_05_31.md`
- Тест-префикс: `~/.cache/axon-test-prefix` (можно удалить: `rm -rf`)
- Логи трасс: `/tmp/axon_inst1.log` (mono-краш), `/tmp/axon_inst3.log` (.NET48, osver=7),
  `/tmp/axon_inst5.log` (.NET48+win10, osver=10, 89×200)
- Скриншоты: `/tmp/axon_inst_shot.png` (зелёный экран при osver=7),
  `/tmp/axon_inst_shot2.png` (рабочий экран «RAZER GAMING SOFTWARE» при win10)
- Распакованный движок: `…/axon-test-prefix/drive_c/windows/Installer/Razer/Installer2/App/`
  (`RazerInstaller.exe`, `InstallerConfiguration.xml`)

---

## (7) УСТАНОВКА ДОВЕДЕНА ДО КОНЦА (2026-05-31, проверено живьём)

Гипотеза п.(6).1 закрыта: **Razer Axon реально установлен в Program Files под Wine.**
Префикс `изолированный тестовый Wine-префикс` (Wine 11.10, RTX 4070, KDE Wayland/XWayland).

### Что обнаружилось дополнительно (новые блокировки, не покрытые п.1-5)

3. **Нет WebView2 Runtime → экран каталога чёрный.** После dotnet48+win10 экран
   подготовки «RAZER GAMING SOFTWARE» показался, но следующий экран (каталог продуктов)
   рисуется WebView2-окном — без рантайма это **чёрный экран с зелёной полоской прогресса**.
   Фикс: установить WebView2 Evergreen Standalone (Microsoft fwlink `linkid=2124701`,
   ~190 МБ) — `wine MicrosoftEdgeWebView2RuntimeInstaller.exe /silent /install`. После этого
   движок поднимает `msedgewebview2.exe`, ставится `EdgeWebView/Application/<ver>/`.

4. **WPF-UI установщика крашится при переходе с экрана EULA.** На экране согласия
   (RU: «Продолжить» / EN: «CONTINUE») клик по кнопке → процесс `RazerInstaller.exe`
   падает с **unhandled `0x80131623`**. Точный стек (из `+eventlog`):
   ```
   Razer.Installer.UI.Language.Attached.TextBlockTextPlugin.Update()
     → System.Windows.Documents.TextElementCollection`1.get_Count()/get_FirstChild()
     → System.Windows.Controls.TextBlock.EnsureComplexContent()
     → FrameworkElement.MeasureCore()  → App.Main()
   ```
   Это WPF measure/layout TextBlock с inline-содержимым (Hyperlink «...License Agreement»)
   под Wine. **НЕ лечится** локалью (краш идентичен на ru и en) и
   `Avalon.Graphics\DisableHWAcceleration=1` (проверено — не помогает). То есть полностью
   пройти родной WPF-UI установщика кликами под Wine 11.10 не получается.

### Обход краха №4 — прямой Inno Setup из манифеста (легально)

WPF-UI и НЕ нужен. Манифест каталога (`ManifesetCache/manifest.json`, объект
`name:"Razer Axon"`) честно содержит прямую ссылку на официальный Inno-сетап Axon:
```
download_url      : https://manifest-assets.razersynapse.com/<ts><rnd>RazerAxonSetup_2.6.2.0.exe
download_file_checksum (MD5) : 24695676971daa8253d88e44e88209d5
file_size         : 88216104
install_parameters: /SP- /VERYSILENT /DIR="%programfiles(x86)%\Razer\Razer Axon" /SUPRESSMSGBOXES /NORESTART
launch_filepath   : %programfiles(x86)%\Razer\Razer Axon\RazerAxon.exe
```
(URL содержит timestamp+random id и со временем протухает — актуальный всегда берётся из
свежего манифеста.) Качаем этот файл, **сверяем MD5 с манифестом** (совпал точь-в-точь),
запускаем `wine RazerAxonSetup_2.6.2.0.exe /SP- /VERYSILENT /DIR=... /SUPPRESSMSGBOXES
/NORESTART`. Inno ставится без WPF.

### Доказательство установки
- `…/drive_c/Program Files (x86)/Razer/Razer Axon/RazerAxon.exe` — **PE32+ x86-64, 452 КБ**.
- Папка Axon: **~230 МБ, 660 файлов** (RazerAxon.exe, RazerAxon.Player.exe,
  RazerAxon.Reporter.exe, unins000.exe — Inno-деинсталлятор, WebView2 runtime DLL, и т.д.).
- Реестр: `…\Uninstall\Razer Axon_is1` → `DisplayName="Razer Axon"`,
  `DisplayVersion="2.6.2.0"`, `Inno Setup: App Path=…\Razer Axon`; протокол `RazerAxon://`.
- **Запуск подтверждён:** `wine RazerAxon.exe` стартует, создаёт
  `AppData\Local\Razer\RazerAxon\UICache\2.6.2.0\EBWebView\` (29 МБ, WebView2 рисует UI) и
  лог `RazerAxon.log`: `Program.cs:TryLoginAsync → Start userLogin`. Дальше упирается в
  `UserManager.cs … RazerClientBase.Connect timeout` — **ждёт Razer Central Service / логин**.
  Это RUNTIME-авторизация (DLL-патч/токен из `openaxon_wine_axon_install_*.md`,
  скрипт `razer-axon.sh`), отдельная от установки.

### Воспроизводимый скрипт «для всех»
`~/Projects/openaxon/install-axon-linux.sh` — идемпотентный, проверки на каждом шаге,
комментарии на русском. Делает: префикс → dotnet48 (если нет) → win10 → WebView2 (если нет)
→ bootstrap для манифеста (UI игнорируется, процесс глушится через ~60с) → парсинг
download_url+MD5 из манифеста → скачивание+проверка MD5 → `/VERYSILENT` установка →
(опц. `APPLY_AUTH_PATCH=1`) DLL-патч авторизации. Детекторы dotnet48/win10/webview2/manifest
и парсер манифеста протестированы против готового `изолированный тестовый Wine-префикс` (зелёные).

### Что подавать в WineHQ AppDB (Razer Axon)
- Wine 11.10, отдельный префикс.
- Обязательные вербы: `winetricks dotnet48`, затем `winecfg -v win10` (ИМЕННО после
  dotnet48, т.к. он сбрасывает версию на win7), WebView2 Evergreen Standalone.
- Известный дефект Wine: WPF-UI установщика крашится (`TextBlock.EnsureComplexContent`
  / `0x80131623`) — обход: ставить через Inno-сетап `RazerAxonSetup` (`/VERYSILENT`),
  ссылка из манифеста Razer. Rating: Garbage→Bronze для самого WPF-инсталлятора;
  приложение Axon после установки запускается (требует логина/Central Service).

---

## Калиброванная уверенность (правило #9)
- ПРОВЕРЕНО ЖИВЬЁМ (уверенность ~95%): mono-краш на голом Wine; HTTP 200 от
  discovery/manifest; osver=7→пустой каталог→зелёный экран; dotnet48+win10→osver=10→
  каталог с Axon (manifest 43 КБ, 65 продуктов, Axon-ассеты, экран подготовки);
  отсутствие WebView2→чёрный экран; WPF-краш `TextBlockTextPlugin`/`0x80131623` на
  EULA-переходе (одинаково ru/en, DisableHWAcceleration не помог); **установка Axon в
  Program Files через Inno `/VERYSILENT` из манифест-URL (MD5 совпал), RazerAxon.exe
  453 КБ, папка 230 МБ/660 файлов, реестр Inno, запуск до экрана логина**.
- ГРАНИЦЫ: проверено на ОДНОЙ машине (Wine 11.10, NVIDIA). На других Wine-версиях/GPU
  WPF-краш и поведение WebView2 могут отличаться. URL Axon-сетапа протухает (берём из
  свежего манифеста). RUNTIME-логин/каталог обоев НЕ покрыт (отдельный шаг).
- 503/404/500 на голых корнях endpoint'ов — НЕ признак недоступности (реальные пути 200).

---

## WebView2 `BrowserProcessExited` под Wine (исследование 2026-06-12)

### Симптом
После авторизации (guest-fallback DLL-патч) `RazerAxon.exe` рендерит домашний
экран (Spotlight/Trending, host-объекты инжектятся, баннеры грузятся), но через
~10-26 с встроенный WebView2 (msedgewebview2, evergreen Chromium 149) падает:
`WebViewWindow.cs:CoreWebView2_ProcessFailed` → `BrowserProcessExited,close window`.
Главный процесс Axon выживает (телеметрия Kinesis крутится дальше), но окно UI
закрывается. Время до краша НЕДЕТЕРМИНИРОВАННОЕ: обычно 10-26 с, изредка ~20 мин
с теми же бинарниками → это гонка IPC/процессов Chromium под Wine, НЕ авторизация
и НЕ DLL-патч.

### Что проверено живьём (Wine 11.10, RTX 4070, Wayland+XWayland)
Тест-харнесс: запуск `RazerAxon.exe -showui`, мониторинг `RazerAxon.log` на
`BrowserProcessExited`, до 600 с. Результаты:

| Конфигурация | Результат |
|---|---|
| Evergreen 149, software-флаги (--no-sandbox --disable-gpu …) | HOME RENDERED, CRASH@15s |
| + `--single-process` (swiftshader) | CRASH@15s (хуже) |
| + `--single-process --no-zygote --disable-dev-shm-usage` | CRASH@10s (ещё хуже) |
| Чистый Xvfb (Mesa software EGL, без NVIDIA) | EGL-ошибки исчезли, но CRASH@25s |
| `WINEDLLOVERRIDES=werfault.exe=d` | CRASH@26s (не помог) |
| `--renderer-process-limit=1 --process-per-site …` (live) | 1× дошёл до 360 с, при повторе CRASH@26s — флак |
| WINEDEBUG=+seh,+process (замедленный Wine) | НЕ крашнул за 60 с → подтверждает гонку по таймауту |
| **Fixed-version 109.0.1518.78 (env-var WEBVIEW2_BROWSER_EXECUTABLE_FOLDER)** | **`Init webview2 failed` — UI не стартует** |
| **Fixed-version 133.0.3065.92 (env-var WEBVIEW2_BROWSER_EXECUTABLE_FOLDER)** | **`Init webview2 failed` → App exit. Дело НЕ в версии — env-var гонит Axon в ветку `InitWebview2WithAbsolutePath`, которая падает синхронно** |
| **Fixed-version 133.0.3065.92 (EdgeCore\133 + registry pv=133, БЕЗ env-var)** | **INIT OK, home рендерится, primary-ветка `CreateCoreWebView2Environment`. НО BrowserProcessExited ~10 с после init — как 149. Стабильности НЕ даёт** |
| Evergreen 149 + `--disable-watchdog --disable-hang-monitor …` | HOME RENDERED, CRASH ~10s (флаги не помогли) |

### Ключевые выводы
1. **EGL/DRI2 — НЕ корень.** Под чистым Xvfb (Mesa software EGL) ошибки
   `libEGL: failed to create dri2 screen` исчезают, но WebView2 всё равно
   крашит. NVIDIA-EGL под XWayland — лишь шум, не причина.
2. **`--single-process` ВРЕДЕН** (крашит быстрее), как и предупреждает upstream.
3. **(ОПРОВЕРГНУТО — см. раздел «КОРЕНЬ ПЕРЕУСТАНОВЛЕН» ниже.)** ~~Корень — нестабильность
   многопроцессного Mojo IPC Chromium под Wine.~~ Реальный корень — viz-процесс на
   DirectComposition (`DCompositionCreateDevice` E_NOTIMPL), а не Mojo/IPC. Этот пункт
   оставлен как историческая гипотеза; актуальный вывод — в финальном разделе.
4. **Fixed-version рантайм НЕ решает краш — ни по версии, ни по механизму
   (проверено 133.0.3065.92 живьём 2026-06-12).** Разобран init-механизм Axon
   (`WebView2Control.cs:InitializeAsync`):
   - **Primary-ветка** (L:198 `start create CoreWebView2Environment`) — обычный
     `CreateCoreWebView2Environment`, использует registry-discovery / env-var.
     Под evergreen 149 РАБОТАЕТ (home рендерится).
   - **Fallback** `try InitWebview2WithAbsolutePath` (L:89/160) — срабатывает,
     ТОЛЬКО когда primary упала; хардкодит `EdgeCore\<evergreen-ver>` и под Wine
     тоже падает → `Init webview2 failed` → **App exit**.
   - Установка `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` (109 ИЛИ 133) ломает primary
     синхронно (~20 мс) → fallback → init fail. Т.е. **env-var-механизм
     fixed-version сам по себе несовместим с Axon под Wine**, не версия.
   - 133, развёрнутый как `EdgeCore\133.0.3065.92` + registry
     `EdgeUpdate\Clients\{F3017226-…}\pv=133.0.3065.92` (БЕЗ env-var), проходит
     primary-ветку: **init OK, home рендерится, живой процесс грузит EdgeCore/133**.
     НО BrowserProcessExited крашит так же ~10 с — стабильности версия не даёт.
   - 109 при попытке через env-var — `Init webview2 failed` (та же ветка fallback).
5. **Микро-смягчения** (software-рендер + Mesa-EGL + минимизация процессов)
   снижают частоту/откладывают краш, но НЕ устраняют его. WebView2 официально
   Wine не поддерживается (MicrosoftEdge/WebView2Feedback#3127).
6. **Главный процесс Axon переживает краш WebView2.** Финальный замер
   (evergreen 149 + наши флаги, 200 с): домашний экран рендерится за ~5 с,
   главный процесс жив >200 с непрерывно, WebView2 падает циклически (~38 раз
   за 200 с) и Axon каждый раз переоткрывает окно (UI мерцает). Краш WebView2
   НЕ роняет приложение — это деградация UI, не фатал. Частота цикла флаки
   между запусками/днями (накануне те же бинарники держали ~20 мин без падений).

### Применённая конфигурация (`razer-axon.sh`)
- Дефолтный префикс исправлен: `~/.local/share/openaxon/prefix` (был `~/.wine`).
- `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu
  --disable-gpu-compositing --disable-software-rasterizer
  --disable-features=RendererCodeIntegrity --disable-crash-reporter
  --disable-renderer-backgrounding --disable-background-timer-throttling"`
  (убран нерекомендованный `--in-process-gpu`).
- `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe` + Mesa-EGL vendor json.
- Опциональный fixed-version рантайм через `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER`
  с авто-детектом несовместимости (`.wv2-fixed-broken` → откат на evergreen).
  Дефолт `INSTALL_WV2_FIXED=0` (109 ломает init; 133 не дотестирован).

### Остаётся (исторический срез до 2026-06-12 — см. РАЗДЕЛ НИЖЕ, корень переустановлен)
- Стабильность WebView2 >5 мин детерминированно НЕ достигнута.
- **Fixed-version 133 ИСКЛЮЧЁН как решение** (2026-06-12): init проходит через
  registry-путь, но BrowserProcessExited крашит идентично 149. Версия рантайма не
  при чём. CAB 133 сохранён в `~/.cache/openaxon/wv2-fixed-133-x64.cab` и
  развёрнут в `EdgeCore\133.0.3065.92` (registry возвращён на 149).

---

## КОРЕНЬ ПЕРЕУСТАНОВЛЕН: это GPU-процесс (0x80000003), а НЕ Mojo named-pipe (2026-06-12)

Прежняя гипотеза «нестабильность многопроцессного Mojo IPC под Wine» и кандидат
«патч Wine по WineHQ #56378» — **ОПРОВЕРГНУТЫ эмпирически**. Перепроверено живьём с
`WINEDEBUG=+seh,+process` + `--enable-logging=stderr --v=1` на Wine 11.10 (RTX 4070,
Wayland/XWayland), префикс `~/.local/share/openaxon/prefix`.

### Что показал stderr Chromium перед смертью (декодировано из dispatch_exception)
```
content\browser\gpu\gpu_process_host.cc:1063] GPU process exited unexpectedly: exit_code=-2147483645
content\browser\gpu\gpu_process_host.cc:1515] The GPU process has crashed 1..2..3..4..5..6 time(s)
```
`exit_code = -2147483645 = 0x80000003 = STATUS_BREAKPOINT (EXCEPTION_BREAKPOINT)`.
То есть **GPU/Viz-процесс** падает на `CHECK()`/`__debugbreak()` при GPU-init под Wine,
крашится ~6 раз за ~12 с, после чего browser-процесс исчерпывает GPU-crash-лимит и
СОЗНАТЕЛЬНО выходит → Axon видит `BrowserProcessExited` и закрывает окно. В wine-трейсе
**нет c0000005/WerFault** у browser-процесса — он не «падает», а упорядоченно сдаётся.

Подсчёт процессов в одном прогоне: **12× gpu-process spawn, 2× renderer, 2× crashpad,
2× NetworkService, 2× StorageService** — браузер именно ПЕРЕЗАПУСКАЕТ gpu-process по кругу.

### Почему `--disable-gpu` НЕ помогает (ключевой нюанс)
По офиц. доке WebView2: `--disable-gpu` отключает HW-ускорение, но **если в системе есть
software-renderer, всё равно поднимается gpu-process под SwiftShader** — и именно он бьёт
0x80000003 под Wine. Наш `--disable-software-rasterizer` в одиночку под WebView2 149 это
НЕ убрал (gpu-process всё равно спавнился 12 раз).

### #56378 — что это на самом деле (research, обход Anubis)
WineHQ Bug **#56378** = "Microsoft Edge and Edge-based WebView2 do not function without
--no-sandbox option" — это **баг Chromium-sandbox bring-up**, НЕ named-pipe/Mojo. **Закрыт
FIXED в Wine 11.1.** Парный #56377 (Edge freezes ~1-3 c) — FIXED в 10.5. Фиксы лежат в
`win32u/winstation.c`, `win32u/sysparams.c`, `server/window.c`, `kernelbase/security.c`,
`ntdll/sec.c` (winstation/desktop/token + `DeriveCapabilitySidsFromName`), **НЕ** в
`server/named_pipe.c`/`ntdll/unix/sync.c`. ПРОВЕРЕНО: все эти фиксы УЖЕ присутствуют в
системном Wine 11.10 (греп подтвердил `DeriveCapabilitySidsFromName`,
`SetAdditionalForegroundBoostProcesses`, `is_service_process`/explorer-desktop).
Chromium Mojo использует named pipes в BYTE-mode (overlapped), которые Wine давно держит;
с Chrome ~112 Mojo вообще ушёл в shared memory (ipcz). → **Патч Wine по named-pipe/#56378
не требуется и не помог бы.** Сборка пропатченного Wine НЕ выполнялась (отменена по
результату research+live-диагностики как заведомо нерелевантная).

### ⚠️ ИТОГОВЫЙ ФИКС (2026-06-18, подтверждён ВИЗУАЛЬНО — заменяет рецепт ниже)
> Настоящее решение чёрного/белого экрана — **`Version=win7` для `msedgewebview2.exe`**
> (подпроцесс-рендерер Chromium). При Windows-версии ≥8.1 viz презентует кадр через
> **DirectComposition** (`DCompositionCreateDevice`), которого Wine не реализует
> (E_NOTIMPL) → CHECK-краш viz → кадр не доходит в окно. Под `win7` тот же
> `SoftwareOutputDevice` идёт через **GDI BitBlt** (без DComp) → пиксели реально в окне.
> `RazerAxon.exe` и глобально префикс остаются **win10** (иначе сервер Razer отдаёт
> пустой каталог — это РАЗНЫЕ per-app оверрайды на разных exe). Подтверждено живьём:
> главная (карусель/TRENDING) и Razer ID Login отрисованы полностью.
> Источники: WineHQ Bug 58921, winetricks #2226, CodeWeavers, Arch [SOLVED].

### Рецепт реестра (актуальная редакция)
1. **Реестр-политика Edge `HardwareAccelerationModeEnabled=0`** (вспомогательное):
   - `HKLM\Software\Policies\Microsoft\Edge`           `HardwareAccelerationModeEnabled=dword:0`
   - `HKLM\Software\Policies\Microsoft\Edge\WebView2`  `HardwareAccelerationModeEnabled=dword:0`
   - `HKCU\Software\Policies\Microsoft\Edge`           `HardwareAccelerationModeEnabled=dword:0`
2. **Версия Windows 7 для `msedgewebview2.exe`** (ГЛАВНОЕ — уводит SoftwareOutputDevice на
   GDI BitBlt вместо DirectComposition): `HKCU\Software\Wine\AppDefaults\msedgewebview2.exe Version=win7`.
   ⚠️ Раньше тут ошибочно стоял `win81` — это РОВНО порог включения DComp, он и давал чёрный экран.
3. Флаги (в `razer-axon.sh`): `--disable-gpu --disable-gpu-compositing --disable-software-rasterizer
   --disable-gpu-sandbox --no-sandbox` + software-EGL (Mesa/llvmpipe).

### Замер (исторический срез до находки win7)
- **Baseline (без реестр-фикса):** GPU-process крашит ~6 раз → `BrowserProcessExited` через
  ~10-17 c, цикл ~38 раз/200 c (мерцание UI).
- **С `win81`-вариантом (опровергнут):** browser-процесс переставал выходить, НО viz зацикливался
  на DComp-краше и не выдавал кадры → **чёрный экран**. Заявление «стабильно >2 мин» относилось к
  выживанию процесса, не к картинке. ИТОГ: лечит только `win7` (см. блок выше).

### Артефакты диагностики
- Харнесс: `~/.cache/openaxon/run_test.sh <секунды> <тег>` (бэкап реестра перед правками:
  `~/.cache/openaxon/reg-backup-20260612/`).
- Логи: `~/.cache/openaxon/diag/winedebug.log` (полный +seh+process трейс с GPU-crash-циклом),
  `~/.cache/openaxon/diag/hwoff_win81_*` (прогон с фиксом).
- Reg-файлы фикса: `/tmp/axon_hwaccel.reg`, `/tmp/axon_winver.reg` (содержимое продублировано выше).

### Оставшиеся кандидаты (УСТАРЕЛО — экран решён через `win7`, 2026-06-18; раздел исторический)
1. **`--disable-gpu-watchdog` + повышение GPU-crash-лимита** — пережить ранний init-bump.
2. **Wine-Staging ≥11.6 (DirectComposition патчсет)** — если CHECK именно в DComp-пути.
3. **Внешний WebView2-хост** (CDP-proxy) — вынести браузер из-под Wine целиком.
- Перебор версий рантайма (109/133/149) и Mojo/named-pipe-патч Wine — ТУПИК (доказано).
