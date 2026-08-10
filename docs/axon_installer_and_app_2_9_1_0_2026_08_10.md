# Razer Axon 2.9.1.0 — разбор свежего установщика и сверка с портом (2026-08-10)

Автор работ: Wehrwolfmann. Продолжение майских документов
`axon_installer_wine_diagnosis_2026_05_31.md` (диагностика установщика под Wine) и
`axon_reverse_engineering_2026_05_31.md` (реверс приложения 2.6.2.0).

**Метод**: только статический разбор. Ни `RazerAxonInstaller.exe`, ни
`RazerAxonSetup_2.9.1.0.exe` НЕ запускались — ни под Wine, ни как-либо иначе. Распаковка
ресурсов PE (`7z`), декомпиляция .NET (`ilspycmd`), чтение строк, публичное скачивание
общедоступных файлов (манифест-API и JS-бандл витрины отдаются без авторизации).

**Калибровка уверенности**: [ДЕКОМП] — прочитано в декомпилированном коде,
[СЕТЬ] — получено живым GET-запросом к публичному адресу, [СТРОКИ] — вытащено из
бинарных строк, [ПРЕДП] — вывод/предположение.

---

## TL;DR

0. ⭐ **ГЛАВНОЕ: функционального рассинхрона у порта НЕТ.** База API, версия пути `v1`,
   схема входа, обязательные заголовки и конверт ответа не изменились, а **все 30
   эндпойнтов, которыми порт реально пользуется, живы в 2.9.1.0** (§4а). Работы по
   порту — это правка номеров версий, а не переделка. Единственный непроверенный
   риск лежит вне API: протокол именованного канала Razer Central 7.23 (§6, п. 9).
1. **Наш порт разошёлся с оригиналом на три версии.** Axon в проде теперь **2.9.1.0**
   (сборка витрины от **20260728**), у нас в коде зашито `2.6.2.0`.
2. **База API и схема авторизации НЕ изменились.** Тот же `https://axon-api.razer.com/v1`,
   тот же `POST /login {token, is_guest, uuid}` → `data.authorization`, те же заголовки
   `Authorization` / `X-Version` / `X-Language` (+ `X-Requested-With`, который мы не шлём
   и без которого работает). Чинить надо только номер версии.
2а. **Поверхность API выросла на 17 эндпойнтов, не потеряв ни одного нашего.** Ещё 19
   «новых путей» оказались клиентскими маршрутами React Router, а 7 — мусором экстрактора;
   первая редакция §4 их ошибочно записала в API и была исправлена (§4, «Дельта»).
3. **Сменился endpoint-hash установщика**: `8TQEz6XZ` → **`N82uNskI`**. В коде он нигде не
   зашит (скрипт парсит манифест), только в майских заметках — но знать надо.
4. **Установщик-обёртка обновилась**: `2.4.0.868` → **`2.6.0.890`**, User-Agent
   `RazerLWI/2.6.0.890`. В `install-axon-linux.sh` зашит старый UA.
5. **В манифесте Axon появился обязательный модуль Razer Central (`Natasha`) 7.23.0.1220**,
   ставится ПЕРЕД Axon (`installation_priority` 300 против 32765). Это прямо касается нашей
   авторизации через именованный канал Razer Central.
6. **Инсталлятор приложения — Inno Setup 6.7.0**, которого не понимает `innoextract` 1.9
   (и даже git-master, потолок 6.4). Файловый состав самого приложения 2.9.1.0 распаковать
   НЕ удалось — см. «Чего не удалось».

---

## 1. Обёртка `RazerAxonInstaller.exe`

Файл: `~/Загрузки/RazerAxonInstaller.exe`, скачан 2026-08-10 01:49.

```
размер            14 923 464 байта
sha256            e4eabf1a0cf030b773a1a14ed22f4cb337c5f85638863260215b6315d83eb570
тип               PE32 GUI i386, MSVC (linker 14.42), 6 секций — НАТИВНЫЙ стаб, не .NET
COFF timestamp    2026-06-02 01:31:37 UTC
FileVersion       2.6.0.890      (было 2.4.0.868 по майским логам UA)
ProductName       Razer Installer
LegalCopyright    Copyright © 2026 Razer Inc.
подпись           DigiCert Trusted G4 Code Signing RSA4096 SHA384 2021 CA1
```

### Упаковщик

Нативный стаб + **ZIP-архив в ресурсе `RCDATA/1337`** (14 443 272 байта). Библиотека
распаковки — DotNetZip (строка `a library for handling zip archives.
http://www.codeplex.com/DotNetZip (Flavor=Retail)` в стабе) [СТРОКИ]. То есть это тот же
«DotNetZip Command-Line Self Extractor», что и в мае, только версией новее.

Ресурс распаковывается напрямую `7z x RazerAxonInstaller.exe`.

Строки управления стабом [СТРОКИ]:

```
\Installer\Razer\Installer2      — куда распаковывать (C:\windows\...)
\App\RazerInstaller.exe          — что запускать после распаковки
 /name                           — аргумент, которым передаётся имя продукта
mscoree.dll                      — запуск управляемого кода
```

### Состав полезной нагрузки

**81 файл, 26 985 275 байт распакованного** (в мае было «84 файла / ~40 МБ» — состав
похудел). Всё датировано 2026-06-02 03:31, кроме `InstallerConfiguration.xml` (2025-09-22).

Ключевое:

