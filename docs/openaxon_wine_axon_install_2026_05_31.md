# OpenAxon — installing/running Razer Axon under Wine: fixing "server access unavailable" (2026-05-31)

Work by: Wehrwolfmann. This document records the diagnosis and the application of our earlier
OpenAxon fix to the Razer green screen "SERVER ACCESS UNAVAILABLE / Service
disabled / Check" that appears when Razer Axon is launched under Wine.

## TL;DR (result)

- Razer Axon **had already been installed** earlier in `~/.wine` (`RazerAxon.exe`, `RazerCentralService.exe`,
  shortcuts). The problem is not at the file installation stage but at the **online authorisation** stage:
  the original Axon talks to Razer Central Service / the Razer server, which does not respond under Wine
  → green screen with a server error.
- Our earlier fix (OpenAxon) = **replacing `RazerAxon.UserManager.dll` with a patched version**
  that stubs out authorisation locally (does not contact the server). After the Axon update
  (7 April) the installed DLL reverted to the original — the patch had been overwritten.
- **Patch re-applied → Axon starts, the working main UI opens (HOT/BROWSE/
  SERIES/ARTISTS), the green error screen is gone.** State as of 2026-05-31: confirmed
  live (window + screenshot of the authorisation screen).
- Confidence ~90% (as of 2026-05-31): verified by launching under Wine (the version current at the log date) +
  a screenshot of the working UI. Limitation: the wallpaper catalogue is empty (grey placeholders) because the token
  has expired — that is a separate step (logging in again) and is unrelated to the server error.

## (a) What our earlier fix consisted of (Wine + DLL)

OpenAxon (repo `wehrwolfmann/openaxon`, locally `<HOME>/Projects/openaxon/`) offers TWO
ways to bypass Razer's online authorisation:

1. **Token injector (preferred, no binary patching)** — `razer-login.py`
   (WebKit Razer ID login window → captures the JWT) + `razer-token-inject.py` (sends
   `WebApp_SetLoginSuccessFromWeb` to RazerCentralService over the named pipe `{FC828A97-...}`). Razer's files
   stay original.

2. **DLL patch (outdated, but direct) — this is what is applied now.**
   The patched file is `RazerAxon.UserManager.dll` (class `UserManager : IUserManager`). Source:
   `<HOME>/Projects/openaxon/patch/src/RazerSequoia.SequoiaUserManager/UserManager.cs`.
   The gist of the rewritten logic:
   - `LoginAsync()` reads a local token from
     `…/AppData/Local/Razer/RazerAxon/wine_login_token.json`; if there is no token or it is empty,
     it creates a local guest (`"noAuth"`, `isGuest`). **No server requests at all.**
   - `GetUserToken()` returns the token from the local `User` object.
   - `GetNatashaStateDescription()` → `"Service not found"` (stub for the service check).
   - Profile/balance/language/theme are local stubs; the feedback/profile windows open in
     the embedded WebView2.
   Effect: the original chain `UserManager → NacClient → named pipe → RazerCentralService →
   Razer server` is replaced by a local stub → the "server access unavailable" screen never appears.

   It is applied by `razer-axon.sh` (function `check_patch`): on launch it compares
   the installed DLL with `patch/RazerAxon.UserManager.dll`; if they differ, it saves `.orig` and
   copies the patch over. The drawback of the method (per the README): **it is reset after every Axon update** —
   which is exactly what happened on 7 April.

   Wine wrapping in `razer-axon.sh`: `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox
   --disable-gpu --disable-gpu-sandbox --in-process-gpu --disable-features=RendererCodeIntegrity"`,
   removing `WM_TRANSIENT_FOR` via xprop (taskbar fix), `wine RazerAxon.exe -showui`.

## (b) Research: WineHQ / workarounds for Razer installers

- Officially Razer Axon is Windows-only (Win10/11), but it is **alive and actively developed**
  (Best Wallpaper 2025 awards, active Insider forum/site). So the "server error" under Wine is
  a network/IPC block, not the product being discontinued.
- "Server Access Unavailable" is a long-standing common problem of Razer installers (Synapse 3/4 and Axon
  use the shared `RazerInstaller.exe`, which we also have in
  `ProgramData/Razer/Installer/App/RazerInstaller.exe`). Community workarounds (Razer Insider):
  prefer IPv4 / disable IPv6, install modules manually bypassing the installer wizard,
  run as administrator + temporarily disable the firewall/AV. Not relevant for us — the files are already
  installed; all that is needed is an authorisation bypass, which our DLL patch provides.
- WineHQ AppDB: no meaningful entries were found for Razer Axon specifically (niche software).

Sources:
- https://www.razer.com/software/axon
- https://www.razer.com/newsroom/featured/razer-axon-best-wallpaper-2025
- https://insider.razer.com/razer-synapse-4-55/error-server-access-unavailable-can-t-install-any-razer-app-87604
- https://insider.razer.com/razer-synapse-3-29/synapse-3-0-install-server-access-unavailable-solution-5807

## (c) Diagnosis of the current failure

Environment: Wine 11.10 (as of the log date, system), prefix `~/.wine`, winetricks available. Proton was not used.

