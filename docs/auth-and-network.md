# Razer Axon 2.9.1.0 — account sign-in and network dependency

Work by: Wehrwolfmann. Started 2026-08-12.

A continuation of `install-under-wine-2.9.1.0.md`: that document proves that **installing** 2.9.1.0
succeeds on a bare wine-11.15 prefix. This one covers what happens **after**
installation — signing in to a Razer account, and the network.

Test prefix: `~/.wine-axon-auth` (a separate one, created from scratch on 2026-08-12).
Wine: system **wine-11.15**.

---

## TL;DR

1. **Axon has no sign-in of its own.** The application shows neither a login form nor a
   "sign in" button. It asks for credentials from a **separate Razer Central service**
   (the `Natasha` module from the manifest) over a local named pipe. The Axon web UI can
   only *sign out* (`logout`), after which the sign-in window is again drawn by Razer Central.
2. **The token is not OAuth.** The web bundle contains no `client_id`, no `redirect_uri`, no
   `code_challenge`, no `Bearer`. The host hands the page a ready-made JWT, the page exchanges
   it for a server session via `POST /v1/login`, and from then on signs requests with an
   opaque string in the `Authorization` header.
3. **The first point of failure under Wine is not the network but the absence of Razer Central.** Measurement: a fresh
   prefix, Axon installed, no Razer Central → the application gets as far as
   `Program.cs:TryLoginAsync / Start userLogin` and **hangs forever**, without opening a single
   window and without making **a single network connection** (checked with `ss`).
4. Installing Razer Central under Wine requires the **real .NET Framework 4.8**
   (`winetricks dotnet48`), because wine-mono does not pass its check. With it,
   Razer Central 7.23.0.1220 installs and the `RzActionSvc` service runs.
5. **The second (and last) point of failure is the Chromium sandbox.** The Razer ID sign-in window
   is drawn by CefSharp inside Razer Central; under Wine the renderer does not start at all
   (`--type=renderer` is missing from the process list), and the window is white. Fixed by the
   **`--no-sandbox`** flag.
6. ⭐ **With these two fixes, sign-in under Wine works end to end.** Guest sign-in was completed
   live: Razer ID window → account issued → Axon restarts with `-showui` → WebView2 →
   storefront. Screenshots in `~/Pictures/Screenshots/axon-2910-окно-входа-razer-central.png`
   and `axon-2910-главное-окно-гость.png`.
7. **Offline, the application is useless.** Installation without network "succeeds" but silently ends up
   without WebView2; signing in without network is impossible both on the first launch and on later ones.

---

## 1. How sign-in works

### 1.1. Three layers and who is responsible for what

```
┌──────────────────────────────────────────────────────────────┐
│ RazerAxon.exe (.NET 8, WinForms shell)                        │
│   └── RazerAxon.UserManager.dll                               │
│         ├── AccountManagerClient ──┐                          │
│         └── UpdateClient ──────────┤ named pipe               │
│                                    ▼                          │
│ RazerCentralService.exe (Natasha module 7.23.0.1220)          │
│   ├── AccountManager  — sign-in, token, profile, cloud settings│
│   ├── UpdateManager   — updates                                │
│   └── NAC (GUI)       — Razer ID SIGN-IN WINDOW                │
│                                                              │
│ WebView2 (msedgewebview2.exe)                                │
│   └── SPA from https://axon-api.razer.com/2.9.1.0/           │
│         talks to the host via chrome.webview.hostObjects.*    │
└──────────────────────────────────────────────────────────────┘
```

The division of responsibilities is strict:

| Layer | What it does during sign-in |
|---|---|
| `RazerAxon.exe` | calls `TryLoginAsync` at startup; does **not draw** a sign-in form itself |
| Razer Central | holds the account, shows the Razer ID window, hands out the JWT over IPC |
| WebView2/SPA | receives a ready-made JWT from the host and exchanges it for an API session |

### 1.2. What the native part does

The window settings live right in the installed Axon's `appsettings.json`:

```json
{
  "WebWindowStartupSettings": {
    "StartupUri": "https://axon-api.razer.com/2.9.1.0/",
    "Width": 1280, "Height": 720,
    "WebServiceDomain": "https://axon-api.razer.com/v1"
  }
}
```