| файл | что это |
|---|---|
| `RazerInstaller.exe` | движок, .NET Framework **4.8**, Assembly Version 2.6.0.890 |
| `Razer.Installer.Core.dll` | сеть, манифест, загрузка, установка |
| `Razer.Installer.UI.dll` | WPF-интерфейс, 9,8 МБ (шрифты RazerF5/Noto/Roboto внутри) |
| `Razer.Installer.Hub.dll` | регистрация приложений в Razer Central |
| `Razer.Installer.DetectManagerWrapper.dll`, `rzS3detmgr.dll`, `rzS3detgmr_CWrapper.dll` | детект устройств |
| `BLEConnect.dll`, `BLEConnectWrapper.dll` | Bluetooth LE |
| `AWSSDK.Core.dll`, `AWSSDK.Kinesis.dll`, `Razer.Analytics.dll` | телеметрия в AWS Kinesis |
| `AllSystems.json`, `systems.json`, `dongle.json`, `dongleV2.json`, `dockEID.json` | таблицы PID устройств |
| `InstallerConfiguration.xml` | адреса серверов |
| `cpprest140_2_10.dll`, `msvcp140.dll`, `vcruntime140.dll` | нативные зависимости |

`RazerInstaller.exe.config` требует ровно `.NETFramework,Version=v4.8` — майский вывод про
обязательный `winetricks dotnet48` в силе.

### Как обёртка узнаёт, что ставить Axon

Строки `axon` нет ни в стабе, ни в одном из 81 файла. Имя продукта выводится **из имени
самого exe** [ДЕКОМП]: `Razer.Installer.Bootstrapper.StartupOptionUtil.ParseAppFromLaunchExe()`
ищет в имени файла ключ из `RazerAppNamesMapping.RazerShortNameMapping`:

```csharp
{ "axon",       "sequoia" },
{ "sequoia",    "sequoia" },
{ "axonbeta",   "axonbeta" },
{ "Razer Axon", "sequoia" },
{ "Axon",       "sequoia" },
```

То есть `RazerAxonInstaller.exe` → внутреннее имя продукта **`sequoia`**. Наш майский вывод
про кодовое имя Sequoia подтверждается со стороны установщика.

Разбираемые аргументы командной строки [ДЕКОМП]: `culture`, `silent`, `showdevice`, `host`,
`ep`, `hash`, `install`, `uninstall`, `app`, `name`, `staging`, `devicestaging`, `ad`,
`beta`, `betatag`, `dmqa`, `dmstaging`. Полезно: `ep`+`hash` позволяют **задать endpoint
вручную**, минуя discovery, а `app` — прямо назвать продукт.

---

## 2. Что и откуда качается

`InstallerConfiguration.xml` (без изменений с мая):

```xml
<DiscoveryServerRoot>discovery3.razerapi.com</DiscoveryServerRoot>
<DiscoveryEndpointName>prod</DiscoveryEndpointName>
<DiscoveryEndpointHash></DiscoveryEndpointHash>
<ManifestServerRoot>manifest3.razerapi.com</ManifestServerRoot>
```

Шаблоны из `Razer.Installer.Core.Config` [ДЕКОМП]:

```
EndpointDiscoveryServerRootProduct  https://discovery3.razerapi.com/
EndpointDiscoveryServerFullUrl      {0}/api/v1/endpoints{1}          ({1} = "?tag={tag}")
ManifestServerRootProduct           https://manifest3.razerapi.com
ManifestUrl                         {0}/api/v1/releases/{1}/tags/{2}/products
                                    ?os={3}&osver={4}&arch={5}&mfr={6}&model={7}0&sku={8}&l={9}
DeviceInfoUrl                       {0}/api/v1/devices/{1}/info?eid={2}&lid={3}
DetectManagerManifestRootProd       https://manifest-assets.razersynapse.com/lwi/
DetectManagerManifestUrl            {0}manifest.json
DetectManagerFileName               latestDM.zip
RazerAppStatUrl                     https://bespoke-analytics.razerapi.com/api/v1/lwi/app-rating-statistics
(staging)                           discovery3-staging / manifest3-staging / manifest-assets-staging
(AWS STS для Kinesis)               https://u05srooyhc.execute-api.us-east-1.amazonaws.com/sts
```

В `ManifestUrl` **`{1}` — это НЕ имя продукта, а хеш endpoint'а**, `{2}` — имя endpoint'а
(`prod`). Обратите внимание на `model={7}0`: лишний ноль после модели — опечатка Razer
в форматной строке, она уходит на сервер как есть (в майском дампе так и было:
`model=OMEN%20by%20HP%2016.1%20inch0`).

`arch` — это `64` или `86` (не `x64`), `osver` — `10`/`11`/`8.1`/`8`/`7`, UA —
`RazerLWI/{версия сборки}` = **`RazerLWI/2.6.0.890`** [ДЕКОМП `EnvironmentVar`].

### Живой ответ серверов [СЕТЬ], 2026-08-10

```
GET https://discovery3.razerapi.com/api/v1/endpoints?tag=prod
    {"data":{"items":[{"hash":"N82uNskI","name":"prod"}]}}
```

⚠️ **Хеш сменился: было `8TQEz6XZ` (май), стало `N82uNskI`.** Он подставляется в путь
манифеста, поэтому старый URL из майских заметок больше не даст каталог.

```
GET https://manifest3.razerapi.com/api/v1/releases/N82uNskI/tags/prod/products
    ?os=WINDOWS&osver=11&arch=64&mfr=Generic-MFR&model=Generic-MDL0&sku=Generic-SKU&l=en-US
```

Каталог прода на сегодня (8 продуктов): `Anne` (Razer Synapse) 4.0.698, `Chroma` 4.0.698,
`GameBooster2` (Cortex) 11.10.0.12, `Alisha` (Streamer Companion) 2.0.1.15, `Sophie` (THX
Spatial Audio) 2.0.1.21, `SophieLite` (7.1 Surround) 1.0.1.21, `Natalie` (Virtual Ring Light)
2.0.0.28 и:

