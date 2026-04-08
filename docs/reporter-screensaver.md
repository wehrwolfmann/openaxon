# Reporter & ScreenSaver

Reverse-engineered from `RazerAxon.Reporter.dll` (277 lines) and
`RazerAxon.ScreenSaver.dll` (455 lines).

---

## Reporter (Retention Analytics)

Sends install/uninstall/upgrade telemetry to AWS Kinesis via Razer's BigData pipeline.

### Entry Point

```
RazerAxon.Reporter.exe -install    # Report installation
RazerAxon.Reporter.exe -uninstall  # Report uninstallation
RazerAxon.Reporter.exe -upgrade    # Report upgrade
```

### Architecture

```
Reporter.exe
  → reads appsettings.json → WebServiceDomain
  → reads Registry: HKCU\Software\Razer\RazerAxon
    → ReportStatus (0 = needs reporting, 1 = done)
    → CurrentVersion
    → OldVersion (for upgrade events)
    → UUID
  → GET /sts (HMAC auth) → AWS STS credentials
    → returns: {ip, arn, token: {AccessKeyId, SecretAccessKey, SessionToken, Expiration}}
  → sends to AWS Kinesis via RazerBigDataClient
    → category: "Retention"
    → action: "Install" | "Uninstall" | "Upgrade"
    → dimensions: {"Installed Version": "<old_version>"} (for upgrades)
  → sets ReportStatus = 1 in registry
```

### API Endpoint

#### GET /sts
Get temporary AWS credentials for Kinesis data upload.

| Field | Value |
|-------|-------|
| Auth | HMAC (guest mode) |
| Response | `{ip, arn, token: {AccessKeyId, SecretAccessKey, SessionToken, Expiration}}` |

### Registry Keys

| Key | Path | Description |
|-----|------|-------------|
| ReportStatus | `HKCU\Software\Razer\RazerAxon` | 0 = pending, 1 = reported |
| CurrentVersion | `HKCU\Software\Razer\RazerAxon` | Current app version |
| OldVersion | `HKCU\Software\Razer\RazerAxon` | Previous version (for upgrades) |
| UUID | `HKCU\Software\Razer\RazerAxon` | Device/user UUID |

### Kinesis Event Data

```json
{
  "eventId": "<random-guid>",
  "sessionId": "<random-guid>",
  "uuid": "<user-uuid>",
  "appVersion": "2.6.2.0",
  "deviceFingerprint": "<hardware-hash>",
  "unixTimestamp": 1744123456.789,
  "category": "Retention",
  "action": "Install",
  "dimensions": {}
}
```

---

## ScreenSaver

Minimal launcher — sends Windows messages to the main Axon process.
Not a standalone screensaver renderer.

### Entry Point

```
RazerAxon.ScreenSaver.exe /s    # Show screensaver
RazerAxon.ScreenSaver.exe /c    # Show config (opens Axon UI)
RazerAxon.ScreenSaver.exe /p    # Preview (not implemented)
```

### How It Works

1. Finds the `RazerAxonHostWindow` using `FindWindow()`
2. Sends a custom Windows message via `PostMessage()`:
   - `/c` (config) → sends `WM_APP + 1` (32769) = Show UI
   - `/s` (screensaver) → sends `WM_APP + 3` (32771) = Show ScreenSaver
3. If Axon is not running, launches `RazerAxon.exe /c` or `RazerAxon.exe /s`

### Custom Window Messages

| Message | Value | Description |
|---------|-------|-------------|
| APP_ShowUI | 32769 (0x8001) | Show main Axon window |
| APP_HideUI | 32770 (0x8002) | Hide main window |
| APP_ShowScreenSaver | 32771 (0x8003) | Start screensaver mode |

These messages are sent to the window titled `"RazerAxonHostWindow"`.

### Screensaver Mode

When Axon receives `APP_ShowScreenSaver`, it switches the WallpaperPlayer to
screensaver mode (`isRunAsScreenSaver = true`), which affects:
- Image wallpapers render as `Web` type instead of `FunctionalWeb`
- Player runs fullscreen over desktop
- No UI controls shown
- Exits on mouse/keyboard input

### Linux Equivalent

For Linux screensaver integration:
```bash
# XScreenSaver: add to ~/.xscreensaver
openaxon-player --play /path/to/wallpaper.mp4 --screensaver

# Systemd idle detection
loginctl lock-session → triggers screensaver wallpaper
```
