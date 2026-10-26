# Razer Axon 2.9.1.0 under Wine — session log and install recipe

Work by: Wehrwolfmann. Started 2026-08-11 on a **completely wiped system**
(the previous prefix, installed files, settings, services and shortcuts were removed).

Continues the May documents `axon_installer_wine_diagnosis_2026_05_31.md`
(diagnosis of the 2.6.2.0 installer) and the August static analysis
`axon_installer_and_app_2_9_1_0_2026_08_10.md`.

Wine: system **wine-11.15**. Test prefix: `~/.local/share/openaxon-test/prefix`
(deliberately in the home directory: `/tmp` is RAM/tmpfs, and the prefix and extraction do not fit there).

➡️ **What happens AFTER installation** — signing in to the Razer account and an analysis of
what exactly is pulled from the network — has been moved to a separate log,
[`auth-and-network.md`](auth-and-network.md). Three conclusions from it matter
for this document:

* the sign-in window is drawn **not by Axon but by Razer Central** (CefSharp), and under Wine it is white
  until `--no-sandbox` is added;
* `winetricks dotnet48` leaves the prefix **on win7** (its last call is
  `winecfg -v win7`), so you have to switch back to win10 yourself;
* resident `MicrosoftEdgeUpdate.exe /c` processes exist **one per prefix**,
  and you must kill strictly your own (the owner is determined via `/proc/<pid>/environ`).

Installer sources (downloaded 2026-08-10):

```
~/Downloads/axon-installer-2026-08-10/RazerAxonSetup_2.9.1.0.exe   63 660 360 B, Inno Setup 6.7
~/Downloads/axon-installer-2026-08-10/RazerAxonInstaller.exe       14 923 464 B, online wrapper
```

---

## Problem statement: two different "installers", do not confuse them

| What | File | Technology | Needed for installation? |
|---|---|---|---|
| Online wrapper | `RazerAxonInstaller.exe` | native stub + .NET Framework 4.8 engine + WPF UI | no, if the setup is already downloaded |
| The application setup itself | `RazerAxonSetup_2.9.1.0.exe` | Inno Setup 6.7 | **yes, this is what installs Axon** |

The May conclusion: the wrapper's WPF UI crashes under Wine on the license screen
(`TextBlockTextPlugin` / `0x80131623`), so the working path is to **take the Inno setup and
run it directly in silent mode**. Razer publishes the parameters itself, in the manifest:

```
/SP- /VERYSILENT /DIR="%programfiles(x86)%\Razer\Razer Axon" /SUPRESSMSGBOXES /NORESTART
```

---

## Session log

Format: what I changed → what happened → evidence (log line/file).

### Session 0 — starting state

The system is wiped. The symptom the user reported on the previous (already removed)
prefix: `rundll32.exe — This application could not be started.`

**On a clean prefix this symptom never reproduced once** — neither when installing Axon,
nor when launching the application, nor when installing Razer Central. The most plausible
explanation (this is reasoning from evidence, not a measurement): the previous prefix was left **with
an unfinished .NET installation**. The evidence: the winetricks log shows that before installing
`dotnet40` it **deletes both copies of `mscoree.dll`**:

```
Executing rm -f …/prefix/dosdevices/c:/windows/syswow64/mscoree.dll
Executing rm -f …/prefix/dosdevices/c:/windows/system32/mscoree.dll
Executing w_do_call dotnet40
```

If the process is interrupted at this point (and there is plenty to interrupt it — see session 8 about
the eternal `wineserver -w` deadlock), the prefix is left **without wine-mono and without real .NET
at the same time**. In such a prefix any launch of managed code — including via
`rundll32` — fails with "This application could not be started", and the Windows version stays
whatever winetricks set at an intermediate step. This explains both the `rundll32` error
and the "Windows 7" at once.

Practical conclusion for the recipe: **in this prefix, either run `winetricks dotnet48` to
completion or do not start it at all**; interrupted halfway, it leaves a broken
prefix that is easier to recreate than to repair.

### Session 1 — which Windows version a FRESH wine-11.15 prefix has

What I did:

```bash
WINEPREFIX=~/.local/share/openaxon-test/prefix WINEARCH=win64 wineboot --init
WINEPREFIX=~/.local/share/openaxon-test/prefix wine reg query \
    'HKLM\Software\Microsoft\Windows NT\CurrentVersion' /v ProductName
```

Result — **a fresh prefix is already Windows 10**, not 7:

```
CurrentBuild        19045
CurrentVersion      6.3
ProductName         Windows 10 Pro
CurrentMajorVersionNumber  0x0000000a   (=10)
EditionId           Professional
```

