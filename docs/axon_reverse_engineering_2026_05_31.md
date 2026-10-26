# Razer Axon — second reverse-engineering pass (2026-05-31)

Static RE of the installed `~/.wine/.../Razer/Razer Axon/`. Goal: find anything NEW or more precise
compared with the existing OpenAxon documentation (`docs/*.md`), assess how accurate the
GTK4 client is, and produce a prioritised list of improvements.

**Method**: the key DLLs were copied to a temporary working directory and decompiled with `ilspycmd`
(v10.0.0.8330, the ILSpy .NET decompiler). The installed Axon was NOT run and NOT modified.
The WebView cache (`UICache/.../EBWebView`) was analysed read-only.

**Confidence calibration**: [DECOMP] = read in decompiled code,
[CACHE] = extracted from the WebView cache, [ASSUMED] = assumption/inference.

---

## 0. Main conclusion (honestly)

The existing OpenAxon documentation is based on real reverse engineering and is accurate and thorough:

- `razer-central-ipc.md` — pipe wire format, pipe GUIDs, full NacCommands enum: **all matches the binary 1:1**.
- `webview-host-objects.md` — 6 host objects, ~124 methods, object names with Razer's typos: **matches**.
- `design-system.md` — palette (#44d62c, #1a1a1a, …), tokens, layout, components: **matches the CSS cache**.
- `wallpaper-player.md` — SequoiaCommand, player pipes: **present**.

Of the original's visual design, only the **GTK4 styling** has been reproduced, not the protocols.
And the GTK client ALREADY uses the exact palette and sizes from the spec
(sidebar 260px, card min-width 240/max 266px, radius 2px, etc.).

So this document is mostly **confirmation + a few new details + gaps**,
not a rewrite.

---

## 1. Inventory and version

[DECOMP/files]

- **Axon version: `2.6.2.0`** (from `appsettings.json` → `StartupUri https://axon-api.razer.com/2.6.2.0/`).
  This is **the same version** recorded in the existing docs → Axon has **NOT been updated** since the previous analysis; there are no new files.
- **Runtime**: .NET **6.0.36** (`Microsoft.NETCore.App` + `Microsoft.WindowsDesktop.App`), win-x64, WPF host.
- **API base**: `https://axon-api.razer.com/v1` (`WebServiceDomain`).
- Internal code name: **Sequoia** (`D:\RazerDev\sequoia-client-v2\...`, namespaces `RazerSequoia.*`).

### ⚠️ IMPORTANT: the installed Axon is already PATCHED by OpenAxon

`RazerAxon.UserManager.dll` in `~/.wine` is **NOT the Razer original** but the version patched by OpenAxon
(matches `patch/RazerLoginForm.cs`): it contains `wine_login_token.json`,
`machineId: "wine-linux"`, the MessageBox "Login successful! Restart Razer Axon", and an embedded JS shim
`callbackObjforjs`/`callJSFromClient`. All the other DLLs (`AccountManager*`, `RazerCentralClient`,
`RcClientBase`, `WallpaperManager`, `WallpaperPlayerManager`, `DataAcquisition`, …) are **original
Razer** ones, and they were the main source of the data below.

> Consequence for future RE: if you need the ORIGINAL `UserManager.dll`, take it from a clean
> installer (deployed into an isolated test Wine prefix), not from `~/.wine`.

---

## 2. Protocols — confirmations and new details

### 2.1 Razer Central named pipe (confirmed 1:1) [DECOMP]

`RcClientBase.dll` → the packet format matches `razer-central-ipc.md`:

```
header (HEADER_LEN = 24):
  int32  version    = 2          (binaryWriter.Write(2))
  int32  serviceType (RzServiceType)
  int32  dataLength
  int32  headerLength = 24
  int64  packetId   (Interlocked.Increment, skipping 0)
payload (dataLength)
```
Reading: MIN_HEADER_LEN = 16 (reads 4×int32), then `if version>1` reads the int64 packetId,
`if headerLen>24` skips the excess. **Refinement to the doc**: the parser is version-tolerant —
it supports headers longer than 24 bytes (forward-compat) by reading `headerLen-24` extra bytes.

Pipe GUIDs (match):
- ActionCenter/Service: `{CD7C71F0-A5B9-4F24-897A-DF6E20E43B96}`
- NAC: `{FC828A97-C116-453D-BD88-AD471496E03C}`
- NAC Client: `{E7A6CCA9-FF3F-4741-8E66-1127EE39471D}` + windows-username
- There are DEBUG variants with a `{DBG-...}` prefix (used when `m_debugPipeName` is set). [new refinement]

`RzServiceType`: UpdateManager=2, AccountManager=4, Notifications=5, ActionCenter=6.

### 2.2 Player IPC (Sequoia native player) [DECOMP] — details for wallpaper-player.md

`RazerAxon.WallpaperPlayerManager.dll` → `ShellLauncher.Launch`:

- Launch: `RazerAxon.Player.exe` with the arguments:
  `readpipename=\\.\pipe\<W>  writepipename=\\.\pipe\<R>  version=<appVersion>`
  (+ `-screensaver` in screensaver mode; in that case it is launched without a shell, as separate argv).
- Two **separate** NamedPipeServerStreams: `writePipename` (PipeDirection.Out) and
  `readPipeName` (PipeDirection.In). Pipe name pattern: **`RazerCortexServiceAndShell{Guid:N}`**.
- Commands are a JSON `SequoiaCommand` object:
  ```csharp
  class SequoiaCommand {
    string Command; string MonitorId; string Source; string Type;
    string NeedDeleteSource; string PlayMode; string PlayEffects;
    // ctor(command, monitorId, type, source, isScreenSaver, WallpaperPlayers player,
    //      Dictionary<WallpaperEffectsEnum,string> playEffects=null, playMode="", needDeleteAfterPlay=false)
  }
  ```
- **Full set of Command verbs (8)**: `Play`, `Switch`, `PlayEffect`, `Volume`, `Pause`,
  `Resume`, `Stop`, `Terminate`. [useful for OpenAxon's own player]
- Serialisation: `JavaScriptEncoder.UnsafeRelaxedJsonEscaping` (important: paths with `\` are not escaped to `\u`).

### 2.3 Analytics / Kinesis / STS [DECOMP] — details

`RazerAxon.DataAcquisition.dll`:
- BigData goes to **AWS Kinesis** via `RazerBigDataClient(RazerBigDataApps=1, ...)`.
- Kinesis credentials are obtained via `GET <apiDomain>/sts` (STS endpoint), then temporary AWS creds
  (accessKeyId/secretAccessKey/sessionToken/expiry/arn). [refinement: the `/sts` path]
- App rating: `GET https://bespoke-analytics.razerapi.com/api/v1/1100/app-rating/recommendation`.
  (new domain `bespoke-analytics.razerapi.com` — worth adding to axon-api.md if it is missing).

### 2.4 Full list of domains/URLs (from all DLLs) [DECOMP]

```
https://axon-api.razer.com            (+ /v1, + /2.6.2.0/)
https://axon-api-staging.razer.com    (staging)
https://bespoke-analytics.razerapi.com
https://id.razer.com/                 (Razer ID login)
https://zvault.razer.com              (wallet/balance)
https://developer.razer.com/chroma
https://mysupport.razer.com/
https://www.razer.com/contact-us
https://www.youtube.com/embed/        (trailers in cards)
```

### 2.5 ITS AES key (NEW, not in the docs) [DECOMP]

`ActionServiceCommon.dll` → `RebootRequiredHelper`:
```
Key (base64) = "BYU/nsHCFDD/90xJUFJtRMrQ/f+tOohC87vhv0Fre/s="
IV  (base64) = "p2V8/a0Ik0noC2Z7iL8U9Q=="
Registry: HKLM\Software\Razer\Services\RazerCentral\ITS,  value "TS" (timestamp), "ITS"
AES-CBC, key/IV from base64.
```
**Purpose**: encrypts the install timestamp in the registry for the "reboot required after
installation" logic (`CanStart()`). **It has nothing to do with wallpapers or user tokens.** It is of
little interest to OpenAxon (there is no need to read ITS on Linux), but it is recorded for completeness —
the question "does Axon have embedded crypto keys" came up earlier: yes, but only this one,
and it is not security-sensitive.

### 2.6 Auth tokens [DECOMP]

`AccountManagerCommon.dll` → `ConnectedAccountCredentials` (XML serialisation):
`AccessToken`, `AccessTokenSecret`, `RefreshToken`, `SsiToken`, `ClientKey`, `ClientSecret`,
`Permissions[]`, `Account`. The NacCommands enum fully matches the doc (including
`WebApp_GenerateToken=131097`, `UI_SetToken=131101`, `GetWallet=58`, `TryAutoLoginAsGuest=61`).

In the patched `UserManager`, the token is stored in
`%LocalAppData%\Razer\RazerAxon\wine_login_token.json` with the fields
`token, uuid, loginId, avatarUrl, nickname` (this is the OpenAxon format, not Razer's).

---

## 3. Wallpaper format / decryption [DECOMP + cross-check with axon.py]

- Wallpaper decryption is ALREADY implemented correctly in OpenAxon (`axon.py`):
  `password = HMAC-SHA256(HMAC_KEY=b"j6l-aUmhCc@tN%T_", ResourceConfig.txt).hexdigest()`,
  a wallpaper is a password-protected ZIP.
- **Confirmation from the binary**: neither `WallpaperManager.dll` nor the native `RazerAxon.Player.exe`
  has any AES/RSA/CryptoStream for wallpapers → a wallpaper is precisely an encrypted ZIP, and decryption happens entirely
  when the archive is unpacked. The native player receives the already unpacked `ResourceConfig.txt`/`PlaySourceInfo`.
  → **The OpenAxon implementation is correct; no new key/algorithm was found.** [high confidence]

### Wallpaper data model (enum refinements) [DECOMP] — `RazerAxon.IWallpaperManager.dll`

```csharp
enum WallPaperTypes      { VIDEO, WEB, IMAGE, LOCALVIDEO, LOCALWEB, LOCALIMAGE, NONE }   // order = numeric value
enum WallPaperStatusEnum { Installed, Playing, FileBroken, FileLost, Uninstalled, Downloading, None }  // [JsonStringEnum]
enum WallpaperEffectsEnum{ None, WallpaperFillingMode, Brightness, Contrast, Hue, Saturation, PlayRate, WebInteraction, ThirdpartInfo }
enum StaticImgFillModesEnum { Fit, Fill, Stretch, Center, Tile }
enum WallpaperPlayers    { WindowsMediaFoundation, WebView2 }   // (ISettingManager) — default WebView2
enum WallpaperThirdparts { Spotify }
```
`WallPaperItem` is a large DTO: `Id, Title, ThumbnailSource, PreviewSource, PlaylistThumbnail,
Type, Source, Author(AuthorInfo), Resolution, WallPaperStatus, PlayResoucePath,
IsChromaEnabled/Supported/Customized, IsWebInteractionSupported, IsMute, Audible,
Category/CategoryName, AllTags, Rating, IsFavorite, Downloads, Upvoted, Silver, LatestVersion, …`.
**Refinement for axon-api.md**: `Audible` is a string ("0"/"1"), not a bool; `Silver` is an int (AI credits).

`UserAppSettings`: `MaxVolume=50` (default), `IsExitDirectly=2` (tri-state: 0/1/2=unset),
`WallpaperPlayer=WebView2` (default), `ThirdpartInfos: Dict<Spotify, string>`.

---

## 4. The real UI (for GTK4 accuracy) [CACHE + DECOMP]

### 4.1 Palette — confirmed from the WebView cache

The cache (`.../EBWebView/Default/Cache/Cache_Data/data_*`) actually contains `#44d62c`
(Razer Green, dominant), `#1a1a1a`, `#cccccc`, `#212121`, `#333333`. This matches
`design-system.md`. The GTK client (`razer-axon-gui.py`) already uses exactly these tokens
(#44d62c/#7ce26b/#359b24/#226916, #1a1a1a/#161616/#2e2e2e, #909090/#c8c8c8). **No discrepancies.**

### 4.2 Local HTML players (NEW — not in the docs) [installation files]

The installation root contains **local HTML files** (not from the CDN):
- **`RazerAxonWebPlayer.html`** — the player's actual layer compositor. Structure:
  - 3 layer types: `.image-player`, `.video-player`, `.web-player` (iframe), all
    `position:absolute; inset 0; width/height 100%`.
  - **Cross-fade transitions**: `opacity:0 → 1`, `transition: opacity 0.3s ease-in-out`,
    the active layer gets the `.cur` class (`opacity:1; z-index:2`). [valuable: the OpenAxon player
    can reproduce exactly this 0.3s opacity cross-fade between wallpapers]
  - image layer: `background-size: cover` (default), `contain` is also available.
  - body bg `#222`.
- **`DefaultScreenSaver.html`** — background `#111111`, class `.logo-background`.

### 4.3 UI structure (from design-system.md — already documented)

Fully covered: title bar, nav, sidebar **260px** (border #111), card grid
(min 240 / max 266px, radius 2px), detail panel (right slide-in), playlist bar (bottom),
buttons, modals (with the `madal` typo in the original), settings, forms (checkbox/radio/switch/
slider/select/input), dropdown/context-menu/pagination. The React routes (`/`, `/browse`,
`/createAI`, `/hall/*`, `/collections`, `/artists`, `/myWallPaper`) are in react-architecture.md.

---

## 5. Concrete improvements for OpenAxon (prioritised)

### P1 — high value, low cost
1. **0.3s cross-fade in our own player** (`openaxon-player.py`): when the wallpaper changes,
   apply `opacity 0→1, 0.3s ease-in-out` over the old layer (as in `RazerAxonWebPlayer.html`).
   Whether the current player already has a cross-fade needs to be checked. [new, from the local HTML]
2. **Add the `bespoke-analytics.razerapi.com` domain and the `/sts` path** to `axon-api.md`
   (if missing) — for a complete network map.
3. **Record in wallpaper-player.md** the exact set of 8 SequoiaCommand verbs and
   the pipe pattern `RazerCortexServiceAndShell{guid:N}` + the `readpipename/writepipename/version` arguments
   (in case OpenAxon ever talks to the real `RazerAxon.Player.exe`
   under Wine, not only to its own Python player).

### P2 — medium value
4. **Refine field types** in the OpenAxon models: `Audible` is a string, `IsExitDirectly` is a tri-state int,
   the `WallpaperPlayer` default is `WebView2`. This guarantees compatibility when parsing API responses/local state.
5. **Fully support `StaticImgFillModesEnum`** (Fit/Fill/Stretch/Center/Tile) in the image
   player — Razer applies it as the `WallpaperFillingMode` effect. Check that OpenAxon
   supports all 5 modes, not only cover.
6. **Version-tolerant pipe parser** (if OpenAxon implements a Central client): read
   `headerLen` and skip `headerLen-24` extra bytes (forward-compat, as Razer does).

### P3 — low value / for completeness
7. **Document the ITS AES key** as "known, not security-critical" (see §2.5) —
   to settle the question "does Axon have embedded keys".
8. **Take the original `UserManager.dll`** for future RE from a clean installer, not from
   the patched `~/.wine` (see §1).
9. The WebView cache bundles are compressed (gzip/brotli) — for a fresh CSS dump it is better to use the direct URL
   `https://axon-assets-cdn.razerzone.com/static/prod/2.6.2.0/` (as the previous RE did) rather than
   unpacking the Chromium cache.

### What NOT to do
- Rewrite the existing protocol/UI docs — they are accurate.
- Look for a different wallpaper decryption algorithm — there is none (HMAC-ZIP is confirmed by the binary).
- Change the GTK palette — it already matches the real CSS.

---

## Appendix: what was decompiled

The temporary decompilation working directory (ilspycmd) contains: RazerAxon, UserManager (patched),
WallpaperManager, WallpaperPlayerManager, WebviewWindowManager, DownloadManager, PlayListManager,
SettingManager, NotificationManager, DataAcquisition, EnvironmentManager, ScreenSaver, Reporter,
RazerCentralClient, RcClientBase, AccountManagerClient/Common, ActionServiceCommon + the interface
DLLs (IWallpaperManager, IWallpaperPlayerManager, IPlayListManager, ISettingManager, IUserManager).
`RazerAxon.exe`/`RazerAxon.Player.exe` are native apphost wrappers (the .NET code is in RazerAxon.dll;
Player.exe is the native C++ Sequoia player, analysed via strings).