⭐ An important correction to earlier notes: **the storefront origin is `axon-api.razer.com`,
not `axon.razer.com`.** In the bundle, `REQUEST_URL` is empty in all four environments
(`dev/test/pro/staging`), meaning all requests go **same-origin** — to wherever the page
was loaded from. The string `axon.razer.com` appears in the bundle only in links
that open in an external browser (`/faq/`, `/communityRules/` and the like).

### 1.3. What the web part does (analysis of the `axon.b454555f59e3550b4628.js` bundle)

Bootstrap:

```js
window.SequoiaClientObj.getUser();          // → {code:0, data:{Token, IsGuest, Id}}
window.SequoiaInfo.is_guest = a.data.IsGuest;
window.SequoiaInfo.token    = a.data.Token;
window.SequoiaInfo.uuid     = a.data.Id;
window.SequoiaClientObj.getPcUniqueCode().then(...)   // → SequoiaInfo.pcCode
return login({token: a.data.Token, is_guest: ..., uuid: a.data.Id});
```

Exchanging the token for a session and signing requests:

```js
post(`${REQUEST_URL}/v1/login`, {token, is_guest, uuid})
  → window.SequoiaInfo.authorization = data.authorization
  → window.SequoiaInfo.country       = data.country

axios.defaults.withCredentials = true;
axios.create({headers: {"X-Requested-With": "XMLHttpRequest", "X-Version": "2.9.1.0"}})
  .interceptors.request.use(cfg => {
      cfg.headers["Authorization"] = window.SequoiaInfo?.authorization || "";
      cfg.headers["X-Language"]    = window.language || "en";
  });
```

Details worth knowing when rebuilding the client:

* The `Authorization` header is an **opaque string** from the `/v1/login` response, not a
  `Bearer` JWT (there is no prefix). `withCredentials: true` → cookies are sent too.
* The server marks an expired session with **`403`, not `401`**; there is no `401` handler
  in the bundle at all. On `403` (except for `/login` itself) the client silently repeats
  `/v1/login` with the same JWT.
* `code == 1001` in the response body → up to three `location.reload()` calls; the
  `refreshNum`/`reloadNum` counters live in `localStorage`.
* HTTP `503` → `SERVER_ERROR_503` event, `502` → `server_maintain`.

⭐ **There is no "sign in" button in the web part.** All three places that look like
sign-in (`UC_LOGIN`, the onboarding screen, the guest modal) call **`logout()`**:

```js
case "UC_LOGIN":  window.SequoiaClientObj.logout(); break;
case "UC_LOGOUT": window.SequoiaClientObj.logout(); break;
```

The idea is this: the page always runs under an already issued account (guest or full).
"Sign in" = drop the current (guest) one and let the native host show the Razer ID window.
`OpenLoginWindow` in the bundle is used **only for Spotify**, not for Razer ID.

Guest mode is fully functional: `window.SequoiaInfo.is_guest` disables favourites,
playlists, publishing, voting and top-ups, but the catalogue is shown.

### 1.4. Where the token is stored

The canonical path (original application) is inside Razer Central: the account is
serialized as `RazerUser` XML (see `razer-central-ipc.md`), containing `<Token>` (JWT),
`<LoginId>`, `<AccessToken>`, `<AccessTokenExpirationDate>`, `<IsGuest>`. Axon only
requests it and does not write it to the registry or a file itself.

The AccountManager commands used for this (service type 4):

| Command | ID | Meaning |
|---|---|---|
| `TryLogin` | 44 | auto-login at startup — what `TryLoginAsync` calls |
| `GetCurrentUser` | 3 | get `RazerUser` (the JWT is in there) |
| `RefreshToken` | 4 | renew |
| `StartLogin` | 1 | show the sign-in window |
| `TryAutoLoginAsGuest` | 61 | guest auto-login |
| `WebApp_SetLoginSuccessFromWeb` | 131094 | **push in a ready-made JWT from outside** |

The last command is the very door through which the port inserts a token obtained
by its own sign-in window (`razer-token-inject.py`).

In the **port**, the token is stored as a file:

```
~/.config/razer-axon/token.json
(and a copy in the prefix: drive_c/users/<user>/AppData/Local/Razer/RazerAxon/wine_login_token.json)
```

The format is exactly the `WebAppTokenInfo` that command 131094 expects:

```json
{"convertFromGuest": false, "token": "eyJhbGciOiJFUzI1NiI…", "isOnline": true,
 "isGuest": false, "uuid": "RZR_…", "loginId": "user@example.com",
 "tokenExpiry": "2026-04-08T21:33:05.000Z", "stayLoggedIn": true}
```

