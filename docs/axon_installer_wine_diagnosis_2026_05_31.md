# Razer Axon — diagnosing the ONLINE INSTALLER under Wine: "server access unavailable" (2026-05-31)

Work by: Wehrwolfmann. This document is separate from
`openaxon_wine_axon_install_2026_05_31.md` (that one is about launching an ALREADY installed app).
This one covers why the online installer `RazerAxonInstaller.exe` itself does NOT GET THROUGH for
new users under Wine, and how to make installation work "for everyone".

## TL;DR (result, confirmed live)

The green "SERVER ACCESS UNAVAILABLE / Service disabled / Check" screen is caused by
**TWO independent causes**, both on the Wine-configuration side, not the server side:

1. **No real .NET Framework 4.8.** `RazerAxonInstaller.exe` is a DotNetZip SFX that
   extracts, offline, into `C:\windows\Installer\Razer\Installer2\App\` the real
   engine `RazerInstaller.exe` (.NET Framework **v4.8**, not .NET Core). On bare Wine with
   wine-mono the engine **crashes before any networking** (`mscoree:LoadLibraryShim error reading registry
   key for installroot` + mono assertion `gmisc-win32.c:138 'filename != NULL'`). Networking never
   even starts.

2. **Wine reports itself as Windows 7 → the server legitimately returns an empty catalog.** After
   installing `winetricks dotnet48` the engine starts and SUCCESSFULLY talks HTTPS (TLS ok, HTTP
   200), BUT sends `osver=7`. For `osver=7` the Razer server returns an **empty product list**
   `{"data":{"items":[]}}` (Axon requires Win10+). The installer treats an empty catalog as
   "service unavailable" → THE SAME green screen, despite HTTP 200.

**The fix "for everyone" (path A, verified live):**
`winetricks dotnet48` + `winetricks win10` in the prefix. After that the installer sends
`osver=10`, receives the full catalog (Synapse 4, Chroma, Cortex, **Razer Axon**), loads the
product cards (`Axon/logo.png`, `Axon/media_*.mp4` etc., 89× HTTP 200) and shows the
normal "RAZER GAMING SOFTWARE / Preparing…" screen. **The green error screen
is gone.** Confidence ~90% (see the limits at the end).

This is NOT a Wine bug — Wine behaves correctly (TLS/winhttp/secur32 work, certificates
pass `netconn_verify_cert returning 0`). It is a matter of **prefix configuration**.

---

## (1) Where the installer fails — what exactly, where, log quotes

Test prefix: `~/.cache/axon-test-prefix` (NOT the working `~/.wine`). Wine 11.10.
All runs with 90–150 s timeouts. The working prefix was not touched.

### Installer architecture (RE)
- `~/Downloads/RazerAxonInstaller.exe` = **DotNetZip Command-Line Self Extractor** (native
  i386 stub). When launched it:
  - makes a quick `wininet:InternetOpenW` (connectivity check, succeeds),
  - **extracts 84 files / ~40 MB offline** into
    `C:\windows\Installer\Razer\Installer2\App\` — this is the `RazerInstaller.exe` engine +
    AWS Kinesis (telemetry) + BLE/dongle modules + configs. **Axon itself is NOT in the SFX** —
    it is downloaded from the server.
  - starts `RazerInstaller.exe` via `mscoree` (.NET).
- `RazerInstaller.exe` is a PE32 **Mono/.NET assembly**; next to it lies
  `RazerInstaller.exe.config` with a hard requirement:
  `<supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.8" />`.
- The endpoints are in the extracted `App/InstallerConfiguration.xml` (in plain text):
  ```xml
  <DiscoveryServerRoot>discovery3.razerapi.com</DiscoveryServerRoot>
  <DiscoveryEndpointName>prod</DiscoveryEndpointName>
  <ManifestServerRoot>manifest3.razerapi.com</ManifestServerRoot>
  ```

### Failure #1 — on bare Wine (wine-mono), BEFORE networking
```
00ec:err:mscoree:LoadLibraryShim error reading registry key for installroot
/builds/mono/wine-mono/.../mono/eglib/gmisc-win32.c:138: assertion 'filename != NULL' failed
```
The engine does not run → empty `ManifesetCache/manifest.json` (`{"items":[]}`), zero-size
`DownloadCache` → green screen. This is the first thing a new user sees.