```json
{
  "endpoint": "N82uNskI",
  "name": "Sequoia",
  "version": "2.9.1.0",
  "code": "1100",
  "display_version": "20260728",
  "metadata": {
    "alias": ["Axon"],
    "display_name": "RAZER AXON",
    "icon_url": "https://manifest-assets.razersynapse.com/Axon/logo.png",
    "marketing_url": "https://www.razer.com/software/axon",
    "pricing_type": {"code": "FREE", "name": "Free"},
    "tag": {"code": "NEW", "name": "NEW"},
    "supported_languages": ["English","Deutsch","Español","Français","日本語","한국어",
                            "Português (Brasileiro)","Русский","中文(简体)","中文(繁體)"],
    "unique_selling_points": ["Create wallpapers using AI", "Free high-quality wallpapers",
                              "Compatible with Chroma RGB", "Monthly Contests & Rewards"],
    "promotional_materials": {"promote_apps": [{"name": "GameBooster2"}]}
  },
  "modules": [
    {
      "name": "Natasha",
      "version": "7.23.0.1220",
      "service_code": "0280",
      "download_url": "https://manifest-assets.razersynapse.com/1778658202qKgcx3XSRazerCentral_v7.23.0.1220.exe",
      "download_file_checksum": "b015e30d20011da3fada698b62741284",
      "file_size": 121821664,
      "installation_priority": 300,
      "install_parameters": "/silent",
      "current_version_registry_key": "HKEY_LOCAL_MACHINE\\SOFTWARE\\Razer\\Services\\RazerCentral",
      "is_primary_module": false,
      "is_register_for_natasha": true,
      "uninstall_filepath": "C:\\Windows\\Installer\\Razer Central\\RCUninstall.exe"
    },
    {
      "name": "Razer Axon",
      "version": "2.9.1.0",
      "service_code": "1100",
      "download_url": "https://manifest-assets.razersynapse.com/1785145082xiAXypkMRazerAxonSetup_2.9.1.0.exe",
      "download_file_checksum": "a04cd17767144b74fe7e24df8e920ed9",
      "file_size": 63660360,
      "installation_priority": 32765,
      "install_parameters": "/SP- /VERYSILENT /DIR=\"%programfiles(x86)%\\Razer\\Razer Axon\" /SUPRESSMSGBOXES /NORESTART",
      "current_version_registry_key": "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Razer Axon_is1",
      "current_version_registry_value": "DisplayVersion",
      "uninstall_filepath_registry_value": "LWIQuietUninstallString",
      "uninstall_parameters": "/SP- /VERYSILENT /SUPRESSMSGBOXES /NORESTART",
      "launch_filepath": "%programfiles(x86)%\\Razer\\Razer Axon\\RazerAxon.exe",
      "is_primary_module": true,
      "error_code_mappings": {"0": "None", "8": "RestartRequired", "100": "RestartRequired"}
    }
  ]
}
```

Файл скачан и проверен: 63 660 360 байт, MD5 `a04cd17767144b74fe7e24df8e920ed9` — совпадает
с манифестом. Ссылка одноразовая по форме (`<unix-ts><8 случайных символов>` перед именем),
но сам объект доступен без авторизации.

---

## 3. `RazerAxonSetup_2.9.1.0.exe`

```
размер            63 660 360 байт  (было 88 216 104 у 2.6.2.0 — минус 28%)
MD5               a04cd17767144b74fe7e24df8e920ed9
тип               PE32 GUI i386, Inno Setup
COFF timestamp    2026-05-22 14:17:58 UTC
FileVersion       2.9.1.0
CompanyName       Razer Inc.
LegalCopyright    Copyright @ 2022. Razer Inc.
внутренние метки  "Inno Setup Messages (6.5.0) (u)", "Inno Setup Setup Data (6.7.0)"
```

`install_parameters` и `launch_filepath` не изменились — путь установки и способ тихой
установки прежние, майский обходной путь (скачать setup по манифесту и запустить
`/SP- /VERYSILENT /DIR=... /SUPPRESSMSGBOXES /NORESTART`) остаётся валидным.

Опечатку `/SUPRESSMSGBOXES` Razer так и не починил.

---

## 4. Само приложение 2.9.1.0 — что удалось узнать без распаковки

UI Axon живёт на сервере, а не в файлах (майский вывод), поэтому версию витрины можно
сверить напрямую [СЕТЬ]:

```
GET https://axon-api.razer.com/2.9.1.0/        → 200, SPA отдаётся
CDN базa: https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/
бандл:    axon.b454555f59e3550b4628.js   (5 139 397 байт; было axon.f8e71bd23f616540077f.js, 2,0 МБ)
стили:    axon.b454555f59e3550b4628.css  (было 2c05d5e95eb0ce13_0.css)
```

Подключаемые скрипты страницы (изменения против 2.6.2.0 помечены **ново**):

```
https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/tf.min.js
https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/ChromaSDKWS.js
https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/ChromaAI6.js
https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/components.js
https://chroma.razer.com/ChromaAI/jszip.min.js
https://deals-assets-cdn.razerzone.com/rating-modal/index.min.js
https://ced.sascdn.com/tag/4064/smart.js                      ← ново: Smart AdServer (реклама)
```

Service worker: `/2.9.1.0/sw.js`. Braintree по-прежнему закомментирован.

### Авторизация — БЕЗ ИЗМЕНЕНИЙ [ДЕКОМП по бандлу]

```js
axios.create({headers:{"X-Requested-With":"XMLHttpRequest","X-Version": APP_VERSION }})
  .interceptors.request.use(cfg => {
     cfg.headers["Authorization"] = window.SequoiaInfo && window.SequoiaInfo.authorization || "";
     cfg.headers["X-Language"]    = window.language || "en";
  });
// логин:
post(`${REQUEST_URL}/${API_VERSION}/login`, {token, is_guest, uuid})
  → window.SequoiaInfo.authorization = data.authorization
  → window.SequoiaInfo.token / .country / .uuid
```