### 1.5. The only real OAuth in Axon — and it is NOT for sign-in

There is no OAuth in the web bundle at all. But there is some in the native part — in
`RazerAxon.UserManager.dll` (strings extracted with `strings -el` from the installed file):

```
Failed to retrieve SSO token: No logged-in user.
grant_type
razer_jwt_bearer
redirect_uri
https://oauth2.razer.com/services/code_sso
Authorization
Bearer
code
…
GetSsoCodeAsync failed. result is empty
GetZVaultWebUrl
https://razerid.razer.com/token-login?c=
Open user ZVault web with sso code failed.
```

This reads unambiguously: holding an **already obtained** JWT, the application makes
`POST https://oauth2.razer.com/services/code_sso` with
`grant_type=razer_jwt_bearer`, `redirect_uri=…` and the header `Authorization: Bearer <JWT>`,
receives a one-time `code` and opens `https://razerid.razer.com/token-login?c=<code>`.

In other words, this is **not sign-in but "delivering an existing session to a browser window"** —
so that the profile, password change and zVault (`https://gold.razer.com`) pages open
already authenticated. The source of the JWT is still Razer Central.

### 1.6. How exactly Axon invokes sign-in (from strings in the same DLL)

```
Razer\Razer Services\Razer Central\Razer Central.exe
App not installed  /  Service not found  /  Service is
Call AccountManagerClient.StartLogin failed.
Wait login failed.
Login over time:
Get current user failed.
AccountManagerClient_LoginComplete result: … , user: …
TryRefreshTokenIfNeed  /  Refresh token  /  Refresh token failed.
RzActionSvc
```

Scenario: `LoginAsync` → `AccountManagerClient.StartLogin` (command 1) → wait for the
`LoginComplete` event with a timeout → `GetCurrentUser`. The name of the Windows service the
application looks for is **`RzActionSvc`**; the GUI executable is
`Razer\Razer Services\Razer Central\Razer Central.exe`.

The same place has the User-Agent generator for API requests:

```
GenerateUserAgent →  "RazerAxon/" + version + " (Windows NT " + os_version + "; Win64)"
fallback:            "RazerAxon/1.0"
```

### 1.7. The bridge through which the sign-in window hands over the token

The `id.razer.com` page is designed for a native host and talks to it through two
globals that the host must declare **before** the page loads:

```js
window.callbackObjforjs = { onEvent: function(action, payload, callback) { … } };
window.callJSFromClient  = function(action, data) { … };
```

The host answers `SET_WEBAPP_READY`, `GET_LANGUAGE`, `GET_THEME`, `GET_LOGIN_STATUS`,
`GET_MACHINE_ID_INFO`, `IS_WINDOW_VISIBLE`, and when sign-in completes the page sends
`SET_LOGIN_SUCCESS_FROM_WEB` with a `WebAppTokenInfo` JSON string. That is the entire
"sign-in protocol" — no OAuth redirects, no PKCE.

---

## 2. What exactly breaks under Wine

### Measurement 1 — clean prefix, Axon without Razer Central

Conditions: `~/.wine-axon-auth`, wine-11.15, fresh `wineboot --init`, installation exactly per
the recipe from `install-under-wine-2.9.1.0.md` (Inno Setup directly, silent mode).
Installation again succeeded without a single prefix tweak: 17:04:33 → 17:08:43, 373 files,
WebView2 was pulled in on its own (892 MB in `Program Files (x86)/Microsoft`).

Launching `RazerAxon.exe` — and here is its entire log over four minutes:

```
17:17:17 |INFO| Program.cs:Main           App start************************************
17:17:17 |INFO| Program.cs:Main           startup args = -wrongaccess,isAdmin:True,userName:user,version:2.9.1.0
17:17:17 |INFO| Program.cs:TryLoginAsync  Start userLogin
17:17:47 |WARN| UserManager.cs:RegisterForUpdateAsync   register update failed.
         System.IO.IOException: Could not establish the connection.
          ---> System.TimeoutException: The operation has timed out.
            at Razer.ServiceClientBase.RazerClientBase.Connect(TimeSpan timeout)
            at Razer.Updater.UpdateClient.RegisterForUpdates(ProductDetails details)
17:18:17 |WARN| UserManager.cs:RegisterForUpdateAsync   Check update failed.   (same stack trace)
```

After that — **silence**. State at 17:21 (four minutes after start):

