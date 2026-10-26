# Razer Axon 2.9.1.0 — analysis of the new installer and comparison with the port (2026-08-10)

Work by: Wehrwolfmann. A follow-up to the May documents
`axon_installer_wine_diagnosis_2026_05_31.md` (diagnosing the installer under Wine) and
`axon_reverse_engineering_2026_05_31.md` (reverse engineering of the 2.6.2.0 app).

**Method**: static analysis only. Neither `RazerAxonInstaller.exe` nor
`RazerAxonSetup_2.9.1.0.exe` was run — not under Wine, not in any other way. Unpacking
PE resources (`7z`), decompiling .NET (`ilspycmd`), reading strings, and publicly
downloading publicly available files (the manifest API and the storefront JS bundle are
served without authorization).

**Confidence calibration**: [DECOMP] — read in decompiled code,
[NET] — obtained with a live GET request to a public address, [STRINGS] — extracted from
binary strings, [ASSUMPTION] — inference/assumption.

---

## TL;DR

0. ⭐ **THE MAIN POINT: the port has NO functional drift.** The API base, the `v1` path
   version, the login scheme, the required headers and the response envelope have not
   changed, and **all 30 endpoints the port actually uses are alive in 2.9.1.0** (§4a).
   The work on the port is updating version numbers, not a redesign. The only unverified
   risk lies outside the API: the Razer Central 7.23 named-pipe protocol (§6, item 9).
1. **Our port has fallen three versions behind the original.** Axon in production is now
   **2.9.1.0** (storefront build **20260728**), while our code has `2.6.2.0` hardcoded.
2. **The API base and the authorization scheme have NOT changed.** Same
   `https://axon-api.razer.com/v1`, same `POST /login {token, is_guest, uuid}` →
   `data.authorization`, same headers `Authorization` / `X-Version` / `X-Language`
   (+ `X-Requested-With`, which we don't send and which isn't needed). Only the version
   number needs fixing.
2a. **The API surface grew by 17 endpoints without losing any of ours.** Another 19
   "new paths" turned out to be client-side React Router routes, and 7 were extractor
   junk; the first revision of §4 mistakenly counted them as API and has been corrected
   (§4, "Endpoint delta").
3. **The installer endpoint hash has changed**: `8TQEz6XZ` → **`N82uNskI`**. It is not
   hardcoded anywhere in the code (the script parses the manifest), only in the May
   notes — but it is worth knowing.
4. **The installer wrapper has been updated**: `2.4.0.868` → **`2.6.0.890`**, User-Agent
   `RazerLWI/2.6.0.890`. `install-axon-linux.sh` has the old UA hardcoded.
5. **The Axon manifest now includes a mandatory Razer Central module (`Natasha`)
   7.23.0.1220**, installed BEFORE Axon (`installation_priority` 300 vs 32765). This
   directly affects our authorization via the Razer Central named pipe.
6. **The app installer is Inno Setup 6.7.0**, which `innoextract` does not understand
   (git master tops out at 6.4). Unpacking still did NOT succeed, but of the two
   obstacles **one has been removed**: the new loader header (revision 2, 64-bit
   offsets) has been analysed and patched; the patch is in
   `patch/innoextract-inno67-loader-rev2.patch`. The second one remains — the setup
   block header. Analysis and plan in §8.

---

## 1. The `RazerAxonInstaller.exe` wrapper

File: `~/Downloads/RazerAxonInstaller.exe`, downloaded 2026-08-10 01:49.

```
size              14,923,464 bytes
sha256            e4eabf1a0cf030b773a1a14ed22f4cb337c5f85638863260215b6315d83eb570
type              PE32 GUI i386, MSVC (linker 14.42), 6 sections — NATIVE stub, not .NET
COFF timestamp    2026-06-02 01:31:37 UTC
FileVersion       2.6.0.890      (was 2.4.0.868 per the May UA logs)
ProductName       Razer Installer
LegalCopyright    Copyright © 2026 Razer Inc.
signature         DigiCert Trusted G4 Code Signing RSA4096 SHA384 2021 CA1
```

### Packer

A native stub + **a ZIP archive in the `RCDATA/1337` resource** (14,443,272 bytes). The
extraction library is DotNetZip (the string `a library for handling zip archives.
http://www.codeplex.com/DotNetZip (Flavor=Retail)` in the stub) [STRINGS]. So it is the
same "DotNetZip Command-Line Self Extractor" as in May, just a newer version.

The resource unpacks directly with `7z x RazerAxonInstaller.exe`.

Stub control strings [STRINGS]:

```
\Installer\Razer\Installer2      — where to extract (C:\windows\...)
\App\RazerInstaller.exe          — what to run after extraction
 /name                           — argument used to pass the product name
mscoree.dll                      — managed code launch
```

### Payload contents

