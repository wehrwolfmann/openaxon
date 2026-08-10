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

1. **Наш порт разошёлся с оригиналом на три версии.** Axon в проде теперь **2.9.1.0**
   (сборка витрины от **20260728**), у нас в коде зашито `2.6.2.0`.
2. **База API и схема авторизации НЕ изменились.** Тот же `https://axon-api.razer.com/v1`,
   тот же `POST /login {token, is_guest, uuid}` → `data.authorization`, те же заголовки
   `Authorization` / `X-Version` / `X-Language`. Чинить надо только номер версии.
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

### Дельта по эндпойнтам

Из бандла извлечено 184 строковых пути. Пропавших относительно `docs/axon-api.md` нет
(разошлись только шаблоны вида `/wallpaper/vote/{type}` против префикса `/wallpaper/vote/`).
Новые (не описаны у нас), сгруппировано:

* **Конкурсы/лидерборды/ежедневки**: `/contest`, `/contest/award/detail`, `/challenge`,
  `/dailychallenge/list`, `/dailychallenge/staytunedbadges`, `/leaderboard`,
  `/explore/leaderboard`, `/explore/dailychallenge`, `/compaigns`, `/compaigns/daily`,
  `/compaigns/leaderboard`, `/campaign/code`
* **Сообщество/доски**: `/explore/board`, `/hall`, `/hall/all`, `/hall/follow`,
  `/hall/liked`, `/hall/personal`, `/feed/messages/pending`
* **Плейлисты**: `/playlist`, `/playlist/followed`, `/playlist/joined`
* **Реклама как источник валюты**: `/task/ads`, `/task/adsid`, `/task/ads/claim`
* **Монетизация/рефералы**: `/silver/detail`, `/redeem/bycode`, `/wallpaper/redeem/bycode`,
  `/referral/redeem`, `/promote/info`
* **Прочее**: `/system/setting`, `/artists`, `/collections`, `/compilations`,
  `/spotlight/index/carousel`, `/spotlight/index/category`, `/browse`, `/create`,
  `/properties`

Новые внешние домены в бандле: `https://www18.smartadserver.com`, `https://cdn.leonardo.ai`,
`https://leonardo.ai`, `https://hidreamai.com`, `https://gold.razer.com` — то есть у
генерации добавились сторонние модели, а у экономики — рекламные задания.

---

## 5. Сводная таблица «май 2026 → август 2026»

| Что | Было (2026-05-31) | Стало (2026-08-10) | Ломает порт? |
|---|---|---|---|
| Версия Axon | 2.6.2.0 | **2.9.1.0** (витрина 20260728) | да, `X-Version`/UA |
| База API | `https://axon-api.razer.com/v1` | без изменений | нет |
| Схема входа | `POST /login {token,is_guest,uuid}` → `authorization` | без изменений | нет |
| Заголовки | `Authorization` / `X-Version` / `X-Language` | без изменений | нет |
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

1. **Версия API.** `razer-sync.py:30` и `razer-axon-gui.py:32`: `API_VERSION = "2.6.2.0"` →
   `"2.9.1.0"`. Там же User-Agent `RazerAxon/2.6.2.0` (три места в `razer-axon-gui.py`:
   строки 250, 331, 910). **Лучше не хардкодить**: тянуть версию из манифеста
   (`GET discovery → GET manifest3 → items[name=="Sequoia"].version`) с фолбэком на
   зашитое значение — тогда следующее обновление Razer нас не догонит.
2. **UA установщика** в `install-axon-linux.sh:306,387`: `RazerLWI/2.4.0.868` →
   `RazerLWI/2.6.0.890` (тоже лучше выводить из версии скачанной обёртки).
3. **Проверить связку с Razer Central.** В манифесте Axon теперь явный модуль
   `Natasha 7.23.0.1220` с `installation_priority: 300`, то есть Razer Central ставится
   первым и Axon от него зависит. Наш `razer-token-inject.py` пишет в канал
   `{FC828A97-C116-453D-BD88-AD471496E03C}` командой `WebApp_SetLoginSuccessFromWeb`
   (131094) — надо убедиться, что в 7.23 номера команд и формат пакета не поменялись.
4. **Скрипт установки** должен брать `download_url` из живого манифеста (он уже так делает
   через `manifest()`), но захардкоженные в комментариях/фолбэках 2.6.2.0 и старый хеш
   `8TQEz6XZ` надо вычистить, чтобы не сбивать с толку.
5. **Обновить `docs/axon-api.md`** новыми эндпойнтами (конкурсы, лидерборды, доски,
   рекламные задания, silver/redeem) — это ~45 новых путей, они же новые экраны в UI.
6. **Патч `RazerAxon.UserManager.dll`** заведомо не подойдёт к 2.9.1.0 (файл собран заново),
   его придётся пересобрать после того, как удастся распаковать setup.

---

## 7. Чего сделать НЕ удалось

* **Распаковать `RazerAxonSetup_2.9.1.0.exe`.** Это Inno Setup с данными версии **6.7.0**;
  `innoextract` 1.9 (в репозитории) знает до 6.0.5, git-master — до 6.4.0.1, оба падают на
  `Unexpected setup loader revision: 2` / `Could not determine setup data version`. 7-Zip
  Inno не поддерживает. Следствие: **файловый состав приложения 2.9.1.0, `appsettings.json`,
  список DLL, версия .NET-рантайма и HMAC-ключ ресурсов НЕ проверены** — всё это в таблице
  выше помечено «?». Варианты дальше: дождаться поддержки 6.7 в innoextract, дописать её
  самому (нужны boost-заголовки и разбор нового loader-заголовка), либо `innounp` под Wine
  (это уже запуск чужого кода — только с отдельного разрешения).
* **Проверить `/v1/login` живьём** — нужен настоящий Razer ID токен, запросов с
  авторизацией не делалось принципиально.
* Файлы разбора лежат в `~/Загрузки/axon-installer-2026-08-10/` (обёртка, распакованный
  payload, декомпилированные исходники установщика, setup 2.9.1.0, JS-бандл витрины).