| What was checked | Result |
|---|---|
| windows (`wmctrl -l`) | not a single Axon window |
| processes | only `RazerAxon.exe -wrongaccess` alive, `msedgewebview2.exe` never started |
| network (`ss -tnp state established`) | **zero established connections** |
| DNS (`resolvectl monitor`) | not a single query from the prefix |

⭐ **Conclusion of the measurement: without Razer Central the application does not even reach the sign-in screen.**
It does not "show a form and refuse entry" — it does not open a window at all, because
`TryLoginAsync` goes into a local IPC that does not exist and never returns. Not a single
byte goes out to the network meanwhile, so the symptom cannot be blamed on the network, blocking or
region.

This is an important refinement of the earlier wording "runs into the absence of Razer Central":
the consequence is not "no updates" but **no UI at all**.

### Measurement 2 — installing Razer Central: sign-in screen **reached**

Razer Central is .NET Framework, so first `winetricks -q -f dotnet48`. A couple of
corrections to earlier notes, both obtained by measurement:

* ⚠️ `winetricks dotnet48` **leaves the prefix on win7** — this is confirmed by the order of
  calls in its own log:

  ```
  line  32:  Executing wine winecfg -v winxp64   ← lowered for dotnet40
  line 177:  Executing wine winecfg -v win10
  line 181:  Executing wine winecfg -v win7      ← THE LAST ONE, stays that way
  ```

  The first revision of this section claimed the opposite ("winetricks restored win10 by itself").
  That was a **misreading of the log**: win10 appeared in the registry not from winetricks but from
  the `winecfg -v win10` line in my own script, which ran right after.
  **Setting the version back to win10 after `dotnet48` is mandatory** — otherwise the Razer server
  returns an empty catalogue (see `install-under-wine-2.9.1.0.md`).
* The `wineserver -w` trap from the installation log was confirmed twice. ⚠️ And here is an important
  addition: **there may be several resident `MicrosoftEdgeUpdate.exe /c` processes in the system — one per
  prefix.** Kill strictly your own, identifying the owner by the process environment:

  ```bash
  for p in $(pgrep -f MicrosoftEdgeUpdate); do
      echo "$p $(tr '\0' '\n' < /proc/$p/environ | grep ^WINEPREFIX=)"
  done
  ```

Next, installing Razer Central itself:

```bash
wine ~/Downloads/axon-installer-2026-08-10/RazerCentral_v7.23.0.1220.exe /silent
```

⭐ **Razer Central 7.23.0.1220 installs under Wine.** Previously the log stopped at the
"Technology Required" window; with the real .NET Framework 4.8 it does not appear.
Evidence:

```
C:\Program Files (x86)\Razer\Razer Services\Razer Central\      294 MB
wine sc query RzActionSvc
    SERVICE_NAME: RzActionSvc
    STATE       : 4  RUNNING
```

Launch Axon again — and the chain goes further:

```
19:45:46 Program.cs:Main          App start
19:45:47 Program.cs:TryLoginAsync Start userLogin
        ↓ (named pipe {CD7C71F0-…} → AccountManager.StartLogin)
19:45:52 WebAppViewModel   WebApp Address: https://id.razer.com/
19:45:54 ViewManager       ShowLoginWindow with center:True
19:45:54 ViewManager       Showing login window finished.
```

That is, **`StartLogin` gets through over IPC, Razer Central brings up its window and loads
`https://id.razer.com/` into it.** The window appears in the window list (`Razer Central`,
1038×640).

### Measurement 3 — why the sign-in window is white at first, and how to fix it

The first time the window is shown: **a solid white rectangle** (the screenshot weighed 468 bytes — a single
fill). The cause is visible in the CEF log
(`C:\ProgramData\Razer\Razer Central\Logs\cef_user.log`):

```
ERROR:network_change_notifier_win.cc(222)  WSALookupServiceBegin failed with: 0
ERROR:angle_platform_impl.cc(43)  ANGLE Display::initialize error 0: Internal Vulkan error (-3)
ERROR:gl_display.cc(917)          eglInitialize SwANGLE failed with error EGL_NOT_INITIALIZED
ERROR:gl_initializer_win.cc(133)  GLDisplayEGL::Initialize failed.
ERROR:viz_main_impl.cc(186)       Exiting GPU process due to errors during initialization
ERROR:gpu_init.cc(523)            Passthrough is not supported, GL is disabled, ANGLE is
ERROR:address_sorter_win.cc(108)  SIO_ADDRESS_LIST_SORT failed 0
```