**81 files, 26,985,275 bytes unpacked** (in May it was "84 files / ~40 MB" — the payload
has slimmed down). Everything is dated 2026-06-02 03:31, except `InstallerConfiguration.xml`
(2025-09-22).

Key items:

| file | what it is |
|---|---|
| `RazerInstaller.exe` | the engine, .NET Framework **4.8**, Assembly Version 2.6.0.890 |
| `Razer.Installer.Core.dll` | networking, manifest, download, installation |
| `Razer.Installer.UI.dll` | WPF UI, 9.8 MB (RazerF5/Noto/Roboto fonts inside) |
| `Razer.Installer.Hub.dll` | app registration in Razer Central |
| `Razer.Installer.DetectManagerWrapper.dll`, `rzS3detmgr.dll`, `rzS3detgmr_CWrapper.dll` | device detection |
| `BLEConnect.dll`, `BLEConnectWrapper.dll` | Bluetooth LE |
| `AWSSDK.Core.dll`, `AWSSDK.Kinesis.dll`, `Razer.Analytics.dll` | telemetry to AWS Kinesis |
| `AllSystems.json`, `systems.json`, `dongle.json`, `dongleV2.json`, `dockEID.json` | device PID tables |
| `InstallerConfiguration.xml` | server addresses |
| `cpprest140_2_10.dll`, `msvcp140.dll`, `vcruntime140.dll` | native dependencies |

`RazerInstaller.exe.config` requires exactly `.NETFramework,Version=v4.8` — the May
conclusion that `winetricks dotnet48` is mandatory still holds.

### How the wrapper knows it should install Axon

The string `axon` appears neither in the stub nor in any of the 81 files. The product
name is derived **from the name of the exe itself** [DECOMP]:
`Razer.Installer.Bootstrapper.StartupOptionUtil.ParseAppFromLaunchExe()` looks for a key
from `RazerAppNamesMapping.RazerShortNameMapping` in the file name:

```csharp
{ "axon",       "sequoia" },
{ "sequoia",    "sequoia" },
{ "axonbeta",   "axonbeta" },
{ "Razer Axon", "sequoia" },
{ "Axon",       "sequoia" },
```

So `RazerAxonInstaller.exe` → internal product name **`sequoia`**. Our May conclusion
about the Sequoia codename is confirmed from the installer side.

Parsed command-line arguments [DECOMP]: `culture`, `silent`, `showdevice`, `host`,
`ep`, `hash`, `install`, `uninstall`, `app`, `name`, `staging`, `devicestaging`, `ad`,
`beta`, `betatag`, `dmqa`, `dmstaging`. Useful: `ep`+`hash` let you **set the endpoint
manually**, bypassing discovery, and `app` lets you name the product directly.

---

## 2. What is downloaded and from where

`InstallerConfiguration.xml` (unchanged since May):

```xml
<DiscoveryServerRoot>discovery3.razerapi.com</DiscoveryServerRoot>
<DiscoveryEndpointName>prod</DiscoveryEndpointName>
<DiscoveryEndpointHash></DiscoveryEndpointHash>
<ManifestServerRoot>manifest3.razerapi.com</ManifestServerRoot>
```

Templates from `Razer.Installer.Core.Config` [DECOMP]:

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
(AWS STS for Kinesis)               https://u05srooyhc.execute-api.us-east-1.amazonaws.com/sts
```

In `ManifestUrl`, **`{1}` is NOT the product name but the endpoint hash**, and `{2}` is
the endpoint name (`prod`). Note `model={7}0`: the extra zero after the model is a Razer
typo in the format string, and it is sent to the server as is (the May dump had exactly
that: `model=OMEN%20by%20HP%2016.1%20inch0`).

`arch` is `64` or `86` (not `x64`), `osver` is `10`/`11`/`8.1`/`8`/`7`, the UA is
`RazerLWI/{build version}` = **`RazerLWI/2.6.0.890`** [DECOMP `EnvironmentVar`].

### Live server response [NET], 2026-08-10

```
GET https://discovery3.razerapi.com/api/v1/endpoints?tag=prod
    {"data":{"items":[{"hash":"N82uNskI","name":"prod"}]}}
```

⚠️ **The hash has changed: it was `8TQEz6XZ` (May), now it is `N82uNskI`.** It is
substituted into the manifest path, so the old URL from the May notes no longer returns
the catalog.

```
GET https://manifest3.razerapi.com/api/v1/releases/N82uNskI/tags/prod/products
    ?os=WINDOWS&osver=11&arch=64&mfr=Generic-MFR&model=Generic-MDL0&sku=Generic-SKU&l=en-US