`REQUEST_URL` в проде — **пустая строка** (запросы идут same-origin на
`https://axon-api.razer.com`), `API_VERSION` = **`"v1"`**, `X-Version` = **`"2.9.1.0"`**.
То есть база `https://axon-api.razer.com/v1` и вся схема входа те же, что мы реализовали.
Меняется только значение `X-Version`.

### Дельта по эндпойнтам [ДЕКОМП по бандлу, уточнено]

> ⚠️ **Правка первой редакции.** В первом заходе список «новых эндпойнтов» был снят
> механическим `grep` по строкам вида `"/что-то"` и получился завышенным: туда попали
> клиентские маршруты React Router и мусор сторонних библиотек. Ниже — разбор с
> проверкой места вызова. Считать верной эту редакцию.

Сырьё: `paths_262.txt` (144 пути, витрина 2.6.2.0) и `paths_291.txt` (184 пути,
витрина 2.9.1.0). Арифметика «184 − 144 = 40 новых» обманчива: на самом деле
**добавилось 47 строк и исчезло 7**.

#### Как отличить эндпойнт от маршрута

В бандле все обращения к API строятся ровно одним шаблоном, поэтому признак железный:

```js
axios.get("".concat(i.REQUEST_URL, "/").concat(l["default"], "/explore/board"), t)
//          ^ REQUEST_URL = "" (same-origin)  ^ l["default"] = "v1"
```

Клиентские же маршруты лежат в таблице роутера и в перечне навигации:

```js
{path:"/browse", key:"browse", component:r["default"]}
var q={DISCOVER:0,MARKET:1,COLLECTION:2,COMPILATIONS:3,…,AI_UPDATE:32}; e.NAV=q;
var Q=["/","/browse","/collections","/compilations","/myWallPaper","/myCreateWallPaper",
       "/create","/createHtml","/createAI","/myWorkshop","/compaigns",
       "/compaigns/contestDetail","/hall","/hall/follow","/hall/liked","/hall/personal",
       "/createAINew","/followSeries","/followArtist","/followSeriesDetail",
       "/followArtistDetail","/artists","/compaigns/leaderboard","/playlist",
       "/playlist/joined","/playlist/followed","/communityAlbums","/hall/all",
       "/compaigns/daily","/leaderboard","/challenge","/compaigns/currentContest",
       "/aiUpdate"];
```

Каждый из 47 «новых» путей проверен на наличие места вызова через `REQUEST_URL`.

#### Разбор 47 добавившихся строк

**1. Настоящие новые эндпойнты API — 17.** У всех подтверждён вызов через `REQUEST_URL`;
в скобках — имя функции клиента и метод.

*Витрина и каталог (4)*

| Путь | Метод | Функция | Смысл |
|---|---|---|---|
| `/spotlight/index/carousel` | GET | `…ightCarousel` | карусель главной, отделена от `/spotlight/index` |
| `/spotlight/index/category` | GET | `…ightCategory` | плитки категорий главной |
| `/promote/info` | GET | `…annerSetting` | настройки промо-баннера |
| `/system/setting` | GET | `…(keys)` | пакетное чтение серверных настроек по списку ключей |

*Кампании, конкурсы, соревнования (5)*

| Путь | Метод | Функция | Смысл |
|---|---|---|---|
| `/campaign/code` | GET | `…(wallpaper_id)` | код участия кампании по обоям |
| `/contest/award/detail` | GET | `…(award_id)` | карточка одной награды (было только `/contest/award/list`) |
| `/explore/dailychallenge` | GET | `…ilyChallenge` | блок ежедневки на «Explore» |
| `/explore/leaderboard` | GET | `…eLeaderboard` | блок лидерборда на «Explore» |
| `/explore/board` | GET | `ExploreBoard` | блок досок сообщества на «Explore» |

Обрати внимание: `/explore/*` — это **виджеты одной страницы**, а не отдельные разделы;
сами разделы (`/leaderboard`, `/challenge`, `/hall`) — маршруты, см. пункт 2.

*Экономика: реклама как валюта (3) — новая механика*

| Путь | Метод | Функция | Смысл |
|---|---|---|---|
| `/task/ads` | GET | `…AdRewardsInfo` | список рекламных заданий и награда за них |
| `/task/adsid` | GET | `…imRewardToken` | токен на получение награды за просмотр |
| `/task/ads/claim` | POST | `…(ads_task_id)` | забрать награду за просмотренную рекламу |

Это стыкуется с новым тегом `<script src="https://ced.sascdn.com/tag/4064/smart.js">`
(Smart AdServer) и доменом `www18.smartadserver.com` в бандле: в 2.9 за просмотр рекламы
дают внутреннюю валюту (silver).

*Погашение кодов и рефералы (4)*

| Путь | Метод | Функция | Смысл |
|---|---|---|---|
| `/redeem/bycode` | POST | `…emByCodeNew` | новый общий обмен кода (суффикс `New` — прежний `/wallpaper/redeem/bycode` оставлен) |
| `/wallpaper/redeem/bycode` | POST | `…edeemByCode` | старый обмен кода на обои |
| `/referral/redeem` | POST | `…(code)` | реферальный код |
| `/silver/detail` | GET | `…SivlerDetail` | выписка по внутренней валюте (опечатка в имени — их) |

*Лента (1)*

| Путь | Метод | Функция | Смысл |
|---|---|---|---|
| `/feed/messages/pending` | GET | `getUnReadNum` | счётчик непрочитанного (раньше считали из `/feed/messages`) |