State of the prefix before the fix:
- Installed: `…/Razer/Razer Axon/RazerAxon.exe` (PE32+ x86-64, .NET 6, self-contained,
  `runtimeconfig.json`: net6.0 / NETCore.App 6.0.36), `RazerCentralService.exe`, the WebView2 runtime.
- `RazerAxon.UserManager.dll` (72904 bytes) **== `RazerAxon.UserManager.dll.orig`** → i.e. the
  ORIGINAL was in place; the patch had been reset (probably by the Axon update of 2026-04-07).
- `wine_login_token.json` exists, but the token has **expired** (the `tokenExpiry` value is in the past).

Cause of the green screen: the original `UserManager` goes to RazerCentralService/the Razer server
for authorisation; under Wine there is no response → the server error screen. (This is neither a Wine crash nor a broken
installer — it is the application's server check.)

## (d) What was applied and the result

The DLL patch was applied:
```bash
AXON_DIR="$HOME/.wine/drive_c/Program Files (x86)/Razer/Razer Axon"
# .orig is already valid (== the current original DLL); an extra timestamped backup was made
cp "$HOME/Projects/openaxon/patch/RazerAxon.UserManager.dll" \
   "$AXON_DIR/RazerAxon.UserManager.dll"
```
The installed DLL is now identical to `patch/RazerAxon.UserManager.dll` (43008 bytes).

Launch (Wine — the version current at the log date):
```bash
WINEPREFIX=~/.wine WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--no-sandbox --disable-gpu \
  --disable-gpu-sandbox --in-process-gpu --disable-features=RendererCodeIntegrity" \
  wine RazerAxon.exe -showui
```
Result:
- The "Razer Axon" window appears in ~8 s and stays up reliably.
- **No** `BadImageFormatException` / `could not load … UserManager` / `Unhandled exception`
  (even though `file` labels the patched DLL as i386, the managed assembly loads into the x64 process
  without problems).
- The log has **no** `server/unavailable/access/central` markers.
- Screenshot (`/tmp/axon_shot.png`): the working main UI — navigation AXON/CREATE/COMMUNITY/
  LIBRARY, tabs HOT/BROWSE/SERIES/ARTISTS, avatar. NO green server error screen.
- Insignificant errors in the log (not blocking): `Windows.UI.Composition.Compositor` (WinRT effects)
  and `combase`/COM classes (native helpers/telemetry) — normal under Wine.

The wallpaper catalogue shows grey placeholders (content did not load) — expected, because
the token has expired. This is NOT an authorisation server error; it is solved by logging in again (see below).

> Note on UI labels: the screens were observed in Axon's Russian UI; the labels above are given in English
> translation and may differ slightly from the exact wording of Axon's English UI.

## (e) What to submit as a "patch for Wine"

Important: our fix is a **patch of the Razer application (replacing a managed DLL)**, NOT a fix in
Wine itself. Wine behaves correctly here; it was Razer's online mechanism that failed. So there is **nothing**
to submit to wine-devel as a Wine source patch — this is not a Wine bug.

What can actually be written up:
- **A WineHQ AppDB entry for Razer Axon**: Wine version (as of the log date), rating (Garbage→Bronze without
  the patch because of the server screen; higher with the authorisation bypass), a test report with the steps:
  installation via `RazerInstaller.exe`, the WEBVIEW2 flags, the authorisation bypass (our DLL patch or
  the token injector), the `WM_TRANSIENT_FOR` fix for the taskbar.
- If a real Wine bug is ever found (e.g. winhttp/secur32/named-pipe IPC, because of
  which RazerCentralService cannot respond), then a minimal repro + a diff against
  the relevant Wine dll module. There is no such repro now: the application-level bypass
  is sufficient, and no root Wine defect has been pinpointed.

## (f) Next steps (for full functionality, not for eliminating the server error)

1. Log in again — the token has expired:
   ```bash
   <HOME>/Projects/openaxon/razer-login.py     # get a fresh JWT
   # with the patched DLL, the token is read directly from wine_login_token.json in LoginAsync;
   # token-inject is only needed for the original (unpatched) chain through the service
   ```
2. Launch via `razer-axon.sh` — it re-applies the patch itself after Axon updates
   (`check_patch`) and fixes the taskbar.
3. After every Razer Axon update the patch is reset → re-apply it
   (`razer-axon.sh` does this automatically). The long-term alternative without patching
   the binary is the token injector method.

## Files

- Patched DLL (the one applied): `<HOME>/Projects/openaxon/patch/RazerAxon.UserManager.dll`
- Patch source: `<HOME>/Projects/openaxon/patch/src/RazerSequoia.SequoiaUserManager/UserManager.cs`
- Launcher with auto-patching: `<HOME>/Projects/openaxon/razer-axon.sh`
- Backup of the original: `…/Razer/Razer Axon/RazerAxon.UserManager.dll.orig` + timestamped `.bak.*`
- Launch logs: `/tmp/axon_run.log`, `/tmp/axon_run2.log`; screenshot `/tmp/axon_shot.png`
