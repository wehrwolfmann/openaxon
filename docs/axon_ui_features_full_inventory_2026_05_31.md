# Razer Axon — полный UI/feature/tab инвентарь и GAP-анализ OpenAxon (Opus 4.8, 2026-05-31)

Углубление RE с **фокусом на UI-слое**: полная карта вкладок/экранов, детальный разбор
AI-генерации обоев (X1/Luma) и приоритезированный GAP-список «что достроить в OpenAxon».

> **АКТУАЛИЗАЦИЯ GAP-снимка.** Этот документ — GAP-снимок от 2026-05-31, когда нативный
> клиент `razer-axon-gui.py` был ~2254 строки с 4 вкладками и заглушкой «Coming soon» для AI.
> **По состоянию на 2026-06-18** клиент вырос до ~3501 строки и **7 вкладок навигации**
> (`["home","gallery","create","collections","community","library","profile"]`), и уже
> реализованы: **AI-генерация** (`CreateAIPage`, `razer-axon-gui.py:1298`, режимы в `AI_MODES:1282`),
> **Home/Spotlight** (`HomePage:1882`), **Профиль** (`ProfilePage:1994`),
> **Collections** (`CollectionsPage:2201`). RE/API-факты ниже остаются верны; статусы «OpenAxon»
> по этим разделам обновлены на ✅. Прочие ❌-статусы (контесты, платежи, Spotify и т.д.) ещё актуальны.

**Метод**: статический анализ. Источник UI — **WebView2-кеш** установленного Axon
(`~/.wine/.../RazerAxon/UICache/2.6.2.0/EBWebView/Default/Cache/Cache_Data`, 343 МБ).
Главный JS-бандл извлечён из gzip-записей кеша (`f_000b38`/`f_000b3a`, ~5 МБ распакован,
8.5 МБ после `js-beautify`), CSS (`f_000b39`), ChromaSDK (`f_000b3d`), и **закешированные
живые JSON-ответы API** (`f_000521`, `f_0009df`, `f_000a7d`, …). Установленный Axon
НЕ запускался. `~/.wine` — только чтение. Rexon не затронут.