**2. Не эндпойнты, а маршруты React Router — 19.** Ни у одного нет вызова через
`REQUEST_URL`; все присутствуют в таблице роутера и/или в массиве `Q` навигации:

```
/browse  /collections  /compilations  /create  /artists
/hall  /hall/all  /hall/follow  /hall/liked  /hall/personal
/playlist  /playlist/followed  /playlist/joined
/leaderboard  /challenge  /contest
/compaigns  /compaigns/daily  /compaigns/leaderboard
```

`compaigns` — опечатка Razer, живёт с самого начала. В бандле есть
`<Redirect from="/compaigns/leaderboard" to="/leaderboard" exact>`, то есть раздел
кампаний как раз распиливают на отдельные экраны. Появление этих строк в 2.9 означает
**новые экраны UI**, а не новые вызовы сервера — данные они берут старыми
`/hall/*`-подобными эндпойнтами (`/board/list`, `/leaderboard/list`, `/dailychallenge/list`).

**3. Мусор экстрактора — 7.** Пять — указатели JSON Schema из библиотеки валидации AJV
(`errSchemaPath + "/else"`, `"/then"`, `"/type"`, `"/required"`, `"/properties"`), две —
UI-счётчики длины текста: `"/2000"` (лимит описания обоев) и `"/300"` (лимит краткого
описания). К API отношения не имеют, но лимиты полей полезно знать.

**4. Не новые, изменилась форма записи — 4.** Клиент склеивает суффикс из аргумента, и
экстрактор 2.9 обрезал плейсхолдер:

```js
axios.post(`${REQUEST_URL}/v1/wallpaper/favorite/${t.type}`, t)   // type = add | cancel
axios.post(`${REQUEST_URL}/v1/wallpaper/vote/${t.type}`, t)
```

| В 2.6.2.0 | В 2.9.1.0 | Что на деле |
|---|---|---|
| `/artist/follow/{type}` | `/artist/follow/` | без изменений |
| `/collection/follow/{type}` | `/collection/follow/` | без изменений |
| `/wallpaper/favorite/{type}`, `/wallpaper/favorite/add`, `/wallpaper/favorite/cancel` | `/wallpaper/favorite/` | без изменений |
| `/wallpaper/vote/{type}` | `/wallpaper/vote/` | без изменений |

#### Разбор 7 исчезнувших строк

Шесть — обратная сторона пункта 4 выше (`/artist/follow/{type}`, `/collection/follow/{type}`,
`/wallpaper/favorite/{type}`, `/wallpaper/favorite/add`, `/wallpaper/favorite/cancel`,
`/wallpaper/vote/{type}`). **По-настоящему исчез ровно один: `/generate/downloaded`** —
его роль забрали `/wallpaper/downloaded` и `/wallpaper/generate/list`, оба на месте.

#### Итог

**Ни один эндпойнт, существовавший в 2.6.2.0, не удалён и не переименован** (кроме
`/generate/downloaded`, которым мы не пользуемся). Все 17 новых — **чистые добавления**
поверх прежней поверхности API.

Новые внешние домены в бандле: `https://www18.smartadserver.com`, `https://cdn.leonardo.ai`,
`https://leonardo.ai`, `https://hidreamai.com`, `https://gold.razer.com` — то есть у
генерации добавились сторонние модели, а у экономики — рекламные задания.

#### Сверка с майскими заметками

* `docs/axon-api.md` (май, 2.6.2.0) описывает базу, вход, заголовки и рабочие разделы
  каталога/генерации — **всё это подтвердилось в 2.9.1.0 без правок**.
* `docs/axon_ui_features_full_inventory_2026_05_31.md` — инвентарь экранов; 19 маршрутов
  из пункта 2 это его прямое продолжение (новые экраны: `/browse`, `/collections`,
  `/compilations`, `/artists`, `/playlist*`, `/hall/*`, `/leaderboard`, `/challenge`,
  `/contest`, `/compaigns*`). Инвентарь стоит дополнить, но на порт это не влияет.
* ⭐ Отдельно: в `docs/axon-api.md` **уже есть** таблица клиентских маршрутов, и `/hall/*`,
  `/collections`, `/compilations`, `/playlist*`, `/compaigns*`, `/contest` перечислены там
  именно как экраны. То есть майский разбор был верен, а ошибку внёс августовский `grep`.
  Урок на будущее: пути из бандла засчитывать в API только при наличии места вызова.

---

## 4а. Расходится ли порт с 2.9.1.0 — окончательный ответ

**Нет. Функционального рассинхрона нет ни в одной точке.** Проверено по четырём осям.

### 1. База и версия протокола — без изменений

```js
axios.get("".concat(REQUEST_URL, "/").concat("v1", "/wallpaper/list"), params)
```

`REQUEST_URL` в проде — пустая строка (запросы same-origin на `https://axon-api.razer.com`),
версия пути — `"v1"` (в бандле ровно одно вхождение строки `"v1"`, в модуле-константе).
У нас `API_BASE = "https://axon-api.razer.com/v1"` (`razer-sync.py:29`,
`razer-axon-gui.py:31`) — **совпадает**.

### 2. Обязательные заголовки — без изменений

Полный набор из бандла:

```js
axios.defaults.withCredentials = true;
axios.create({ headers: { "X-Requested-With": "XMLHttpRequest",
                          "X-Version": "2.9.1.0" } });
  .interceptors.request.use(cfg => {
     cfg.headers["Authorization"] = window.SequoiaInfo?.authorization || "";
     cfg.headers["X-Language"]    = window.language || "en";
  });
```