### Failure #2 — after `dotnet48`, but Wine=Win7
With real .NET 4.8 the engine starts and really works over the network. The log
(`+winhttp,+secur32`) shows successful calls:
```
winhttp:send_request full request:
  GET /api/v1/endpoints  Host: discovery3.razerapi.com  UserAgent: RazerLWI/2.4.0.868
secur32:schan_handshake Handshake completed
winhttp:netconn_verify_cert returning 0           <- certificate accepted
read_reply ... status code [L"200"]               <- discovery 200
  -> body: {"data":{"items":[{"hash":"8TQEz6XZ","name":"prod"}]}}

  GET /api/v1/releases/8TQEz6XZ/tags/prod/products?os=WINDOWS&osver=7&arch=64&mfr=HP
      &model=OMEN%20by%20HP%2016.1%20inch0&sku=8L370EA  Host: manifest3.razerapi.com
  -> status 200, Content-Length: 21  ->  {"data":{"items":[]}}   <- EMPTY because of osver=7
```
So **the server is reachable, TLS works, HTTP 200** — but `osver=7` → empty catalog →
the installer concludes "service disabled" → green screen again (confirmed by the screenshot
`/tmp/axon_inst_shot.png`).

---

## (2) Communication mechanism: DIRECT HTTPS (not Central Service IPC)

Unambiguously **direct HTTPS via WinHttp**, without the local Razer Central Service / named pipe.
The installer uses `System.Net.Http.WinHttpHandler` → Wine `winhttp` → `secur32`
(Schannel on top of GnuTLS). The trace showed the whole chain of requests:

1. `GET https://discovery3.razerapi.com/api/v1/endpoints` → `{hash:"8TQEz6XZ", name:"prod"}`.
2. `GET https://manifest3.razerapi.com/api/v1/releases/8TQEz6XZ/tags/prod/products?os=WINDOWS&osver=<N>&arch=64&mfr=...&sku=...`
   → the product catalog (depends on osver!).
3. `GET https://bespoke-analytics.razerapi.com/api/v1/lwi/app-rating-statistics` (ratings).
4. Card assets: `https://manifest-assets.razersynapse.com/Axon/logo.png`, `media_*.mp4`…
5. AWS telemetry: `https://u05srooyhc.execute-api.us-east-1.amazonaws.com/sts` (Kinesis).

The actual application packages are downloaded from URLs in the manifest (assets/S3, with random hashes —
see research). In this test the installer was not taken as far as that phase (it needs an "Install" click in the UI).

**Conclusion:** fixable at the Wine-configuration level (winhttp/TLS/osver), NOT via a service
stub. The "UserManager.dll stub" approach is NOT needed and NOT applicable here (that is a different binary,
a different stage — the installer, not launching the app).

### Proof that the server is healthy both under Wine and natively
| Request | Native (curl) | Under Wine (winhttp) |
|---|---|---|
| discovery `/api/v1/endpoints` | 200, returns hash `8TQEz6XZ` | 200 |
| manifest products `osver=7` | 200, `items:[]` | 200, `items:[]` → green screen |
| manifest products `osver=10` | 200, **11597 bytes, RAZER AXON present** | 200, loads Axon assets, 89×200 |

(Requests to the bare `discovery3/manifest3` roots return 503/404/500 — that is normal; the real
paths with hash/params return 200. "Server 503" is a false lead if you hit the root `/`.)

---

## (3) Research: WineHQ / community / workarounds

- **Symptom confirmation** (Razer Insider / Level1Techs): Synapse 4 users under
  Bottles/Lutris hit "installer wants to download additional data from Razer and isn't
  granted access" — the same class of problem. Their cause is the same: .NET and/or osver/network.