and in the log of Central itself:

```
DEBUG WebAppManager  Error, CefBrowser.IsWebAppReady: False, message: SET_LANGUAGE
```

Examining the processes gave a precise clue: there were **six CEF subprocesses — and not a single
renderer**:

```
2 × --type=gpu-process
4 × --type=utility
0 × --type=renderer      ← there is physically nobody to draw the page
```

⭐ **The problem is not the GPU but the Chromium sandbox: under Wine the renderer does not start.** Check —
restarting the Razer Central GUI with Chromium flags:

```bash
cd "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Services/Razer Central"
wine "Razer Central.exe" /Client --no-sandbox --disable-gpu \
     --disable-gpu-compositing --disable-features=RendererCodeIntegrity
```

Result — renderers appeared, and **the Razer ID sign-in screen rendered completely**:

```
2 × --type=renderer     ← appeared
```

Screenshot as evidence: `~/Pictures/Screenshots/axon-2910-окно-входа-razer-central.png`
(1038×640). On screen, in Russian (Central set the `Russian` language on its own): the Razer logo,
the **LOG IN**, **SIGN UP**, **CONTINUE AS GUEST** buttons, and sign-in via Apple,
Facebook, Google, Twitch, WeChat, Discord.

⚠️ This is a **different** defect from the known WebView2/DirectComposition one: Razer Central
does not draw with WebView2 but with **CefSharp** (its own Chromium). The earlier README wording
"the Razer Central GUI does not display under Wine due to WPF rendering limitations"
is inaccurate — WPF is only the window frame there, the content is drawn by CEF, and the fix is
`--no-sandbox`.

### Measurement 4 — guest sign-in completes end to end

Pressing **"CONTINUE AS GUEST"** (the only path available without someone else's
credentials):

1. the Razer Central window closed by itself;
2. Axon restarted itself with the `-showui` switch;
3. **six `msedgewebview2.exe` processes** came up;
4. the `RazerAxonHostWindow` and `Razer Axon` windows appeared;
5. the log showed the web layer at work:

```
19:50:58 UserManagerHostObejct.cs:GetUserProfile   UserManagerHostObejct GetUserProfile called
19:51:00 UserManagerHostObejct.cs:PrintLog         UI Log:UI log- showBoarding true!
19:51:01 KinesisClient.cs:SendDataAsync            Send kinesis data: …|Settings|WallpaperPlay|…|Reason:AppStart
```

⭐ **Conclusion: the entire sign-in path works under Wine — IPC, the Razer ID window, issuing the account,
launching the storefront.** Not a single fundamental breakage remains on the authorization route;
all that stood in the way was two Chromium flags.

What remains imperfect: the main Axon window renders only partially (dark background and
the "AXON" logo in the corner) — this is the **already known WebView2/DirectComposition problem**, the
rendering stage, not sign-in. This session shows why the workaround did not work: the
`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` variable **did not reach the browser** — our flags are absent
from the `msedgewebview2.exe` command line:

```
msedgewebview2.exe --embedded-browser-webview=1 --webview-exe-name=RazerAxon.exe
   --user-data-dir=…\UICache\2.9.1.0\EBWebView --noerrdialogs
   --embedded-browser-webview-dpi-awareness=2 --edge-webview-host-pid=928 …
```

So Axon sets `AdditionalBrowserArguments` in code and overrides the environment
variable. Takeaway for the port: **WebView2 flags must be delivered other than through the environment**
(for example, `AppDefaults` + `--no-sandbox` through another mechanism), or by a patch.

### About WebView2 and the black window

The known defect (`DCompositionCreateDevice` → `E_NOTIMPL`, analysed in
`axon_installer_wine_diagnosis_2026_05_31.md`) **could not be checked** in this session:
things never got as far as launching WebView2. The fix (`Version=win7` specifically for
`msedgewebview2.exe` while the rest of the prefix is on win10) was put into the prefix in advance and
confirmed in the registry:

```
[Software\Wine\AppDefaults\msedgewebview2.exe]
"Version"="win7"
```

but it fixes a different stage — rendering an already open window, not sign-in.

---

---

## 3. Guest versus a real Razer ID