**Калибровка уверенности (#9)**:
- `[БАНДЛ]` — прочитано в декодированном app-бандле `f_000b38` (высокая).
- `[КЕШ-JSON]` — извлечено из закешированного живого ответа API (фактические данные, высокая).
- `[ДОКИ]` — уже было в существующих доках, здесь подтверждено/сведено.
- `[ПРЕДП]` — вывод/предположение.

---

## 0. Главный вывод (честно, для калибровки ожиданий)

Архитектура: **UI Axon — это веб-приложение, загружаемое с сервера**
(`appsettings.json` → `StartupUri https://axon-api.razer.com/2.6.2.0/`), а НЕ локальные файлы.
WPF-хост открывает WebView2 на этот URL; локально лежат только `DefaultScreenSaver.html`,
`RazerAxonWebPlayer.html` и DLL. Поэтому UI-бандл доступен **только через WebView2-кеш** —
что я и извлёк. Версия бандла собрана `2026-02-04`/обновл. `2026-05-18` (из gzip mtime).

**Что НЕ новое**: API-эндпоинты AI-генерации и маршрутный список React **уже задокументированы**
в `docs/axon-api.md` (раздел 6, все `/wallpaper/generate/*`) и `docs/react-architecture.md`
(раздел 6.4 + полная таблица маршрутов). Прошлый проход (или он же по бандлу) их вытащил.

**Что ДЕЙСТВИТЕЛЬНО новое в этом документе**:
1. Перечень **моделей AI** и значения enum-методов (`text2image/image2image/image2motion/image2video/text2video/upscale`) + соотношения сторон + токен-экономика — `[БАНДЛ]`, в API-доке стояло только «Auth: JWT» без payload.
2. **Фактическая модель данных** AI-фида из живого кеша (поля `prompt/type/method/supplier_name/...`) — `[КЕШ-JSON]`.
3. **Сведённая таблица «UI-вкладка → статус в OpenAxon»** — её не было; именно она нужна для достройки.
4. Полный список **`NAV_*` ключей** (главная навигация) — в доках их не было (0 упоминаний `NAV_`).
5. Подтверждение **рекламы** (`smartadserver.com`, `/task/ads`) и **платежей** (Braintree/PayPal) в UI-слое.

> Итог: «карта» в основном уже есть в `react-architecture.md`. На момент снимка (2026-05-31) дыра —
> **GTK-клиент OpenAxon реализовал лишь 3 из ~20 разделов**, а вкладка Create/AI = заглушка
> `toast("Coming soon")`. **Обновление 2026-06-18:** AI-генерация, Home/Spotlight, Profile и
> Collections уже реализованы (7 вкладок); см. шапку и §1/§3 — соответствующие статусы исправлены.

---

## 1. Полная карта вкладок/экранов (UI-маршруты)

Главная навигация (top-bar) задаётся `NAV_*` i18n-ключами `[БАНДЛ]`. Маршруты — из route-config
бандла (подтверждает `react-architecture.md` §3). Колонка «OpenAxon» — фактический статус в
`razer-axon-gui.py`. **Top-nav (2026-06-18) = 7 кнопок** `["home","gallery","create","collections",
"community","library","profile"]` (`razer-axon-gui.py:2642`); на дату снимка было 4 кнопки.

| Раздел / маршрут | Назначение | Ключевые API / host-методы | OpenAxon |
|---|---|---|---|
| `/` Spotlight (Home) `NAV_DISCOVER` | Главная: карусель, рекомендации, ленты | `/spotlight/index`, `/spotlight/feed`, `/feed/selections` | ✅ есть (`HomePage`, `razer-axon-gui.py:1882`) |
| `/browse` Gallery `NAV_GALLERY` | Каталог обоев + фильтры/категории | `/wallpaper/list`, `/wallpaper/detail`, `/feed/presets` | ✅ есть (вкладки wallpapers/series/authors) |
| — фильтры: Audio/AI/Dynamic/Static/Interactive | Фасеты каталога | query-параметры списка | 🟡 частично (есть чекбоксы, «ai» — фильтр контента, не генерация) |
| `/collections` `NAV_COLLECTION` | Кураторские подборки | `/collection/list`, `/collection/detail` | ✅ есть (`CollectionsPage`, `razer-axon-gui.py:2201`) |
| `/artists` `NAV_ARTISTS` | Каталог художников | `/artist/list`, `/artist/detail`, `/artist/follow` | 🟡 частично (есть ArtistPage по клику, нет общего каталога-вкладки) |
| **`/createAI` `/createAINew` `NAV_AI`** | **AI-генерация обоев (X1/Luma)** | **`/wallpaper/generate/*` (см. §2)** | ✅ **есть (`CreateAIPage`, `razer-axon-gui.py:1298`; режимы `AI_MODES:1282`)** |
| `/aiUpdate` | Редактирование/апдейт AI-обоев | `/aiUpdate`, `/wallpaper/generate/again` | ❌ нет |
| `/create` (legacy) `NAV_CREATE` | Загрузка своих обоев (upload) | `/wallpaper/generate/upload`, `/uploadurl` | ❌ нет (вкладка `create` занята AI-генерацией; upload своих файлов не реализован) |
| `/createHtml` | Конструктор HTML/Canvas-обоев | client-side + upload | ❌ нет |
| `/myWallPaper` `NAV_MYWALLPAPER_NEW` | Библиотека (скачанные) | `/wallpaper/downloaded`, `/library/wishlist` | ✅ есть (Library) |
| `/myCreateWallPaper` | Свои созданные обои | `/wallpaper/generate/list` | ❌ нет |
| `/myWorkshop` `NAV_WORKSHOP_NEW` | Управление публикациями | board/feed API | ❌ нет |
| `/hall` + `/hall/{follow,liked,personal,all}` `NAV_HALL`/`NAV_COMMUNITY` | Community Hall: лента, подписки, лайки, профиль | `/hall/*`, `/feed/public`, `/feed/personal` | 🟡 частично («Community» = популярное, без подвкладок follow/liked/personal) |
| `/communityAlbums` | Альбомы сообщества (доски) | `/board/list`, `/board/detail/list` | ❌ нет |
| `/playlist` + `/playlist/{joined,followed}` `NAV_PALYLISTS` | Плейлисты обоев (ротация) | `/playlist`, `/playlist/followed`, `/playlist/joined` | ❌ нет |
| `/contest` `/contestDetail` `NAV_CONTEST*` | Конкурсы + работы + голосование | `/contest/*` (16 эндпоинтов), `/contest/vote/up` | ❌ нет |
| `/leaderboard` `NAV_*` | Рейтинги/лидерборды | `/leaderboard/*`, `/leaderboard/awardclaim` | ❌ нет |
| `/challenge` | Хэштег-челленджи | `/dailychallenge/list` | ❌ нет |
| `/compaigns` + `/compaigns/{daily,leaderboard,contestDetail,currentContest}` `NAV_CAMPAIGNS`/`NAV_DAILY` | Кампании/ежедневки/события | `/compaigns/*`, `/task/*` | ❌ нет |
| `/followSeries` `/followSeriesDetail` `NAV_SERIES` | Подписки на серии | `/followSeries`, `/collection/*` | 🟡 частично (Series как подвкладка Gallery, без follow) |
| `/followArtist` `/followArtistDetail` | Подписки на художников | `/artist/followlist`, `/artist/follow` | ❌ нет |
| Profile/Account (`/hall/personal`, аватар, badges) | Профиль, бейджи, кошелёк | `/user/profiling`, `/badge/list`, `/wallet/balance`, `/silver/detail` | ✅ есть (`ProfilePage`, `razer-axon-gui.py:1994`) |
| Settings (`SETTINGS`/`GENERAL`/`DISPLAY`/`PERFORMANCE`/`PREFERENCES`) | Настройки приложения | `/user/setting`, `/user/setting/set`, `/system/language` | 🟡 частично (язык RU/EN есть, отдельной вкладки настроек нет) |
| Invite/Referral (`INVITE_FRIENDS_*`) | Приглашение друзей за токены | `/invite`, `/invite/claim` | ❌ нет |
| Redeem (`/wallpaper/redeem`, `/redeem/bycode`) | Активация кодов/банеров | `/redeem/bycode`, `/wallpaper/redeem/list` | ❌ нет |
| Payment/Store (`/payment/*`) | Покупка токенов/подписок | `/payment/order`, `/payment/pkg/list`, Braintree/PayPal | ❌ нет |
| Spotify-обои (`SPOTIFY_*`) | Привязка Spotify к обоям | `/spotify/auth`, `/spotify/token`, `/spotify/profile` | ❌ нет |
| Notifications/Messages (`/feed/messages/*`) | Уведомления, лайки, входящие | `/feed/messages/*`, `/notification/splashscreen` | ❌ нет |
| Badges (`NAV_BADGES`, `BADGES_*`) | Бейджи/награды, декор аватара | `/badge/list`, `/badge/decorate`, `/badge/corner` | ❌ нет |
| Customize (`NAV_CUSTOMIZE`) / Local (`NAV_LOCAL`) | Кастомизация / локальные обои | client-side + player | ❌ нет |

**Итог по разделам (снимок 2026-05-31):** реализовано полностью ✅ — 2 (Gallery, Library);
частично 🟡 — 5; отсутствует ❌ — ~20; AI-генерация отсутствовала целиком.

**Итог по разделам (обновлено 2026-06-18):** реализовано полностью ✅ — 6
(Gallery, Library, **AI-генерация** `CreateAIPage`, **Home/Spotlight** `HomePage`,
**Collections** `CollectionsPage`, **Профиль/кошелёк** `ProfilePage`); частично 🟡 — 5;
отсутствует ❌ — ~16. **AI-генерация теперь есть** (7 вкладок навигации, см. шапку).

### Доп. находки UI-слоя `[БАНДЛ]/[КЕШ]`
- **Реклама встроена в клиент**: `smartadserver.com` (euw1/euw2/europe-west4) — 243+135+104 запросов в кеше; маршруты `/task/ads`, `/task/ads/claim`, `/task/adsid`; в бандле webpack-чанк рекламного SDK (`f_000724`: `RENDER_BEGUN/AD_FOUND`). Пользователь смотрит рекламу за токены.
- **Платежи**: `js.braintreegateway.com`, `www.paypal.com`/`sandbox.paypal.com` в кеше → внутренние покупки токенов/подписок через Braintree+PayPal.
- **Razer Gold/Silver экономика**: `SPOTIFY_PAPER_RAZER_GOLD`, `/silver/detail`, `/wallet/balance` — двойная валюта (Gold платная, Silver зарабатываемая).
- **CDN ассетов**: `axon-assets-cdn.razerzone.com` (thumbnails, carousel, luma/thumbs, community-feed/motion/*.mp4), `avatar.razerzone.com` (аватары).
- **Chroma/RGB**: `CHROMA_POWERBY`, `CHROMA_REMARK`, ChromaSDK JS (`f_000b3d`) — синхронизация обоев с RGB-периферией Razer (документировано в `chroma-sdk.md`).

---

## 2. AI-генерация обоев (X1 / Luma) — ДЕТАЛЬНО

Это приоритет. Фича присутствует и зрелая: 811 упоминаний `GENERATE`, 569 `PROMPT`, отдельные
enum `GenerateType/GenerateStatus/GenerateResult`, контексты `generateVideo/generateImg/generateAgain`. `[БАНДЛ]`

### 2.1 Точки входа (UI)
- Маршруты `/createAI`, `/createAINew` (новый UI, тот же компонент), `/aiUpdate` (правка).
- React-компоненты (по `react-architecture.md`): `CreateWithAI` (prompt→generate→publish),
  `Upscaler`. Контекст данных — `LumaDataContext` (text2image/text2video). `[ДОКИ]`
- UI-события: `CHANGE_AI_TAB`, `SHOW_AI_TUTORIAL`, `SHOW_UPSCALE_RESULT`, `ACCEPT_UPSCALE`. `[ДОКИ]`
- i18n-разделы: `AI_TYPE_TEXT` (text-to-image), `AI_TYPE_UPSCALER`, `AI_MOTION_*` (image-to-motion), `UPSCALE_*` (≈20 ключей), `GENERATE_*` (≈40 ключей). `[БАНДЛ]`

### 2.2 Режимы генерации (enum `method`) `[БАНДЛ]`
Из бандла: `["image2motion","text2video","image2video"]` группируются как видео-вывод;
полный набор значений `method`:

| `method` | Что делает | Эндпоинт |
|---|---|---|
| `text2image` | Текст → картинка | `POST /wallpaper/generate` |
| `image2image` | Картинка → картинка | `POST /wallpaper/generate/image2image` |
| `text2video` | Текст → видео-обои | `POST /wallpaper/generate/video` |
| `image2video` | Картинка → видео | `POST /wallpaper/generate/image2video` |
| `image2motion` | Картинка → «motion» (живое фото) | `POST /wallpaper/generate/image2motion` |
| `upscale` | Апскейл результата | `POST /wallpaper/generate/upscale` |
| (alchemy/sample) | Стартовая генерация-семпл | `POST /wallpaper/generate/alchemy` |
| (nobg) | Удалить фон | `POST /wallpaper/generate/nobg` |
| (batch) | Пакетная (Luma pipeline) | `POST /wallpaper/generate/batch` |
| (reference) | Luma image-reference | `POST /wallpaper/generate/image2image/reference` |

### 2.3 Параметры запроса (поля payload) `[БАНДЛ]`
- `prompt`, `negative_prompt` — позитивный/негативный промпт.
- `resolution` (исп. 9×), `ratio` — соотношение сторон из набора: **`1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `21:9`** (по 3 вхождения каждого).
- `strength` — сила влияния референса (image2image/motion: `AI_IMAGE_STRENGTH`, `AI_MOTION_STRENGTH`).
- модель — выбирается из `GET /wallpaper/generate/model`.
- Upscale-параметры (i18n `UPSCALE_SETTING_*`): `DIMEN` (целевое разрешение), `MULTI` (кратность), `STRENGTH`, `STYLE` (4 стиля: **CI, GE, CG, 2D** — `UPSCALE_STYLE_CI/GE/CG`), `PROMPT`.

### 2.4 Модели/поставщики `[БАНДЛ]/[ДОКИ]`
- `GET /wallpaper/generate/model` возвращает список моделей. В доке `axon-api.md` упомянуты **Leonardo, HiDream, Luma**. В бандле явно встречается `"leonardo"`; CDN-путь `axon-assets-cdn.../luma/thumbs/...` подтверждает **Luma AI** для видео/motion.
- `GET /wallpaper/generate/product` — список «продуктов» (тарифов/пакетов генерации).
- Поле `supplier_name` в данных обоев → имя поставщика модели показывается в UI.
- `GENERATE_POWERED` («Powered by …») — атрибуция модели в интерфейсе.

### 2.5 Токен-экономика `[БАНДЛ]`
- `GET /wallpaper/generate/price` — цена генерации в токенах.
- i18n: `GENERATE_COST`, `GENERATE_TOKEN(S)`, `GENERATE_REMAINING`, `GENERATE_TOP_UP`, `GENERATE_PAID`, `cost_tokens`, `token_counts`, `balance_help`.
- Токены пополняются: покупкой (`/payment/*`, Braintree/PayPal), просмотром рекламы (`/task/ads/claim`), приглашением друзей (`INVITE_FRIENDS_GET_TOKENS_INFO`), ежедневками/конкурсами.
- `GET /wallpaper/generate/existorder` / `suborder` — управление заказами/подзаказами генерации.

### 2.6 Полный процесс (flow) воспроизведения
1. Открыть `/createAINew`; выбрать режим (`CHANGE_AI_TAB`: Text / Image / Motion / Upscaler).
2. Загрузить токены, получить модели: `GET /generate/model`, `GET /generate/product`, `GET /generate/price`.
3. (image2*) загрузить исходник: `GET /generate/uploadurl` → PUT на presigned URL → `/generate/upload`, список загрузок `/generate/uploadlist`.
4. Отправить генерацию: `POST /wallpaper/generate` (или `/image2image|/image2motion|/image2video|/video|/batch|/alchemy`) с `{prompt, negative_prompt, ratio, strength, model, ...}`.
5. Поллинг статуса: `GET /generate/info` (status); список заказов `GET /generate/list`; детали `GET /generate/details` / `/detail`. Состояния включают «генерируется» (`GENERATE_GENERATEING`/`AI_FITLER_ING` — идёт NSFW-фильтрация).
6. Пост-обработка: `POST /generate/upscale`, `POST /generate/nobg`, `POST /generate/again` (повтор с теми же параметрами).
7. **NSFW-модерация**: `AI_NSFW_TITLE/CLICK/SHARE_TIPS/APPEAL` — результат может быть помечен, есть апелляция (`/appeal`, `AI_APPEAL_*`).
8. **Публикация**: `AI_PUBLISH/PUBLISHING/PUBLISHED`, `AI_AUTOPUB` (автопубликация), `AI_PUBLISH_TC` (условия) → обои попадают в Community-фид.
9. Удаление: `POST /generate/delete` (весь заказ) / `/deletedetail` (один итог).

### 2.7 Фактическая модель данных (из живого кеша) `[КЕШ-JSON]`
Из закешированного ответа фида (`f_0009df`, `f_000a7d`):
```json
{
  "feed_id": 148259,
  "uuid": "ZoRHdcEvF4O...==",        // base64-обёрнутый id (ср. шифрование обоев в прошлом RE)
  "title": "Waves: Crimson Dusk",
  "prompt": "anime-style ocean waves ... \n<negative/стиль во второй строке>",
  "type": 1,                          // 1 = image, 2 = motion/video (image -> .mp4 в поле image)
  "image":  "https://axon-assets-cdn.razerzone.com/community-feed/.../*.webp|*.mp4",
  "image1": ".../thumbs/500x280/*.webp",
  "fav_num": 12, "is_fav": false, "download_num": 268,
  "avatar": "...", "razer_id": "Vivierra",
  "detail_id": 2869726,
  "sharing": "https://axon.razer.com/sharing/community?f=148259",
  "user_leaderboard_best_rank": 1, "decorate_badge_image": "...badge..."
}
```
То есть промпт хранится прямо в фиде (часто включает «4k wallpaper, negative space» и
вторую строку с цветовой схемой/негативом). Motion-обои хранятся как `.mp4` на CDN.

### 2.8 Как достроить в OpenAxon (практически)
- Эндпоинты и host-объект уже описаны (`axon-api.md` §6, `webview-host-objects.md`). Нужна **GTK-страница** `CreateAIPage`: textarea промпта (+ negative), выбор режима/модели/ratio, кнопка Generate, грид результатов с поллингом `GET /generate/info`, действия Upscale/NoBG/Again/Publish/Download.
- Для рендера: image → статичные обои (есть в player), motion/video `.mp4` → Video-обои (player уже умеет `.mp4`, `openaxon-player.py:52`).
- Токены/оплата — отдельная зона; на первом этапе можно показывать баланс (`/wallet/balance`) и сообщение, что пополнение — в оригинальном клиенте.

---

## 3. GAP-список (приоритезированный): что достроить в OpenAxon

**Снимок 2026-05-31** (для истории): OpenAxon (`razer-axon-gui.py`, ~2254 строки) реализовывал
top-nav из 4 кнопок (`gallery`/`create`/`community`/`library`), Gallery с подвкладками
wallpapers/series/authors + фильтры, ArtistPage, DetailView, Community (популярное),
Library (скачанные); `create` → `toast("Coming soon")`.

**Обновлено 2026-06-18:** клиент (`razer-axon-gui.py`, ~3501 строка) имеет **7 кнопок навигации**
`["home","gallery","create","collections","community","library","profile"]` и реализует
**AI-генерацию** (`CreateAIPage:1298`, режимы `AI_MODES:1282`), **Home/Spotlight** (`HomePage:1882`),
**Профиль/кошелёк** (`ProfilePage:1994`), **Collections** (`CollectionsPage:2201`) — пункты #1, #3, #5, #6
ниже отмечены ✅ ГОТОВО. Player (`openaxon-player.py`) умеет Video + Static (Web детектится, но не рендерится).

| # | Фича | Приоритет | Сложность | Зависимости (готовы?) |
|---|---|---|---|---|
| 1 | **AI-генерация (`/createAI`)** — страница Text/Image/Motion/Upscale, поллинг, download/apply | ✅ **ГОТОВО** (`CreateAIPage:1298`) | — | реализовано 2026-06 |
| 2 | **AI Upscaler** (4 стиля CI/GE/CG/2D) | 🔴 P0 | Средняя | часть AI-страницы |
| 3 | **Spotlight/Home** стартовый экран (карусель + ленты) | ✅ **ГОТОВО** (`HomePage:1882`) | — | реализовано 2026-06 |
| 4 | **Community Hall** подвкладки (Follow/Liked/Personal) + лента | 🟠 P1 | Средняя | частично есть (Community) |
| 5 | **Профиль/аккаунт** (avatar, badges, wallet/silver) | ✅ **ГОТОВО** (`ProfilePage:1994`) | — | реализовано 2026-06 |
| 6 | **Collections / Series follow** как полноценные разделы | ✅ **ГОТОВО** (`CollectionsPage:2201`; Series follow — частично) | — | реализовано 2026-06 |
| 7 | **Playlists** (ротация обоев) | 🟡 P2 | Средняя | `/playlist/*`; нужна логика смены в player |
| 8 | **Settings-вкладка** (General/Display/Performance, мультимонитор) | 🟡 P2 | Низкая–средняя | `/user/setting*`; язык уже есть |
| 9 | **Contest / Leaderboard / Daily / Campaigns** (геймификация) | 🟡 P2 | Высокая (много экранов) | `/contest/*`, `/leaderboard/*`, `/compaigns/*` |
| 10 | **Notifications / Messages** | 🟢 P3 | Средняя | `/feed/messages/*` |
| 11 | **Invite friends / Redeem codes** | 🟢 P3 | Низкая | `/invite`, `/redeem/bycode` |
| 12 | **Spotify-обои** привязка | 🟢 P3 | Средняя | `/spotify/*` (нужен OAuth) |
| 13 | **Payment/Store** (токены/подписки) | 🟢 P3 | Высокая | Braintree/PayPal — на Linux спорно, можно отложить |
| 14 | **Web-обои в player** (HTML рендер) | 🟡 P2 | Средняя | player детектит, но не рендерит |
| 15 | **Реклама за токены** | ⚪ skip | — | не нужно воспроизводить на open-клиенте |

Рекомендуемый порядок старта (снимок 2026-05-31): **#1 → #2** (AI + Upscaler, прямой запрос),
затем #5 (профиль/кошелёк нужен для отображения токенов AI), затем #3/#4 (Home/Community для полноты UX).

**Обновлено 2026-06-18:** пункты #1 (AI-генерация), #3 (Home), #5 (Профиль), #6 (Collections)
уже реализованы. **Актуальные приоритеты:** доделать #2 (AI Upscaler, если ещё не в `CreateAIPage`),
#4 (подвкладки Community Hall Follow/Liked/Personal), затем #7 (Playlists) и #8 (Settings-вкладка).

---

## 4. Что найдено НОВОГО vs прошлый RE

| Находка | Статус в прошлых доках | Источник |
|---|---|---|
| Полный список `NAV_*` (20 разделов главной навигации) | отсутствовал (0 упоминаний `NAV_`) | `[БАНДЛ]` |
| enum значения `method` (text2image/image2image/image2motion/image2video/text2video/upscale) | частично (эндпоинты были, enum-значения нет) | `[БАНДЛ]` |
| Соотношения сторон AI (1:1,16:9,9:16,4:3,3:4,21:9) | нет | `[БАНДЛ]` |
| Upscale-стили CI/GE/CG/2D + настройки (DIMEN/MULTI/STRENGTH/STYLE) | нет | `[БАНДЛ]` |
| Токен-экономика AI (price/cost_tokens/top_up/remaining) детально | поверхностно | `[БАНДЛ]` |
| NSFW-модерация + апелляция + autopub flow | нет | `[БАНДЛ]` |
| Фактическая модель данных AI-фида (prompt/type/method/CDN-пути) | нет | `[КЕШ-JSON]` |
| Реклама в UI (smartadserver, /task/ads*) | нет | `[БАНДЛ]/[КЕШ]` |
| Платежи Braintree+PayPal в WebView | нет | `[КЕШ]` |
| Модели: Leonardo подтверждён в бандле, Luma по CDN-путям | были названы в доке без подтверждения | `[БАНДЛ]/[КЕШ]` |
| UICache как извлекаемый источник всего UI-бандла (gzip-записи) | метод не описан | метод |

**Уже было (подтверждено, не дублирую)**: полный список `/wallpaper/generate/*` эндпоинтов
(`axon-api.md` §6), таблица React-маршрутов и компонентов `CreateWithAI`/`Upscaler`/`LumaDataContext`
(`react-architecture.md` §3, §6.4), host-объекты/пайпы/расшифровка обоев
(`webview-host-objects.md`, `razer-central-ipc.md`, `axon_reverse_engineering_2026_05_31.md`).

---

## 5. Ограничения / честность
- i18n в бандле — **только ключи**, значения (англ. тексты) подгружаются с сервера → точные надписи кнопок не извлечь оффлайн (есть ключи + смысл).
- `GenerateType`/`GenerateStatus` — это runtime-enum'ы (минифицированные `V`,`fe`); числовые значения не раскрыты статически без трассировки.
- Payload'ы запросов восстановлены по именам полей в бандле + живым ответам кеша; точные обязательные/опциональные поля каждого POST не валидированы (Axon не запускался).
- Версия UI зафиксирована на `2.6.2.0` (как и в прошлом RE) — обновлений не было.
