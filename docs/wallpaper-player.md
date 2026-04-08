# Razer Axon WallpaperPlayer Protocol

Reverse-engineered from decompiled `RazerAxon.WallpaperPlayerManager.dll`,
`RazerAxon.IWallpaperPlayerManager.dll`, `RazerAxon.IWallpaperManager.dll`,
and `RazerAxon.ISettingManager.dll`.

---

## Architecture Overview

```
┌──────────────────────┐       Named Pipes (UTF-8 JSON)       ┌──────────────────────┐
│  RazerAxon.exe       │ ─────────────────────────────────────►│  RazerAxon.Player.exe│
│  (.NET 6, WebView2)  │ Write Pipe                            │  (Native C++ x64)    │
│                      │◄───────────────────────────────────── │                      │
│  WallpaperPlayer     │ Read Pipe                             │  Renders wallpapers  │
│  Manager             │                                       │  on desktop          │
└──────────────────────┘                                       └──────────────────────┘
```

### Pipe Names

Generated at runtime with random GUIDs:
```
Write: \\.\pipe\RazerCortexServiceAndShell{GUID}
Read:  \\.\pipe\RazerCortexServiceAndShell{GUID}
```

Player is launched with:
```
RazerAxon.Player.exe readpipename=\\.\pipe\{write_guid} writepipename=\\.\pipe\{read_guid} version=2.6.2.0
```

Note: "read" and "write" are from the Player's perspective — reversed from Axon's perspective.

---

## Wire Protocol

- **Encoding:** UTF-8 strings
- **Delimiter:** `<END>` marks end of each message
- **Buffer size:** 5120 bytes per read
- **Format:** JSON (serialized with `System.Text.Json`, `UnsafeRelaxedJsonEscaping`)
- **Direction:** Bidirectional — Axon sends commands, Player sends events back

---

## Commands (Axon → Player)

### SequoiaCommand JSON Format

```json
{
  "Command": "Play",
  "MonitorId": "\\\\?\\DISPLAY#GSM5BCD#...",
  "Type": "Video",
  "Source": "C:\\Users\\...\\wallpaper.mp4",
  "NeedDeleteSource": "0",
  "PlayMode": "Span",
  "PlayEffects": "{\"Brightness\":\"0.8\",\"Contrast\":\"1.0\"}"
}
```

### Command Types

| Command | MonitorId | Type | Source | Description |
|---------|-----------|------|--------|-------------|
| `Play` | monitor ID | wallpaper type | file path | Start playing wallpaper |
| `Switch` | monitor ID | wallpaper type | file path | Switch to different wallpaper |
| `Stop` | monitor ID | — | — | Stop playback on monitor |
| `Pause` | monitor ID | — | — | Pause playback |
| `Resume` | monitor ID | — | — | Resume playback |
| `Volume` | monitor ID | — | volume (0.0-1.0) | Set volume (Source field used for value) |
| `PlayEffect` | monitor ID | — | — | Update visual effects |
| `Terminate` | — | — | — | Terminate Player process |

### Wallpaper Types (in Type field)

| Raw Type | Mapped Type (WMF player) | Mapped Type (WebView2 player) |
|----------|--------------------------|-------------------------------|
| `VIDEO` | `Video` | `FunctionalWeb` |
| `LOCALVIDEO` | `Video` | `FunctionalWeb` |
| `WEB` | `Web` | `Web` |
| `LOCALWEB` | `Web` | `Web` |
| `IMAGE` | `FunctionalWeb` (or `Web` if screensaver) | `FunctionalWeb` |
| `LOCALIMAGE` | `FunctionalWeb` | `FunctionalWeb` |

Player supports two rendering backends:
- **WindowsMediaFoundation** — native video playback
- **WebView2** — web-based wallpapers (HTML/CSS/JS), also used for static images via `FunctionalWeb`

### PlayMode

| Mode | Description |
|------|-------------|
| `None` | Default — wallpaper on single monitor |
| `Span` | Span wallpaper across all monitors |
| `Duplicate` | Same wallpaper on all monitors |

### PlayEffects JSON

The `PlayEffects` field contains a JSON dictionary of effects:

```json
{
  "WallpaperFillingMode": "Fill",
  "Brightness": "0.8",
  "Contrast": "1.2",
  "Hue": "0",
  "Saturation": "1.0",
  "PlayRate": "1.0",
  "WebInteraction": "true",
  "ThirdpartInfo": "{\"spotify_token\":\"...\"}"
}
```

#### WallpaperEffectsEnum

| Effect | Values | Description |
|--------|--------|-------------|
| `WallpaperFillingMode` | `Fit`, `Fill`, `Stretch`, `Center`, `Tile` | Static image fill mode |
| `Brightness` | float (0.0-1.0) | Brightness adjustment |
| `Contrast` | float | Contrast adjustment |
| `Hue` | float | Hue rotation |
| `Saturation` | float | Saturation adjustment |
| `PlayRate` | float | Playback speed |
| `WebInteraction` | `"true"` / `"false"` | Enable mouse interaction for web wallpapers |
| `ThirdpartInfo` | JSON string | Third-party integration (e.g., Spotify) |

### NeedDeleteSource

| Value | Description |
|-------|-------------|
| `"0"` | Keep source file after playback |
| `"1"` | Delete source after playback (used for decrypted ZIP wallpapers) |

---

## Events (Player → Axon)

### SequoiaClientMessage JSON Format