| Заголовок | В 2.9.1.0 | У нас | Вердикт |
|---|---|---|---|
| `Authorization` | сырая строка из `data.authorization` | так же | ок |
| `X-Version` | `2.9.1.0` | `2.6.2.0` | **устарело, косметика** |
| `X-Language` | `en` | `en` | ок |
| `Content-Type` | `application/json` | так же | ок |
| `X-Requested-With` | `XMLHttpRequest` | **не шлём** | не мешало в мае; добавить как страховку |
| подпись/nonce/капча | **нет** | — | новых требований не появилось |

Ни одного нового обязательного заголовка, ни JWT-Bearer, ни anti-bot-подписи.
`withCredentials: true` для нас нерелевантен — авторизует `Authorization`, не cookie.

### 3. Вход и конверт ответа — без изменений

```js
post(`${REQUEST_URL}/v1/login`, {token, is_guest, uuid})
  → if (res.code == 200) { SequoiaInfo.authorization = res.data.authorization;
                           SequoiaInfo.token = …; SequoiaInfo.uuid = …; }
```

Конверт прежний — `{code, msg, data}`, успех при `code == 200`; наш код проверяет ровно
это (`resp.get("code") != 200`). Перехватчик ошибок различает только транспортные статусы
(403 → сообщение, 503 → событие `SERVER_ERROR_503`, 502 → «обслуживание»); новых кодов
авторизации, требующих реакции клиента, нет.

### 4. Эндпойнты, которыми порт реально пользуется — 30 из 30 на месте

Список собран по вызовам `api_get` / `api_post` / `hmac_request` в
`razer-axon-gui.py` и `razer-sync.py` и сверен с `paths_291.txt`:

| Группа | Эндпойнты | В 2.9.1.0 |
|---|---|---|
| Вход | `/login` | ✅ |
| Каталог | `/wallpaper/list`, `/wallpaper/detail`, `/wallpaper/setting`, `/wallpaper/favorite/{add\|cancel}` | ✅ |
| Авторы | `/artist/list`, `/artist/detail` | ✅ |
| Коллекции | `/collection/list`, `/collection/followlist`, `/collection/follow/{add\|cancel}` | ✅ |
| Главная | `/spotlight/index`, `/spotlight/feed`, `/feed/selections`, `/feed/personal/state` | ✅ |
| Профиль | `/wallet/balance`, `/silver/detail`, `/badge/list` | ✅ |
| Генерация | `/wallpaper/generate` и `…/image2image`, `…/video`, `…/image2video`, `…/image2motion`, `…/upscale`, `…/model`, `…/uploadurl`, `…/upload`, `…/info`, `…/detail` | ✅ |
| HMAC-загрузка | `/wallpaper/resource`, `/wallpaper/downloaded` | ✅ |

Ни один не удалён, не переименован и не переехал на другую версию пути.

Параметры тоже совпали: официальный клиент подмешивает в `/wallpaper/list` параметр
`not_offical = true` (их опечатка в слове «official») — **мы его уже шлём**
(`razer-axon-gui.py:2963`, `:1056`), это было поймано ещё в мае
(`docs/axon-api.md:130`, `:1597`).

### Схемы ответов

Изменений в разборе ответов у используемых нами эндпойнтов по бандлу не видно: те же
`data.list` / `data.total` в постраничных выдачах и те же имена полей. Оговорка о
доверии: сверка **статическая, по коду клиента**; живых ответов с авторизацией мы не
запрашивали принципиально, так что «схемы не менялись» — вывод по чтению клиента, а не
измерение. Риск считаю низким: сломайся форма, сломался бы и официальный клиент.

### Что из 17 новых эндпойнтов стоит поддержать

**Стоит (полезно и дёшево):**

| Эндпойнт | Зачем | Оценка |
|---|---|---|
| `/spotlight/index/carousel`, `/spotlight/index/category` | главная в 2.9 разъехалась на три вызова; сейчас мы тянем только `/spotlight/index` и получаем часть контента | низкая |
| `/system/setting` | серверные флаги/лимиты одним запросом — снимает часть хардкода | низкая |
| `/feed/messages/pending` | готовый счётчик непрочитанного вместо подсчёта вручную | низкая |

**Можно (если будем расширять экраны):** `/explore/board`, `/explore/dailychallenge`,
`/explore/leaderboard` — три виджета одной страницы «Explore»; имеет смысл только вместе
с самим экраном.

**Не нужно:**

* `/task/ads`, `/task/adsid`, `/task/ads/claim` — просмотр рекламы за внутреннюю валюту.
  Тянет за собой Smart AdServer (`ced.sascdn.com`). В порт **не берём**.
* `/campaign/code`, `/contest/award/detail` — кампании и конкурсы, экранов у нас нет.
* `/redeem/bycode`, `/wallpaper/redeem/bycode`, `/referral/redeem`, `/promote/info` —
  промокоды, рефералы и баннеры; к базовой задаче (каталог + обои + генерация) не относятся.
* `/silver/detail` — **уже поддержан**, отдельной работы не требует.

---

## 5. Сводная таблица «май 2026 → август 2026»