```

The production catalog as of today (8 products): `Anne` (Razer Synapse) 4.0.698, `Chroma`
4.0.698, `GameBooster2` (Cortex) 11.10.0.12, `Alisha` (Streamer Companion) 2.0.1.15,
`Sophie` (THX Spatial Audio) 2.0.1.21, `SophieLite` (7.1 Surround) 1.0.1.21, `Natalie`
(Virtual Ring Light) 2.0.0.28, and:

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

The file was downloaded and verified: 63,660,360 bytes, MD5
`a04cd17767144b74fe7e24df8e920ed9` — matches the manifest. The link looks single-use in
form (`<unix-ts><8 random characters>` before the name), but the object itself is
accessible without authorization.

---

## 3. `RazerAxonSetup_2.9.1.0.exe`

```
size              63,660,360 bytes  (was 88,216,104 for 2.6.2.0 — minus 28%)
MD5               a04cd17767144b74fe7e24df8e920ed9
type              PE32 GUI i386, Inno Setup
COFF timestamp    2026-05-22 14:17:58 UTC
FileVersion       2.9.1.0
CompanyName       Razer Inc.
LegalCopyright    Copyright @ 2022. Razer Inc.
internal markers  "Inno Setup Messages (6.5.0) (u)", "Inno Setup Setup Data (6.7.0)"
```

`install_parameters` and `launch_filepath` have not changed — the install path and the
silent-install method are the same, so the May workaround (download the setup via the
manifest and run `/SP- /VERYSILENT /DIR=... /SUPPRESSMSGBOXES /NORESTART`) remains valid.

Razer still hasn't fixed the `/SUPRESSMSGBOXES` typo.

---

## 4. The 2.9.1.0 app itself — what could be learned without unpacking

The Axon UI lives on the server, not in files (a May finding), so the storefront version
can be checked directly [NET]:

```
GET https://axon-api.razer.com/2.9.1.0/        → 200, SPA is served
CDN base: https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/
bundle:   axon.b454555f59e3550b4628.js   (5,139,397 bytes; was axon.f8e71bd23f616540077f.js, 2.0 MB)
styles:   axon.b454555f59e3550b4628.css  (was 2c05d5e95eb0ce13_0.css)
```

Scripts included by the page (changes vs 2.6.2.0 marked **new**):

```
https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/tf.min.js
https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/ChromaSDKWS.js
https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/ChromaAI6.js
https://axon-assets-cdn.razerzone.com/static/prod/2.9.1.0/components.js
https://chroma.razer.com/ChromaAI/jszip.min.js
https://deals-assets-cdn.razerzone.com/rating-modal/index.min.js
https://ced.sascdn.com/tag/4064/smart.js                      ← new: Smart AdServer (ads)
```

Service worker: `/2.9.1.0/sw.js`. Braintree is still commented out.

### Authorization — UNCHANGED [DECOMP of the bundle]

```js
axios.create({headers:{"X-Requested-With":"XMLHttpRequest","X-Version": APP_VERSION }})
  .interceptors.request.use(cfg => {
     cfg.headers["Authorization"] = window.SequoiaInfo && window.SequoiaInfo.authorization || "";
     cfg.headers["X-Language"]    = window.language || "en";
  });
// login:
post(`${REQUEST_URL}/${API_VERSION}/login`, {token, is_guest, uuid})
  → window.SequoiaInfo.authorization = data.authorization
  → window.SequoiaInfo.token / .country / .uuid
```

In production `REQUEST_URL` is **an empty string** (requests go same-origin to
`https://axon-api.razer.com`), `API_VERSION` = **`"v1"`**, `X-Version` = **`"2.9.1.0"`**.
So the base `https://axon-api.razer.com/v1` and the whole login scheme are the same as
what we implemented. Only the `X-Version` value changes.

### Endpoint delta [DECOMP of the bundle, refined]

> ⚠️ **Correction of the first revision.** In the first pass the list of "new endpoints"
> was taken with a mechanical `grep` for strings of the form `"/something"` and came out
> inflated: it picked up client-side React Router routes and junk from third-party
> libraries. Below is an analysis that checks each call site. This revision is the one
> to trust.

Raw data: `paths_262.txt` (144 paths, storefront 2.6.2.0) and `paths_291.txt` (184 paths,
storefront 2.9.1.0). The arithmetic "184 − 144 = 40 new" is misleading: in fact
**47 strings were added and 7 disappeared**.

#### How to tell an endpoint from a route

In the bundle every API call is built with exactly one template, so the indicator is
reliable:

```js
axios.get("".concat(i.REQUEST_URL, "/").concat(l["default"], "/explore/board"), t)
//          ^ REQUEST_URL = "" (same-origin)  ^ l["default"] = "v1"
```

Client-side routes, on the other hand, live in the router table and in the navigation
list:

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

Each of the 47 "new" paths was checked for a call site via `REQUEST_URL`.

#### Breakdown of the 47 added strings