| | Guest | Full account |
|---|---|---|
| how to get it | the "Continue as guest" button | "Log in" / social networks |
| identifier | `RZR_<32 hex>`, issued by the server | `RZR_<32 hex>` + `loginId` (email/phone) |
| where it lives | `C:\ProgramData\Razer\Razer Central\Accounts\<RZR_…>\` | same place |
| in the Axon registry | `HKCU\Software\Razer\RazerAxon` → `ShownGuestTC = RZR_…` | — |
| JWT | issued the same way | issued the same way |
| "remember me" | no | Razer Central client certificate (`UI_UpdateCertificate`, `WebApp_DeleteCert`; sign-out reasons `CertDeleted`/`CertError`) |
| in the bundle | `window.SequoiaInfo.is_guest = true` | `false` |
| what is disabled | favourites, playlists, publishing works, voting, wallet | nothing |

Guest sign-in measurement (2026-08-12): the server issued `RZR_02807e25…f393`, the directory
`Accounts/RZR_02807e25…f393/` was created, and `ShownGuestTC` with the same identifier appeared
in `HKCU\Software\Razer\RazerAxon`.

⚠️ **There is no plaintext token on disk.** The account directory contains only
`Notifications\Cache.xml`, `FeatureCache.bin` and `AxonLaunchDetails.bin` — Razer Central keeps
the JWT itself in the service's memory and hands it out over IPC (`GetCurrentUser`, command 3).
This is exactly the case `razer-token-inject.py` was made for in the port: a token can be inserted
from outside only with the `WebApp_SetLoginSuccessFromWeb` (131094) command, not
via a file.

The storefront session after sign-in is visible in the WebView2 cookies
(`UICache\2.9.1.0\EBWebView\Default\Network\Cookies`):

```
domain axon-api.razer.com
cookie sequoia_RZR_02807e25…f393_profiling
```

that is, the cookie is named after the account identifier, and requests additionally carry the
`Authorization` header from the `/v1/login` response (see section 1.3).

---

## 4. Internet dependency

### 4.1. What is downloaded at install time

| What | From where | Size | Required? |
|---|---|---|---|
| `RazerAxonSetup_2.9.1.0.exe` itself | `manifest-assets.razersynapse.com` (link from the manifest) | 63.7 MB | download once, then it is a file |
| the link to it | `discovery3.razerapi.com` → `manifest3.razerapi.com` | bytes | only to learn the URL |
| **WebView2 Evergreen** | `MicrosoftEdgeWebview2Setup.exe` inside setup → Microsoft servers | ~190 MB downloaded, **892 MB** on disk | **yes, for the UI** |
| `RazerCentral_v7.23.0.1220.exe` | `manifest-assets.razersynapse.com` | 121.8 MB | **yes, for sign-in** |

All of Axon's own content (165 MB, 373 files) is inside setup — the only thing downloaded
from the network during installation is WebView2.

**Offline installation measurement.** A separate prefix `~/.wine-axon-offline`, the whole installation
inside an isolated network namespace (only `lo`):

```bash
unshare -rn bash -c 'ip link set lo up; wine RazerAxonSetup_2.9.1.0.exe /SP- /VERYSILENT …'
```

Result:

```
setup rc=0                                                    ← the installer is happy
Program Files (x86)/Razer          165 MB                     ← Axon fully laid out
Program Files (x86)/Razer/Razer Axon/RazerAxon.exe            ← in place
Program Files (x86)/Microsoft/EdgeWebView                     ← MISSING
```

⭐ **Offline, the installer finishes "successfully" and says nothing about WebView2 not being installed.**
It takes longer than usual (5.5 min versus 4) — the extra time goes to Edge Update trying
to reach Microsoft. This is exactly where the earlier symptom "it installed, but the window is empty" came from.

### 4.2. What is downloaded on first launch and on every launch

Live measurement (connections of the `~/.wine-axon-auth` prefix, selected by the PID of its
`wineserver`; names recovered from certificates and direct name resolution):

| Host | Who connects | Why | Required |
|---|---|---|---|
| `id.razer.com` | Razer Central (CEF) | sign-in page | **yes, for sign-in** |
| `manifest3.razerapi.com` | RazerCentralService | product catalogue/updates | no |
| Razer's Akamai edge (`85.182.250.18/43/82`, cert `a248.e.akamai.net`) | RazerCentralService | static content/notifications | no |
| CloudFront (`3.174.46.109`) | Razer Central.exe | GUI resources | no |
| `axon-api.razer.com` | WebView2 | **the storefront itself + the whole API** | **yes** |
| `axon-assets-cdn.razerzone.com` | WebView2 | scripts, styles, thumbnails | **yes** |
| `oauth2.razer.com` | RazerAxon.UserManager | `code_sso` for profile web pages | no |
| `razerid.razer.com`, `gold.razer.com` | same | profile/zVault via SSO code | no |
| Kinesis / `bespoke-analytics.razerapi.com` | Axon | telemetry (`KinesisClient.SendDataAsync`) | no |
| `ced.sascdn.com`, ~20 `*.id5-sync.com` hosts | WebView2 | **advertising and tracking** | no |
| Google (`2a00:1450:…`), Microsoft (`2620:1ec:33::11`) | CEF/WebView2 | connectivity checks, Edge telemetry | no |

⚠️ The advertising loop deserves a separate note: `ced.sascdn.com` (Smart AdServer)
pulls in the **`id5-sync.com` identity network** — more than twenty of its hosts
(`lb.eu-1-id5-sync.com`, `d0…d7.eu-3-id5-sync.com`
and so on) settled in the WebView2 network state. For the port this is a pure negative with no reason to reproduce it.

⚠️ Another constant network consumer is the **resident `MicrosoftEdgeUpdate.exe /c`**.
It stays in the prefix forever after installation, restarts itself and contacts
Microsoft with its own `/ping` and `/handoff` regardless of whether Axon is running.

### 4.3. What Razer put in the cache in advance

⭐ A finding of this session: **the installer ships a ready-made Service Worker cache**, and Razer Central a
ready-made `WebAppCache`. From the Inno installation log:

```
Dest filename: C:\users\…\AppData\Local\Razer\RazerAxon\UICache\2.9.1.0\
               EBWebView\Default\Service Worker\CacheStorage\2453e6f6…\index.txt
