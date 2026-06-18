# Razer Axon — повторный реверс-инжиниринг (2026-05-31)

Статический RE установленного `~/.wine/.../Razer/Razer Axon/`. Цель — найти НОВОЕ/уточнения
по сравнению с уже существующей документацией OpenAxon (`docs/*.md`), оценить точность
GTK4-клиента и выдать приоритезированный список улучшений.

**Метод**: ключевые DLL скопированы во временный рабочий каталог, декомпилированы через `ilspycmd`
(v10.0.0.8330, .NET-декомпилятор ILSpy). Установленный Axon НЕ запускался, НЕ модифицировался.
WebView-кеш (`UICache/.../EBWebView`) проанализирован только на чтение.

**Калибровка уверенности**: помечено [ДЕКОМП] = прочитано в декомпилированном коде,
[КЕШ] = извлечено из WebView-кеша, [ПРЕДП] = предположение/вывод.

---

## 0. Главный вывод (честно)

Существующая документация OpenAxon основана на реальном реверсе и точна/глубока:

- `razer-central-ipc.md` — wire-формат пайпа, GUID'ы пайпов, полный NacCommands enum: **всё совпадает с бинарём 1:1**.
- `webview-host-objects.md` — 6 host-объектов, ~124 метода, имена объектов с опечатками Razer: **совпадает**.
- `design-system.md` — палитра (#44d62c, #1a1a1a, …), токены, layout, компоненты: **совпадает с CSS-кешем**.
- `wallpaper-player.md` — SequoiaCommand, пайпы плеера: **присутствует**.

Из визуального оформления оригинала воспроизведено только **оформление GTK4**, а не протоколы.
И GTK-клиент УЖЕ использует точную палитру и размеры из спеки
(sidebar 260px, card min-width 240/max 266px, радиус 2px и т.д.).

Поэтому этот документ — в основном **подтверждение + точечные новые детали + пробелы**,
а не переписывание.

---

## 1. Инвентарь и версия

[ДЕКОМП/файлы]

- **Версия Axon: `2.6.2.0`** (из `appsettings.json` → `StartupUri https://axon-api.razer.com/2.6.2.0/`).
  Это **та же версия**, что зафиксирована в существующих доках → Axon с предыдущего разбора **НЕ обновлялся**, новых файлов нет.
- **Рантайм**: .NET **6.0.36** (`Microsoft.NETCore.App` + `Microsoft.WindowsDesktop.App`), win-x64, WPF-хост.
- **API base**: `https://axon-api.razer.com/v1` (`WebServiceDomain`).
- Внутреннее кодовое имя — **Sequoia** (`D:\RazerDev\sequoia-client-v2\...`, неймспейсы `RazerSequoia.*`).

### ⚠️ ВАЖНО: установленный Axon уже ПРОПАТЧЕН OpenAxon

`RazerAxon.UserManager.dll` в `~/.wine` — это **НЕ оригинал Razer**, а пропатченная OpenAxon
версия (совпадает с `patch/RazerLoginForm.cs`): содержит `wine_login_token.json`,
`machineId: "wine-linux"`, MessageBox «Login successful! Restart Razer Axon», вшитый JS-шим
`callbackObjforjs`/`callJSFromClient`. Все остальные DLL (`AccountManager*`, `RazerCentralClient`,
`RcClientBase`, `WallpaperManager`, `WallpaperPlayerManager`, `DataAcquisition`, …) — **оригинальные
Razer**, и именно они были основным источником данных ниже.

> Следствие для будущих RE: если нужен ОРИГИНАЛЬНЫЙ `UserManager.dll` — брать из чистого
> установщика (развёрнутого в изолированный тестовый Wine-префикс), а не из `~/.wine`.

---

## 2. Протоколы — подтверждения и новые детали

### 2.1 Razer Central named-pipe (подтверждено 1:1) [ДЕКОМП]

`RcClientBase.dll` → формат пакета совпадает с `razer-central-ipc.md`:

```
header (HEADER_LEN = 24):
  int32  version    = 2          (binaryWriter.Write(2))
  int32  serviceType (RzServiceType)
  int32  dataLength
  int32  headerLength = 24
  int64  packetId   (Interlocked.Increment, пропуск 0)
payload (dataLength)
```
Чтение: MIN_HEADER_LEN = 16 (читает 4×int32), затем `if version>1` читает int64 packetId,
`if headerLen>24` пропускает лишнее. **Уточнение к доке**: парсер версионно-устойчив —
поддерживает заголовки >24 байт (forward-compat), читая `headerLen-24` лишних байт.

GUID-пайпы (совпадают):
- ActionCenter/Service: `{CD7C71F0-A5B9-4F24-897A-DF6E20E43B96}`
- NAC: `{FC828A97-C116-453D-BD88-AD471496E03C}`
- NAC Client: `{E7A6CCA9-FF3F-4741-8E66-1127EE39471D}` + windows-username
- Есть DEBUG-варианты с префиксом `{DBG-...}` (используются при `m_debugPipeName`). [новое уточнение]

`RzServiceType`: UpdateManager=2, AccountManager=4, Notifications=5, ActionCenter=6.

### 2.2 Player IPC (Sequoia native player) [ДЕКОМП] — детали для wallpaper-player.md

`RazerAxon.WallpaperPlayerManager.dll` → `ShellLauncher.Launch`:

- Запуск: `RazerAxon.Player.exe` с аргументами:
  `readpipename=\\.\pipe\<W>  writepipename=\\.\pipe\<R>  version=<appVersion>`
  (+ `-screensaver` в режиме скринсейвера; тогда запуск без shell, отдельными argv).
- Два **раздельных** NamedPipeServerStream: `writePipename` (PipeDirection.Out) и
  `readPipeName` (PipeDirection.In). Имя пайпа-паттерн: **`RazerCortexServiceAndShell{Guid:N}`**.
- Команды — JSON-объект `SequoiaCommand`:
  ```csharp
  class SequoiaCommand {
    string Command; string MonitorId; string Source; string Type;
    string NeedDeleteSource; string PlayMode; string PlayEffects;
    // ctor(command, monitorId, type, source, isScreenSaver, WallpaperPlayers player,
    //      Dictionary<WallpaperEffectsEnum,string> playEffects=null, playMode="", needDeleteAfterPlay=false)
  }
  ```
- **Полный набор Command-вербов (8)**: `Play`, `Switch`, `PlayEffect`, `Volume`, `Pause`,
  `Resume`, `Stop`, `Terminate`. [полезно для собственного плеера OpenAxon]
- Сериализация: `JavaScriptEncoder.UnsafeRelaxedJsonEscaping` (важно — пути с `\` не эскейпятся в `\u`).

### 2.3 Аналитика / Kinesis / STS [ДЕКОМП] — детали

`RazerAxon.DataAcquisition.dll`:
- BigData идёт в **AWS Kinesis** через `RazerBigDataClient(RazerBigDataApps=1, ...)`.
- Креды Kinesis берутся по `GET <apiDomain>/sts` (STS-эндпоинт), затем temporary AWS creds
  (accessKeyId/secretAccessKey/sessionToken/expiry/arn). [уточнение: путь `/sts`]
- App-rating: `GET https://bespoke-analytics.razerapi.com/api/v1/1100/app-rating/recommendation`.
  (новый домен `bespoke-analytics.razerapi.com` — стоит добавить в axon-api.md, если нет).

### 2.4 Полный список доменов/URL (из всех DLL) [ДЕКОМП]

```
https://axon-api.razer.com            (+ /v1, + /2.6.2.0/)
https://axon-api-staging.razer.com    (staging)
https://bespoke-analytics.razerapi.com
https://id.razer.com/                 (Razer ID login)
https://zvault.razer.com              (кошелёк/баланс)
https://developer.razer.com/chroma
https://mysupport.razer.com/
https://www.razer.com/contact-us
https://www.youtube.com/embed/        (трейлеры в карточках)
```

### 2.5 ITS AES-ключ (НОВОЕ, не в доках) [ДЕКОМП]

`ActionServiceCommon.dll` → `RebootRequiredHelper`:
```
Key (base64) = "BYU/nsHCFDD/90xJUFJtRMrQ/f+tOohC87vhv0Fre/s="
IV  (base64) = "p2V8/a0Ik0noC2Z7iL8U9Q=="
Registry: HKLM\Software\Razer\Services\RazerCentral\ITS,  value "TS" (timestamp), "ITS"
AES-CBC, ключ/IV из base64.
```
**Назначение**: шифрует install-timestamp в реестре для логики «нужна перезагрузка после
установки» (`CanStart()`). **НЕ относится к обоям и НЕ к токенам пользователя.** Для OpenAxon
интереса почти не представляет (нет нужды читать ITS на Linux), но зафиксировано для полноты —
раньше где-то всплывал вопрос «есть ли в Axon вшитые крипто-ключи»: да, но только этот,
и он не security-sensitive.

### 2.6 Auth-токены [ДЕКОМП]

`AccountManagerCommon.dll` → `ConnectedAccountCredentials` (XML-сериализация):
`AccessToken`, `AccessTokenSecret`, `RefreshToken`, `SsiToken`, `ClientKey`, `ClientSecret`,
`Permissions[]`, `Account`. NacCommands enum полностью совпадает с докой (включая
`WebApp_GenerateToken=131097`, `UI_SetToken=131101`, `GetWallet=58`, `TryAutoLoginAsGuest=61`).

В пропатченном `UserManager` токен лежит в
`%LocalAppData%\Razer\RazerAxon\wine_login_token.json` с полями
`token, uuid, loginId, avatarUrl, nickname` (это формат OpenAxon, не Razer).

---

## 3. Формат обоев / расшифровка [ДЕКОМП + сверка с axon.py]

- Расшифровка обоев УЖЕ корректно реализована в OpenAxon (`axon.py`):
  `password = HMAC-SHA256(HMAC_KEY=b"j6l-aUmhCc@tN%T_", ResourceConfig.txt).hexdigest()`,
  обои — password-protected ZIP.
- **Подтверждение из бинаря**: ни в `WallpaperManager.dll`, ни в native `RazerAxon.Player.exe`
  нет AES/RSA/CryptoStream для обоев → обои = именно зашифрованный ZIP, дешифровка целиком
  на распаковке архива. Нативный плеер получает уже распакованный `ResourceConfig.txt`/`PlaySourceInfo`.
  → **Реализация OpenAxon верна, новый ключ/алгоритм не обнаружен.** [уверенность высокая]

### Модель данных обоев (уточнения enum) [ДЕКОМП] — `RazerAxon.IWallpaperManager.dll`

```csharp
enum WallPaperTypes      { VIDEO, WEB, IMAGE, LOCALVIDEO, LOCALWEB, LOCALIMAGE, NONE }   // порядок = числовое значение
enum WallPaperStatusEnum { Installed, Playing, FileBroken, FileLost, Uninstalled, Downloading, None }  // [JsonStringEnum]
enum WallpaperEffectsEnum{ None, WallpaperFillingMode, Brightness, Contrast, Hue, Saturation, PlayRate, WebInteraction, ThirdpartInfo }
enum StaticImgFillModesEnum { Fit, Fill, Stretch, Center, Tile }
enum WallpaperPlayers    { WindowsMediaFoundation, WebView2 }   // (ISettingManager) — дефолт WebView2
enum WallpaperThirdparts { Spotify }
```
`WallPaperItem` — большой DTO: `Id, Title, ThumbnailSource, PreviewSource, PlaylistThumbnail,
Type, Source, Author(AuthorInfo), Resolution, WallPaperStatus, PlayResoucePath,
IsChromaEnabled/Supported/Customized, IsWebInteractionSupported, IsMute, Audible,
Category/CategoryName, AllTags, Rating, IsFavorite, Downloads, Upvoted, Silver, LatestVersion, …`.
**Уточнение для axon-api.md**: `Audible` — строка ("0"/"1"), не bool; `Silver` — int (AI-кредиты).

`UserAppSettings`: `MaxVolume=50` (дефолт), `IsExitDirectly=2` (3-стейт: 0/1/2=не задано),
`WallpaperPlayer=WebView2` (дефолт), `ThirdpartInfos: Dict<Spotify, string>`.

---

## 4. Реальный UI (для GTK4-точности) [КЕШ + ДЕКОМП]

### 4.1 Палитра — подтверждена из WebView-кеша

В кеше (`.../EBWebView/Default/Cache/Cache_Data/data_*`) реально встречаются `#44d62c`
(Razer Green, доминирующий), `#1a1a1a`, `#cccccc`, `#212121`, `#333333`. Совпадает с
`design-system.md`. GTK-клиент (`razer-axon-gui.py`) уже использует именно эти токены
(#44d62c/#7ce26b/#359b24/#226916, #1a1a1a/#161616/#2e2e2e, #909090/#c8c8c8). **Расхождений нет.**

### 4.2 Локальные HTML-плееры (НОВОЕ — не в доках) [файлы установки]

В корне установки лежат **локальные HTML** (не из CDN):
- **`RazerAxonWebPlayer.html`** — реальный layer-композитор плеера. Структура:
  - 3 типа слоёв: `.image-player`, `.video-player`, `.web-player` (iframe), все
    `position:absolute; inset 0; width/height 100%`.
  - **Кросс-фейд переходов**: `opacity:0 → 1`, `transition: opacity 0.3s ease-in-out`,
    активный слой получает класс `.cur` (`opacity:1; z-index:2`). [ценно: OpenAxon-плеер
    может воспроизвести ровно такой 0.3s opacity-кроссфейд между обоями]
  - image-слой: `background-size: cover` (по умолч.), есть `contain`.
  - body bg `#222`.
- **`DefaultScreenSaver.html`** — фон `#111111`, класс `.logo-background`.

### 4.3 Структура UI (из design-system.md — уже задокументирована)

Полностью покрыта: title bar, nav, sidebar **260px** (граница #111), грид-карточки
(min 240 / max 266px, radius 2px), detail-панель (right slide-in), playlist-бар (низ),
кнопки, модалки (с опечаткой `madal` в оригинале), settings, формы (checkbox/radio/switch/
slider/select/input), dropdown/context-menu/pagination. React-маршруты (`/`, `/browse`,
`/createAI`, `/hall/*`, `/collections`, `/artists`, `/myWallPaper`) — в react-architecture.md.

---

## 5. Конкретные улучшения для OpenAxon (приоритезировано)

### P1 — высокая ценность, низкая цена
1. **Кроссфейд 0.3s в собственном плеере** (`openaxon-player.py`): при смене обои
   делать `opacity 0→1, 0.3s ease-in-out` поверх старого слоя (как `RazerAxonWebPlayer.html`).
   Наличие кроссфейда в текущем плеере требует проверки. [новое из локального HTML]
2. **Добавить домен `bespoke-analytics.razerapi.com` и путь `/sts`** в `axon-api.md`
   (если отсутствуют) — для полноты карты сети.
3. **Зафиксировать в wallpaper-player.md** точный набор из 8 SequoiaCommand-вербов и
   паттерн пайпа `RazerCortexServiceAndShell{guid:N}` + аргументы `readpipename/writepipename/version`
   (на случай, если OpenAxon когда-нибудь будет говорить с настоящим `RazerAxon.Player.exe`
   под Wine, а не только своим Python-плеером).

### P2 — средняя ценность
4. **Уточнить типы полей** в моделях OpenAxon: `Audible` — строка, `IsExitDirectly` — 3-стейт int,
   `WallpaperPlayer` дефолт = `WebView2`. Гарантирует совместимость при парсинге ответов API/локального стейта.
5. **Поддержать `StaticImgFillModesEnum` полностью** (Fit/Fill/Stretch/Center/Tile) в плеере
   изображений — Razer применяет это как effect `WallpaperFillingMode`. Проверить, что OpenAxon
   умеет все 5 режимов, не только cover.
6. **Версионно-устойчивый парсер пайпа** (если OpenAxon реализует клиент Central): читать
   `headerLen` и пропускать `headerLen-24` лишних байт (forward-compat, как делает Razer).

### P3 — низкая ценность / для полноты
7. **Документировать ITS AES-ключ** как «известный, не security-критичный» (см. §2.5) —
   чтобы закрыть вопрос «есть ли в Axon вшитые ключи».
8. **Брать оригинальный `UserManager.dll`** для будущих RE из чистого установщика, а не из
   пропатченного `~/.wine` (см. §1).
9. WebView-кеш-бандлы сжаты (gzip/brotli) — для свежей выгрузки CSS лучше брать прямой URL
   `https://axon-assets-cdn.razerzone.com/static/prod/2.6.2.0/` (как делал прошлый RE), а не
   распаковывать Chromium-кеш.

### Чего делать НЕ нужно
- Переписывать существующие доки протоколов/UI — они точны.
- Искать иной алгоритм расшифровки обоев — его нет (HMAC-ZIP подтверждён бинарём).
- Менять палитру GTK — она уже совпадает с реальным CSS.

---

## Приложение: что декомпилировано

Временный рабочий каталог декомпиляции (ilspycmd) содержит: RazerAxon, UserManager(пропатчен),
WallpaperManager, WallpaperPlayerManager, WebviewWindowManager, DownloadManager, PlayListManager,
SettingManager, NotificationManager, DataAcquisition, EnvironmentManager, ScreenSaver, Reporter,
RazerCentralClient, RcClientBase, AccountManagerClient/Common, ActionServiceCommon + интерфейсные
DLL (IWallpaperManager, IWallpaperPlayerManager, IPlayListManager, ISettingManager, IUserManager).
`RazerAxon.exe`/`RazerAxon.Player.exe` — нативные apphost-обёртки (.NET-код в RazerAxon.dll;
Player.exe — нативный C++ Sequoia-плеер, анализ через strings).