- **Architecture of Razer installers** (Bioruebe/UniExtract2 #165): the primary .exe is only a
  bootstrap; the real engine `RazerInstaller.exe` lands in `C:\Windows\Installer\Razer\…`;
  it creates an XML with packages and download URLs; the packages are 7-Zip Solid SFX; the download URLs contain
  a timestamp + random id (deliberately not shareable → an "honest" offline installer is impossible without
  keeping the already downloaded files). This matches what we see.
- **`discovery.razerapi.com/manifest.razerapi.com` are Akamai CDN**, the endpoints are alive.
- **WineHQ AppDB for Razer Axon** — no meaningful entries (niche software) → worth
  creating one.
- An alternative for mouse/keyboard drivers is OpenRazer+Polychromatic, but that is NOT about
  the Axon wallpaper app (irrelevant to our task).

Sources: razer.com/software/axon; Razer Insider "Server Access Unavailable" (Synapse 3/4);
Level1Techs Synapse-on-Linux; GitHub Bioruebe/UniExtract2 #165; Winetricks issues #1792/#2367
(dotnet48 under Wine/Proton).

---

## (4) Hypotheses tested in the test prefix (what helped / what did not)

| # | Hypothesis | Result | Evidence |
|---|---|---|---|
| H1 | Bare Wine (mono) will run the installer | **NO** | mscoree/mono crash before networking |
| H2 | The server is unreachable under Wine (TLS/certificates) | **REFUTED** | `Handshake completed`, `verify_cert returning 0`, HTTP 200 |
| H3 | `winetricks dotnet48` fixes startup | **YES (partially)** | the engine starts, goes online, HTTP 200 |
| H4 | Under Win7 the catalog is empty → green screen | **YES, this is the 2nd cause** | `osver=7` → `items:[]`; screenshot of the green screen |
| H5 | `winetricks win10` + dotnet48 = a working installer | **YES (the main fix)** | `osver=10`, 11597 B catalog with Axon, 89×HTTP 200, "RAZER GAMING SOFTWARE / Preparing" screen, NO green screen |

Process notes:
- `winetricks -q dotnet48` installs .NET 4.8 (registry `NDP\v4\Full` Release=`0x80eb1`=528113,
  mono removed), but **deadlocks on the final `wineserver -w`** (a known winetricks bug).
  The installation itself succeeds; it is enough to kill the hung one with `wineserver -k`.
- `winetricks win10` sets `CurrentBuild=19045`; the installer correctly started sending `osver=10`.
- A clean CA bundle/system certificates were NOT needed — secur32+GnuTLS accepted the Razer
  chain as is.

---

## (5) RECOMMENDATION "for everyone"

### Path A — Wine configuration (RECOMMENDED, verified live)
This is not a patch to the Wine sources (the bug is not in Wine) but a reproducible prefix recipe. As a
contribution — a **WineHQ AppDB test report for Razer Axon** + a ready-made OpenAxon wrapper script
that sets up the prefix correctly. Minimal steps:

```bash
export WINEPREFIX="$HOME/.local/share/openaxon/prefix"   # a separate one, not ~/.wine
wineboot --init
winetricks -q dotnet48          # REQUIRED: .NET Framework 4.8 (mono cannot run the installer)
winetricks -q win10             # REQUIRED: otherwise osver=7 → empty catalog → green screen
# (winetricks may hang on 'wineserver -w' — finish it off: WINEPREFIX=... wineserver -k)
wine ~/Downloads/RazerAxonInstaller.exe   # now gets to the catalog and installs Axon
```
Optionally, for Axon's WebView2 windows (already in our razer-axon.sh):
`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu --in-process-gpu --disable-features=RendererCodeIntegrity"`.

Implementation "for everyone" = add to OpenAxon an `openaxon-install.sh` script that:
1. creates an isolated prefix, installs `dotnet48`+`win10` (working around the winetricks deadlock),
2. runs the original `RazerAxonInstaller.exe` (nobody patches it — it legally downloads
   Axon from the Razer server),
3. after installation applies our existing launch-authorization workaround (DLL patch/
   token injector from `openaxon_wine_axon_install_2026_05_31.md`) and creates a shortcut.

Pros: we modify nothing proprietary at the installation stage; the user gets the
official Axon files; reproducible on a clean machine. This is the "contributable fix".

### Path B — an OpenAxon offline bundle (fallback, NOT recommended as the main one)
Copy an installed Axon directory + our DLL patch and lay it out bypassing the installer.
Cons (per the Bioruebe research): the package download URLs contain timestamp+random id and are not shareable;
bundling Razer's binaries is a legal risk (see the clean-room / don't-bundle-third-party-code rules in MEMORY).
So B only if the user has NO internet access to Razer; otherwise path A is more honest and simpler.

**Bottom line: path A.** It removes BOTH roots (dotnet48 + win10) and has been verified up to the catalog screen
with Axon. Keep B as an offline fallback, without bundling third-party binaries into the product.

---

## (6) What is needed from Wehrwolfmann

1. **Finish testing path A through to the end of installation**: in the test prefix the installer was taken to the
   catalog/preparation screen (Axon cards load), but the "Install Axon" click → the actual
   package download and writing to `Program Files` were not carried out in the headless run. The UI has to be
   clicked through live (or confirm that I may automate the clicks via
   xdotool/spectacle in the test prefix) and it has to be checked that the Axon package really downloads and
   installs under Wine (the 7-Zip SFX phase / possible launch of sub-installers).