```

Inside `index.txt` are the cache name and its origin:

```
cache-axon-static      https://axon-api.razer.com/
```

The files are dated 27.07.2026 (the build date), so this is a **pre-populated offline copy
of the storefront shell**, not the result of user activity. Similarly, Razer Central at
startup copies `C:\ProgramData\Razer\Razer Central\WebAppCache` →
`…\AppData\Local\Razer\Razer Central\WebAppCache`.

The intent is clear: the first launch should not look empty while the network loads. But
**this does not give full offline operation** — the wallpaper catalogue, thumbnails and sign-in are still
network-bound.

### 4.4. Can it work offline — the short answer

| Scenario | Result |
|---|---|
| installing Axon without network | **succeeds**, but WebView2 is not installed → there will be no UI |
| turnkey installation without network | no: WebView2 (~190 MB) and Razer Central (121 MB) are needed |
| first sign-in without network | **impossible**: the sign-in window is `id.razer.com` |
| relaunch without network after guest sign-in | **runs into the same sign-in window** (measurement below) |
| already downloaded wallpapers | play locally (the player does not need the network) |

**Measurement of launching without network on a fully configured prefix.** The same
`~/.wine-axon-auth` where guest sign-in had already succeeded; the prefix was shut down and restarted
entirely inside an isolated network namespace:

```bash
wineserver -k
unshare -rn bash -c 'ip link set lo up; wine RazerAxon.exe'
```

After 100 seconds:

```
processes: RazerAxon.exe -wrongaccess
           RazerCentralService.exe
           Razer Central.exe /Client + 3 × CefSharp.BrowserSubprocess.exe
           msedgewebview2.exe — NOT A SINGLE ONE
windows:   "Razer Central"  (a new sign-in window)
```

⭐ **The guest session did not survive the restart**: Razer Central brought up the sign-in window again.
And the window itself is empty without network — the Razer frame is drawn (that is WPF), the content does not load
because `id.razer.com` is unreachable. Screenshot:
`~/Pictures/Screenshots/axon-2910-вход-без-сети.png`.

Practical takeaway: **the pre-populated cache saves only the storefront shell, not
sign-in.** Until Razer Central hands over an account, Axon does not even launch WebView2 — that
is, offline the application is useless on any launch, not just the first one.

The minimal list of domains without which **nothing works at all**:

```
axon-api.razer.com               storefront + API + API sign-in
axon-assets-cdn.razerzone.com    storefront static content
id.razer.com                     Razer ID sign-in page
+ at install time: Microsoft servers for WebView2
+ when obtaining the installer: discovery3/manifest3.razerapi.com,
                                manifest-assets.razersynapse.com
