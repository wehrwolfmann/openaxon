# Razer Axon on Linux

Run [Razer Axon](https://www.razer.com/software/axon) wallpaper engine on Linux via Wine — with login support, taskbar fixes, and wallpaper decryption.

## What's included

| File | Description |
|------|-------------|
| `razer-login.py` | Login to Razer ID without Razer Central |
| `razer-axon.sh` | Launch script with Wine/WebView2 fixes |
| `razer-axon-taskbar-fix.sh` | Daemon that keeps the window visible in taskbar |
| `razer-axon-decrypt.py` | Extract encrypted wallpaper videos |
| `patch/RazerAxon.UserManager.dll` | Patched DLL — replaces Razer Central auth with standalone login |

## Requirements

- **Wine** (tested with Wine 9.x / 10.x)
- **Python 3.10+**
- **PyGObject** with WebKit2 (`webkit2gtk-4.1`)
- **xdotool**, **xprop** (for taskbar fix on X11)
- **7z** or **unzip** (for wallpaper decryption)

### Arch Linux / CachyOS

```bash
sudo pacman -S wine python-gobject webkit2gtk-4.1 xdotool xorg-xprop p7zip
```

### Ubuntu / Debian

```bash
sudo apt install wine python3-gi gir1.2-webkit2-4.1 xdotool x11-utils p7zip-full
```

### Fedora

```bash
sudo dnf install wine python3-gobject webkit2gtk4.1 xdotool xprop p7zip
```

## Installation

### 1. Install Razer Axon via Wine

```bash
# Download the installer
wget -O /tmp/RazerAxonInstaller.exe "https://rzr.to/axon"

# Install
wine /tmp/RazerAxonInstaller.exe
```

Follow the installer. Default path: `C:\Program Files (x86)\Razer\Razer Axon`.

### 2. Patch the UserManager DLL

The original `RazerAxon.UserManager.dll` requires Razer Central (a Windows-only service) for authentication. The patched version replaces this with a standalone login flow that reads tokens from a local JSON file.

```bash
AXON_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"

# Backup original
cp "$AXON_DIR/RazerAxon.UserManager.dll" "$AXON_DIR/RazerAxon.UserManager.dll.orig"

# Apply patch
cp patch/RazerAxon.UserManager.dll "$AXON_DIR/"
```

### 3. Install scripts

```bash
# Copy scripts
cp razer-axon.sh razer-axon-taskbar-fix.sh razer-login.py razer-axon-decrypt.py ~/.local/bin/
chmod +x ~/.local/bin/razer-axon.sh ~/.local/bin/razer-axon-taskbar-fix.sh
chmod +x ~/.local/bin/razer-login.py ~/.local/bin/razer-axon-decrypt.py
```

### 4. Login to Razer ID

```bash
razer-login.py
```

This opens a WebKit window with the Razer ID login page. After you log in, the script captures your JWT token and saves it to `wine_login_token.json` where the patched DLL expects it.

The login uses a two-phase approach:
1. **Phase 1** — Opens id.razer.com as a normal website for login
2. **Phase 2** — After login detected, reloads with a "natasha bridge" shim to extract the JWT token

### 5. Launch Razer Axon

```bash
razer-axon.sh
```

## Usage

### Login / Token refresh

```bash
razer-login.py            # Open login window
razer-login.py --status   # Check current token status
```

Tokens expire after ~24 hours. Re-run `razer-login.py` when expired.

### Launch

```bash
razer-axon.sh             # Start Razer Axon
```

The launch script:
- Sets Wine environment variables for WebView2 compatibility
- If Axon is already running, activates the existing window
- Fixes the taskbar visibility issue after launch

### Taskbar fix (autostart)

Razer Axon sets `WM_TRANSIENT_FOR` on its window, which hides it from the taskbar on some window managers. The fix daemon watches for this and removes the property.

```bash
# Run manually
razer-axon-taskbar-fix.sh &

# Or add to autostart (KDE example)
cat > ~/.config/autostart/razer-axon-taskbar-fix.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Razer Axon Taskbar Fix
Exec=$HOME/.local/bin/razer-axon-taskbar-fix.sh
Hidden=false
X-KDE-autostart-phase=2
EOF
```

### Decrypt wallpapers

Razer Axon stores downloaded wallpapers as ZipCrypto-encrypted ZIP archives disguised with `.mp4` extensions.

```bash
# Auto-scan and extract all wallpapers
razer-axon-decrypt.py

# Show passwords without extracting
razer-axon-decrypt.py -p

# Custom directories
razer-axon-decrypt.py -d /path/to/wallpapers -o /path/to/output

# Single file
razer-axon-decrypt.py -f wallpaper.mp4 -c ResourceConfig.txt
```

#### How decryption works

Each wallpaper's password is derived from its `ResourceConfig.txt`:

```python
import hmac, hashlib
content = open("ResourceConfig.txt").read()
password = hmac.new(b"j6l-aUmhCc@tN%T_", content.encode(), hashlib.sha256).hexdigest()
```

The HMAC key is hardcoded in Razer Axon's .NET assemblies.

## How it works

### Architecture

```
┌─────────────────────────────────────────────────────┐
│ Razer Axon (Wine)                                   │
│                                                     │
│  RazerAxon.exe                                      │
│       │                                             │
│       ├── RazerAxon.UserManager.dll (PATCHED)       │
│       │       │                                     │
│       │       ├── Reads wine_login_token.json        │
│       │       └── No Razer Central dependency       │
│       │                                             │
│       ├── WebView2 UI ──► axon-api.razer.com        │
│       │                                             │
│       └── WallpaperPlayerManager                    │
│               └── Decrypts ZIP → plays MP4          │
│                                                     │
├─────────────────────────────────────────────────────┤
│ Linux                                               │
│                                                     │
│  razer-login.py ──► id.razer.com ──► JWT token      │
│  razer-axon.sh ──► Wine + env fixes                 │
│  razer-axon-taskbar-fix.sh ──► xprop WM fix         │
│  razer-axon-decrypt.py ──► HMAC-SHA256 → unzip      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Patched DLL details

The original `RazerAxon.UserManager.dll` communicates with Razer Central via named pipes (`NacClient`) for authentication. Since Razer Central doesn't run under Wine, the patched DLL:

- Removes all Razer Central / AccountManager dependencies
- Adds a `RazerLoginForm` with WebView2 for direct Razer ID login
- Stores/loads tokens from `wine_login_token.json` in AppData
- Exposes the same `IUserManager` interface to the rest of Razer Axon

Source was compiled from `/tmp/razer_usershim/` targeting `net6.0-windows`.

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

### Axon shows blank/white window
Make sure WebView2 runtime is installed in Wine:
```bash
# Axon installer should handle this, but if not:
winetricks -q webview2
```

### Token expired
```bash
razer-login.py --status   # Check
razer-login.py            # Refresh
```

### Window not visible in taskbar
```bash
razer-axon-taskbar-fix.sh &
```

### Wallpaper decryption fails
Ensure `7z` or `unzip` is installed and supports ZipCrypto.

## License

MIT