2. **Razer login/token for the wallpaper catalog** — a separate step, it has NOTHING to do with the
   installer error (it is needed after installation, for content; see `razer-login.py`). A fresh JWT
   is needed, since the previous one expired on 2026-04-08.
3. A decision: whether to create a **WineHQ AppDB entry** for Razer Axon (rating + test report with
   the dotnet48+win10 recipe) — this is the "contribution for everyone".

---

## Files and artifacts
- This doc: `~/Projects/openaxon/docs/axon_installer_wine_diagnosis_2026_05_31.md`
- Related (launching the app): `~/Projects/openaxon/docs/openaxon_wine_axon_install_2026_05_31.md`
- Test prefix: `~/.cache/axon-test-prefix` (can be deleted: `rm -rf`)
- Trace logs: `/tmp/axon_inst1.log` (mono crash), `/tmp/axon_inst3.log` (.NET48, osver=7),
  `/tmp/axon_inst5.log` (.NET48+win10, osver=10, 89×200)
- Screenshots: `/tmp/axon_inst_shot.png` (green screen with osver=7),
  `/tmp/axon_inst_shot2.png` (the working "RAZER GAMING SOFTWARE" screen with win10)
- Extracted engine: `…/axon-test-prefix/drive_c/windows/Installer/Razer/Installer2/App/`
  (`RazerInstaller.exe`, `InstallerConfiguration.xml`)

---

## (7) INSTALLATION COMPLETED (2026-05-31, verified live)

Hypothesis (6).1 is closed: **Razer Axon is actually installed into Program Files under Wine.**
Prefix: an isolated test Wine prefix (Wine 11.10, RTX 4070, KDE Wayland/XWayland).

### What else turned up (new blockers not covered by items 1-5)

3. **No WebView2 Runtime → the catalog screen is black.** After dotnet48+win10 the
   "RAZER GAMING SOFTWARE" preparation screen appeared, but the next screen (the product catalog)
   is drawn by a WebView2 window — without the runtime it is a **black screen with a green progress bar**.
   Fix: install WebView2 Evergreen Standalone (Microsoft fwlink `linkid=2124701`,
   ~190 MB) — `wine MicrosoftEdgeWebView2RuntimeInstaller.exe /silent /install`. After that
   the engine brings up `msedgewebview2.exe`, and `EdgeWebView/Application/<ver>/` gets installed.

4. **The installer's WPF UI crashes when moving on from the EULA screen.** On the consent screen
   (RU: «Продолжить» / EN: "CONTINUE") clicking the button → the `RazerInstaller.exe` process
   crashes with an **unhandled `0x80131623`**. The exact stack (from `+eventlog`):
   ```
   Razer.Installer.UI.Language.Attached.TextBlockTextPlugin.Update()
     → System.Windows.Documents.TextElementCollection`1.get_Count()/get_FirstChild()
     → System.Windows.Controls.TextBlock.EnsureComplexContent()
     → FrameworkElement.MeasureCore()  → App.Main()
   ```
   This is WPF measure/layout of a TextBlock with inline content (the "...License Agreement" Hyperlink)
   under Wine. It is **NOT cured** by the locale (the crash is identical in ru and en) nor by
   `Avalon.Graphics\DisableHWAcceleration=1` (tested — does not help). So getting all the way
   through the installer's native WPF UI by clicking under Wine 11.10 is not possible.

### Workaround for crash #4 — direct Inno Setup from the manifest (legal)

The WPF UI is not needed at all. The catalog manifest (`ManifesetCache/manifest.json`, the object
`name:"Razer Axon"`) openly contains a direct link to the official Axon Inno setup:
```
download_url      : https://manifest-assets.razersynapse.com/<ts><rnd>RazerAxonSetup_2.6.2.0.exe
download_file_checksum (MD5) : 24695676971daa8253d88e44e88209d5
file_size         : 88216104
install_parameters: /SP- /VERYSILENT /DIR="%programfiles(x86)%\Razer\Razer Axon" /SUPRESSMSGBOXES /NORESTART
launch_filepath   : %programfiles(x86)%\Razer\Razer Axon\RazerAxon.exe
```
(The URL contains a timestamp+random id and goes stale over time — the current one is always taken from a
fresh manifest.) We download this file, **check the MD5 against the manifest** (an exact match),
run `wine RazerAxonSetup_2.6.2.0.exe /SP- /VERYSILENT /DIR=... /SUPPRESSMSGBOXES
/NORESTART`. Inno installs without WPF.

### Proof of installation
- `…/drive_c/Program Files (x86)/Razer/Razer Axon/RazerAxon.exe` — **PE32+ x86-64, 452 KB**.
- The Axon folder: **~230 MB, 660 files** (RazerAxon.exe, RazerAxon.Player.exe,
  RazerAxon.Reporter.exe, unins000.exe — the Inno uninstaller, WebView2 runtime DLLs, etc.).
- Registry: `…\Uninstall\Razer Axon_is1` → `DisplayName="Razer Axon"`,
  `DisplayVersion="2.6.2.0"`, `Inno Setup: App Path=…\Razer Axon`; the `RazerAxon://` protocol.