```json
{
  "Type": "FullScreen",
  "Message": "\\\\?\\DISPLAY#GSM5BCD#..."
}
```

### Event Types

| Type | Message | Description |
|------|---------|-------------|
| `BadFormat` | error details | Wallpaper file format error |
| `FullScreen` | monitor ID | Fullscreen app detected on monitor (pause wallpaper) |
| `FullScreenResume` | monitor ID | Fullscreen app closed (resume wallpaper) |
| `Spotify` | JSON data | Spotify integration event |

---

## IWallpaperPlayerManager Interface

Full .NET interface exposed to the rest of Axon:

```csharp
interface IWallpaperPlayerManager
{
    // Events
    event EventHandler<PlayingWallpaperChangedEventArgs> OnPlayingWallpaperChanged;
    event EventHandler<int> OnPlayerProcessExit;
    event EventHandler<string> OnPlayerFormatError;
    event EventHandler<string> OnPlayerMonitorFullScreen;
    event EventHandler<string> OnPlayerMonitorFullScreenResume;
    event EventHandler<bool> OnPlayerD3DGameRunningStateChanged;
    event EventHandler<WallPaperItem> OnWallPaperItemPlaySourcePathChanged;

    // Playback control
    WallPaperStatusEnum CheckWallPaperStatus(WallPaperItem item);
    WallPaperItem? GetCurrentPlayingItem(string monitorId);
    Task PlayOrSwitch(WallPaperItem item, string monitorId);
    Task TryStopPlay(string monitorId);
    Task PausePlayer(string monitorId);
    Task ResumePlayer(string monitorId);
    Task SetVolume(string monitorId, int volume);
    Task SetPlayEffect(string monitorId, Dictionary<WallpaperEffectsEnum, string> playEffects);
    Task<bool> TerminatePlayer();

    // Monitor management
    Task RefreshMonitor();
    void SetDuplicateEnable(bool isDuplicate);
    void SetPlayMode(PlayModeEnums playMode);
    void SetMonitors(List<string> monitors);

    // Resource management
    Task<Tuple<string, bool>> UnzipPlaySource(string wallpaperId, string zipFilePath, WallPaperTypes type);
    PlaySourceInfo? GetPlaySourceInfoFromDir(string dir);
    WallPaperStatusEnum CheckWebWallpaperSource(string filePath, out string playSourcePath);

    // Chroma RGB
    void StartPlayChroma(WallPaperItem item);
    void StopPlayChroma();
    bool RemoveChromaEffects(WallPaperItem wallpaperItem);
    void SetChromaEffects(WallPaperItem wallpaperItem, List<string> chromaFiles);
}
```

---

## PlaySourceInfo

Describes the wallpaper resource after extraction:

```json
{
  "WallPaperType": "VIDEO",
  "Version": "1.0",
  "Source": "wallpaper.mp4",
  "ChromaPreset": [
    {
      "ChromaType": "KEYBOARD",
      "ChromaResource": "chroma_keyboard.json",
      "ForgroundRed": 68, "ForgroundGreen": 214, "ForgroundBlue": 44,
      "BackgroundRed": 0, "BackgroundGreen": 0, "BackgroundBlue": 0
    }
  ],
  "CustomChromaPreset": [],
  "Integrity": ["hash1", "hash2"],
  "SourceEncryptedTypes": "ZIP",
  "SourceEncryptedLevel": "LOW"
}
```

### ChromaResourceTypes
```
HEADSET, CHROMA_LINK, KEYBOARD, KEYPAD, MOUSE, MOUSEPAD
```

### SourceEncryptedTypes
```
NONE — unencrypted resource
ZIP  — ZipCrypto encrypted (HMAC-SHA256 password from ResourceConfig.txt)
```

### SourceEncryptedLevels
```
LOW  — standard ZipCrypto
HIGH — additional protection
```

---

## Wallpaper Types

| Type | Source | Description |
|------|--------|-------------|
| `VIDEO` | Remote | Video wallpaper from Axon CDN |
| `LOCALVIDEO` | Local | User's local video file |
| `WEB` | Remote | HTML/CSS/JS interactive wallpaper |
| `LOCALWEB` | Local | Local HTML wallpaper |
| `IMAGE` | Remote | Static image wallpaper |
| `LOCALIMAGE` | Local | Local image file |
| `NONE` | — | No wallpaper |

---

## Wallpaper Status

| Status | Description |
|--------|-------------|
| `Installed` | Downloaded and ready to play |
| `Playing` | Currently active as wallpaper |
| `FileBroken` | File corrupted or invalid format |
| `FileLost` | File missing from disk |
| `Uninstalled` | Not downloaded |
| `Downloading` | Currently being downloaded |
| `None` | Unknown state |

---

## Player Backends

| Backend | Enum Value | Used For |
|---------|------------|----------|
| `WindowsMediaFoundation` | 0 | Video playback (MP4, WMV) |
| `WebView2` | 1 | Web wallpapers (HTML), static images, interactive content |

The backend selection affects how wallpaper types are mapped to Player types
(see Type mapping table above).

---

## Spotify Integration

When a wallpaper has `source: "spotify"`, the Spotify token is passed via
`PlayEffects.ThirdpartInfo` as a JSON string. The Player can synchronize
wallpaper visuals with Spotify playback.

```json
{
  "ThirdpartInfo": "{\"spotify_access_token\":\"...\",\"spotify_refresh_token\":\"...\"}"
}
```