| Что | Было (2026-05-31) | Стало (2026-08-10) | Ломает порт? |
|---|---|---|---|
| Версия Axon | 2.6.2.0 | **2.9.1.0** (витрина 20260728) | да, `X-Version`/UA |
| База API | `https://axon-api.razer.com/v1` | без изменений | нет |
| Версия пути API | `v1` | без изменений | нет |
| Схема входа | `POST /login {token,is_guest,uuid}` → `authorization` | без изменений | нет |
| Заголовки | `Authorization` / `X-Version` / `X-Language` / `X-Requested-With` | без изменений | нет |
| Конверт ответа | `{code, msg, data}`, успех `code==200` | без изменений | нет |
| Наши 30 эндпойнтов | — | **30 из 30 на месте** | нет |
| Поверхность API | 143 пути | +17 новых, удалён 1 (`/generate/downloaded`, не наш) | нет |
| Экраны UI | — | +19 маршрутов роутера | нет |
| HMAC-ключ ресурсов | `j6l-aUmhCc@tN%T_` | не проверен (нужны файлы app) | ? |
| CDN витрины | `.../static/prod/2.6.2.0/` | `.../static/prod/2.9.1.0/` | да, путь |
| JS-бандл | `axon.f8e71bd23f616540077f.js` (2,0 МБ) | `axon.b454555f59e3550b4628.js` (5,1 МБ) | нет |
| Обёртка-установщик | UA `RazerLWI/2.4.0.868` | **`RazerLWI/2.6.0.890`** | косметически |
| Payload обёртки | 84 файла / ~40 МБ | 81 файл / 27 МБ | нет |
| endpoint hash | `8TQEz6XZ` | **`N82uNskI`** | нет (парсим из ответа) |
| discovery/manifest хосты | discovery3/manifest3.razerapi.com | без изменений | нет |
| Setup приложения | `RazerAxonSetup_2.6.2.0.exe`, 88 216 104 | `RazerAxonSetup_2.9.1.0.exe`, 63 660 360 | ссылку в скрипте |
| Inno Setup | распаковывался `innoextract` 1.9 | **Inno 6.7.0**, 1.9 не берёт | да, для сборки |
| Модуль Razer Central | в майской выписке манифеста не фигурировал | **`Natasha` 7.23.0.1220, приоритет 300** | вероятно да |
| Параметры тихой установки | `/SP- /VERYSILENT /DIR=...` | без изменений | нет |

---

## 6. Что чинить в порте (по приоритету)

> Контекст: рассинхрона по API нет (§4а). Всё ниже — либо косметика версий, либо
> устойчивость к следующему обновлению, либо необязательные улучшения.

**П1 — обязательное (косметика версий, 15 минут).**

1. **Версия клиента.** `razer-sync.py:30` и `razer-axon-gui.py:32`:
   `API_VERSION = "2.6.2.0"` → `"2.9.1.0"`. Там же User-Agent `RazerAxon/2.6.2.0`
   (три места в `razer-axon-gui.py`: строки 250, 331, 910). Заголовок `X-Version`
   на бэкенде, судя по всему, не проверяется строго (порт работал с маем), но врать
   о версии без нужды не стоит.
2. **UA установщика** в `install-axon-linux.sh:306,387`: `RazerLWI/2.4.0.868` →
   `RazerLWI/2.6.0.890`.

**П2 — чтобы следующее обновление нас не догнало.**

3. **Перестать хардкодить версию.** Тянуть её из манифеста
   (`GET discovery → GET manifest3 → items[name=="Sequoia"].version`) с фолбэком на
   зашитое значение. Тогда пункт 1 больше никогда не понадобится — а он повторяется
   каждый релиз Razer.
4. **Добавить `X-Requested-With: XMLHttpRequest`** в `api_get`/`api_post`
   (`razer-axon-gui.py:216,230,278`, `razer-sync.py:95`). Сейчас без него работает, но
   официальный клиент шлёт его всегда — дешёвая страховка от будущей проверки.
5. **Вычистить мусор в скрипте установки.** `download_url` уже берётся из живого
   манифеста через `manifest()`, но захардкоженные в комментариях/фолбэках `2.6.2.0`
   и старый хеш эндпойнта `8TQEz6XZ` сбивают с толку (актуальный — `N82uNskI`, но и его
   зашивать не надо, он парсится из ответа).

**П3 — по желанию, новая функциональность.**

6. **Главная страница.** Добавить `/spotlight/index/carousel` и
   `/spotlight/index/category` в `HomePage._load` (`razer-axon-gui.py:1924`): в 2.9 главная
   разъехалась на три вызова, и мы показываем только часть контента.
7. **`/system/setting`** — серверные лимиты и флаги одним запросом вместо хардкода.
8. **`/feed/messages/pending`** — готовый счётчик непрочитанного.

**П4 — не связано с API.**

9. **Проверить связку с Razer Central.** В манифесте Axon теперь явный модуль
   `Natasha 7.23.0.1220` с `installation_priority: 300`, то есть Razer Central ставится
   первым и Axon от него зависит. Наш `razer-token-inject.py` пишет в канал
   `{FC828A97-C116-453D-BD88-AD471496E03C}` командой `WebApp_SetLoginSuccessFromWeb`
   (131094) — надо убедиться, что в 7.23 номера команд и формат пакета не поменялись.
   **Это единственный реальный риск, оставшийся непроверенным.**
10. **Обновить `docs/axon-api.md`**: 17 новых эндпойнтов из §4а в таблицу API, 19 новых
    маршрутов — в таблицу экранов (в том же файле она уже есть).
11. **Патч `RazerAxon.UserManager.dll`** заведомо не подойдёт к 2.9.1.0 (файл собран
    заново), его придётся пересобрать после того, как удастся распаковать setup.

**Чего делать НЕ надо:** рекламные задания (`/task/ads*`), кампании/конкурсы, промокоды
и рефералы — см. разбор в конце §4а.

---

## 7. Чего сделать НЕ удалось

* **Распаковать `RazerAxonSetup_2.9.1.0.exe`.** Не удалось, но **продвинулись на один из
  двух барьеров** — подробности ниже в §8, чтобы следующий заход начинал не с нуля.
  Следствие прежнее: **файловый состав приложения 2.9.1.0, `appsettings.json`, список DLL,
  версия .NET-рантайма и HMAC-ключ ресурсов НЕ проверены** — всё это в таблице выше
  помечено «?». Для ответа на главный вопрос (§4а) распаковка не нужна.
* **Проверить `/v1/login` живьём** — нужен настоящий Razer ID токен, запросов с
  авторизацией не делалось принципиально.