```

Everything else (ads, telemetry, updates, zVault) can be cut without losing the
core function.

---

## 5. What is needed from a human

The measurements have been taken as far as possible without someone else's account:

* **guest sign-in completed end to end and works** — this was enough to prove that
  the entire route is sound under Wine: IPC → Razer ID window → account issued → storefront launched;
* **real sign-in with a Razer ID was not tested** — the person doing the work has no Razer
  account, and making one up or registering a new one is not allowed.

To close the remainder, exactly one action is needed from Wehrwolfmann:

1. launch the application using the recipe below and wait for the Razer ID window;
2. press **"LOG IN"** and sign in with his Razer account (the password is entered in Razer's
   own window, is not passed anywhere and does not end up in any log);
3. report what happened: whether the storefront opened with his name and avatar.

```bash
export WINEPREFIX="$HOME/.wine-axon-auth"

# 1. Razer Central GUI — must use --no-sandbox, otherwise the window is white
cd "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Services/Razer Central"
wine "Razer Central.exe" /Client --no-sandbox --disable-gpu &

# 2. the application itself
cd "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"
wine RazerAxon.exe
```

What exactly a live sign-in will give, which cannot be obtained as a guest:

| Question | Answered only by a real sign-in |
|---|---|
| does two-factor verification (`OtpRequired` in `LoginResult`) pass under Wine | yes |
| does "stay signed in" work (Razer Central client certificate) | yes |
| does the session survive a prefix restart | yes |
| does `oauth2.razer.com/services/code_sso` return a code and does the profile open | yes |
| does sign-in via social networks work (`ConnectToAccount`, Google/Twitch/Discord) | yes |
| are favourites, playlists and purchases visible | yes |

⛔ There is no need to share the password or token in correspondence: all that is required is the fact
"signed in / did not sign in" and, if it did not, lines from
`C:\ProgramData\Razer\Razer Central\Logs\Razer Central_<user>.log`.

---

## 6. Wine defects found on the sign-in route

Fixes for games and Windows programs are submitted to **Wine**, not to Proton. Listed here is only
what has been confirmed by measurement on this route (defects of the installation stage are in
`install-under-wine-2.9.1.0.md`).

### A1. The Chromium renderer does not start without `--no-sandbox` — **the main finding of this session**

Symptom: CefSharp brings up `gpu-process` and `utility`, but **not a single
`--type=renderer`**; the window stays white, and the application considers the page not loaded
(`CefBrowser.IsWebAppReady: False`). With `--no-sandbox` the renderers appear and the page
renders completely.

The value for upstream is high: this hits **any CEF/Electron application under
Wine**, not just Razer. Before submitting, it needs to be pinned down what exactly trips up
launching the child process in the sandbox (a run with `WINEDEBUG=+process,+seh` and capturing the
renderer's exit code) — for now only the fact is recorded.

### A2. `WSALookupServiceBegin` does not work — Chromium does not see network changes

```
ERROR:network_change_notifier_win.cc(222)  WSALookupServiceBegin failed with: 0
```

Repeats on every CEF start. Chromium uses this to track
connections; under Wine network notifications do not arrive. It did not affect sign-in, but it is
a genuine gap in `ws2_32`.

### A3. `SIO_ADDRESS_LIST_SORT` is not supported

```
ERROR:address_sorter_win.cc(108)  SIO_ADDRESS_LIST_SORT failed 0
```

Chromium sorts addresses (RFC 3484) through this ioctl; under Wine it does not work,
and the IPv4/IPv6 order remains arbitrary. Low priority, but the fix is trivial.

### A4. ANGLE does not initialize even in software mode

```
ANGLE Display::initialize error 0: Internal Vulkan error (-3)
eglInitialize SwANGLE failed with error EGL_NOT_INITIALIZED
GLDisplayEGL::Initialize failed → Exiting GPU process
```

Not only the hardware path fails, but also the software **SwANGLE** one. Related to the known
WebView2 problem with DirectComposition, but shows up earlier and in a different place. It does not
affect sign-in (after `--no-sandbox` the page renders even without a GPU).

### A5. Not a Wine defect: `AdditionalBrowserArguments` overrides the environment

The `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` variable **does not reach** the browser — Axon
sets the WebView2 arguments in code. This is a property of the application, not of Wine; for the port
it means WebView2 flags have to be delivered some other way.
