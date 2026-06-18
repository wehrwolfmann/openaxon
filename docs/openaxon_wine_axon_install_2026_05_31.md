# OpenAxon — установка/запуск Razer Axon под Wine: фикс «доступ к серверу невозможен» (2026-05-31)

Автор работ: Wehrwolfmann. Документ фиксирует диагностику и применение нашего прошлого
OpenAxon-фикса к проблеме зелёного экрана Razer «ДОСТУП К СЕРВЕРУ НЕВОЗМОЖЕН / Услуга
отключена / Проверьте» при запуске Razer Axon под Wine.

## TL;DR (результат)

- Razer Axon **уже был установлен** ранее в `~/.wine` (`RazerAxon.exe`, `RazerCentralService.exe`,
  ярлыки). Проблема не на этапе установки файлов, а на этапе **онлайн-авторизации**:
  оригинальный Axon обращается к Razer Central Service / серверу Razer, который под Wine
  не отвечает → зелёный экран с ошибкой сервера.
- Наш прошлый фикс (OpenAxon) = **подмена `RazerAxon.UserManager.dll` на патч-версию**,
  которая локально заглушает авторизацию (не ходит на сервер). После обновления Axon
  (7 апреля) установленная DLL вернулась к оригиналу — патч был перетёрт.
- **Патч переприменён → Axon запускается, открывается рабочий главный UI (ГОРЯЧЕЕ/ОБЗОР/
  СЕРИЯ/АВТОРЫ), зелёного экрана ошибки больше нет.** Состояние на 2026-05-31: подтверждено
  живьём (окно + скриншот экрана авторизации).
- Уверенность ~90% (на 2026-05-31): проверено запуском под Wine (версия на дату лога) +
  скриншотом рабочего UI. Граница: каталог обоев пуст (серые плейсхолдеры), т.к. токен
  истёк — это отдельный шаг (перелогин), не относится к ошибке сервера.

## (а) В чём состоял наш прошлый фикс (Wine + DLL)

OpenAxon (репо `wehrwolfmann/openaxon`, локально `<HOME>/Projects/openaxon/`) предлагает ДВА
метода обхода онлайн-авторизации Razer:

1. **Токен-инжектор (предпочтительный, без патча бинарника)** — `razer-login.py`
   (WebKit-окно входа Razer ID → перехват JWT) + `razer-token-inject.py` (через named pipe
   `{FC828A97-...}` шлёт `WebApp_SetLoginSuccessFromWeb` в RazerCentralService). Файлы Razer
   остаются оригинальными.

2. **DLL-патч (устаревший, но прямой) — то, что применено сейчас.**
   Патчится `RazerAxon.UserManager.dll` (класс `UserManager : IUserManager`). Исходник:
   `<HOME>/Projects/openaxon/patch/src/RazerSequoia.SequoiaUserManager/UserManager.cs`.
   Суть переписанной логики:
   - `LoginAsync()` — читает локальный токен из
     `…/AppData/Local/Razer/RazerAxon/wine_login_token.json`; если токена нет/пуст —
     создаёт локального гостя (`"noAuth"`, `isGuest`). **Никакого обращения к серверу.**
   - `GetUserToken()` отдаёт токен из локального объекта `User`.
   - `GetNatashaStateDescription()` → `"Service not found"` (заглушка проверки сервиса).
   - Профиль/баланс/язык/тема — локальные заглушки; feedback/profile-окна открываются через
     встроенный WebView2.
   Эффект: оригинальная цепочка `UserManager → NacClient → named pipe → RazerCentralService →
   сервер Razer` заменена локальной заглушкой → экран «доступ к серверу невозможен» не возникает.

   Применяется через `razer-axon.sh` (функция `check_patch`): при запуске сравнивает
   установленную DLL с `patch/RazerAxon.UserManager.dll`, при отличии сохраняет `.orig` и
   копирует патч. Минус метода (по README): **сбрасывается после каждого обновления Axon** —
   ровно это и произошло 7 апреля.

   Wine-обвязка из `razer-axon.sh`: `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox
   --disable-gpu --disable-gpu-sandbox --in-process-gpu --disable-features=RendererCodeIntegrity"`,
   снятие `WM_TRANSIENT_FOR` через xprop (фикс панели задач), `wine RazerAxon.exe -showui`.

## (б) Research: WineHQ / обходы Razer-инсталляторов

- Официально: Razer Axon — Windows-only (Win10/11), но **жив и активно развивается**
  (награды Best Wallpaper 2025, активный insider/сайт). Значит «ошибка сервера» под Wine =
  сетевая/IPC-блокировка, а не закрытие продукта.
- «Server Access Unavailable» — давняя общая проблема инсталляторов Razer (Synapse 3/4 и Axon
  используют общий `RazerInstaller.exe`, он есть и у нас в
  `ProgramData/Razer/Installer/App/RazerInstaller.exe`). Community-обходы (Razer Insider):
  приоритет IPv4 / отключение IPv6, ручная установка модулей минуя визард инсталлятора,
  запуск от админа + временное отключение firewall/AV. Для нас неактуально — файлы уже
  установлены; нужен только обход авторизации, что делает наш DLL-патч.
- WineHQ AppDB по конкретно Razer Axon — содержательных записей не найдено (нишевое ПО).

Источники:
- https://www.razer.com/software/axon
- https://www.razer.com/newsroom/featured/razer-axon-best-wallpaper-2025
- https://insider.razer.com/razer-synapse-4-55/error-server-access-unavailable-can-t-install-any-razer-app-87604
- https://insider.razer.com/razer-synapse-3-29/synapse-3-0-install-server-access-unavailable-solution-5807