- **Launch confirmed:** `wine RazerAxon.exe` starts, creates
  `AppData\Local\Razer\RazerAxon\UICache\2.6.2.0\EBWebView\` (29 MB, WebView2 draws the UI) and
  the log `RazerAxon.log`: `Program.cs:TryLoginAsync → Start userLogin`. Then it hits
  `UserManager.cs … RazerClientBase.Connect timeout` — **it waits for Razer Central Service / login**.
  This is RUNTIME authorization (DLL patch/token from `openaxon_wine_axon_install_*.md`,
  the `razer-axon.sh` script), separate from installation.

### A reproducible script "for everyone"
`~/Projects/openaxon/install-axon-linux.sh` — idempotent, with checks at every step,
comments in Russian. It does: prefix → dotnet48 (if missing) → win10 → WebView2 (if missing)
→ bootstrap for the manifest (the UI is ignored, the process is killed after ~60 s) → parsing
download_url+MD5 from the manifest → download+MD5 check → `/VERYSILENT` installation →
(optional `APPLY_AUTH_PATCH=1`) the authorization DLL patch. The dotnet48/win10/webview2/manifest detectors
and the manifest parser were tested against a ready isolated test Wine prefix (green).

### What to submit to WineHQ AppDB (Razer Axon)
- Wine 11.10, a separate prefix.
- Required verbs: `winetricks dotnet48`, then `winecfg -v win10` (EXACTLY after
  dotnet48, since it resets the version to win7), WebView2 Evergreen Standalone.
- Known Wine defect: the installer's WPF UI crashes (`TextBlock.EnsureComplexContent`
  / `0x80131623`) — workaround: install via the Inno setup `RazerAxonSetup` (`/VERYSILENT`),
  link from the Razer manifest. Rating: Garbage→Bronze for the WPF installer itself;
  the Axon application starts after installation (requires login/Central Service).

---

## Calibrated confidence (rule #9)
- VERIFIED LIVE (confidence ~95%): mono crash on bare Wine; HTTP 200 from
  discovery/manifest; osver=7→empty catalog→green screen; dotnet48+win10→osver=10→
  catalog with Axon (manifest 43 KB, 65 products, Axon assets, preparation screen);
  missing WebView2→black screen; WPF crash `TextBlockTextPlugin`/`0x80131623` on the
  EULA transition (same for ru/en, DisableHWAcceleration did not help); **Axon installed into
  Program Files via Inno `/VERYSILENT` from the manifest URL (MD5 matched), RazerAxon.exe
  453 KB, folder 230 MB/660 files, Inno registry entries, launch up to the login screen**.
- LIMITS: verified on ONE machine (Wine 11.10, NVIDIA). On other Wine versions/GPUs
  the WPF crash and WebView2 behaviour may differ. The Axon setup URL goes stale (take it from a
  fresh manifest). RUNTIME login/wallpaper catalog NOT covered (a separate step).
- 503/404/500 on the bare endpoint roots is NOT a sign of unavailability (the real paths return 200).

---

## WebView2 `BrowserProcessExited` under Wine (investigation 2026-06-12)

### Symptom
After authorization (guest-fallback DLL patch) `RazerAxon.exe` renders the home
screen (Spotlight/Trending, host objects are injected, banners load), but after
~10-26 s the embedded WebView2 (msedgewebview2, evergreen Chromium 149) crashes:
`WebViewWindow.cs:CoreWebView2_ProcessFailed` → `BrowserProcessExited,close window`.
The main Axon process survives (Kinesis telemetry keeps running), but the UI window
closes. The time to crash is NON-DETERMINISTIC: usually 10-26 s, occasionally ~20 min
with the same binaries → this is an IPC/process race in Chromium under Wine, NOT authorization
and NOT the DLL patch.

### What was verified live (Wine 11.10, RTX 4070, Wayland+XWayland)
Test harness: run `RazerAxon.exe -showui`, monitor `RazerAxon.log` for
`BrowserProcessExited`, up to 600 s. Results:

| Configuration | Result |
|---|---|
| Evergreen 149, software flags (--no-sandbox --disable-gpu …) | HOME RENDERED, CRASH@15s |
| + `--single-process` (swiftshader) | CRASH@15s (worse) |
| + `--single-process --no-zygote --disable-dev-shm-usage` | CRASH@10s (even worse) |
| Plain Xvfb (Mesa software EGL, no NVIDIA) | EGL errors gone, but CRASH@25s |
| `WINEDLLOVERRIDES=werfault.exe=d` | CRASH@26s (did not help) |
| `--renderer-process-limit=1 --process-per-site …` (live) | once reached 360 s, on repeat CRASH@26s — flaky |
| WINEDEBUG=+seh,+process (slowed-down Wine) | did NOT crash within 60 s → confirms a timing race |
| **Fixed-version 109.0.1518.78 (env var WEBVIEW2_BROWSER_EXECUTABLE_FOLDER)** | **`Init webview2 failed` — UI does not start** |
| **Fixed-version 133.0.3065.92 (env var WEBVIEW2_BROWSER_EXECUTABLE_FOLDER)** | **`Init webview2 failed` → App exit. It is NOT about the version — the env var drives Axon into the `InitWebview2WithAbsolutePath` branch, which fails synchronously** |
| **Fixed-version 133.0.3065.92 (EdgeCore\133 + registry pv=133, NO env var)** | **INIT OK, home renders, primary branch `CreateCoreWebView2Environment`. BUT BrowserProcessExited ~10 s after init — same as 149. Gives NO stability** |
| Evergreen 149 + `--disable-watchdog --disable-hang-monitor …` | HOME RENDERED, CRASH ~10s (flags did not help) |

### Key conclusions
1. **EGL/DRI2 is NOT the root.** Under plain Xvfb (Mesa software EGL) the
   `libEGL: failed to create dri2 screen` errors disappear, but WebView2 still
   crashes. NVIDIA EGL under XWayland is just noise, not the cause.
2. **`--single-process` is HARMFUL** (crashes faster), just as upstream warns.
3. **(REFUTED — see the "ROOT CAUSE REVISED" section below.)** ~~The root is the instability
   of Chromium's multi-process Mojo IPC under Wine.~~ The real root is the viz process on
   DirectComposition (`DCompositionCreateDevice` E_NOTIMPL), not Mojo/IPC. This item is
   kept as a historical hypothesis; the current conclusion is in the final section.
4. **A fixed-version runtime does NOT solve the crash — neither by version nor by mechanism
   (133.0.3065.92 verified live on 2026-06-12).** Axon's init mechanism was analysed
   (`WebView2Control.cs:InitializeAsync`):
   - **Primary branch** (L:198 `start create CoreWebView2Environment`) — a plain
     `CreateCoreWebView2Environment`, uses registry discovery / the env var.
     Under evergreen 149 it WORKS (home renders).
   - **Fallback** `try InitWebview2WithAbsolutePath` (L:89/160) — fires
     ONLY when the primary has failed; it hardcodes `EdgeCore\<evergreen-ver>` and under Wine
     also fails → `Init webview2 failed` → **App exit**.
   - Setting `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` (109 OR 133) breaks the primary
     synchronously (~20 ms) → fallback → init fail. I.e. **the fixed-version env-var
     mechanism by itself is incompatible with Axon under Wine**, not the version.
   - 133 deployed as `EdgeCore\133.0.3065.92` + registry
     `EdgeUpdate\Clients\{F3017226-…}\pv=133.0.3065.92` (NO env var) goes through the
     primary branch: **init OK, home renders, the live process loads EdgeCore/133**.
     BUT BrowserProcessExited crashes just the same after ~10 s — the version gives no stability.
   - 109 when tried via the env var — `Init webview2 failed` (the same fallback branch).
5. **Micro-mitigations** (software rendering + Mesa EGL + minimising processes)
   reduce the frequency/delay the crash, but do NOT eliminate it. WebView2 is officially
   not supported on Wine (MicrosoftEdge/WebView2Feedback#3127).
6. **The main Axon process survives the WebView2 crash.** Final measurement
   (evergreen 149 + our flags, 200 s): the home screen renders in ~5 s,
   the main process stays alive >200 s continuously, WebView2 crashes cyclically (~38 times
   in 200 s) and Axon reopens the window each time (the UI flickers). The WebView2 crash
   does NOT bring down the application — it is UI degradation, not fatal. The cycle frequency is flaky
   between runs/days (the day before, the same binaries held for ~20 min without crashing).

### Applied configuration (`razer-axon.sh`)
- Default prefix fixed: `~/.local/share/openaxon/prefix` (was `~/.wine`).
- `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu
  --disable-gpu-compositing --disable-software-rasterizer
  --disable-features=RendererCodeIntegrity --disable-crash-reporter
  --disable-renderer-backgrounding --disable-background-timer-throttling"`
  (the non-recommended `--in-process-gpu` removed).
