# Razer Axon — full UI/feature/tab inventory and OpenAxon GAP analysis (2026-05-31)

A deeper RE pass **focused on the UI layer**: a complete map of tabs/screens, a detailed breakdown
of AI wallpaper generation (X1/Luma) and a prioritized GAP list of "what to build next in OpenAxon".

> **GAP SNAPSHOT UPDATE.** This document is a GAP snapshot from 2026-05-31, when the native
> client `razer-axon-gui.py` was ~2254 lines with 4 tabs and a "Coming soon" stub for AI.
> **As of 2026-06-18** the client has grown to ~3501 lines and **7 navigation tabs**
> (`["home","gallery","create","collections","community","library","profile"]`), and the following
> are already implemented: **AI generation** (`CreateAIPage`, `razer-axon-gui.py:1298`, modes in `AI_MODES:1282`),
> **Home/Spotlight** (`HomePage:1882`), **Profile** (`ProfilePage:1994`),
> **Collections** (`CollectionsPage:2201`). The RE/API facts below remain correct; the "OpenAxon" statuses
> for these sections have been updated to ✅. The other ❌ statuses (contests, payments, Spotify, etc.) are still current.

**Method**: static analysis. The UI source is the **WebView2 cache** of the installed Axon
(`~/.wine/.../RazerAxon/UICache/2.6.2.0/EBWebView/Default/Cache/Cache_Data`, 343 MB).
The main JS bundle was extracted from the cache's gzip entries (`f_000b38`/`f_000b3a`, ~5 MB unpacked,
8.5 MB after `js-beautify`), along with the CSS (`f_000b39`), ChromaSDK (`f_000b3d`), and **cached
live API JSON responses** (`f_000521`, `f_0009df`, `f_000a7d`, …). The installed Axon
was NOT launched. `~/.wine` was read-only.