* Файлы разбора лежат в `~/Загрузки/axon-installer-2026-08-10/` (обёртка, распакованный
  payload, декомпилированные исходники установщика, setup 2.9.1.0, JS-бандл витрины).

---

## 8. Inno Setup 6.7.0: барьер 1 снят, барьер 2 описан

Заход был ограничен получасом (на распаковке уже трижды сгорало время). Уложились;
из двух препятствий снято одно. Записано подробно, чтобы не выводить это заново.

Инструмент: `innoextract` 1.10-dev (`6e9e34e`) в `~/Загрузки/axon-installer-2026-08-10/ie-src`,
собранный бинарь — `ie-src/build/innoextract`. Итоговая правка сохранена в репозитории:
**`patch/innoextract-inno67-loader-rev2.patch`**.

### Барьер 1 — заголовок загрузчика, ревизия 2 → РЕШЁН

Было: `Unexpected setup loader revision: 2` → `Setup loader checksum mismatch` →
`Could not determine setup data version`.

Причина: начиная примерно с Inno Setup 6.5 в заголовке загрузчика (сигнатура
`rDlPtS \xcd\xe6\xd7\x7b\x0b\x2a`, в нашем файле по смещению **1 123 164**) поднята ревизия
с 1 до 2, и **смещения расширены до 64 бит** — чтобы описывать установщики больше 4 ГиБ.
`innoextract` продолжал читать их как 32-битные, получал мусорный `header_offset` и потому
не находил строку версии.

Разобранная раскладка ревизии 2 (смещения — от конца 12-байтовой сигнатуры):

| Смещ. | Тип | Значение в нашем файле | Поле |
|---|---|---|---|
| +0 | u32 | 2 | `revision` |
| +4 | **u64** | 63 648 382 | полный размер (пропускается) |
| +12 | **u64** | 62 386 888 | `exe_offset` |
| +20 | u32 | 4 640 968 | `exe_uncompressed_size` |
| +24 | u32 | `0xf2dbe0a5` | CRC32 от `setup.e32` |
| +28 | **u64** | 62 315 557 | `header_offset` |
| +36 | **u64** | 1 126 912 | `data_offset` |
| +44 | u32 | 0 | зарезервировано (новое) |
| +48 | u32 | `0x9be8e908` | CRC32 заголовка |

Раскладка подтверждена тремя независимыми проверками, а не подогнана:

1. `header_offset` = 62 315 557 — **ровно** смещение строки
   `Inno Setup Setup Data (6.7.0)` в файле;
2. `data_offset` = 1 126 912 — **ровно** смещение маркера `zlb\x1a`;
3. CRC32 по 60 байтам от начала сигнатуры даёт `0x9be8e908` — совпадает с записанным.

Правка (`src/loader/offsets.hpp` — расширить `exe_offset`/`header_offset`/`data_offset`
до `boost::uint64_t`; `src/loader/offsets.cpp` — ветка `revision >= 2`) собирается и
работает: теперь выводится `detected setup version: 6.4.0.1 (unicode)`. Таблица версий в
`src/setup/version.cpp` уже была дополнена строками 6.5.0…6.9.0 (сопоставлены с 6.4.0.1).

### Барьер 2 — заголовок блока настроек → ОСТАНОВИЛИСЬ ЗДЕСЬ

Текущая ошибка:

```
Stream error while parsing setup headers!
 ├─ detected setup version: 6.4.0.1 (unicode)
 └─ error reason: block header CRC32 mismatch: iostream error
```

`innoextract` (`src/stream/block.cpp`, `block_reader::get`) ждёт сразу за 64-байтовым
блоком версии девять байт: `CRC32 (u32) + stored_size (u32) + compressed (u8)`.
Фактические байты от `header_offset`:

```
  +64  b2 89 92 dc  00 00 00 00 00 00 00 00 00 00 00 00
  +80  00 00 00 00  00 60 5b 03 00 00 00 00 00 00 00 00
  +96  00 00 00 00  00 00 00 00 00 00 00 00 00 00 00 00
 +112  00 00 00 00  00 fa e8 c9 05 a0 c7 00 00 00 00 00
 +128  00 01 | 6b eb e6 6c | 5d 00 00 20 00 | 00 0a 00 33 …
              ^ CRC подблока  ^ свойства LZMA1
```

Что отсюда точно известно:

* `0xdc9289b2` на `+64` — почти наверняка тот самый CRC32 заголовка блока;
* **данные блока начинаются на `+130`**: сначала 4-байтовый CRC подблока
  (`6b eb e6 6c`), сразу за ним свойства LZMA1 `5d 00 00 20 00` — это опорная точка,
  сомнений не вызывает;
* значит заголовок блока занимает `+68 … +129` = **62 байта** вместо ожидаемых 5.
  Чем заполнены эти 62 байта (почти сплошные нули с вкраплениями
  `00 60 5b 03` на `+85` и `fa e8 c9 05 a0 c7` на `+117`) — **не разобрано**.
  Разумная догадка [ПРЕДП]: размер тоже расширен до 64 бит, добавлены поля под
  многотомность/размер распакованного, но подгонять вслепую не стали.

Чего делать дальше (в порядке дешевизны):

1. Взять исходники Inno Setup 6.7.0 (они открыты, `jrsoftware/issrc`), прочитать
   `TSetupLdrOffsetTable`/`CompressedBlockWriter` — раскладка выяснится за минуты и
   без гадания. **Это правильный путь, начинать надо с него.**
2. Только потом — доводить `block.cpp` и проверять CRC на реальном файле.
3. Барьер 1 к тому моменту уже снят, патч лежит в `patch/`.

Что для этой задачи НЕ требуется: `innounp` под Wine (это запуск чужого кода), и вообще
любой запуск установщика. Барьер 2 — чисто разбор формата.