- `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe` + Mesa EGL vendor json.
- An optional fixed-version runtime via `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER`
  with auto-detection of incompatibility (`.wv2-fixed-broken` → fall back to evergreen).
  Default `INSTALL_WV2_FIXED=0` (109 breaks init; 133 not fully tested).

### Remaining (historical snapshot before 2026-06-12 — see the SECTION BELOW, root cause revised)
- Deterministic WebView2 stability >5 min was NOT achieved.
- **Fixed-version 133 RULED OUT as a solution** (2026-06-12): init goes through the
  registry path, but BrowserProcessExited crashes identically to 149. The runtime version has nothing
  to do with it. The 133 CAB is kept in `~/.cache/openaxon/wv2-fixed-133-x64.cab` and
  deployed to `EdgeCore\133.0.3065.92` (registry reverted to 149).

---

## ROOT CAUSE REVISED: it is the GPU process (0x80000003), NOT a Mojo named pipe (2026-06-12)

The earlier hypothesis "instability of multi-process Mojo IPC under Wine" and the candidate
"a Wine patch per WineHQ #56378" are **REFUTED empirically**. Re-verified live with
`WINEDEBUG=+seh,+process` + `--enable-logging=stderr --v=1` on Wine 11.10 (RTX 4070,
Wayland/XWayland), prefix `~/.local/share/openaxon/prefix`.