**Confidence calibration (#9)**:
- `[BUNDLE]` — read in the decoded app bundle `f_000b38` (high).
- `[CACHE-JSON]` — extracted from a cached live API response (actual data, high).
- `[DOCS]` — already present in existing docs, confirmed/consolidated here.
- `[ASSUMED]` — inference/assumption.

---

## 0. Main conclusion (honestly, to calibrate expectations)

Architecture: **the Axon UI is a web application loaded from a server**
(`appsettings.json` → `StartupUri https://axon-api.razer.com/2.6.2.0/`), NOT local files.
The WPF host opens WebView2 on that URL; locally there are only `DefaultScreenSaver.html`,
`RazerAxonWebPlayer.html` and DLLs. So the UI bundle is available **only through the WebView2 cache** —
which is what I extracted. The bundle version was built `2026-02-04`/updated `2026-05-18` (from the gzip mtime).

**What is NOT new**: the AI generation API endpoints and the React route list are **already documented**
in `docs/axon-api.md` (section 6, all `/wallpaper/generate/*`) and `docs/react-architecture.md`
(section 6.4 + the full route table). A previous pass (or this same one, over the bundle) extracted them.

**What IS new in this document**:
1. The list of **AI models** and the enum values of the methods (`text2image/image2image/image2motion/image2video/text2video/upscale`) + aspect ratios + token economy — `[BUNDLE]`; the API doc only said "Auth: JWT" with no payload.
2. The **actual data model** of the AI feed from the live cache (fields `prompt/type/method/supplier_name/...`) — `[CACHE-JSON]`.
3. A **consolidated "UI tab → status in OpenAxon" table** — it did not exist; this is exactly what is needed to complete the client.
4. The full list of **`NAV_*` keys** (main navigation) — they were absent from the docs (0 mentions of `NAV_`).
5. Confirmation of **ads** (`smartadserver.com`, `/task/ads`) and **payments** (Braintree/PayPal) in the UI layer.

> Bottom line: the "map" mostly already exists in `react-architecture.md`. At the time of the snapshot (2026-05-31) the gap was that
> **the OpenAxon GTK client implemented only 3 of ~20 sections**, and the Create/AI tab was a stub
> `toast("Coming soon")`. **Update 2026-06-18:** AI generation, Home/Spotlight, Profile and
> Collections are already implemented (7 tabs); see the header and §1/§3 — the corresponding statuses have been corrected.

---

## 1. Full map of tabs/screens (UI routes)

The main navigation (top bar) is defined by `NAV_*` i18n keys `[BUNDLE]`. The routes come from the bundle's route config
(confirms `react-architecture.md` §3). The "OpenAxon" column is the actual status in
`razer-axon-gui.py`. **Top nav (2026-06-18) = 7 buttons** `["home","gallery","create","collections",
"community","library","profile"]` (`razer-axon-gui.py:2642`); at the snapshot date there were 4 buttons.

| Section / route | Purpose | Key APIs / host methods | OpenAxon |
|---|---|---|---|
| `/` Spotlight (Home) `NAV_DISCOVER` | Home: carousel, recommendations, feeds | `/spotlight/index`, `/spotlight/feed`, `/feed/selections` | ✅ present (`HomePage`, `razer-axon-gui.py:1882`) |
| `/browse` Gallery `NAV_GALLERY` | Wallpaper catalog + filters/categories | `/wallpaper/list`, `/wallpaper/detail`, `/feed/presets` | ✅ present (wallpapers/series/authors tabs) |
| — filters: Audio/AI/Dynamic/Static/Interactive | Catalog facets | list query parameters | 🟡 partial (checkboxes exist; "ai" is a content filter, not generation) |
| `/collections` `NAV_COLLECTION` | Curated collections | `/collection/list`, `/collection/detail` | ✅ present (`CollectionsPage`, `razer-axon-gui.py:2201`) |
| `/artists` `NAV_ARTISTS` | Artist catalog | `/artist/list`, `/artist/detail`, `/artist/follow` | 🟡 partial (ArtistPage on click exists, no general catalog tab) |
| **`/createAI` `/createAINew` `NAV_AI`** | **AI wallpaper generation (X1/Luma)** | **`/wallpaper/generate/*` (see §2)** | ✅ **present (`CreateAIPage`, `razer-axon-gui.py:1298`; modes `AI_MODES:1282`)** |
| `/aiUpdate` | Editing/updating AI wallpapers | `/aiUpdate`, `/wallpaper/generate/again` | ❌ missing |
| `/create` (legacy) `NAV_CREATE` | Uploading your own wallpapers | `/wallpaper/generate/upload`, `/uploadurl` | ❌ missing (the `create` tab is taken by AI generation; uploading your own files is not implemented) |
| `/createHtml` | HTML/Canvas wallpaper builder | client-side + upload | ❌ missing |
| `/myWallPaper` `NAV_MYWALLPAPER_NEW` | Library (downloaded) | `/wallpaper/downloaded`, `/library/wishlist` | ✅ present (Library) |
| `/myCreateWallPaper` | Your own created wallpapers | `/wallpaper/generate/list` | ❌ missing |
| `/myWorkshop` `NAV_WORKSHOP_NEW` | Managing publications | board/feed API | ❌ missing |
| `/hall` + `/hall/{follow,liked,personal,all}` `NAV_HALL`/`NAV_COMMUNITY` | Community Hall: feed, follows, likes, profile | `/hall/*`, `/feed/public`, `/feed/personal` | 🟡 partial ("Community" = popular, without the follow/liked/personal subtabs) |
| `/communityAlbums` | Community albums (boards) | `/board/list`, `/board/detail/list` | ❌ missing |
| `/playlist` + `/playlist/{joined,followed}` `NAV_PALYLISTS` | Wallpaper playlists (rotation) | `/playlist`, `/playlist/followed`, `/playlist/joined` | ❌ missing |
| `/contest` `/contestDetail` `NAV_CONTEST*` | Contests + entries + voting | `/contest/*` (16 endpoints), `/contest/vote/up` | ❌ missing |
| `/leaderboard` `NAV_*` | Rankings/leaderboards | `/leaderboard/*`, `/leaderboard/awardclaim` | ❌ missing |
| `/challenge` | Hashtag challenges | `/dailychallenge/list` | ❌ missing |
| `/compaigns` + `/compaigns/{daily,leaderboard,contestDetail,currentContest}` `NAV_CAMPAIGNS`/`NAV_DAILY` | Campaigns/dailies/events | `/compaigns/*`, `/task/*` | ❌ missing |
| `/followSeries` `/followSeriesDetail` `NAV_SERIES` | Series subscriptions | `/followSeries`, `/collection/*` | 🟡 partial (Series as a Gallery subtab, without follow) |
| `/followArtist` `/followArtistDetail` | Artist subscriptions | `/artist/followlist`, `/artist/follow` | ❌ missing |
| Profile/Account (`/hall/personal`, avatar, badges) | Profile, badges, wallet | `/user/profiling`, `/badge/list`, `/wallet/balance`, `/silver/detail` | ✅ present (`ProfilePage`, `razer-axon-gui.py:1994`) |
| Settings (`SETTINGS`/`GENERAL`/`DISPLAY`/`PERFORMANCE`/`PREFERENCES`) | App settings | `/user/setting`, `/user/setting/set`, `/system/language` | 🟡 partial (RU/EN language exists, no separate settings tab) |
| Invite/Referral (`INVITE_FRIENDS_*`) | Inviting friends for tokens | `/invite`, `/invite/claim` | ❌ missing |
| Redeem (`/wallpaper/redeem`, `/redeem/bycode`) | Activating codes/banners | `/redeem/bycode`, `/wallpaper/redeem/list` | ❌ missing |
| Payment/Store (`/payment/*`) | Buying tokens/subscriptions | `/payment/order`, `/payment/pkg/list`, Braintree/PayPal | ❌ missing |
| Spotify wallpapers (`SPOTIFY_*`) | Linking Spotify to wallpapers | `/spotify/auth`, `/spotify/token`, `/spotify/profile` | ❌ missing |
| Notifications/Messages (`/feed/messages/*`) | Notifications, likes, inbox | `/feed/messages/*`, `/notification/splashscreen` | ❌ missing |
| Badges (`NAV_BADGES`, `BADGES_*`) | Badges/rewards, avatar decoration | `/badge/list`, `/badge/decorate`, `/badge/corner` | ❌ missing |
| Customize (`NAV_CUSTOMIZE`) / Local (`NAV_LOCAL`) | Customization / local wallpapers | client-side + player | ❌ missing |

**Section totals (snapshot 2026-05-31):** fully implemented ✅ — 2 (Gallery, Library);
partial 🟡 — 5; missing ❌ — ~20; AI generation was missing entirely.

**Section totals (updated 2026-06-18):** fully implemented ✅ — 6
(Gallery, Library, **AI generation** `CreateAIPage`, **Home/Spotlight** `HomePage`,
**Collections** `CollectionsPage`, **Profile/wallet** `ProfilePage`); partial 🟡 — 5;
missing ❌ — ~16. **AI generation is now present** (7 navigation tabs, see the header).

### Additional UI-layer findings `[BUNDLE]/[CACHE]`
- **Ads are built into the client**: `smartadserver.com` (euw1/euw2/europe-west4) — 243+135+104 requests in the cache; routes `/task/ads`, `/task/ads/claim`, `/task/adsid`; the bundle contains a webpack chunk of an ad SDK (`f_000724`: `RENDER_BEGUN/AD_FOUND`). The user watches ads in exchange for tokens.
- **Payments**: `js.braintreegateway.com`, `www.paypal.com`/`sandbox.paypal.com` in the cache → in-app purchases of tokens/subscriptions via Braintree+PayPal.
- **Razer Gold/Silver economy**: `SPOTIFY_PAPER_RAZER_GOLD`, `/silver/detail`, `/wallet/balance` — a dual currency (Gold is paid, Silver is earned).
- **Asset CDN**: `axon-assets-cdn.razerzone.com` (thumbnails, carousel, luma/thumbs, community-feed/motion/*.mp4), `avatar.razerzone.com` (avatars).
- **Chroma/RGB**: `CHROMA_POWERBY`, `CHROMA_REMARK`, ChromaSDK JS (`f_000b3d`) — syncing wallpapers with Razer RGB peripherals (documented in `chroma-sdk.md`).

---

## 2. AI wallpaper generation (X1 / Luma) — IN DETAIL

This is the priority. The feature is present and mature: 811 mentions of `GENERATE`, 569 of `PROMPT`, separate
enums `GenerateType/GenerateStatus/GenerateResult`, contexts `generateVideo/generateImg/generateAgain`. `[BUNDLE]`

### 2.1 Entry points (UI)
- Routes `/createAI`, `/createAINew` (new UI, same component), `/aiUpdate` (editing).
- React components (per `react-architecture.md`): `CreateWithAI` (prompt→generate→publish),
  `Upscaler`. The data context is `LumaDataContext` (text2image/text2video). `[DOCS]`
- UI events: `CHANGE_AI_TAB`, `SHOW_AI_TUTORIAL`, `SHOW_UPSCALE_RESULT`, `ACCEPT_UPSCALE`. `[DOCS]`
- i18n sections: `AI_TYPE_TEXT` (text-to-image), `AI_TYPE_UPSCALER`, `AI_MOTION_*` (image-to-motion), `UPSCALE_*` (≈20 keys), `GENERATE_*` (≈40 keys). `[BUNDLE]`

### 2.2 Generation modes (enum `method`) `[BUNDLE]`
From the bundle: `["image2motion","text2video","image2video"]` are grouped as video output;
the full set of `method` values:

| `method` | What it does | Endpoint |
|---|---|---|
| `text2image` | Text → image | `POST /wallpaper/generate` |
| `image2image` | Image → image | `POST /wallpaper/generate/image2image` |
| `text2video` | Text → video wallpaper | `POST /wallpaper/generate/video` |
| `image2video` | Image → video | `POST /wallpaper/generate/image2video` |
| `image2motion` | Image → "motion" (live photo) | `POST /wallpaper/generate/image2motion` |
| `upscale` | Upscaling the result | `POST /wallpaper/generate/upscale` |
| (alchemy/sample) | Initial sample generation | `POST /wallpaper/generate/alchemy` |
| (nobg) | Remove background | `POST /wallpaper/generate/nobg` |
| (batch) | Batch (Luma pipeline) | `POST /wallpaper/generate/batch` |
| (reference) | Luma image reference | `POST /wallpaper/generate/image2image/reference` |

### 2.3 Request parameters (payload fields) `[BUNDLE]`
- `prompt`, `negative_prompt` — positive/negative prompt.
- `resolution` (used 9×), `ratio` — aspect ratio from the set: **`1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `21:9`** (3 occurrences each).
- `strength` — strength of the reference's influence (image2image/motion: `AI_IMAGE_STRENGTH`, `AI_MOTION_STRENGTH`).
- model — chosen from `GET /wallpaper/generate/model`.
- Upscale parameters (i18n `UPSCALE_SETTING_*`): `DIMEN` (target resolution), `MULTI` (multiplier), `STRENGTH`, `STYLE` (4 styles: **CI, GE, CG, 2D** — `UPSCALE_STYLE_CI/GE/CG`), `PROMPT`.

### 2.4 Models/providers `[BUNDLE]/[DOCS]`
- `GET /wallpaper/generate/model` returns the list of models. The `axon-api.md` doc mentions **Leonardo, HiDream, Luma**. The bundle explicitly contains `"leonardo"`; the CDN path `axon-assets-cdn.../luma/thumbs/...` confirms **Luma AI** for video/motion.
- `GET /wallpaper/generate/product` — list of "products" (generation plans/packages).
- The `supplier_name` field in wallpaper data → the model provider's name is shown in the UI.
- `GENERATE_POWERED` ("Powered by …") — model attribution in the interface.

### 2.5 Token economy `[BUNDLE]`
- `GET /wallpaper/generate/price` — generation price in tokens.
- i18n: `GENERATE_COST`, `GENERATE_TOKEN(S)`, `GENERATE_REMAINING`, `GENERATE_TOP_UP`, `GENERATE_PAID`, `cost_tokens`, `token_counts`, `balance_help`.
- Tokens are topped up by: purchase (`/payment/*`, Braintree/PayPal), watching ads (`/task/ads/claim`), inviting friends (`INVITE_FRIENDS_GET_TOKENS_INFO`), dailies/contests.
- `GET /wallpaper/generate/existorder` / `suborder` — managing generation orders/suborders.

### 2.6 Full flow to reproduce
1. Open `/createAINew`; choose a mode (`CHANGE_AI_TAB`: Text / Image / Motion / Upscaler).
2. Load tokens, fetch models: `GET /generate/model`, `GET /generate/product`, `GET /generate/price`.
3. (image2*) upload the source: `GET /generate/uploadurl` → PUT to the presigned URL → `/generate/upload`, list of uploads `/generate/uploadlist`.
4. Submit the generation: `POST /wallpaper/generate` (or `/image2image|/image2motion|/image2video|/video|/batch|/alchemy`) with `{prompt, negative_prompt, ratio, strength, model, ...}`.
5. Poll the status: `GET /generate/info` (status); list of orders `GET /generate/list`; details `GET /generate/details` / `/detail`. The states include "generating" (`GENERATE_GENERATEING`/`AI_FITLER_ING` — NSFW filtering in progress).
6. Post-processing: `POST /generate/upscale`, `POST /generate/nobg`, `POST /generate/again` (repeat with the same parameters).
7. **NSFW moderation**: `AI_NSFW_TITLE/CLICK/SHARE_TIPS/APPEAL` — a result may be flagged; an appeal is available (`/appeal`, `AI_APPEAL_*`).
8. **Publishing**: `AI_PUBLISH/PUBLISHING/PUBLISHED`, `AI_AUTOPUB` (auto-publish), `AI_PUBLISH_TC` (terms) → the wallpaper goes to the Community feed.
9. Deletion: `POST /generate/delete` (the whole order) / `/deletedetail` (a single result).

### 2.7 Actual data model (from the live cache) `[CACHE-JSON]`
From a cached feed response (`f_0009df`, `f_000a7d`):
```json
{
  "feed_id": 148259,
  "uuid": "ZoRHdcEvF4O...==",        // base64-wrapped id (cf. wallpaper encryption in the previous RE)
  "title": "Waves: Crimson Dusk",
  "prompt": "anime-style ocean waves ... \n<negative/style on the second line>",
  "type": 1,                          // 1 = image, 2 = motion/video (image -> .mp4 in the image field)
  "image":  "https://axon-assets-cdn.razerzone.com/community-feed/.../*.webp|*.mp4",
  "image1": ".../thumbs/500x280/*.webp",
  "fav_num": 12, "is_fav": false, "download_num": 268,
  "avatar": "...", "razer_id": "Vivierra",
  "detail_id": 2869726,
  "sharing": "https://axon.razer.com/sharing/community?f=148259",
  "user_leaderboard_best_rank": 1, "decorate_badge_image": "...badge..."
}
```
So the prompt is stored right in the feed (it often includes "4k wallpaper, negative space" and
a second line with the color scheme/negative). Motion wallpapers are stored as `.mp4` on the CDN.

### 2.8 How to build it in OpenAxon (in practice)
- The endpoints and the host object are already described (`axon-api.md` §6, `webview-host-objects.md`). What is needed is a **GTK page** `CreateAIPage`: a prompt textarea (+ negative), mode/model/ratio selection, a Generate button, a results grid polling `GET /generate/info`, and Upscale/NoBG/Again/Publish/Download actions.
- For rendering: image → static wallpaper (supported in the player), motion/video `.mp4` → video wallpaper (the player already handles `.mp4`, `openaxon-player.py:52`).
- Tokens/payment are a separate area; in the first stage it is enough to show the balance (`/wallet/balance`) and a message that top-ups are done in the original client.

---

## 3. GAP list (prioritized): what to build next in OpenAxon

**Snapshot 2026-05-31** (for history): OpenAxon (`razer-axon-gui.py`, ~2254 lines) implemented
a 4-button top nav (`gallery`/`create`/`community`/`library`), Gallery with the
wallpapers/series/authors subtabs + filters, ArtistPage, DetailView, Community (popular),
Library (downloaded); `create` → `toast("Coming soon")`.

**Updated 2026-06-18:** the client (`razer-axon-gui.py`, ~3501 lines) has **7 navigation buttons**
`["home","gallery","create","collections","community","library","profile"]` and implements
**AI generation** (`CreateAIPage:1298`, modes `AI_MODES:1282`), **Home/Spotlight** (`HomePage:1882`),
**Profile/wallet** (`ProfilePage:1994`), **Collections** (`CollectionsPage:2201`) — items #1, #3, #5, #6
below are marked ✅ DONE. The player (`openaxon-player.py`) handles Video + Static (Web is detected but not rendered).

| # | Feature | Priority | Complexity | Dependencies (ready?) |
|---|---|---|---|---|
| 1 | **AI generation (`/createAI`)** — Text/Image/Motion/Upscale page, polling, download/apply | ✅ **DONE** (`CreateAIPage:1298`) | — | implemented 2026-06 |
| 2 | **AI Upscaler** (4 styles CI/GE/CG/2D) | 🔴 P0 | Medium | part of the AI page |
| 3 | **Spotlight/Home** start screen (carousel + feeds) | ✅ **DONE** (`HomePage:1882`) | — | implemented 2026-06 |
| 4 | **Community Hall** subtabs (Follow/Liked/Personal) + feed | 🟠 P1 | Medium | partially present (Community) |
| 5 | **Profile/account** (avatar, badges, wallet/silver) | ✅ **DONE** (`ProfilePage:1994`) | — | implemented 2026-06 |
| 6 | **Collections / Series follow** as full sections | ✅ **DONE** (`CollectionsPage:2201`; Series follow — partial) | — | implemented 2026-06 |
| 7 | **Playlists** (wallpaper rotation) | 🟡 P2 | Medium | `/playlist/*`; needs switching logic in the player |
| 8 | **Settings tab** (General/Display/Performance, multi-monitor) | 🟡 P2 | Low–medium | `/user/setting*`; language already present |
| 9 | **Contest / Leaderboard / Daily / Campaigns** (gamification) | 🟡 P2 | High (many screens) | `/contest/*`, `/leaderboard/*`, `/compaigns/*` |
| 10 | **Notifications / Messages** | 🟢 P3 | Medium | `/feed/messages/*` |
| 11 | **Invite friends / Redeem codes** | 🟢 P3 | Low | `/invite`, `/redeem/bycode` |
| 12 | **Spotify wallpapers** linking | 🟢 P3 | Medium | `/spotify/*` (needs OAuth) |
| 13 | **Payment/Store** (tokens/subscriptions) | 🟢 P3 | High | Braintree/PayPal — questionable on Linux, can be postponed |
| 14 | **Web wallpapers in the player** (HTML rendering) | 🟡 P2 | Medium | the player detects them but does not render |
| 15 | **Ads for tokens** | ⚪ skip | — | no need to reproduce in an open client |

Recommended starting order (snapshot 2026-05-31): **#1 → #2** (AI + Upscaler, a direct request),
then #5 (profile/wallet is needed to display AI tokens), then #3/#4 (Home/Community for a complete UX).

**Updated 2026-06-18:** items #1 (AI generation), #3 (Home), #5 (Profile), #6 (Collections)
are already implemented. **Current priorities:** finish #2 (AI Upscaler, if it is not yet in `CreateAIPage`),
#4 (Community Hall Follow/Liked/Personal subtabs), then #7 (Playlists) and #8 (Settings tab).

---

## 4. What was found that is NEW vs the previous RE

| Finding | Status in previous docs | Source |
|---|---|---|
| Full list of `NAV_*` (20 main navigation sections) | absent (0 mentions of `NAV_`) | `[BUNDLE]` |
| enum values of `method` (text2image/image2image/image2motion/image2video/text2video/upscale) | partial (endpoints were there, enum values were not) | `[BUNDLE]` |
| AI aspect ratios (1:1,16:9,9:16,4:3,3:4,21:9) | no | `[BUNDLE]` |
| Upscale styles CI/GE/CG/2D + settings (DIMEN/MULTI/STRENGTH/STYLE) | no | `[BUNDLE]` |
| AI token economy (price/cost_tokens/top_up/remaining) in detail | superficial | `[BUNDLE]` |
| NSFW moderation + appeal + autopub flow | no | `[BUNDLE]` |
| Actual data model of the AI feed (prompt/type/method/CDN paths) | no | `[CACHE-JSON]` |
| Ads in the UI (smartadserver, /task/ads*) | no | `[BUNDLE]/[CACHE]` |
| Braintree+PayPal payments in the WebView | no | `[CACHE]` |
| Models: Leonardo confirmed in the bundle, Luma via CDN paths | named in the doc without confirmation | `[BUNDLE]/[CACHE]` |
| UICache as an extractable source of the entire UI bundle (gzip entries) | method not described | method |

**Already known (confirmed, not duplicated here)**: the full list of `/wallpaper/generate/*` endpoints
(`axon-api.md` §6), the table of React routes and the `CreateWithAI`/`Upscaler`/`LumaDataContext` components
(`react-architecture.md` §3, §6.4), host objects/pipes/wallpaper decryption
(`webview-host-objects.md`, `razer-central-ipc.md`, `axon_reverse_engineering_2026_05_31.md`).

---

## 5. Limitations / honesty
- The i18n in the bundle is **keys only**; the values (English texts) are loaded from the server → the exact button labels cannot be extracted offline (we have the keys + their meaning).
- `GenerateType`/`GenerateStatus` are runtime enums (minified `V`, `fe`); their numeric values are not revealed statically without tracing.
- The request payloads were reconstructed from field names in the bundle + live cache responses; the exact required/optional fields of each POST were not validated (Axon was not launched).
- The UI version is pinned at `2.6.2.0` (as in the previous RE) — there were no updates.