## (в) Диагностика текущего падения

Окружение: Wine 11.10 (на дату лога, system), префикс `~/.wine`, winetricks доступен. Proton не использовался.

Состояние префикса до фикса:
- Установлены: `…/Razer/Razer Axon/RazerAxon.exe` (PE32+ x86-64, .NET 6, self-contained,
  `runtimeconfig.json`: net6.0 / NETCore.App 6.0.36), `RazerCentralService.exe`, WebView2 runtime.
- `RazerAxon.UserManager.dll` (72904 байт) **== `RazerAxon.UserManager.dll.orig`** → т.е. стоял
  ОРИГИНАЛ, патч был сброшен (вероятно апдейтом Axon 2026-04-07).
- `wine_login_token.json` существует, но токен **истёк** (значение `tokenExpiry` в прошлом).

Причина зелёного экрана: оригинальный `UserManager` идёт в RazerCentralService/сервер Razer
за авторизацией; под Wine ответа нет → экран ошибки сервера. (Это не Wine-краш и не битый
инсталлятор — это серверная проверка приложения.)

## (г) Что применено и результат

Применён DLL-патч:
```bash
AXON_DIR="$HOME/.wine/drive_c/Program Files (x86)/Razer/Razer Axon"
# .orig уже валиден (== текущей оригинальной DLL); сделан доп. timestamped бэкап
cp "$HOME/Projects/openaxon/patch/RazerAxon.UserManager.dll" \
   "$AXON_DIR/RazerAxon.UserManager.dll"
```
Установленная DLL теперь идентична `patch/RazerAxon.UserManager.dll` (43008 байт).

Запуск (Wine — версия на дату лога):
```bash
WINEPREFIX=~/.wine WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu \
  --disable-gpu-sandbox --in-process-gpu --disable-features=RendererCodeIntegrity" \
  wine RazerAxon.exe -showui
```
Результат:
- Окно «Razer Axon» появляется за ~8с и стабильно живёт.
- **Нет** `BadImageFormatException` / `could not load … UserManager` / `Unhandled exception`
  (несмотря на то, что `file` метит патч-DLL как i386 — managed-сборка грузится в x64-процесс
  без проблем).
- В логе **нет** маркеров `server/unavailable/access/central`.
- Скриншот (`/tmp/axon_shot.png`): рабочий главный UI — навигация AXON/СОЗДАТЬ/СООБЩЕСТВО/
  БИБЛИОТЕКА, вкладки ГОРЯЧЕЕ/ОБЗОР/СЕРИЯ/АВТОРЫ, аватар. Зелёного экрана ошибки сервера НЕТ.
- Незначимые ошибки в логе (не блокируют): `Windows.UI.Composition.Compositor` (WinRT-эффекты)
  и `combase`/COM-классы (нативные хелперы/телеметрия) — норма под Wine.

Каталог обоев показывает серые плейсхолдеры (контент не подгрузился) — ожидаемо, т.к.
истёк токен. Это НЕ ошибка сервера авторизации; решается перелогином (см. ниже).

## (д) Что подавать как «патч для Wine»

Важно: наш фикс — это **патч приложения Razer (подмена managed-DLL)**, а НЕ исправление в
самом Wine. Wine здесь ведёт себя корректно; падал онлайн-механизм Razer. Поэтому в wine-devel
подавать как патч исходников Wine **нечего** — это не баг Wine.

Что реально можно оформить:
- **WineHQ AppDB запись для Razer Axon**: версия Wine (на дату лога), рейтинг (Garbage→Bronze без
  патча из-за серверного экрана; с обходом авторизации — выше), test report с шагами:
  установка через `RazerInstaller.exe`, WEBVIEW2-флаги, обход авторизации (наш DLL-патч или
  токен-инжектор), фикс `WM_TRANSIENT_FOR` для панели задач.
- Если когда-либо найдётся настоящий Wine-баг (напр. winhttp/secur32/named-pipe IPC, из-за
  которого RazerCentralService не может ответить), тогда — минимальный repro + diff в
  соответствующий dll-модуль Wine. Сейчас такого repro нет: обход на уровне приложения
  достаточен, корневой Wine-дефект не локализован.

## (е) Следующие шаги (для полноценной работы, не для устранения ошибки сервера)

1. Перелогин — токен истёк:
   ```bash
   <HOME>/Projects/openaxon/razer-login.py     # получить свежий JWT
   # с патч-DLL токен читается напрямую из wine_login_token.json при LoginAsync;
   # token-inject нужен только для оригинальной (непатченой) цепочки через сервис
   ```
2. Запускать через `razer-axon.sh` — он сам переприменяет патч при апдейтах Axon
   (`check_patch`) и чинит панель задач.
3. После каждого обновления Razer Axon патч сбрасывается → переприменить
   (`razer-axon.sh` делает это автоматически). Долгосрочная альтернатива без патча
   бинарника — метод токен-инжектора.

## Файлы

- Патч-DLL (применяемый): `<HOME>/Projects/openaxon/patch/RazerAxon.UserManager.dll`
- Исходник патча: `<HOME>/Projects/openaxon/patch/src/RazerSequoia.SequoiaUserManager/UserManager.cs`
- Лаунчер с авто-патчем: `<HOME>/Projects/openaxon/razer-axon.sh`
- Бэкап оригинала: `…/Razer/Razer Axon/RazerAxon.UserManager.dll.orig` + timestamped `.bak.*`
- Логи запуска: `/tmp/axon_run.log`, `/tmp/axon_run2.log`; скриншот `/tmp/axon_shot.png`