### What Chromium's stderr showed before dying (decoded from dispatch_exception)
```
content\browser\gpu\gpu_process_host.cc:1063] GPU process exited unexpectedly: exit_code=-2147483645
content\browser\gpu\gpu_process_host.cc:1515] The GPU process has crashed 1..2..3..4..5..6 time(s)
```
`exit_code = -2147483645 = 0x80000003 = STATUS_BREAKPOINT (EXCEPTION_BREAKPOINT)`.
That is, the **GPU/Viz process** dies on a `CHECK()`/`__debugbreak()` during GPU init under Wine,
crashes ~6 times in ~12 s, after which the browser process exhausts its GPU crash limit and
DELIBERATELY exits → Axon sees `BrowserProcessExited` and closes the window. In the Wine trace
there is **no c0000005/WerFault** for the browser process — it does not "crash", it gives up in an orderly way.

Process count in one run: **12× gpu-process spawn, 2× renderer, 2× crashpad,
2× NetworkService, 2× StorageService** — the browser is RESTARTING the gpu-process in a loop.

### Why `--disable-gpu` does NOT help (the key nuance)
According to the official WebView2 docs: `--disable-gpu` disables HW acceleration, but **if the system has a
software renderer, a gpu-process is still brought up under SwiftShader** — and that is exactly what hits
0x80000003 under Wine. Our `--disable-software-rasterizer` alone did NOT remove it under WebView2 149
(the gpu-process was still spawned 12 times).