**1. Genuinely new API endpoints — 17.** Each has a confirmed call via `REQUEST_URL`;
the client function name and method are given in parentheses.

*Storefront and catalog (4)*

| Path | Method | Function | Meaning |
|---|---|---|---|
| `/spotlight/index/carousel` | GET | `…ightCarousel` | home page carousel, split off from `/spotlight/index` |
| `/spotlight/index/category` | GET | `…ightCategory` | home page category tiles |
| `/promote/info` | GET | `…annerSetting` | promo banner settings |
| `/system/setting` | GET | `…(keys)` | batch read of server settings by a list of keys |

*Campaigns, contests, competitions (5)*

| Path | Method | Function | Meaning |
|---|---|---|---|
| `/campaign/code` | GET | `…(wallpaper_id)` | campaign participation code for a wallpaper |
| `/contest/award/detail` | GET | `…(award_id)` | a single award card (previously only `/contest/award/list`) |
| `/explore/dailychallenge` | GET | `…ilyChallenge` | the daily challenge block on "Explore" |
| `/explore/leaderboard` | GET | `…eLeaderboard` | the leaderboard block on "Explore" |
| `/explore/board` | GET | `ExploreBoard` | the community boards block on "Explore" |

Note: `/explore/*` are **widgets of a single page**, not separate sections; the sections
themselves (`/leaderboard`, `/challenge`, `/hall`) are routes, see item 2.

*Economy: ads as currency (3) — a new mechanic*

| Path | Method | Function | Meaning |
|---|---|---|---|
| `/task/ads` | GET | `…AdRewardsInfo` | list of ad tasks and their rewards |
| `/task/adsid` | GET | `…imRewardToken` | token for claiming a reward for a view |
| `/task/ads/claim` | POST | `…(ads_task_id)` | claim the reward for a watched ad |

This ties in with the new `<script src="https://ced.sascdn.com/tag/4064/smart.js">` tag
(Smart AdServer) and the `www18.smartadserver.com` domain in the bundle: in 2.9 watching
ads earns in-app currency (silver).

*Code redemption and referrals (4)*

| Path | Method | Function | Meaning |
|---|---|---|---|
| `/redeem/bycode` | POST | `…emByCodeNew` | new general code redemption (suffix `New` — the old `/wallpaper/redeem/bycode` was kept) |
| `/wallpaper/redeem/bycode` | POST | `…edeemByCode` | old code-for-wallpaper redemption |
| `/referral/redeem` | POST | `…(code)` | referral code |
| `/silver/detail` | GET | `…SivlerDetail` | in-app currency statement (the typo in the name is theirs) |

*Feed (1)*

| Path | Method | Function | Meaning |
|---|---|---|---|
| `/feed/messages/pending` | GET | `getUnReadNum` | unread counter (previously counted from `/feed/messages`) |

**2. Not endpoints but React Router routes — 19.** None of them has a call via
`REQUEST_URL`; all are present in the router table and/or the `Q` navigation array:

```
/browse  /collections  /compilations  /create  /artists
/hall  /hall/all  /hall/follow  /hall/liked  /hall/personal
/playlist  /playlist/followed  /playlist/joined
/leaderboard  /challenge  /contest
/compaigns  /compaigns/daily  /compaigns/leaderboard
```

`compaigns` is a Razer typo that has been there from the very beginning. The bundle has
`<Redirect from="/compaigns/leaderboard" to="/leaderboard" exact>`, i.e. the campaigns
section is being split into separate screens. The appearance of these strings in 2.9
means **new UI screens**, not new server calls — they fetch their data through the old
`/hall/*`-style endpoints (`/board/list`, `/leaderboard/list`, `/dailychallenge/list`).

**3. Extractor junk — 7.** Five are JSON Schema pointers from the AJV validation library
(`errSchemaPath + "/else"`, `"/then"`, `"/type"`, `"/required"`, `"/properties"`), two
are UI text-length counters: `"/2000"` (wallpaper description limit) and `"/300"`
(short description limit). They have nothing to do with the API, but the field limits
are useful to know.

**4. Not new, only the notation changed — 4.** The client concatenates the suffix from
an argument, and the 2.9 extractor truncated the placeholder:

```js
axios.post(`${REQUEST_URL}/v1/wallpaper/favorite/${t.type}`, t)   // type = add | cancel
axios.post(`${REQUEST_URL}/v1/wallpaper/vote/${t.type}`, t)
```

| In 2.6.2.0 | In 2.9.1.0 | What it really is |
|---|---|---|
| `/artist/follow/{type}` | `/artist/follow/` | unchanged |
| `/collection/follow/{type}` | `/collection/follow/` | unchanged |
| `/wallpaper/favorite/{type}`, `/wallpaper/favorite/add`, `/wallpaper/favorite/cancel` | `/wallpaper/favorite/` | unchanged |
| `/wallpaper/vote/{type}` | `/wallpaper/vote/` | unchanged |