⭐ **Conclusion: the premise of the hypothesis is wrong for wine-11.15** — the default has not been Windows 7
for a long time (Wine switched to win10 as the default back in 7.0). There is no need to set `winecfg` to 10:
it already is 10. Below I work out where the Windows 7 comes from then (see the section "Hypothesis
about the Windows version").

### Session 2 — Inno setup 2.9.1.0 directly, silent mode, fresh prefix without a single tweak

What I did (exactly the parameters Razer publishes in its own manifest):

```bash
WINEPREFIX=~/.local/share/openaxon-test/prefix \
wine ~/Downloads/axon-installer-2026-08-10/RazerAxonSetup_2.9.1.0.exe \
     /SP- /VERYSILENT '/DIR=C:\Program Files (x86)\Razer\Razer Axon' \
     /SUPRESSMSGBOXES /NORESTART
```

Result — **it worked right away**: the extractor started
`…\Temp\is-*.tmp\RazerAxonSetup_2.9.1.0.tmp /SL5=$2004E,62315557,1126912,…`
and began filling `drive_c/Program Files (x86)/Razer/Razer Axon/`.
Neither `winetricks`, nor `dotnet48`, nor changing the Windows version was needed for this step.

Extraction takes ~1.5 minutes (noticeably slower under `+seh` tracing), it lays down
**≈165 MB / 430 files**, after which Inno moves on to the "post-install" step.

### Session 3 — what Inno does AFTER extraction: pulls WebView2 from the network

⭐ This is the very "something was going on with the internet". In 2.9.1.0 Razer **embedded an online
WebView2 downloader in the setup** and runs it itself (in May the runtime was installed by hand
as a separate file):

```
C:\Program Files (x86)\Razer\Razer Axon\MicrosoftEdgeWebview2Setup.exe /silent /install
  └─ C:\Program Files (x86)\Microsoft\Temp\EU*.tmp\MicrosoftEdgeUpdate.exe /silent /install
        appguid={F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}
        &appname=Microsoft%20Edge%20Webview2%20Runtime&needsadmin=prefers
```

So the Axon setup is **not self-contained**: it is a thin wrapper around Microsoft Edge Update,
which downloads the Evergreen WebView2 runtime (~190 MB) from Microsoft's servers. Without internet
(or with `msedge.api.cdp.microsoft.com` / `msedge.b.tlu.dl.delivery.mp.microsoft.com` blocked)
this step silently fails — and the application then draws an empty window, because the whole
Axon UI is WebView2.

Wine side noise at this step (not installation errors, harmless in itself):

```
fixme:seh:WerRegisterCustomMetadata (L"EdgeUpdateDllVersion", L"1.3.167.21") stub
err:combase:RoGetActivationFactory Failed to find library for
    L"Windows.System.Diagnostics.Telemetry.PlatformTelemetryClient"
err:ole:com_get_class_object no class object {cecddd22-2e72-4832-9606-a9b0e5e344b2} …
err:ole:CoSetProxyBlanket -- failed with 0x80004002
```

### Session 4 — installation result

The WebView2 download succeeded: `C:\Program Files (x86)\Microsoft\EdgeWebView` — **670 MB**.
About 4 minutes after the start, the installer processes exited on their own.

**The installation succeeded.** Evidence:

```
C:\Program Files (x86)\Razer\Razer Axon\   165 MB, 430 files
    RazerAxon.exe            457 416 B   PE32+ x86-64
    RazerAxon.Player.exe     897 224 B
    RazerAxon.Reporter.exe   457 928 B
    unins000.exe           4 640 968 B   Inno uninstaller

HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\Razer Axon_is1
    DisplayName     = "Razer Axon"
    DisplayVersion  = "2.9.1.0"
    Inno Setup: App Path = "C:\Program Files (x86)\Razer\Razer Axon"
```

⭐ All of this is on a **bare fresh wine-11.15 prefix without a single tweak**: no `winetricks`,
no `dotnet48`, no `winecfg`, no manual WebView2 installation.

### Session 5 — control run: the same setup under Windows 7

To test the user's hypothesis by measurement rather than reasoning, I set up a **second
prefix** and forced Windows 7 in it:

```bash
export WINEPREFIX="$HOME/.local/share/openaxon-test/prefix-win7"
WINEARCH=win64 wineboot --init
winecfg -v win7          # → ProductName = "Microsoft Windows 7"
wine …/RazerAxonSetup_2.9.1.0.exe /SP- /VERYSILENT '/DIR=…' /SUPRESSMSGBOXES /NORESTART
```

Result: **the installation did not happen.** The `Program Files (x86)\Razer` folder never
appeared (under win10 it showed up at second 16); instead the installer raised a
modal window with the classic Inno Setup error:

> **This program does not support the version of Windows your computer is running.**

Screenshot as evidence: `~/Pictures/Screenshots/axon-2910-установщик-под-win7-ошибка.png`
(window `Error`, 299×82). After clicking "OK" the installer simply exits without
installing anything.

⭐ **This is exactly the symptom the user observed** ("under Windows 7 the installer
silently does not start"), and here is why it looks "silent":

* it is launched with `/VERYSILENT`, so there is no installer window at all — the only thing that
  appears on screen is a tiny untitled `Error` window of 299×82, which is easy
  to miss or mistake for a system one;
* ⚠️ **Razer made a typo in its own parameters**: the manifest says
  `/SUPRESSMSGBOXES`, whereas the real Inno switch is `/SUPPRESSMSGBOXES` (two `p`s).
  Inno ignores the misspelled switch, so message boxes are **not suppressed**. In a
  headless run (no visible desktop) the installer therefore does not "crash"
  but **hangs forever on an invisible modal window** — outwardly indistinguishable from "silently
  doing nothing".

Conclusion of the measurement: **the Windows version decides the outcome of the installation, but the check is done by the Inno setup itself
(the `MinVersion` field in its `[Setup]`), not by Razer's server.** This is a separate, second
tie to the Windows version — in May only the server-side one was known (an empty catalog with
`osver=7`).

### Session 6 — launching the installed application

```bash
cd "$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon" && wine RazerAxon.exe
```

The application **starts** and gets as far as the sign-in attempt:

```
Program.cs:Main   App start************************************
Program.cs:Main   startup args = -wrongaccess,isAdmin:True,userName:user,version:2.9.1.0
Program.cs:TryLoginAsync   Start userLogin
```

Then it runs into the absence of Razer Central:

```
UserManager.cs:RegisterForUpdateAsync   Check update failed.
System.IO.IOException: Could not establish the connection.
 ---> System.TimeoutException: The operation has timed out.
   at Razer.ServiceClientBase.RazerClientBase.Connect(TimeSpan timeout)
   at Razer.Updater.UpdateClient.RegisterForUpdates(ProductDetails details)
```

This is **expected and not an installation defect**: Razer's manifest puts the mandatory
module `Natasha` = **Razer Central 7.23.0.1220** before Axon (`installation_priority`
300 versus 32765 for Axon itself), while the recipe above installs only Axon. It is the
Razer Central service that `RazerClientBase.Connect` is knocking on.

Incidentally, `startup args = -wrongaccess`: Axon restarts itself with this switch
because Wine reports `isAdmin:True`. It does not affect how the application works.

### Session 7 — the second manifest module: Razer Central 7.23.0.1220

The link is taken from the same manifest (checked today, 2026-08-11 — both the hash `N82uNskI`
and both links have been alive since the August analysis):

```
Natasha 7.23.0.1220
  url    https://manifest-assets.razersynapse.com/1778658202qKgcx3XSRazerCentral_v7.23.0.1220.exe
  md5    b015e30d20011da3fada698b62741284    (downloaded file matched)
  size   121 821 664
  flags  /silent
```

Running `wine RazerCentral_v7.23.0.1220.exe /silent` — **the `/silent` switch is not honoured**:
a `RazerCentral Setup` window comes up, followed by a modal `Technology Required`:

> **RazerCentral has detected that your Microsoft .NET run-time files are out of date.
> Click OK to install this technology now or Cancel to abort the installation.**

Screenshot: `~/Pictures/Screenshots/axon-2910-razer-central-требует-dotnet.png`.

Cause: Razer Central is a .NET Framework application, and a fresh prefix has **wine-mono**,
which does not pass Razer's check. So `winetricks dotnet48` from the May recipe
**is needed after all — but not for Axon, for Razer Central.** This refines the May picture:
it used to be thought that .NET was needed by the online wrapper; in fact both of Razer's .NET components
require it, while the Axon Inno setup itself does not need it at all.

### Session 8 — `winetricks -q dotnet48` and why it "hangs"

⭐ **Found the real cause of the deadlock that the May document blamed on a "known
winetricks bug".** The bug is not in winetricks. The point is that the WebView2 installation (session 3)
leaves a **resident process** in the prefix:

```
C:\Program Files (x86)\Microsoft\EdgeUpdate\MicrosoftEdgeUpdate.exe /c
```

It does not exit on its own and lives in the prefix indefinitely (in the measurement — 1010 s, and it would have kept going).
And winetricks runs `wineserver -w` at every step, which by definition waits for
**all** processes of the prefix to exit:

```
warning: Running /usr/bin/wineserver -w. This will hang until all wine processes
in prefix=… terminate
```

Result: any winetricks verb run in the prefix AFTER installing Axon locks up dead.
Killing exactly this process (by the PID of your own instance, not by name) immediately unblocks
winetricks, and the .NET installation proceeds.

The step order that removes the problem entirely: **install `dotnet48` BEFORE Axon**, not after.

A second observation from the log — how winetricks handles the Windows version:

```
Executing w_do_call dotnet40
win10                          ← remembered the prefix's current version
Executing w_do_call winxp
Executing wine winecfg -v winxp64   ← temporarily lowered to XP for dotnet40
```

So during the installation the prefix version is lowered (winxp64 → then win7), and if
the process is interrupted or winetricks does not restore the value, the prefix is left with a foreign
Windows version. This is where the very "Windows 7 by default" from the hypothesis comes from —
it is left behind by winetricks, not by `wineboot`.

### Session 9 — no window at all: Razer Central is required for ANY UI

Date: 2026-08-12. Measurement prefix: `~/.local/share/openaxon-test/prefix` (Axon 2.9.1.0
already installed in session 2).

First, a methodological mistake in session 6 was corrected: there Axon was launched as
`wine RazerAxon.exe`, **without the `-showui` switch**. The project's own launcher
(`razer-axon.sh`) launches it exactly with this switch — without it the application is not obliged
to show a window. The repeat measurement was done "by the book":

* applied the per-app override `HKCU\Software\Wine\AppDefaults\msedgewebview2.exe → Version=win7`
  with `win10` for the rest of the prefix (checked in the registry: the value is there);
* set `HardwareAccelerationModeEnabled=0` in three Edge policy branches;
* set `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`, `LIBGL_ALWAYS_SOFTWARE=1`,
  `GALLIUM_DRIVER=llvmpipe`;
* launch: `wine RazerAxon.exe -showui`.

Result after 55 s: the processes are alive (`RazerAxon.exe -wrongaccess` and
`RazerAxon.exe -wrongaccess -showui`), **there is not a single window** — neither visible nor
hidden. Checked in three independent ways:

```
wmctrl -l                                   → only Steam
xdotool search --all --onlyvisible          → no window with Razer/Axon
xwininfo -root -tree | grep -i 'razer|axon' → empty
```

The application log stops exactly at sign-in:

```
Program.cs:TryLoginAsync   Start userLogin        ← and nothing after that
UserManager.cs:RegisterForUpdateAsync   register update failed  (Razer.Updater.UpdateClient)
UserManager.cs:RegisterForUpdateAsync   Check update failed
```

⭐ **Conclusion of the measurement (answer to "is Razer Central needed"): yes, and not for signing in
to the account but for showing any window at all.** `RazerAxon.exe` does not create a window **before**
`TryLoginAsync` completes, and that one runs into Razer Central's named pipe and
hangs on it. So an "empty window" is not the symptom we have: we have
**no window at all**, and WebView2 has nothing to do with it — things simply never get that far.

This also dictates the order of further work: first make something answer on
the Razer Central pipe, and only then does it make sense to test the WebView2/DirectComposition path.

### Session 10 — Razer Central 7.23.0.1220 installs under Wine, and `/silent` works

Date: 2026-08-12. Prefix: `~/.wine-axon` (created from scratch, `WINEARCH=win64`).

Session 7 concluded that "`/silent` is not honoured" — that conclusion turned out to be **wrong about the cause**.
`/silent` is honoured perfectly well; in session 7 it was overridden by the modal window
`Technology Required`, which the installer raises **before** parsing its switches when
it does not find a real .NET Framework. Remove the cause — and the symptom goes away too.

The order verified live:

```bash
export WINEPREFIX="$HOME/.wine-axon"
WINEARCH=win64 wineboot --init          # fresh prefix: win10, build 19045
winetricks -q dotnet48                  # ~14 min
wine winecfg -v win10                   # MANDATORY after dotnet48
wine RazerCentral_v7.23.0.1220.exe /silent
```

The dotnet48 side effect predicted in session 8 is now confirmed by a number:

```
before winecfg -v win10:  "CurrentBuild"="7601"    ← left by dotnet48
after                     "CurrentBuild"="19045"
```

⭐ The same conclusion is confirmed by a **second, independent source — the source code of
winetricks itself** (`/usr/bin/winetricks`, function `load_dotnet48`):

```sh
w_call remove_mono internal
w_call dotnet40
w_set_winver win7          ← lowers the version and NEVER TOUCHES IT AGAIN
…
w_override_dlls native mscoree
w_try touch "${W_WINDIR_UNIX}/dotnet48.installed.workaround"
```

winetricks does have a restore mechanism — the function `w_restore_winver`, called by a couple of dozen
other verbs — but `load_dotnet48` **does not call it**. So `winecfg -v win10`
after `dotnet48` is mandatory: this follows both from the registry measurement and from the code.

Result of the Central installation — **success, completely silent, not a single window**:

```
C:\Program Files (x86)\Razer\Razer Services\Razer Central\   294 MB
    RazerCentralService.exe
    Razer Central.exe
    Razer Updater.exe
    CefSharp.BrowserSubprocess.exe
    ndp48-web.exe                 (the very .NET web installer it called in session 7)
    locales: de-DE en-US es-ES fr-FR ja-JP ko-KR pt-BR ru-RU zh-CN zh-CHT
```

⭐ **The service registers ITSELF, and its name differs from the one in the project README.**
The README suggests `sc create RazerCentralService …` — you should not do that, and the service
will not be found under that name. The installer creates it itself:

```
[System\ControlSet001\Services\RzActionSvc]
    "DisplayName" = "Razer Central Service"
    "ImagePath"   = "C:\Program Files (x86)\Razer\Razer Services\Razer Central\RazerCentralService.exe"
    "Start"       = dword:00000002      (auto start)
    "Type"        = dword:00000010      (own process)
```

Starting and checking:

```
wine sc start RzActionSvc
wine sc query RzActionSvc
    SERVICE_NAME: RzActionSvc
    STATE : 4  RUNNING
```

⚠️ **A practical trap for the script and the launcher:** the service lives exactly as long as
the prefix's `wineserver` lives. After a few seconds of inactivity wineserver shuts down and
takes `RazerCentralService.exe` with it — verified: right after `sc query … RUNNING`
not a single Wine process was left in the prefix. So the service has to be started
**in the same session** in which Axon is launched, not "once at install time".

### Session 11 — Axon and WebView2 in the same prefix, renderer registry fix

Date: 2026-08-12, prefix `~/.wine-axon` (after session 10, i.e. on top of .NET 4.8 + Central).

Axon is installed with the same silent call as in session 2, but with the **corrected**
message-box suppression switch (`/SUPPRESSMSGBOXES`, two `p`s — there is no reason to repeat Razer's typo):

```bash
wine RazerAxonSetup_2.9.1.0.exe /SP- /VERYSILENT \
     '/DIR=C:\Program Files (x86)\Razer\Razer Axon' /SUPPRESSMSGBOXES /NORESTART
```

Measured result:

```
C:\Program Files (x86)\Razer\Razer Axon\        165 MB
C:\Program Files (x86)\Microsoft\EdgeWebView\   670 MB
    Application\151.0.4129.78\                  ← WebView2 Evergreen version as of 2026-08-12
```

Then the renderer registry fix was applied (the very workaround from Wine bug 58921, see
`wine-defect-candidates.md`): version **win7 only for `msedgewebview2.exe`**, while
the prefix and `RazerAxon.exe` stay win10. The contents are exactly:

```
[HKEY_LOCAL_MACHINE\Software\Policies\Microsoft\Edge]           "HardwareAccelerationModeEnabled"=dword:00000000
[HKEY_LOCAL_MACHINE\Software\Policies\Microsoft\Edge\WebView2]  "HardwareAccelerationModeEnabled"=dword:00000000
[HKEY_CURRENT_USER\Software\Policies\Microsoft\Edge]            "HardwareAccelerationModeEnabled"=dword:00000000
[HKEY_CURRENT_USER\Software\Wine\AppDefaults\msedgewebview2.exe] "Version"="win7"
[HKEY_CURRENT_USER\Environment]                                  "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"=…
```

Verified by reading the prefix registry, not "taken on trust":

```
user.reg:736  [Software\\Wine\\AppDefaults\\msedgewebview2.exe]  → "Version"="win7"
user.reg:246  "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"="--no-sandbox --disable-gpu …"
system.reg    "HardwareAccelerationModeEnabled"=dword:00000000   ×2
```

Browser flags set by the fix:

```
--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer
--disable-gpu-sandbox --disable-features=RendererCodeIntegrity --disable-crash-reporter
--disable-renderer-backgrounding --disable-background-timer-throttling
```

⚠️ The session 8 trap reproduced exactly: after installing Axon, **four** resident
`MicrosoftEdgeUpdate.exe /c` processes were left hanging in the prefix. `winetricks` will no longer
work in such a prefix, so in the recipe `dotnet48` is the first step, and the residents are killed
at the end — by the PIDs of processes of your own prefix (checked against `/proc/PID/environ`), not by name.

### Session 12 — the Razer Central window with full content

Date: 2026-08-12, prefix `~/.wine-axon`. The launch was done in a single session so that the service
would not die together with wineserver (see the trap in session 10):

```bash
wineserver -p                 # keep the session alive
wine sc start RzActionSvc     # → STATE : 4  RUNNING
wine RazerAxon.exe -showui
```

⭐ **For the first time a window appeared** — more precisely, two windows at once titled `Razer Central`
(1038×640). So the service, once up, launches its own UI (NAC) by itself, and it is
that UI that handles sign-in, not Axon.

The first snapshot of the content was **empty**: the WPF frame (RAZER logo, gear,
minimize/maximize/close) is drawn, but the page area is a flat dark
rectangle, 105 unique colours over 1038×640.

The cause can be seen in CEF's own log, which Razer Central keeps itself:
`C:\ProgramData\Razer\Razer Central\Logs\cef_user.log`

```
ERROR:angle_platform_impl.cc(43)  ANGLE Display::initialize error 0:
    Internal Vulkan error (-3) … RendererVk.cpp, initialize:1457
ERROR:gl_display.cc(917)  eglInitialize SwANGLE failed with error EGL_NOT_INITIALIZED
ERROR:gl_initializer_win.cc(133)  GLDisplayEGL::Initialize failed.
ERROR:viz_main_impl.cc(186)  Exiting GPU process due to errors during initialization
ERROR:gpu_init.cc(523)  Passthrough is not supported, GL is disabled, ANGLE is
```

⭐ An important refinement of the project's picture: **Razer Central has a completely different browser engine
than Axon.** Axon uses WebView2 (`msedgewebview2.exe`), Central uses CefSharp
(`CefSharp.BrowserSubprocess.exe`). So the per-app override made for WebView2
does not apply to Central, and what fails there is not `DCompositionCreateDevice` but
ANGLE initialization on top of Vulkan (SwANGLE). The override was added for the second engine as well:

```
[HKEY_CURRENT_USER\Software\Wine\AppDefaults\CefSharp.BrowserSubprocess.exe]
"Version"="win7"                      (verified: user.reg:739)
```

After restarting the UI (`Razer Central.exe /Client`) the window **rendered
completely**: 93 645 unique colours instead of 105 — the background picture, the sign-in panel with
the Razer logo, the buttons `LOG IN` / `SIGN UP` / `CONTINUE AS GUEST` (shown in Russian in this session) and six
icons for external sign-in (Apple, Facebook, Google, Twitch, WeChat, Discord). The UI
came up **in Russian**, i.e. the prefix locale was picked up correctly.

Screenshot as evidence: `~/Pictures/Screenshots/axon-central-вход-работает.png`.
The empty state is kept for comparison: `~/Pictures/Screenshots/axon-central-окно-логина.png`.

⚠️ An honest caveat about causality: between the empty and the full snapshot **two** things changed
at once — the `CefSharp.BrowserSubprocess.exe → win7` override was added and the UI was
restarted (i.e. the page got more time to load). No separate measurement of
"override only" / "restart only" was made, so the contribution of each is not separated.
The CEF GPU process crashes in both cases — after that Chromium honestly falls back to
software rendering, and that, evidently, is enough.

### Session 13 — ⭐ a working Axon window with the wallpaper catalog

Date: 2026-08-12, prefix `~/.wine-axon`. A direct continuation of session 12.

In the Razer Central window the **`CONTINUE AS GUEST`** button was pressed (the click was sent
with `xdotool` to the button's coordinates inside the window). The reaction is instant — **windows
of Axon itself** appeared, of which there had been none before:

```
0x07600001  RazerAxonHostWindow
0x07600004  Razer Axon            1280×720
```

Rendering does not catch up immediately; this shows in the number of colours in the window:

```
 8 s after the window appeared:     144 colours   (empty)
28 s after:                     117 577 colours (full content)
```

⭐ **Result: Axon works.** Screenshot as evidence:
`~/Pictures/Screenshots/axon-окно-работает.png`. It shows not a placeholder or an empty
canvas, but a live UI with data that came from Razer's servers:

* the top menu `AXON / CREATE / COMMUNITY / LIBRARY`;
* the catalog tabs `HOT / BROWSE / SERIES / CREATORS`;
* the filters "Favourites only", "With sound", "Not AI", wallpaper search, sorting;
* a wallpaper grid with **loaded thumbnails** — `The Beauty of Space` (Razer), and also
  the `Timeless Masterpieces` series: "The Starry Night", "Sunflowers", "Nighthawks",
  "Girl with a Pearl Earring", "Water Lilies", "The Birth of Venus", "The Great Wave
  off Kanagawa", "Liberty Leading the People", "The Creation of Adam", "The Scream", "The Last Supper";
* the left category column and the first-run tooltip "DETAILED
  WALLPAPER INFORMATION";
* the whole UI is **in Russian** (the labels above are translated).

⭐⭐ **Separately important for the "works for anyone" goal: no Razer account is needed.**
The Razer Central guest sign-in takes Axon all the way to a fully functional catalog.
Registration is required only for what is tied to an account (favourites,
purchases, sync), while browsing and launching wallpapers is available to a guest.

The full sequence that led to this (it also became the install script):

```bash
export WINEPREFIX="$HOME/.wine-axon"
WINEARCH=win64 wineboot --init                 # win10, build 19045
winetricks -q dotnet48                         # ~14 min; MUST be first
wine winecfg -v win10                          # dotnet48 leaves build 7601
wine RazerCentral_v7.23.0.1220.exe /silent     # 294 MB, silent, service RzActionSvc
wine RazerAxonSetup_2.9.1.0.exe /SP- /VERYSILENT \
     '/DIR=C:\Program Files (x86)\Razer\Razer Axon' /SUPPRESSMSGBOXES /NORESTART
#   ↑ pulls WebView2 Evergreen by itself (670 MB)
wine regedit  …win7 for msedgewebview2.exe AND CefSharp.BrowserSubprocess.exe…
#   launch:
wineserver -p && wine sc start RzActionSvc && wine RazerAxon.exe -showui
#   first time: in the Razer Central window click "Continue as guest"
```

### Session 14 — running the script on a clean prefix

Date: 2026-08-13, prefix `~/.wine-axon2`, created by the script from scratch. The download cache
(`~/.cache/openaxon`) was wiped beforehand so that the installers were really downloaded
rather than taken from what was already there.

Timing per step (from the timestamps in the log):

| Step | Time | Result |
|---|---|---|
| creating the prefix | ~1 min | `system.reg` appeared |
| `winetricks -q dotnet48` | ~11 min | `Release=0x80eb1` (8 registry entries) |
| `winecfg -v win10` | ~15 s | `CurrentBuild` 7601 → **19045** |
| querying the Razer catalog | ~2 s | URLs and MD5s received |
| downloading Razer Central 116 MB | ~50 s | **MD5 matched** |
| downloading Razer Axon 61 MB | ~25 s | **MD5 matched** |
| installing Razer Central | ~30 s | 294 MB, service `RzActionSvc` |
| installing Axon + WebView2 | ~2.5 min | Axon 165 MB, WebView2 **151.0.4129.78**, 670 MB |

The measurement this run was set up for: **the Windows version after `dotnet48` had to be
corrected on a second, independent prefix as well** — so this is not a fluke of the first
session but the behaviour of winetricks (and it is in its source code too).

⚠️ The "wait until the installer finishes" logic had to be taught not to wait for everlasting background
programs. Three kinds of them remain in the compartment after installation, and none of them exits on its own:
`MicrosoftEdgeUpdate.exe /c` (session 8), `RazerCentralService.exe` (the service) and
`mscorsvw.exe` — the .NET background compiler that winetricks leaves behind after `dotnet48`.
Without an exclusion list every step idled for the full wait limit instead of seconds.

The script's own final check — **ten checks out of ten**:

```
✓ Razer Axon is in place                  ✓ Windows 10 is reported
✓ Razer Central is in place               ✓ Razer Central service is registered
✓ WebView2 interface engine is in place   ✓ rendering configured for Axon
✓ .NET Framework 4.8 is installed         ✓ rendering configured for Razer Central
✓ razer-axon command created              ✓ menu entry created
```

Running the same script again on an already installed compartment finished in **16 seconds**,
skipping all completed steps — idempotency confirmed by measurement.

### Session 15 — why a stranger's sign-in window would have stayed white

Date: 2026-08-13, prefix `~/.wine-axon2` (installed by the script).

The very first launch of the installed setup exposed a defect that was not visible in session 12:
the service came up, the `Razer Central` window appeared — and turned out to be **completely empty**:

```
import -window … → 1038×640, unique colours: 1
```

Exactly one colour — i.e. a filled rectangle, not even a frame. In session 12 the same
place looked fine only because there the Central UI was **restarted
by hand**, and that time it got different conditions.

The cause has been established (and matches the independent analysis in
[`auth-and-network.md`](auth-and-network.md)): **the Chromium sandbox does not work under Wine**,
so CefSharp's rendering subprocesses do not start at all. The service
`RzActionSvc` launches its UI **without** the `--no-sandbox` switch — and the window stays
white no matter how long you wait.

Measuring the workaround: kill the instance started by the service (by the process IDs of your own compartment)
and start your own with the switches —

```bash
wine "Razer Central.exe" /Client --no-sandbox --disable-gpu \
     --disable-gpu-compositing --disable-features=RendererCodeIntegrity
```

Result within 27 seconds:

```
before: unique colours 1        (empty)
after:  unique colours 94 240   (the whole sign-in screen)
--type=renderer processes: 7    (without the switch there were none)
```

⭐ That is why this workaround is built into the launcher that the install script creates: after the
service comes up, it closes the UI instance the service started and launches its own, with the required switches.
Without this, "installs and runs for anyone" would not hold: a stranger would get
a white window on the very first launch and no way to guess why.

### Session 16 — ⭐ the "as a stranger" check: one command, from start to finish

Date: 2026-08-13. Everything was done only with the means an ordinary person gets
after installation — no manual `wine` calls.

```bash
razer-axon          # the only command created by the installer
```

What happened by itself, without intervention:

| What | Measurement |
|---|---|
| the Razer Central service came up | `RzActionSvc` → `STATE : 4 RUNNING` |
| the launcher replaced the Central UI with its own, with `--no-sandbox` | **7** `--type=renderer` processes appeared |
| the sign-in window rendered **immediately** | 1038×640, **94 240** unique colours |
| the "CONTINUE AS GUEST" button was pressed | the sign-in window closed by itself |
| the Axon window came up | `RazerAxonHostWindow` + `Razer Axon`, 1280×720 |
| the window filled with content | **117 577** unique colours |
| the window's `WM_CLASS` | `"razeraxon.exe"` — matches `StartupWMClass` in the shortcut, so the window is grouped correctly in the taskbar |
| `razer-axon --stop` | no Razer windows left, compartment processes — **0** |

Screenshots as evidence:

* `~/Pictures/Screenshots/axon-проверка-вход-central.png` — the Razer Central sign-in screen;
* `~/Pictures/Screenshots/axon-проверка-окно-axon.png` — the Axon wallpaper catalog.

⭐ **Result: the "installs and runs for anyone" goal is achieved.** A stranger
runs one install command, waits, then launches the menu entry or the command
`razer-axon`, clicks "Continue as guest" once — and gets a working
wallpaper catalog. No Razer account needed, no Wine knowledge needed, no manual tweaks.

---

### Session 17 — the tray icon menu: the tray is fine, WPF rendering turns it black

> ⚠️ The "it is not Wine's fault" conclusion of this session **was revised in session 18**: behind the black
> menu there is a real Wine defect in `winex11.drv`, and the registry key merely steers
> WPF away from the broken path. The session is left as is so that the history is visible.

Date: 2026-08-14. Setup: wine-11.15, Axon 2.9.1.0, prefix `~/.wine-axon2`,
KDE Plasma 6.7.4 on Wayland, tray icons are bridged by `xembedsniproxy`.

**Complaint:** right-clicking the Razer icon in the tray does nothing.

#### Who passes the click to whom

The chain is long, and the culprit was searched for along it from the start:

```
plasmashell → xembedsniproxy → synthetic click into the XEmbed window
            → explorer.exe (Wine tray) → the Razer program's owner window
```

A `WINEDEBUG=+systray` measurement showed that **the whole chain works**:

```
trace:systray:X11DRV_SystrayDockInsert icon window 0x100ba/1e0000b
trace:systray:notify_owner relaying 0x204     ← WM_RBUTTONDOWN
trace:systray:notify_owner relaying 0x205     ← WM_RBUTTONUP
trace:systray:notify_owner relaying 0x7b      ← WM_CONTEXTMENU
```

Plasma's own journal shows its side as well — it honestly calls the program:

```
plasmashell[2351]: Could not find DBusMenu interface, falling back to calling ContextMenu()
```

Moreover, the menu window **is created and placed where it should be**: 157×186 at point (350, 814) —
i.e. flipped upwards above the bottom panel, as it should be.

#### What was really going on

The menu window exists, but there is no content in it: a solid black rectangle. Hence the
feeling that "nothing happens".

The cause is that Razer Central has **two different renderers**. The window itself is drawn by
the embedded browser (CefSharp), while the icon menu is drawn by `Hardcodet.Wpf.TaskbarNotification`,
i.e. WPF. By default WPF goes through Direct3D 9 — and on exactly this path the window
stays black (why exactly — see session 18).

Control experiment (`repro/tray_min.c`, ~170 lines, plain Win32): an ordinary
`TrackPopupMenu` menu in the same tray, on the same Plasma, renders fully and works fine.
**So there is no defect in the Wine tray.**

| Experiment | Result |
|---|---|
| `tray_min.exe` (Win32, `TrackPopupMenu`) | menu fully visible, items "Hello"/"Quit" |
| Razer Central (WPF) before the fix | menu window exists, content is black |
| Razer Central (WPF) after the fix | menu fully visible, 7 items |

#### The fix

WPF's own standard key — switches it to CPU rendering:

```
[HKEY_CURRENT_USER\Software\Microsoft\Avalon.Graphics]
"DisableHWAcceleration"=dword:00000001
```

Added to `scripts/install-axon.sh`, step 8 ("Configuring window rendering"), and added
to the list of checks at the end of the installation. Requires no separate action from the user.

#### What remains open

* **Cyrillic in the menu shows as boxes.** Latin text ("Razer Central", "Razer Axon", "Axon")
  renders correctly, Russian labels are empty rectangles. It was verified that the problem is
  **not in the prefix**: dropping in `tahoma.ttf` (which has Cyrillic) changes nothing,
  and neither does removing `Roboto-Regular.ttf` from `C:\windows\Fonts` — the typeface in the menu stays
  the same. So WPF takes the font from the Razer program's own resources, not from the system,
  and that font has no Cyrillic coverage. This cannot be cured from the prefix.
  The WPF fallback tables (`GlobalUserInterface.CompositeFont`) are in place and for the range
  `0000-052F` point to `Segoe UI, Tahoma, Arial, …`, but the substitution does not kick in —
  the program specifies the typeface explicitly.
* **The Axon window is not in the taskbar.** The old workaround
  `scripts/razer-axon-taskbar-fix.sh` removed `WM_TRANSIENT_FOR`. On the current stack
  the measurement is negative: the property was removed (`xprop … -remove`), the window was raised and got
  `_NET_WM_STATE_FOCUSED` — there is still no taskbar entry. The workaround is **obsolete**:
  KWin decides the window's fate at the moment it is shown, and any watcher (including the old one,
  polling every 2 seconds) arrives later. Neither the installer nor the shortcut ever installed this
  script — it was dead weight and has been removed.

Screenshots as evidence:

* `~/Pictures/Screenshots/axon-трей-меню-чёрное.png` — before;
* `~/Pictures/Screenshots/axon-трей-меню-работает.png` — after;
* `~/Pictures/Screenshots/axon-трей-меню-win32-контроль.png` — the Win32 control menu.

### Session 18 — ⭐ why WPF's hardware path gives a black window: Wine defect found

Date: 2026-08-14. Setup: wine-11.15 and wine-staging-11.15, driver `winex11.drv`,
default wined3d renderer (GL), Plasma 6.7.4 on Wayland, Mesa/AMD Radeon 780M.
The measurement was done on a **copy** of the prefix (`cp --reflink=auto`); the working `~/.wine-axon2` was left untouched.

**The question of the session:** the `Avalon.Graphics\DisableHWAcceleration` key fixes the menu, but it is a workaround.
What breaks on the hardware path, and is it a Wine defect?

#### Answer: there is a Wine defect, and it is not in d3d9

There is not a single failure on the Direct3D side. With the key removed:

* `RenderCapability.Tier` = `0x00020000` — WPF considers the hardware path available;
* `Direct3DCreate9Ex`, `CreateDeviceEx`, `CreateAdditionalSwapChain`,
  `GetRenderTargetData`, `LockRect` — all `S_OK`, the `+d3d9,+d3d` trace
  has neither `E_NOTIMPL` nor `D3DERR_*`;
* the pixels read back are correct, `UpdateLayeredWindow` returns `TRUE`.

What breaks is presentation. The swapchain attaches a **client X window** to the window — an opaque
child exactly the size of the window, and it covers everything `UpdateLayeredWindow` has drawn.

#### What turns black and what does not

A WPF probe with four windows in one program (`repro/wpf_layered.cs`):

| What | Result |
|---|---|
| ordinary window | renders |
| window with `AllowsTransparency="True"` | **black** |
| popup without transparency | renders |
| popup with transparency (like a menu) | **black** |

So it is not about "popups" and not about WPF in general, but exactly about layered windows
(`WS_EX_LAYERED`). WPF menus, tooltips and drop-down lists are all layered, hence the
black Razer Central menu.

#### Reproduction without Razer and without .NET

`repro/d3d9_layered.c` — ~190 lines of plain Win32: a layered window, a D3D9Ex swapchain on
it, `Clear` to red, read back, `UpdateLayeredWindow`. Built with mingw:

```
x86_64-w64-mingw32-gcc -O1 -o d3d9_layered.exe d3d9_layered.c -ld3d9 -lgdi32 -luser32
```

| Run | Result |
|---|---|
| `d3d9_layered.exe` (layered + D3D) | **black rectangle** |
| `d3d9_layered.exe nod3d` (same window, no D3D) | red, correct |
| `d3d9_layered.exe plain` (ordinary window + D3D) | red, correct |

#### Location in the code and a verified fix

`dlls/winex11.drv/init.c`, `needs_offscreen_rendering()` — its list has three cases
(DPI scaling, child window, window with children); a layered window is not among them. Adding one
line

```c
if (NtUserGetWindowLongW( hwnd, GWL_EXSTYLE ) & WS_EX_LAYERED) return TRUE;
```

and rebuilding `winex11.so` flips the measurement: the pixel at the centre of the window was
`rgb(0,0,0)`, it became `rgb(255,0,0)`; in the WPF probe all four windows render.

#### What this changes for us

The `DisableHWAcceleration` workaround in `scripts/install-axon.sh` **stays** — it is
correct and needed until the fix lands in Wine. But what goes upstream now is not
"WPF can't do it" but a specific bug with a reproduction and a verified fix.
Analysis and texts are in `docs/wine-defect-candidates.md`, section 9.

---

---

## Hypothesis about the Windows version

The user's formulation: Wine creates a prefix with Windows 7 by default, while Axon
requires 10 or 11; under Windows 7 the installer silently does not start.

**Result of the check: the hypothesis is right about the EFFECT (win7 really does prevent installation,
win10/11 allow it) and wrong about the CAUSE (Wine has nothing to do with it — the default has long been win10).**

There turned out to be two checks, and it all comes down to TWO independent ties to the Windows version:

| # | Who checks | What happens under win7 | Measurement |
|---|---|---|---|
| 1 | Razer's server `manifest3.razerapi.com` | `osver=7` → empty catalog → the online wrapper says "the server cannot be reached" | May 2026 |
| 2 | the Inno setup itself (`MinVersion`) | modal `This program does not support the version of Windows your computer is running`, installation does not proceed | session 5, screenshot |

Below is a point-by-point analysis.

1. That Windows 7 breaks the installation is **true**, and the mechanism was documented back in May:
   the online wrapper's engine sends the parameter `osver=7` to `manifest3.razerapi.com`, Razer's server
   legitimately replies with an **empty catalog** `{"data":{"items":[]}}` (Axon requires
   Win10+), and the wrapper treats the empty catalog as "service disabled" and shows
   a green "the server cannot be reached" screen. Accordingly, there is nothing to install.
2. That Windows 7 is set **by Wine itself** is **false**. A fresh wine-11.15 prefix is already
   Windows 10 (measured in session 1).
3. ⭐ The real source of Windows 7 is **`winetricks dotnet48`**: as a side
   effect it switches the prefix version to win7 (this is stated directly in the May
   document: "`winecfg -v win10` PRECISELY after dotnet48, because it resets the version
   to win7"). So Windows 7 appears not when the prefix is created but at the
   .NET Framework installation step — and it hits exactly the installation path that goes through the .NET
   wrapper.

Practical conclusion: **the order of the steps matters more than the steps themselves.** If you install via the online
wrapper, `winetricks -q dotnet48` must come BEFORE switching the version back to win10, otherwise
you get "silently does not install". If you run the Inno setup directly (session 2), the question
of the Windows version does not arise at install time at all.

---

## Install recipe

⭐ The whole recipe is packaged as the script [`scripts/install-axon.sh`](../scripts/install-axon.sh):
it is non-interactive and idempotent, works around all the traps listed below by itself, creates
the `razer-axon` command and a menu entry, and at the end checks ten installation indicators.
Below is the same thing by hand, so that you can see what the script consists of.

The first version of the recipe (2026-08-11) installed **only Axon** — that was enough for
the installation to succeed, but the application then showed no window at all. The full recipe,
which gets you to a working window, was verified on 2026-08-12 (sessions 10-13) and includes **two** Razer
products and rendering setup. A working internet connection is required: about 1 GB is downloaded in total
(Central ~120 MB, Axon ~60 MB, WebView2 ~190 MB downloaded / 670 MB on disk, plus .NET).

```bash
# 1. A fresh 64-bit prefix. No need to tweak it: wine-11.15
#    already sets Windows 10 (build 19045).
export WINEPREFIX="$HOME/.local/share/openaxon/prefix"
WINEARCH=win64 wineboot --init

# 2. .NET Framework 4.8 — MUST BE FIRST, before Axon.
#    It is needed not by Axon but by Razer Central. And first — because the Axon installation
#    leaves behind an everlasting MicrosoftEdgeUpdate.exe /c, after which winetricks
#    hangs forever on wineserver -w (session 8).
winetricks -q dotnet48

# 3. Switch back to Windows 10: step 2 leaves build 7601 behind,
#    and the Axon Inno installer refuses to work on Windows 7 (session 5).
wine winecfg -v win10

# 4. Razer Central. Without it Axon shows NO window AT ALL (session 9).
#    With real .NET it installs completely silently (session 10).
wine RazerCentral_v7.23.0.1220.exe /silent

# 5. Axon itself. It also pulls in and installs the WebView2 Runtime by itself.
#    The message-box suppression switch has two "p"s; we do not repeat Razer's typo.
wine RazerAxonSetup_2.9.1.0.exe \
     /SP- /VERYSILENT '/DIR=C:\Program Files (x86)\Razer\Razer Axon' \
     /SUPPRESSMSGBOXES /NORESTART

# 6. Rendering: version win7 for TWO browser subprocesses — WebView2 for Axon
#    and CefSharp for Razer Central. The Razer programs themselves stay on win10.
wine regedit …   # contents — in session 11 and in the script

# 7. Launch. The service lives only within a session, so do everything in one go.
wineserver -p
wine sc start RzActionSvc
wine RazerAxon.exe -showui
#    First time: in the Razer Central window click "Continue as guest".
```

Checking the result:

```bash
wine reg query \
  'HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\Razer Axon_is1' /v DisplayVersion
# → DisplayVersion    REG_SZ    2.9.1.0
wine sc query RzActionSvc
# → STATE : 4  RUNNING
```

### Where to get the installers

Razer publishes both links itself, in an open catalog and without any authorization. The
MD5 checksums come from there too — the install script verifies the downloads against them:

```bash
HASH=$(curl -s 'https://discovery3.razerapi.com/api/v1/endpoints?tag=prod' \
       | grep -oP '"hash":"\K[^"]+')
curl -s "https://manifest3.razerapi.com/api/v1/releases/$HASH/tags/prod/products?os=WINDOWS&osver=11&arch=64&mfr=Generic-MFR&model=Generic-MDL0&sku=Generic-SKU&l=en-US"
```

Two entries are needed (checked 2026-08-12, both checksums matched the local files):

| Catalog entry | What it is | MD5 |
|---|---|---|
| `Razer Axon` 2.9.1.0 | `RazerAxonSetup_2.9.1.0.exe` | `a04cd17767144b74fe7e24df8e920ed9` |
| `Natasha` 7.23.0.1220 | `RazerCentral_v7.23.0.1220.exe` | `b015e30d20011da3fada698b62741284` |

⚠️ `osver` in this request must be `10` or `11`: with `osver=7` Razer's server returns
an empty catalog, and there is nowhere to get the links from (see the section on the Windows version).

### The install script: what it takes into account

`scripts/install-axon.sh` — one command without a single question. How it is built:

| Script step | What it does | Which trap from the log it removes |
|---|---|---|
| `check_system` | checks for wine, winetricks, curl, python3 | suggests the install command for six distributions instead of "command not found" |
| `make_prefix` | a separate prefix in the home directory | Wine refuses to work in a directory owned by someone else |
| `install_dotnet` | `winetricks -q dotnet48` | session 8: only BEFORE Axon, otherwise an everlasting `wineserver -w` |
| `set_win10` | `winecfg -v win10` | session 10: after dotnet48 the registry is left with build 7601 |
| `ask_catalog` | takes URLs and MD5s from the Razer catalog | links go stale, they must not be hard-coded |
| `download_installers` | downloads and verifies MD5, caches | catches "HTML downloaded instead of the program" by the `MZ` signature |
| `install_central` | `/silent` | session 10: installs silently only with real .NET |
| `install_axon` | `/VERYSILENT` with **two** `p`s in the switch | session 5: Razer's typo, message boxes are not suppressed |
| `setup_rendering` | win7 for both browser subprocesses | sessions 11-12: WebView2 for Axon and CefSharp for Central — different engines |
| `make_launcher` | the `razer-axon` command + a menu entry | session 10: the service lives only within a session, the launcher starts it itself |
| `cleanup` | kills processes of **its own** prefix | the resident `MicrosoftEdgeUpdate.exe /c`; the owner is determined via `/proc/<pid>/environ`, not by process name |
| `verify` | ten checks against files and the registry | "installed" is reported only on the basis of a measurement, not on "the command finished" |

Idempotency: every step first checks whether it has already been done, so an interrupted
run can simply be repeated.

⚠️ A note for the future that cost one run: **bash does not allow Cyrillic in variable
names.** It parses `КЭШ="…"` not as an assignment but as a command, and fails with
"command not found" only at run time — while `bash -n` considers such a program
syntactically correct and stays silent. So the names in the script are in Latin characters; Russian was used only for
messages and comments.

⚠️ Second: **you must not edit the script file while it is running.** bash reads
the program from disk as it executes, by byte offset, so an edit shifts
the unread remainder and breaks the run already in progress.

⭐ Third — the most instructive one, it cost two runs. **The script was killing itself.**

The project rule "kill processes only by your own prefix, never by name" was
followed literally: the process owner was determined by `WINEPREFIX` in
`/proc/<pid>/environ`. The trouble is that `WINEPREFIX` is exported both by **the script itself** and
by each of its subshells — so by this criterion it found itself, and at the "clean up
after yourself" step sent `SIGTERM` to its own process ID. Outwardly this looked like
"the run silently broke off in the middle of the installation": the log ends at a step line, .NET is
installed, and the process is gone.

The same defect silently broke the waiting as well: `wait_quiet` asked "are there any processes of the
compartment left?", the command substitution subshell saw itself — and the answer was always "yes",
so every wait honestly idled until the limit instead of seconds.

The cure is a second condition: the process must be **a Wine program specifically**. This is checked by
the first command-line argument — a Windows-style path (`C:\…`) or a Wine binary
(`wineserver`, `wine`, `wine-preloader`). Verified by measurement on a live prefix: the function
finds all eleven processes of the compartment (`wineserver`, `services.exe`, `winedevice.exe`,
`svchost.exe`, `mscorsvw.exe`, `explorer.exe`, `plugplay.exe`, `rpcss.exe`, `cmd.exe`)
and **does not find itself**.

### What is NOT in the recipe and why

| Step from the May recipe (2.6.2.0) | Needed | Why |
|---|---|---|
| manual installation of WebView2 Evergreen | **no** | setup 2.9.1.0 itself calls the embedded `MicrosoftEdgeWebview2Setup.exe /silent /install` |
| running `RazerAxonInstaller.exe` (WPF wrapper) | **no** | its UI crashes under Wine on the license screen; it is bypassed entirely |
| `sc create RazerCentralService …` (from the README) | **no** | the Central installer registers the service itself, and under a different name — `RzActionSvc` |
| the `RazerAxon.UserManager.dll` patch | **no** | it was needed to work around the missing Central; now Central installs normally, and the guest sign-in also removes the account requirement |

### What had to be PUT BACK into the recipe compared with the version of 11 August

| Step | Why it was first considered unnecessary | Why it is needed after all |
|---|---|---|
| `winetricks -q dotnet48` | the Axon Inno setup does without .NET — and that is true | Razer Central requires .NET, and without Central Axon shows no window (sessions 9-10) |
| `winecfg -v win10` | a fresh wine-11.15 prefix is win10 anyway — also true | but after `dotnet48` the registry is left with build 7601, measured (session 10) |

---

## Wine defects (upstream candidates)

Fixes for games and Windows programs are submitted to **Wine**, not to Proton (Proton is a fork of Wine,
fixes flow downstream, not upstream). Only what has been confirmed by measurement is listed here, with a note on
what exactly it breaks.

⭐ **The main point: no Wine defect blocks the installation of 2.9.1.0.** The setup installs on a
bare prefix. Everything listed below is either noise or interference on adjacent paths.

> An analysis of each candidate (duplicate / confirmed / dropped), measurements on wine-11.15 and
> ready-made texts for Bugzilla are in [wine-defect-candidates.md](wine-defect-candidates.md).

### D1. `wineserver -w` cannot wait out the resident `MicrosoftEdgeUpdate.exe /c`

**Confirmed, session 8.** Not a Wine defect in the narrow sense, but a practical trap
that cost the May analysis a wrong conclusion ("a known winetricks bug"). The WebView2
installation leaves an everlasting Edge Update process in the prefix, after which any winetricks verb
locks up dead. Where it belongs: **a note in winetricks** (kill the Edge Update resident
before `wineserver -w`) and/or a line in AppDB.

Evidence: `MicrosoftEdgeUpdate.exe /c` alive for 1010 s; killing exactly this PID
immediately unblocked winetricks, and the .NET installation continued.

### D2. `richedit`: incomplete RTF parsing when showing the license

```
err:richedit:ReadColorTbl malformed entry           (×6)
err:richedit:ReadStyleSheet skipping optional destination   (×9)
```

Occurs when Inno loads the license text. Does not affect installation (the text is not
shown with `/VERYSILENT` anyway), but it is a genuine gap in the `riched20` implementation —
the RTF colour table and style sheet are not parsed completely. A candidate for Wine as
a small standalone bug with a reproduction on a specific RTF.

### D3. `shell32`: `IShellLinkW::QueryInterface` returns `E_NOINTERFACE`

```
err:shell:IShellLinkW_fnQueryInterface -- Interface: E_NOINTERFACE   (×4)
```

Caught at `RazerAxon.exe` startup (creating/reading a shortcut). Needs clarification of which
IID exactly is requested (a run with `WINEDEBUG=+shell,+ole` is needed), after which it is
a ready report: Wine's shortcut object does not return an interface that real Windows does.

### D4. `combase`: no WinRT telemetry class

```
err:combase:RoGetActivationFactory Failed to find library for
    L"Windows.System.Diagnostics.Telemetry.PlatformTelemetryClient"
err:ole:com_get_class_object no class object {cecddd22-2e72-4832-9606-a9b0e5e344b2}
    could be created for context 0x17
err:ole:CoSetProxyBlanket -- failed with 0x80004002
```

From inside Edge Update. Harmless (telemetry), but it reveals a missing WinRT class.
Low priority.

### D5. Stubs noticed along the way

```
fixme:seh:WerRegisterCustomMetadata (L"EdgeUpdateDllVersion", …) stub
fixme:clusapi:ClusterEnum / ClusterCloseEnum / CloseCluster (DEADBEEF, …) stub!
fixme:advapi:DecryptFileW (…) stub
fixme:nls:get_dummy_preferred_ui_language … returning a dummy value
fixme:msi:internal_ui_handler internal UI not implemented for message 0x0b000000
```

None of them got in the way of the installation. Recorded for completeness.

### Previously known (from the May analysis, not re-checked for 2.9.1.0)

* **Crash of the online wrapper's WPF UI** on leaving the license screen:
  `Razer.Installer.UI.Language.Attached.TextBlockTextPlugin.Update()` →
  `TextBlock.EnsureComplexContent()` → `0x80131623`. Worked around by not using the wrapper
  at all (see the recipe), so it was not reproduced in this session.
* **WebView2 and DirectComposition**: `DCompositionCreateDevice` returns `E_NOTIMPL`,
  which makes Chromium's viz process hit a CHECK when the Windows version is ≥ 8.1, and the frame does not reach
  the window. Workaround — a per-app override `Version=win7` for `msedgewebview2.exe` while
  keeping win10 for the rest of the prefix. **This is the weightiest upstream candidate**
  in the whole history of the project.

### Not Wine defects, but quirks of Razer itself

Noted separately so as not to submit to Wine something that does not concern Wine:

1. **The typo `/SUPRESSMSGBOXES`** instead of `/SUPPRESSMSGBOXES` in Razer's manifest —
   the switch does not work, message boxes are not suppressed, and on refusal the "silent" installation
   gets stuck on an invisible modal window.
2. **`MinVersion` in the Inno setup** cuts off Windows 7 — this is a deliberate requirement by Razer
   (Axon is stated for Windows 10+), not a breakage.
3. **RazerCentral's `/silent` is not honoured** — the installer shows windows anyway.
