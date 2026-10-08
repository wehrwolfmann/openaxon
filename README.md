English | [Русский](README.ru.md)

# OpenAxon — Razer Axon on Linux

Run [Razer Axon](https://www.razer.com/software/axon) on Linux through Wine — with login support, taskbar fixes and wallpaper decryption. Includes a native GTK4 client and full reverse-engineering documentation of the Razer Axon protocols.

## What's included

### Scripts

| File | Description |
|------|-------------|
| `scripts/установить-axon.sh` | **One-command install**: prefix, .NET, Razer Central, Axon, WebView2, rendering, launcher |
| `razer-login.py` | Razer ID login |
| `razer-token-inject.py` | Injects the token into Razer Central Service (works without patching the DLL) |
| `razer-token-refresh.sh` | Silent token auto-refresh (for a systemd `--user` timer, see `systemd/`) |
| `razer-axon-gui.py` | Native GTK4/Adwaita client for Linux |
| `openaxon-player.py` | Native wallpaper daemon (video/static, multi-monitor, effects) |
| `razer-axon.sh` | Launches the original Axon through Wine |
| `razer-axon-decrypt.py` | Extracts encrypted video wallpapers |
| `razer-sync.py` | Syncs wallpapers with your Razer account |
| `patch/RazerAxon.UserManager.dll` | Patched DLL (legacy method, see below) |

### Reverse-engineering documentation

Full documentation of the Razer Axon protocols, extracted from 27 .NET DLLs and JS bundles:

| Document | Description |
|----------|-------------|
| [`docs/razer-central-ipc.md`](docs/razer-central-ipc.md) | Razer Central IPC protocol — 4 services, 137+ commands, wire format |
| [`docs/axon-api.md`](docs/axon-api.md) | REST API — ~110 endpoints, HMAC authentication, download manager |
| [`docs/react-architecture.md`](docs/react-architecture.md) | React 18 frontend — 24 routes, state management, WebView2 bridge |
| [`docs/wallpaper-player.md`](docs/wallpaper-player.md) | Player pipe protocol — JSON commands, effects, multi-monitor |
| [`docs/chroma-sdk.md`](docs/chroma-sdk.md) | Chroma RGB — REST API, .chroma format, AI generation, LED maps |
| [`docs/design-system.md`](docs/design-system.md) | CSS design system — colors, fonts, 13 component groups |
| [`docs/webview-host-objects.md`](docs/webview-host-objects.md) | JS↔C# bridge — 6 host objects, 111 methods |
| [`docs/utilities.md`](docs/utilities.md) | Logger, Environment, Notifications, Telemetry |
| [`docs/reporter-screensaver.md`](docs/reporter-screensaver.md) | Analytics reporter and screensaver launcher |

## Dependencies

### Required

- **Wine** (tested with Wine 9.x / 10.x; the full Axon 2.9.1.0 install — on Wine 11.15)
- **Python 3.10+**
- **PyGObject** with GTK4, libadwaita and WebKit2
- **xdotool**, **xprop** (for the taskbar fix on X11)
- **7z** or **unzip** (for wallpaper decryption)

### Optional

- **mpvpaper** — video wallpapers on Wayland
- **xwinwrap** + **mpv** — video wallpapers on X11
- **feh** — setting static wallpapers (fallback)

### Arch Linux / CachyOS

```bash
sudo pacman -S wine python-gobject gtk4 libadwaita webkit2gtk-4.1 xdotool xorg-xprop p7zip
```

### Ubuntu / Debian

```bash
sudo apt install wine python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit2-4.1 xdotool x11-utils p7zip-full
```

### Fedora

```bash
sudo dnf install wine python3-gobject gtk4 libadwaita webkit2gtk4.1 xdotool xprop p7zip
```

### openSUSE

```bash
sudo zypper install wine python3-gobject gtk4 libadwaita webkit2gtk3-soup2-devel xdotool xprop p7zip
```

### Void Linux

```bash
sudo xbps-install wine python3-gobject gtk4 libadwaita webkit2gtk41 xdotool xprop p7zip
```

### Gentoo

```bash
sudo emerge app-emulation/wine dev-python/pygobject gui-libs/gtk:4 gui-libs/libadwaita net-libs/webkit-gtk x11-misc/xdotool x11-apps/xprop app-arch/p7zip
```

### NixOS

```nix
# configuration.nix or home-manager
environment.systemPackages = with pkgs; [
  wineWowPackages.stable
  python3
  python3Packages.pygobject3
  gtk4
  libadwaita
  webkitgtk_4_1
  xdotool
  xorg.xprop
  p7zip
];
```

## Installation

### The easiest way — one command

```bash
./scripts/установить-axon.sh
```

The script is non-interactive: it creates a dedicated Wine prefix, installs .NET Framework 4.8,
Razer Central, Razer Axon itself and the WebView2 UI engine, configures rendering,
creates a `razer-axon` command and a "Razer Axon" entry in the application menu, and at the end
checks ten signs that everything is in place. It takes 25-40 minutes and downloads about 1 GB.
An interrupted run can be restarted — completed steps are skipped.

On first launch a Razer Central window opens. **No Razer account is needed** —
just click "Continue as guest", and the full wallpaper catalog opens.

A breakdown of every step and the measurements behind it (in Russian) is in
[`docs/установка_под_wine_2_9_1_0.md`](docs/установка_под_wine_2_9_1_0.md).

### Manually, if you want to control every step

```bash
export WINEPREFIX="$HOME/.local/share/openaxon/prefix"
WINEARCH=win64 wineboot --init                 # fresh prefix: already win10, build 19045
winetricks -q dotnet48                         # MUST come before Axon (see below)
wine winecfg -v win10                          # dotnet48 leaves build 7601 behind
wine RazerCentral_v7.23.0.1220.exe /silent     # installs silently only with real .NET
wine RazerAxonSetup_2.9.1.0.exe /SP- /VERYSILENT \
     '/DIR=C:\Program Files (x86)\Razer\Razer Axon' /SUPPRESSMSGBOXES /NORESTART
```

Three places where it's easy to go wrong:

* `dotnet48` **before** Axon. The Axon installer leaves a never-ending
  `MicrosoftEdgeUpdate.exe /c` in the prefix, and `winetricks` waits for `wineserver -w`
  at every step — that is, for all processes in the prefix to exit. After Axon, any winetricks
  verb hangs forever.
* `winecfg -v win10` **after** `dotnet48`: it switches the Windows version to 7, and
  the Axon Inno installer refuses to run on Windows 7 (`MinVersion`).
* the message-box suppression switch is `/SUPPRESSMSGBOXES`, with two `p`s. Razer
  made a typo in its manifest (`/SUPRESSMSGBOXES`), and Inno silently ignores that switch.

### Razer Central service

You **don't need** to register it manually — the Razer Central installer creates it itself,
under the name `RzActionSvc` (not `RazerCentralService`, as was wrongly stated here
before):

```bash
wine sc query RzActionSvc     # → STATE : 4  RUNNING
```

⚠️ The service lives exactly as long as the prefix's `wineserver`. So it has to be started
in the same session in which Axon is launched — which is exactly what the `razer-axon`
command created by the script does:

```bash
wineserver -p                 # keep the session open
wine sc start RzActionSvc
wine RazerAxon.exe -showui
```

### Installing the helper scripts

```bash
cp razer-axon.sh razer-login.py razer-token-inject.py razer-axon-decrypt.py ~/.local/bin/
chmod +x ~/.local/bin/razer-axon.sh ~/.local/bin/razer-login.py ~/.local/bin/razer-token-inject.py ~/.local/bin/razer-axon-decrypt.py
```

### Razer ID login (only if you need your own account)

```bash
# Get a token
razer-login.py

# Inject it into Razer Central Service
razer-token-inject.py
```

`razer-login.py` opens a WebKit window with the Razer ID login page. After you log in, the script intercepts the JWT token and saves it.

`razer-token-inject.py` passes the token to Razer Central Service over named pipe IPC. On first run it automatically builds a .NET helper (requires the `dotnet` SDK 6.0+).

### Launch

```bash
razer-axon.sh
```

> **Note:** You can also log in directly through the Axon UI — click "Log in" in the app window. The token injector is only needed if direct login doesn't work.

### Alternative method: patched DLL (legacy)

If the Razer Central Service method doesn't work, you can replace `RazerAxon.UserManager.dll` with a patched version:

```bash
AXON_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"
cp "$AXON_DIR/RazerAxon.UserManager.dll" "$AXON_DIR/RazerAxon.UserManager.dll.orig"
cp patch/RazerAxon.UserManager.dll "$AXON_DIR/"
```

This method removes the dependency on Razer Central, but has to be reapplied after every Axon update.

## Usage

### Login / token refresh

```bash
razer-login.py            # Open the login window
razer-login.py --status   # Check the current token's status
razer-token-inject.py     # Inject the token into the service
razer-token-inject.py --status  # Check the state
```

Tokens expire after about 24 hours. You can refresh manually (`razer-login.py`), but it's more convenient to set up **auto-refresh** (below).

### Token auto-refresh (no repeated login)

`razer-login.py --refresh` silently gets a new token using the saved Razer ID session
cookies — **without a login window** — and only when the token expires within the hour
(otherwise it's a quick no-op). As long as the Razer ID session is alive, you don't need to
enter your login/password again.

`razer-token-refresh.sh` wraps this: it calls `--refresh` and syncs the fresh
token into the Wine prefix (where the `RazerAxon.UserManager.dll` patch reads
`wine_login_token.json` from). Put it on a systemd `--user` timer (every 30 min):

```bash
# The units in systemd/ point to %h/Projects/openaxon/razer-token-refresh.sh —
# adjust ExecStart to your path if the repository lives elsewhere.
cp systemd/razer-axon-token-refresh.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
# WebKit needs access to the graphical session for silent refresh:
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR
systemctl --user enable --now razer-axon-token-refresh.timer
```

When the session cookies eventually expire (weeks), the timer logs an error — then
log in interactively once (`razer-login.py`).

### Launch

```bash
razer-axon.sh             # Launch Razer Axon
```

The launch script:
- Sets Wine environment variables for WebView2 compatibility
- If Axon is already running, activates the existing window
- ~~Reactively fixes taskbar visibility (removes `WM_TRANSIENT_FOR`)~~ — the workaround is obsolete and has been removed: on wine 11.15 with Plasma 6.7.4, removing the property does not bring back the taskbar entry (measured, run 17)

### WebView2: stability under Wine

The Razer Axon UI is rendered by an embedded **WebView2** (msedgewebview2 / Chromium).
Under Wine, Chromium's **GPU/Viz process** crashes on `CHECK()`/`__debugbreak()` during
GPU init (exit code `0x80000003` = `STATUS_BREAKPOINT`) and restarts in a loop;
once the GPU crash limit is exhausted (~3-6 crashes in a row), the browser process
**exits deliberately** → Axon sees `CoreWebView2ProcessFailed` / reason
`BrowserProcessExited` and closes the UI window. The main Axon process
survives. **This is NOT Mojo IPC and NOT authentication** (the earlier hypothesis was disproven,
see below).

**Fix (the main lever) — Windows 7 for the renderer, to bypass DirectComposition:**
`razer-axon.sh` and `install-axon-linux.sh` idempotently set in the prefix registry:
- `Version=win7` for `msedgewebview2.exe` in `HKCU\Software\Wine\AppDefaults` —
  **the key part**. With a Windows version ≥8.1, Chromium's viz presents the frame (even a
  software bitmap) through **DirectComposition** (`DCompositionCreateDevice`),
  which Wine doesn't implement (`E_NOTIMPL`/`0x80004001`) → CHECK → viz crash → the frame
  never reaches the window = **black screen**. Under `win7` the same `SoftwareOutputDevice`
  goes through **GDI BitBlt** (no DComp) and actually copies the pixels into the window;
- `HardwareAccelerationModeEnabled=0` in `HKLM/HKCU\Software\Policies\Microsoft\Edge`
  and `...\Edge\WebView2` — auxiliary (Edge doesn't start a HW GPU process).

> **Important — two DIFFERENT Windows-version levers:**
> - `win7` is set **ONLY** for the renderer subprocess `msedgewebview2.exe`;
> - `RazerAxon.exe` and **the prefix globally stay on `win10`** — otherwise the Razer server
>   returns an empty catalog (login/content don't work). See `set_win10` in the installer.
>
> Sources for the fix: WineHQ Bug 58921, winetricks #2226, CodeWeavers, Arch Forums.

Additional mitigations applied by `razer-axon.sh`:

1. **Evergreen runtime (default).** Axon renders home through the bundled
   evergreen WebView2 (Chromium **149**) — the only configuration in which
   `CreateCoreWebView2Environment` initializes under Wine. Fixed-version
   (`INSTALL_WV2_FIXED=1`) is **not recommended** (see below).
2. **Software-only rendering.** `LIBGL_ALWAYS_SOFTWARE=1`, `GALLIUM_DRIVER=llvmpipe`,
   Mesa EGL — remove NVIDIA EGL noise under XWayland.
3. **Chromium flags** (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`):
   `--no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer
   --disable-gpu-sandbox --disable-features=RendererCodeIntegrity
   --disable-crash-reporter --disable-renderer-backgrounding
   --disable-background-timer-throttling`.

> **Status (2026-06-12):** verified live on Wine 11.10 + RTX 4070 (Wayland).
> The root cause was re-established from Chromium's stderr (`gpu_process_host.cc:1063 GPU process
> exited unexpectedly: exit_code=-2147483645` = `0x80000003`, "has crashed N
> time(s)"). A single baseline run recorded **12 gpu-process spawns**.
>
> **Before the fix (baseline):** the GPU process crashes ~6 times → `BrowserProcessExited`
> after ~10-17 s, the cycle repeats ~38 times in 200 s (the UI flickers).
>
> **After the fix (`win7` for msedgewebview2.exe + win10 for the app):**
> the Axon UI **actually renders** — confirmed visually (the home page with the banner
> carousel/TRENDING and the Razer ID Login screen rendered fully, 2026-06-18).
> The black screen is gone: viz no longer calls `DCompositionCreateDevice`,
> presentation goes through GDI BitBlt. The `--disable-gpu-process-crash-limit` flag
> has been **removed** under `win7` as redundant (the DComp crash loop is fixed at the root; the flag only
> masked the symptom) — verified live, the UI renders without it.
>
> _Background: the registry used to set `win81` by mistake (= the threshold at which DComp is enabled) —
> this got rid of `BrowserProcessExited` (white screen), but viz looped on the
> DComp crash and produced no frames → a **black** screen. Switching to `win7` is the real
> fix._
>
> **WineHQ #56378 is NOT about named pipes/Mojo** (research, Anubis workaround): it's a
> Chromium sandbox bring-up bug, closed FIXED in Wine **11.1**; its companion #56377 (freeze)
> was FIXED in 10.5. All their fixes (winstation/desktop/token, `DeriveCapabilitySidsFromName`,
> `SetAdditionalForegroundBoostProcesses`) **are already present in the system Wine 11.10**.
> Chromium Mojo uses named pipes in BYTE mode (long supported by Wine); since Chrome
> ~112, Mojo has moved to shared memory (ipcz). → **A Wine named-pipe patch is not needed
> and wouldn't help; no patched Wine was built** (cancelled based on the research).
>
> What did NOT help before (verified live): `--single-process` (crashes faster),
> `--no-zygote`, disabling `werfault.exe`, Xvfb without NVIDIA EGL (EGL is not the root cause),
> `--disable-watchdog/--disable-hang-monitor`, the fixed-version runtime 109/133
> (the version doesn't bring stability). To get rid of the remaining single early crash:
> `--disable-gpu-watchdog` + a higher GPU crash limit, Wine-Staging ≥11.6
> (DirectComposition patchset), or moving WebView2 into an external host (CDP proxy).

### Wallpaper decryption

Razer Axon stores downloaded wallpapers as ZipCrypto-encrypted ZIP archives disguised as `.mp4`.

```bash
# Auto-scan and extract all wallpapers
razer-axon-decrypt.py

# Show passwords only
razer-axon-decrypt.py -p

# Dry run (no extraction)
razer-axon-decrypt.py -n

# Skip already extracted
razer-axon-decrypt.py -s

# Custom directories
razer-axon-decrypt.py -d /path/to/wallpapers -o /path/to/output

# A single file
razer-axon-decrypt.py -f wallpaper.mp4 -c ResourceConfig.txt

# JSON output (for automation)
razer-axon-decrypt.py -j

# English interface
razer-axon-decrypt.py --lang en

# Verbose output (debug)
razer-axon-decrypt.py -v
```

#### How decryption works

Each wallpaper's password is derived from its `ResourceConfig.txt`:

```python
import hmac, hashlib
content = open("ResourceConfig.txt").read()
password = hmac.new(b"j6l-aUmhCc@tN%T_", content.encode(), hashlib.sha256).hexdigest()
```

The HMAC key is hardcoded in the Razer Axon .NET assemblies.

## How it works

### Architecture

```
┌─────────────────────────────────────────────────────┐
│ Razer Axon (Wine) — original files, no patches      │
│                                                     │
│  RazerAxon.exe                                      │
│       │                                             │
│       ├── RazerAxon.UserManager.dll (ORIGINAL)      │
│       │       └── NacClient ──► named pipe IPC      │
│       │                                             │
│       ├── WebView2 UI ──► axon-api.razer.com        │
│       │                                             │
│       └── WallpaperPlayerManager                    │
│               └── ZIP decryption → playback         │
│                                                     │
│  RazerCentralService.exe (Wine service)             │
│       ├── AccountManager ──► authentication         │
│       ├── Named pipe IPC ──► link to Axon           │
│       └── Razer API ──► manifest.razerapi.com       │
│                                                     │
├─────────────────────────────────────────────────────┤
│ Linux                                               │
│                                                     │
│  razer-login.py ──► id.razer.com ──► JWT token      │
│  razer-token-inject.py ──► pipe IPC ──► service     │
│  razer-axon.sh ──► Wine + environment/taskbar fixes │
│  razer-axon-decrypt.py ──► HMAC-SHA256 → unzip      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### How authentication works

Razer Central Service (`RazerCentralService.exe`) runs as a Wine service and listens on the named pipe `{FC828A97-C116-453D-BD88-AD471496E03C}`. Axon connects to it through `NacClient.dll` to obtain the authentication token.

`razer-token-inject.py` connects to the same pipe and sends the `WebApp_SetLoginSuccessFromWeb` command with the JWT token obtained via `razer-login.py`. This emulates web login through the Razer Central GUI (which doesn't display under Wine due to WPF rendering limitations).

All Razer files stay original — no binary patches.

### Token format

`~/.wine/drive_c/users/<USER>/AppData/Local/Razer/RazerAxon/wine_login_token.json`:

```json
{
  "convertFromGuest": false,
  "token": "eyJhbGciOiJFUzI1NiI...",
  "isOnline": true,
  "isGuest": false,
  "uuid": "RZR_...",
  "loginId": "user@example.com",
  "tokenExpiry": "2026-04-01T21:46:43.000Z",
  "stayLoggedIn": true
}
```

### Wallpaper encryption

Wallpapers in `~/RazerAxonWallpapers/<id>/Resource/` are ZipCrypto-encrypted ZIP archives:

```
password = HMAC-SHA256("j6l-aUmhCc@tN%T_", ResourceConfig.txt).hexdigest()
```

## Troubleshooting

### Axon shows a black/empty window
The token wasn't injected or has expired:
```bash
razer-login.py            # Refresh the token
razer-token-inject.py     # Inject it
```

### Razer Central Service doesn't start

The service is registered by the Razer installer under the name `RzActionSvc`
(the name `RazerCentralService` doesn't exist — `sc` will reply "service not found" for it):

```bash
# Check the state
wine sc query RzActionSvc          # expect STATE : 4  RUNNING

# Start it manually. wineserver -p is required: the service lives exactly as long
# as the Wine session does, and without it shuts down after a few seconds.
wineserver -p
wine sc start RzActionSvc
```

If Axon starts but there's **no window at all**, this is almost always the reason:
`RazerAxon.exe` doesn't create a window until login through Razer Central has completed.

### Cyrillic text in the tray shows up as boxes
```bash
wine reg add "HKCU\Software\Wine\Fonts\Replacements" /v "Segoe UI" /t REG_SZ /d "Tahoma" /f
```

### Token expired
```bash
razer-login.py --status   # Check
razer-login.py            # Refresh
razer-token-inject.py     # Inject again
```

### Window not visible in the taskbar
The launch script fixes this automatically. If the problem persists, make sure `xdotool` and `xprop` are installed.

### Wallpaper decryption doesn't work
Make sure `7z` or `unzip` is installed and supports ZipCrypto.

## Contributing

Contributions are accepted under the [Contributor License Agreement](CLA.md).
See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose a change.

## License

MIT