#### Breakdown of the 7 disappeared strings

Six are the flip side of item 4 above (`/artist/follow/{type}`, `/collection/follow/{type}`,
`/wallpaper/favorite/{type}`, `/wallpaper/favorite/add`, `/wallpaper/favorite/cancel`,
`/wallpaper/vote/{type}`). **Exactly one has truly disappeared: `/generate/downloaded`** —
its role has been taken over by `/wallpaper/downloaded` and `/wallpaper/generate/list`,
both still present.

#### Summary

**No endpoint that existed in 2.6.2.0 has been removed or renamed** (except
`/generate/downloaded`, which we don't use). All 17 new ones are **pure additions** on
top of the previous API surface.

New external domains in the bundle: `https://www18.smartadserver.com`,
`https://cdn.leonardo.ai`, `https://leonardo.ai`, `https://hidreamai.com`,
`https://gold.razer.com` — i.e. generation gained third-party models, and the economy
gained ad tasks.

#### Cross-check with the May notes

* `docs/axon-api.md` (May, 2.6.2.0) describes the base, login, headers and the working
  catalog/generation sections — **all of it was confirmed in 2.9.1.0 without changes**.
* `docs/axon_ui_features_full_inventory_2026_05_31.md` is the screen inventory; the 19
  routes from item 2 are its direct continuation (new screens: `/browse`, `/collections`,
  `/compilations`, `/artists`, `/playlist*`, `/hall/*`, `/leaderboard`, `/challenge`,
  `/contest`, `/compaigns*`). The inventory is worth extending, but this doesn't affect
  the port.
* ⭐ Separately: `docs/axon-api.md` **already has** a table of client-side routes, and
  `/hall/*`, `/collections`, `/compilations`, `/playlist*`, `/compaigns*`, `/contest` are
  listed there precisely as screens. So the May analysis was correct, and the error was
  introduced by the August `grep`. Lesson for the future: count paths from the bundle as
  API only when there is a call site.

---

## 4a. Does the port diverge from 2.9.1.0 — the final answer

**No. There is no functional drift at any point.** Checked along four axes.

### 1. Base and protocol version — unchanged

```js
axios.get("".concat(REQUEST_URL, "/").concat("v1", "/wallpaper/list"), params)
```

In production `REQUEST_URL` is an empty string (requests go same-origin to
`https://axon-api.razer.com`), the path version is `"v1"` (the bundle contains exactly
one occurrence of the string `"v1"`, in a constants module). We have
`API_BASE = "https://axon-api.razer.com/v1"` (`razer-sync.py:29`,
`razer-axon-gui.py:31`) — **it matches**.

### 2. Required headers — unchanged

The full set from the bundle:

```js
axios.defaults.withCredentials = true;
axios.create({ headers: { "X-Requested-With": "XMLHttpRequest",
                          "X-Version": "2.9.1.0" } });
  .interceptors.request.use(cfg => {
     cfg.headers["Authorization"] = window.SequoiaInfo?.authorization || "";
     cfg.headers["X-Language"]    = window.language || "en";
  });
```

| Header | In 2.9.1.0 | Ours | Verdict |
|---|---|---|---|
| `Authorization` | raw string from `data.authorization` | same | ok |
| `X-Version` | `2.9.1.0` | `2.6.2.0` | **outdated, cosmetic** |
| `X-Language` | `en` | `en` | ok |
| `Content-Type` | `application/json` | same | ok |
| `X-Requested-With` | `XMLHttpRequest` | **not sent** | didn't matter in May; add as a safeguard |
| signature/nonce/captcha | **none** | — | no new requirements have appeared |

Not a single new required header, no JWT Bearer, no anti-bot signature.
`withCredentials: true` is irrelevant for us — authorization is done by `Authorization`,
not by a cookie.

### 3. Login and response envelope — unchanged

```js
post(`${REQUEST_URL}/v1/login`, {token, is_guest, uuid})
  → if (res.code == 200) { SequoiaInfo.authorization = res.data.authorization;
                           SequoiaInfo.token = …; SequoiaInfo.uuid = …; }
```

The envelope is the same — `{code, msg, data}`, success when `code == 200`; our code
checks exactly that (`resp.get("code") != 200`). The error interceptor distinguishes only
transport statuses (403 → message, 503 → `SERVER_ERROR_503` event, 502 → "maintenance");
there are no new authorization codes that require a client reaction.

### 4. Endpoints the port actually uses — 30 of 30 present

The list was compiled from the `api_get` / `api_post` / `hmac_request` calls in
`razer-axon-gui.py` and `razer-sync.py` and checked against `paths_291.txt`:

| Group | Endpoints | In 2.9.1.0 |
|---|---|---|
| Login | `/login` | ✅ |
| Catalog | `/wallpaper/list`, `/wallpaper/detail`, `/wallpaper/setting`, `/wallpaper/favorite/{add\|cancel}` | ✅ |
| Artists | `/artist/list`, `/artist/detail` | ✅ |
| Collections | `/collection/list`, `/collection/followlist`, `/collection/follow/{add\|cancel}` | ✅ |
| Home | `/spotlight/index`, `/spotlight/feed`, `/feed/selections`, `/feed/personal/state` | ✅ |
| Profile | `/wallet/balance`, `/silver/detail`, `/badge/list` | ✅ |
| Generation | `/wallpaper/generate` and `…/image2image`, `…/video`, `…/image2video`, `…/image2motion`, `…/upscale`, `…/model`, `…/uploadurl`, `…/upload`, `…/info`, `…/detail` | ✅ |
| HMAC download | `/wallpaper/resource`, `/wallpaper/downloaded` | ✅ |

None has been removed, renamed or moved to a different path version.

The parameters match too: the official client adds the parameter `not_offical = true` to
`/wallpaper/list` (their typo in the word "official") — **we already send it**
(`razer-axon-gui.py:2963`, `:1056`); this was caught back in May
(`docs/axon-api.md:130`, `:1597`).

### Response schemas

No changes in response parsing for the endpoints we use are visible in the bundle: the
same `data.list` / `data.total` in paginated results and the same field names. A caveat
on confidence: the check is **static, based on the client code**; as a matter of
principle we did not request live authorized responses, so "the schemas haven't changed"
is a conclusion from reading the client, not a measurement. I consider the risk low: if
the shape had broken, the official client would have broken too.

### Which of the 17 new endpoints are worth supporting

**Worth it (useful and cheap):**

| Endpoint | Why | Effort |
|---|---|---|
| `/spotlight/index/carousel`, `/spotlight/index/category` | in 2.9 the home page split into three calls; we currently fetch only `/spotlight/index` and get part of the content | low |
| `/system/setting` | server flags/limits in a single request — removes some hardcoding | low |
| `/feed/messages/pending` | a ready-made unread counter instead of counting manually | low |

**Optional (if we extend the screens):** `/explore/board`, `/explore/dailychallenge`,
`/explore/leaderboard` — three widgets of a single "Explore" page; only makes sense
together with the screen itself.

**Not needed:**

* `/task/ads`, `/task/adsid`, `/task/ads/claim` — watching ads for in-app currency.
  Drags in Smart AdServer (`ced.sascdn.com`). **Not taking it** into the port.
* `/campaign/code`, `/contest/award/detail` — campaigns and contests; we have no such
  screens.
* `/redeem/bycode`, `/wallpaper/redeem/bycode`, `/referral/redeem`, `/promote/info` —
  promo codes, referrals and banners; not related to the core task (catalog + wallpapers
  + generation).
* `/silver/detail` — **already supported**, no separate work needed.

---

## 5. Summary table "May 2026 → August 2026"

| What | Before (2026-05-31) | Now (2026-08-10) | Breaks the port? |
|---|---|---|---|
| Axon version | 2.6.2.0 | **2.9.1.0** (storefront 20260728) | yes, `X-Version`/UA |
| API base | `https://axon-api.razer.com/v1` | unchanged | no |
| API path version | `v1` | unchanged | no |
| Login scheme | `POST /login {token,is_guest,uuid}` → `authorization` | unchanged | no |
| Headers | `Authorization` / `X-Version` / `X-Language` / `X-Requested-With` | unchanged | no |
| Response envelope | `{code, msg, data}`, success `code==200` | unchanged | no |
| Our 30 endpoints | — | **30 of 30 present** | no |
| API surface | 143 paths | +17 new, 1 removed (`/generate/downloaded`, not ours) | no |
| UI screens | — | +19 router routes | no |
| Resource HMAC key | `j6l-aUmhCc@tN%T_` | not checked (needs the app files) | ? |
| Storefront CDN | `.../static/prod/2.6.2.0/` | `.../static/prod/2.9.1.0/` | yes, the path |
| JS bundle | `axon.f8e71bd23f616540077f.js` (2.0 MB) | `axon.b454555f59e3550b4628.js` (5.1 MB) | no |
| Installer wrapper | UA `RazerLWI/2.4.0.868` | **`RazerLWI/2.6.0.890`** | cosmetic |
| Wrapper payload | 84 files / ~40 MB | 81 files / 27 MB | no |
| endpoint hash | `8TQEz6XZ` | **`N82uNskI`** | no (parsed from the response) |
| discovery/manifest hosts | discovery3/manifest3.razerapi.com | unchanged | no |
| App setup | `RazerAxonSetup_2.6.2.0.exe`, 88,216,104 | `RazerAxonSetup_2.9.1.0.exe`, 63,660,360 | the link in the script |
| Inno Setup | unpacked by `innoextract` 1.9 | **Inno 6.7.0**, 1.9 can't handle it | yes, for the build |
| Razer Central module | did not appear in the May manifest extract | **`Natasha` 7.23.0.1220, priority 300** | probably yes |
| Silent install parameters | `/SP- /VERYSILENT /DIR=...` | unchanged | no |

---

## 6. What to fix in the port (by priority)

> Context: there is no API drift (§4a). Everything below is either version cosmetics,
> resilience against the next update, or optional improvements.

**P1 — mandatory (version cosmetics, 15 minutes).**

1. **Client version.** `razer-sync.py:30` and `razer-axon-gui.py:32`:
   `API_VERSION = "2.6.2.0"` → `"2.9.1.0"`. Likewise the User-Agent `RazerAxon/2.6.2.0`
   (three places in `razer-axon-gui.py`: lines 250, 331, 910). The backend apparently
   doesn't check the `X-Version` header strictly (the port has worked since May), but
   there's no reason to misreport the version.
2. **Installer UA** in `install-axon-linux.sh:306,387`: `RazerLWI/2.4.0.868` →
   `RazerLWI/2.6.0.890`.

**P2 — so that the next update doesn't catch us out.**

3. **Stop hardcoding the version.** Fetch it from the manifest
   (`GET discovery → GET manifest3 → items[name=="Sequoia"].version`) with a fallback to
   the hardcoded value. Then item 1 will never be needed again — and it recurs with
   every Razer release.
4. **Add `X-Requested-With: XMLHttpRequest`** to `api_get`/`api_post`
   (`razer-axon-gui.py:216,230,278`, `razer-sync.py:95`). It works without it now, but
   the official client always sends it — a cheap safeguard against a future check.
5. **Clean up the cruft in the install script.** `download_url` is already taken from the
   live manifest via `manifest()`, but the `2.6.2.0` hardcoded in comments/fallbacks and
   the old endpoint hash `8TQEz6XZ` are confusing (the current one is `N82uNskI`, but it
   shouldn't be hardcoded either — it is parsed from the response).

**P3 — optional, new functionality.**

6. **Home page.** Add `/spotlight/index/carousel` and `/spotlight/index/category` to
   `HomePage._load` (`razer-axon-gui.py:1924`): in 2.9 the home page split into three
   calls, and we only show part of the content.
7. **`/system/setting`** — server limits and flags in a single request instead of
   hardcoding.
8. **`/feed/messages/pending`** — a ready-made unread counter.

**P4 — not related to the API.**

9. **Check the integration with Razer Central.** The Axon manifest now has an explicit
   `Natasha 7.23.0.1220` module with `installation_priority: 300`, i.e. Razer Central is
   installed first and Axon depends on it. Our `razer-token-inject.py` writes to the pipe
   `{FC828A97-C116-453D-BD88-AD471496E03C}` with the `WebApp_SetLoginSuccessFromWeb`
   command (131094) — we need to make sure the command numbers and packet format haven't
   changed in 7.23. **This is the only real risk that remains unverified.**
10. **Update `docs/axon-api.md`**: the 17 new endpoints from §4a into the API table, the
    19 new routes into the screens table (it already exists in the same file).
11. **The `RazerAxon.UserManager.dll` patch** is known not to fit 2.9.1.0 (the file was
    rebuilt); it will have to be rebuilt once the setup can be unpacked.

**What NOT to do:** ad tasks (`/task/ads*`), campaigns/contests, promo codes and
referrals — see the analysis at the end of §4a.

---

## 7. What could NOT be done

* **Unpacking `RazerAxonSetup_2.9.1.0.exe`.** It failed, but **we got past one of the two
  barriers** — details in §8 below, so that the next attempt doesn't start from scratch.
  The consequence is unchanged: **the file layout of the 2.9.1.0 app, `appsettings.json`,
  the DLL list, the .NET runtime version and the resource HMAC key were NOT checked** —
  all of these are marked "?" in the table above. Unpacking is not needed to answer the
  main question (§4a).
* **Checking `/v1/login` live** — this requires a real Razer ID token; as a matter of
  principle no authorized requests were made.
* The analysis files are in `~/Downloads/axon-installer-2026-08-10/` (the wrapper, the
  unpacked payload, the decompiled installer sources, the 2.9.1.0 setup, the storefront
  JS bundle).

---

## 8. Inno Setup 6.7.0: barrier 1 removed, barrier 2 described

The attempt was capped at half an hour (time had already been burned on unpacking three
times). We stayed within it; of the two obstacles, one was removed. It is written down in
detail so that this doesn't have to be worked out again.

Tool: `innoextract` 1.10-dev (`6e9e34e`) in `~/Downloads/axon-installer-2026-08-10/ie-src`,
the built binary is `ie-src/build/innoextract`. The final change is saved in the
repository: **`patch/innoextract-inno67-loader-rev2.patch`**.

### Barrier 1 — loader header, revision 2 → SOLVED

Before: `Unexpected setup loader revision: 2` → `Setup loader checksum mismatch` →
`Could not determine setup data version`.

Cause: starting roughly with Inno Setup 6.5, the loader header (signature
`rDlPtS \xcd\xe6\xd7\x7b\x0b\x2a`, at offset **1,123,164** in our file) has its revision
bumped from 1 to 2, and **the offsets are widened to 64 bits** — to describe installers
larger than 4 GiB. `innoextract` kept reading them as 32-bit, got a garbage
`header_offset`, and therefore couldn't find the version string.

The decoded revision 2 layout (offsets are from the end of the 12-byte signature):

| Offset | Type | Value in our file | Field |
|---|---|---|---|
| +0 | u32 | 2 | `revision` |
| +4 | **u64** | 63,648,382 | total size (skipped) |
| +12 | **u64** | 62,386,888 | `exe_offset` |
| +20 | u32 | 4,640,968 | `exe_uncompressed_size` |
| +24 | u32 | `0xf2dbe0a5` | CRC32 of `setup.e32` |
| +28 | **u64** | 62,315,557 | `header_offset` |
| +36 | **u64** | 1,126,912 | `data_offset` |
| +44 | u32 | 0 | reserved (new) |
| +48 | u32 | `0x9be8e908` | header CRC32 |

The layout is confirmed by three independent checks, not fitted to the data:

1. `header_offset` = 62,315,557 — **exactly** the offset of the string
   `Inno Setup Setup Data (6.7.0)` in the file;
2. `data_offset` = 1,126,912 — **exactly** the offset of the `zlb\x1a` marker;
3. the CRC32 over the 60 bytes from the start of the signature gives `0x9be8e908` —
   matching the stored value.

The change (`src/loader/offsets.hpp` — widen `exe_offset`/`header_offset`/`data_offset`
to `boost::uint64_t`; `src/loader/offsets.cpp` — a `revision >= 2` branch) builds and
works: it now prints `detected setup version: 6.4.0.1 (unicode)`. The version table in
`src/setup/version.cpp` had already been extended with rows 6.5.0…6.9.0 (mapped to
6.4.0.1).

### Barrier 2 — setup block header → STOPPED HERE

Current error:

```
Stream error while parsing setup headers!
 ├─ detected setup version: 6.4.0.1 (unicode)
 └─ error reason: block header CRC32 mismatch: iostream error
```

`innoextract` (`src/stream/block.cpp`, `block_reader::get`) expects nine bytes right
after the 64-byte version block: `CRC32 (u32) + stored_size (u32) + compressed (u8)`.
The actual bytes from `header_offset`:

```
  +64  b2 89 92 dc  00 00 00 00 00 00 00 00 00 00 00 00
  +80  00 00 00 00  00 60 5b 03 00 00 00 00 00 00 00 00
  +96  00 00 00 00  00 00 00 00 00 00 00 00 00 00 00 00
 +112  00 00 00 00  00 fa e8 c9 05 a0 c7 00 00 00 00 00
 +128  00 01 | 6b eb e6 6c | 5d 00 00 20 00 | 00 0a 00 33 …
              ^ sub-block CRC  ^ LZMA1 properties
```

What is known for certain from this:

* `0xdc9289b2` at `+64` is almost certainly the block header CRC32 itself;
* **the block data starts at `+130`**: first the 4-byte sub-block CRC (`6b eb e6 6c`),
  immediately followed by the LZMA1 properties `5d 00 00 20 00` — this is an anchor
  point and is not in doubt;
* so the block header occupies `+68 … +129` = **62 bytes** instead of the expected 5.
  What fills those 62 bytes (almost entirely zeros with `00 60 5b 03` at `+85` and
  `fa e8 c9 05 a0 c7` at `+117` interspersed) — **not decoded**.
  A reasonable guess [ASSUMPTION]: the size was also widened to 64 bits, and fields were
  added for multi-volume support / uncompressed size, but we did not try to fit it
  blindly.

What to do next (cheapest first):

1. Take the Inno Setup 6.7.0 sources (they are open, `jrsoftware/issrc`) and read
   `TSetupLdrOffsetTable`/`CompressedBlockWriter` — the layout will become clear within
   minutes and without guesswork. **This is the right path; start with it.**
2. Only then finish `block.cpp` and check the CRC on the real file.
3. Barrier 1 is already removed by then; the patch is in `patch/`.

What this task does NOT require: `innounp` under Wine (that means running someone else's
code), or running the installer at all. Barrier 2 is purely a format analysis.