### #56378 — what it really is (research, working around Anubis)
WineHQ Bug **#56378** = "Microsoft Edge and Edge-based WebView2 do not function without
--no-sandbox option" — this is a **Chromium sandbox bring-up bug**, NOT named-pipe/Mojo. **Closed
FIXED in Wine 11.1.** Its companion #56377 (Edge freezes ~1-3 s) — FIXED in 10.5. The fixes are in
`win32u/winstation.c`, `win32u/sysparams.c`, `server/window.c`, `kernelbase/security.c`,
`ntdll/sec.c` (winstation/desktop/token + `DeriveCapabilitySidsFromName`), **NOT** in
`server/named_pipe.c`/`ntdll/unix/sync.c`. VERIFIED: all these fixes are ALREADY present in
the system Wine 11.10 (grep confirmed `DeriveCapabilitySidsFromName`,
`SetAdditionalForegroundBoostProcesses`, `is_service_process`/explorer-desktop).
Chromium Mojo uses named pipes in BYTE mode (overlapped), which Wine has supported for a long time;
since Chrome ~112 Mojo moved to shared memory (ipcz) altogether. → **A Wine patch for named pipes/#56378
is not required and would not have helped.** A patched Wine was NOT built (cancelled based on the
research + live diagnostics as obviously irrelevant).

### ⚠️ FINAL FIX (2026-06-18, confirmed VISUALLY — supersedes the recipe below)
> The real solution for the black/white screen is **`Version=win7` for `msedgewebview2.exe`**
> (Chromium's renderer subprocess). With a Windows version ≥8.1, viz presents the frame via
> **DirectComposition** (`DCompositionCreateDevice`), which Wine does not implement
> (E_NOTIMPL) → viz CHECK crash → the frame never reaches the window. Under `win7` the same
> `SoftwareOutputDevice` goes through **GDI BitBlt** (no DComp) → the pixels actually land in the window.
> `RazerAxon.exe` and the prefix globally stay **win10** (otherwise the Razer server returns an
> empty catalog — these are DIFFERENT per-app overrides on different exes). Confirmed live:
> the home screen (carousel/TRENDING) and Razer ID Login are drawn completely.
> Sources: WineHQ Bug 58921, winetricks #2226, CodeWeavers, Arch [SOLVED].

### Registry recipe (current revision)
1. **Edge registry policy `HardwareAccelerationModeEnabled=0`** (auxiliary):
   - `HKLM\Software\Policies\Microsoft\Edge`           `HardwareAccelerationModeEnabled=dword:0`
   - `HKLM\Software\Policies\Microsoft\Edge\WebView2`  `HardwareAccelerationModeEnabled=dword:0`
   - `HKCU\Software\Policies\Microsoft\Edge`           `HardwareAccelerationModeEnabled=dword:0`
2. **Windows 7 version for `msedgewebview2.exe`** (THE MAIN THING — moves SoftwareOutputDevice to
   GDI BitBlt instead of DirectComposition): `HKCU\Software\Wine\AppDefaults\msedgewebview2.exe Version=win7`.
   ⚠️ Previously this mistakenly said `win81` — that is EXACTLY the threshold at which DComp kicks in, and it was what produced the black screen.
3. Flags (in `razer-axon.sh`): `--disable-gpu --disable-gpu-compositing --disable-software-rasterizer
   --disable-gpu-sandbox --no-sandbox` + software EGL (Mesa/llvmpipe).

### Measurement (historical snapshot before the win7 finding)
- **Baseline (without the registry fix):** the GPU process crashes ~6 times → `BrowserProcessExited` after
  ~10-17 s, cycle ~38 times/200 s (UI flicker).
- **With the `win81` variant (refuted):** the browser process stopped exiting, BUT viz looped
  on the DComp crash and produced no frames → **black screen**. The claim "stable >2 min" referred to
  the process surviving, not to the picture. BOTTOM LINE: only `win7` cures it (see the block above).

### Diagnostic artifacts
- Harness: `~/.cache/openaxon/run_test.sh <seconds> <tag>` (registry backup before the edits:
  `~/.cache/openaxon/reg-backup-20260612/`).
- Logs: `~/.cache/openaxon/diag/winedebug.log` (full +seh+process trace with the GPU crash loop),
  `~/.cache/openaxon/diag/hwoff_win81_*` (run with the fix).
- Fix reg files: `/tmp/axon_hwaccel.reg`, `/tmp/axon_winver.reg` (their contents are duplicated above).

### Remaining candidates (OBSOLETE — the screen was solved via `win7`, 2026-06-18; historical section)
1. **`--disable-gpu-watchdog` + raising the GPU crash limit** — to survive the early init bump.
2. **Wine-Staging ≥11.6 (DirectComposition patchset)** — if the CHECK is specifically in the DComp path.
3. **An external WebView2 host** (CDP proxy) — move the browser out from under Wine entirely.
- Iterating over runtime versions (109/133/149) and a Mojo/named-pipe Wine patch — a DEAD END (proven).
