# Razer Axon DLL Reference (11 modules)

All modules target .NET 6.0, Windows 7.0+ (NotificationManager requires Windows 10.0.22000+).
Internal codename: **Sequoia** (namespaces use `RazerSequoia.*`).
Source path leaked in debug strings: `D:\RazerDev\sequoia-client-v2\Src\Razer.SequoiaClient\`

---

## 1. RazerAxon.ILogger

**Purpose:** Logger interface contract.

**Namespace:** `RazerSequoia.ILogger`

**Interface: `ISequoiaLogger`**
- `Info(msg, file, func, line)` / `Info(ex, msg, ...)`
- `Debug(msg, ...)` / `Debug(ex, msg, ...)`
- `Warn(msg, ...)` / `Warn(ex, msg, ...)`
- `Error(msg, ...)` / `Error(ex, msg, ...)`
- `Flush()`
- `GetDebugModel()` -> bool (note: typo "Model" instead of "Mode")
- `GetDiagnosticsMode()` -> bool

All methods use `[CallerFilePath]`, `[CallerMemberName]`, `[CallerLineNumber]` for automatic source location capture.

**Class: `AppLogSetting`**
- `DebugMode` (bool)
- `DiagnosticsMode` (bool)

---

## 2. RazerAxon.Logger

**Purpose:** NLog-based logger implementation.

**Namespace:** `RazerSequoia.Logger`

**Class: `CortexLogger` (implements `ISequoiaLogger`)**

**Constructor:** `CortexLogger(string logPath, string logDebugPath, bool debugMode, bool diagnosticsMode)`

**Log format:**
```
${date:format=yyyy-MM-dd HH:mm:ss.ffff zzz}|${level}|T:${threadid}|L:${line}|${file}:${func}\n${message}
```

**File targets:**
- **Main log:** async file target, max 512 KB per file, 2 archive files (rolling)
- **Debug log:** async file target, max 20 MB per file, 1 archive file (rolling), only written when `debugMode=true`
- Both use `KeepFileOpen=true`, `ConcurrentWrites=false`, `OverflowAction=Block`

**In-memory cache:**
- `IsMemCacheEnabled` property - toggleable in-memory log buffer
- `GetMemCache()` / `ClearMemCache()` - thread-safe via lock
- `OnLogAction` callback populates the mem cache with formatted log lines

**Key methods:**
- `FlushAndShutdown()` - calls `LogManager.Shutdown()`
- Debug-level messages are only logged when `_debugMode` is true

**Linux port notes:** NLog is cross-platform. File paths need adaptation. No Win32 dependencies.

---

## 3. RazerAxon.IModuleFactory

**Purpose:** Generic service locator interface.

**Namespace:** `RazerSequoia.SequoiaIModuleFactory`

**Interface: `IModuleFactory`**
- `TModule? GetInstance<TModule>()` - resolve a module by type

---

## 4. RazerAxon.ModuleFactory

**Purpose:** DI container wrapper using `Microsoft.Extensions.DependencyInjection`.

**Namespace:** `RazerSequoia.SequoiaModuleFactory`

**Class: `ModuleFactory` (implements `IModuleFactory`)**

**Constructor:** `ModuleFactory(IServiceProvider serviceProvider)`

- `GetInstance<TModule>()` - calls `_serviceProvider.GetService<TModule>()`
- `Dispose()` - disposes the `ServiceProvider` if `_isInit` is true

**Linux port notes:** Fully cross-platform. Standard MS DI.

---

## 5. RazerAxon.IEnviroment (note: typo in name)

**Purpose:** Environment monitoring interface - monitors, power, network, sessions.

**Namespace:** `RazerSequoia.ISequoiaEnvironment` (interface), `RazerSequoia.IEnviroment.Models` (models)

**Interface: `IEnvironment`**

Events:
- `OnMonitorInfosChanged` -> `List<MonitorInfo>`
- `OnPcPowerInfoChanged` -> `PCPowerInfo`
- `OnNetworkStateChanged` -> `bool`
- `OnPcSessionEndChanged`
- `OnPcSuspendStateChanged` -> `bool`

Methods:
- `GetMonitorInfosAsync()` -> `Task<List<MonitorInfo>>`
- `GetMonitorPowerInfo()` -> `Task<PCPowerInfo>`
- `GetNetworkIsAvailable()` -> `Task<bool>`
- `GetDeviceFingerPrint()` -> `Task<string>`
- `GetMonitorsWorkAreaCache()` -> `List<Rectangle>`

**Model: `MonitorInfo`**
- `MonitorId`, `MonitorName` (string)
- `ResolutionX`, `ResolutionY` (int)
- `Rotate` (EnumMonitorRotates)
- `IsPrimaryMonitor` (bool)

**Enum: `EnumMonitorRotates`** - `Identity`, `Rotate90`, `Rotate180`, `Rotate270`, `ForceUint32`
  (JSON-serialized as string via `JsonStringEnumConverter`)

**Model: `PCPowerInfo`** - `IsPowerSupply` (bool)

---

## 6. RazerAxon.EnvironmentManager

**Purpose:** Windows environment monitoring implementation.

**Namespace:** `RazerSequoia.SequoiaEnvironmentManager` (main), `RazerSequoia.EnvironmentManager` (helpers), `RazerSequoia.SequoiaEnvironmentManager.Interop` (Win32)

### Class: `EnvironmentManager` (implements `IEnvironment`, `IAsyncDisposable`)

**Constructor:** hooks into `SystemEvents.DisplaySettingsChanged`, `SessionEnding`, `SessionSwitch`, `PowerModeChanged`, and `NetworkChange` events.

**Key methods:**
- `GetMonitorInfosAsync()` - uses `Screen.AllScreens` (WinForms), caches work areas
- `GetMonitorPowerInfo()` - checks `SystemInformation.PowerStatus.BatteryChargeStatus`
- `GetNetworkIsAvailable()` - calls `InternetGetConnectedState` (wininet.dll)
- `GetDeviceFingerPrint()` - generates base64 of `"{MAC}_{VolumeSerial}_{OSID}"` (cached)

**Session handling:**
- `SessionLock` -> fires `OnPcSuspendStateChanged(true)`
- `SessionUnlock` -> fires `OnPcSuspendStateChanged(false)`

### Static class: `PCHelper`

**Registry keys:**
- `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` - read for OS ID

**HMAC key:** `j6l-aUmhCc@tN%T_` - used in `GetSpecialFileName()` to HMAC-SHA256 the volume serial number

**Key methods:**
- `GetLogonUser()` - WTS API to get active console session user
- `GetOSID()` - reads MachineGuid from registry
- `GetVolumeSerialNumber()` - C: drive volume serial via `GetVolumeInformation`
- `GetDefaultMacAddress()` - uses `Razer.HardwareDetector.SlimHardwareDetector` to find NIC with most traffic
- `GetMemory()` - total RAM via `SlimHardwareDetector`
- `GetSpecialFileName()` - HMAC-SHA256 of volume serial, used as unique device file name

**Win32 imports:**
- `user32.dll`: `GetSystemMetrics` (screen dimensions)
- `kernel32.dll`: `GetVolumeInformation`
- `Kernel32.dll`: `WTSGetActiveConsoleSessionId`
- `Wtsapi32.dll`: `WTSQuerySessionInformation`, `WTSFreeMemory`
- `wininet.dll`: `InternetGetConnectedState`

### Static class: `EnvironmentWin32Interop`

Full Win32 display configuration API bindings:
- `GetDisplayConfigBufferSizes`, `QueryDisplayConfig`, `DisplayConfigGetDeviceInfo`
- Structs: `DISPLAYCONFIG_PATH_INFO`, `DISPLAYCONFIG_MODE_INFO`, `DISPLAYCONFIG_TARGET_DEVICE_NAME`, etc.
- Enums: `QUERY_DEVICE_CONFIG_FLAGS`, `DISPLAYCONFIG_VIDEO_OUTPUT_TECHNOLOGY`, `DISPLAYCONFIG_ROTATION`, `DISPLAYCONFIG_SCALING`, `DISPLAYCONFIG_PIXELFORMAT`, etc.

**Linux port notes:** Heavy Windows dependency. Need replacements for:
- `Screen.AllScreens` -> Wayland/X11 monitor enumeration
- `InternetGetConnectedState` -> NetworkManager/sysfs
- WTS session APIs -> systemd-logind
- Volume serial / MachineGuid -> `/etc/machine-id`
- `SlimHardwareDetector` -> `/sys/class/net/`, `/proc/meminfo`

---

## 7. RazerAxon.CrashReporter

**Purpose:** Crash/error reporting via Razer Analytics service.

**Namespace:** `RazerSequoia.CrashReporter`

### Static class: `CrashReporterEntry`

**Constants:**
- `ModuleAxon = "axon"`
- `ModuleNatasha = "natasha"` (Razer Central Service)
- `_hashKey = "j6l-aUmhCc@tN%T_"` (same HMAC key as EnvironmentManager)

**Default API:** `https://axon-api-staging.razer.com/v1`

**Registry keys:**
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{D4E0AA57-2D20-4CEC-B397-4B8959298863}` - if exists, sets header flag "Rise" and enables OAR (Open UI) events. This is likely Razer Cortex or another Razer product.

**Key methods:**
- `Init(apiDomain, appVersion, logDir, logger)` - stores config
- `SetUser(uuid)` - creates `RazerAnalytics` instance, sets keepalive, checks Rise registry
- `SendReportAsync(reportType, exception, module)` - sends crash/error diagnostics
  - For "natasha" module: reads Razer Central Service log
  - For "axon" module: reads `RazerAxon.log` (100 lines) + `RazerAxon.Player.log` (200 lines)
  - Appends "Updater running" to title if `Razer Updater` process is active
- `SendOpenUIEventAsync()` - sends OpenUI launch event (only if "Rise" detected)

**Log file paths read during crash report:**
- `{logDir}/RazerAxon.log` (last 100 lines)
- `{logDir}/RazerAxon.Player.log` (last 200 lines)
- `{CommonAppData}/Razer/Razer Central/Logs/Razer Central Service.log` (last 100 lines, for natasha)

**External dependency:** `Razer.Analytics` library (`RazerAnalytics`, `DiagnosticsInfo`, `DiagnosticsReportTypes`, `LaunchEventTypes`)

**Enum: `ReportTypes`** - `Error`, `Crash`

**Class: `RazerAnalyticsLogger`** - adapter bridging `ISequoiaLogger` to `IRazerAnalyticsLogger`

**Linux port notes:** Can be stubbed out entirely or replaced with simpler crash reporting. Registry checks irrelevant.

---

## 8. RazerAxon.INotification

**Purpose:** Notification manager interface.

**Namespace:** `RazerAxon.INotification` (interface), `RazerAxon.INotification.Models` (models)

**Interface: `INotificationManager`**
- Event: `OnNavigateRequested` -> string (URL/path to navigate to)
- `Init(checkIntervalSeconds, languageKey)`

**Model: `NotificationSettings`**
- `ShownNotificationMaxId` (int) - tracks highest shown notification ID
- `IsShowNotification` (bool, default true)

---

## 9. RazerAxon.NotificationManager

**Purpose:** Windows toast notification system for new wallpaper announcements and systray items.

**Namespace:** `RazerAxon.NotificationManager`

**Target platform:** Windows 10.0.22000+ (Windows 11)

### Class: `NotificationManager` (implements `INotificationManager`, `IDisposable`)

**Dependencies:** `ISequoiaLogger`, `ISettingManager`, `IUserManager`, `IDataAcquisition`

**Constructor behavior:**
- Notification temp images stored in `%LocalAppData%\NotificationTemp`
- Loads language manager from `PathConstants.LanguagesDir` with system locale
- Default check interval: 10800 seconds (3 hours), 30 seconds in debug mode
- Start delay: 180 seconds (3 minutes) before first notification display, 10 seconds in debug

**Init flow:**
1. Gets wallpaper resource path for protected temp root
2. Reads `NotificationSettings` from user settings
3. Hooks `ToastNotificationManagerCompat.OnActivated`
4. Sets Axon toast notification display info in registry
5. Starts periodic notification polling
6. Fetches systray wallpaper items

**API endpoints (relative to `GetWebServiceDomain()`):**
- `{domain}/notification/newest` - fetch new notifications (with `language_tag`, `filter_ids` params)
- `{domain}/wallpaper/central` - fetch systray wallpapers (with `language_tag`)

**Registry keys:**
- `HKCU\SOFTWARE\Classes\AppUserModelId\*` - scans for entries with DisplayName "RazerAxon" or "Razer Axon", updates to "RAZER AXON" with icon path `{AppDir}\Axon.ico` and background color `FF339933` (Razer green)

**Notification data model: `NewWallpaperNotificationInfo`**
- `Id`, `AppIconTitle`, `IconUrl`, `Title`, `Description`
- `InlineImageUrl`, `HeroImageUrl`
- `NavigateTarget` (URL)
- `IfNavigateWithDefaultBrowser` (bool)
- `NotificationType`, `IconType` ("circle" or other)

**Notification IDs:** formatted as `AxonNoti{NotificationType}{Id}`

**Toast actions:**
- Click -> navigate to `NavigateTarget` (in-app or default browser)
- "VIEW DETAILS" button (localized via `common_view_detail` language key)
- Tracks view/click/dismiss via `IDataAcquisition.SendEvent` with dimensions: notification type, notification ID

**Settings persistence:** `NotificationSettings` read/written via `ISettingManager.TryRead/TryWrite("NotificationSettings", userDir: true)`

**Default systray fallback:** wallpaper named "Razer Axon" with id "-1" and cover `PathConstants.DataDir/DefaultNotification.webp`

**Response parsing:** Regex-based code extraction: `['"]code['"]\s*:\s*(?<code>-?\d+)`, expects code 200, then reads `data` property from JSON.

### Internal types:
- `ISysNotificationItem` - internal notification item interface with image prep, display state, and lifecycle callbacks
- `SysNotificationItem<T>` - generic implementation with delegate-based callbacks:
  - `CreateContent`, `OnPrepare`, `OnShown`, `OnShowFailed`, `OnActivated`, `OnDimissed`
- `NotificationImgGenerator` - downloads and caches notification images

**Linux port notes:** Requires complete replacement. Use `libnotify`/D-Bus notifications on Linux. The toast notification system (`Microsoft.Toolkit.Uwp.Notifications`, `Windows.UI.Notifications`) is Windows-only.

---

## 10. RazerAxon.IDataAcquisition

**Purpose:** Telemetry/analytics interface and event taxonomy.

**Namespace:** `RazerSequoia.ISequoiaDataAcquisition` (interface), `RazerSequoia.ISequoiaDataAcquisition.Models` (enums/models)

**Interface: `IDataAcquisition`**
- `SendEvent(category, action, label?, value?, dimensions?)` - send telemetry event
- `Init(realInit)` - initialize (real init sends environment/install events)
- `GetIsNeedToToastRatingPage(ExpirationSeconds)` -> bool
- `SetIsToastRatingPage()` - mark rating as shown

### Event taxonomy enums:

**EventCategories:** `Environment`, `Marketplace`, `MyWallpaper`, `Playlist`, `Settings`, `Retention`, `Notification`

**EventDimensions:** `OsVersion`, `Monitor1`-`Monitor3`, `WallpaperType`, `WallpaperName`, `WallpaperResolution`, `WallPaperId`, `InstalledVersion`, `AutoLaunchApprove`

**EventRetentionActions:** `Install`, `Upgrade`, `Uninstall`

**EventEnvirenmentActions:** `Monitor`, `Software`, `DownloadFileCheck`, `SystemTray`, `Icon`, `Startup`, `SystemTrayCoverClick`

**EventMarketplaceActions:** `ViewWallpaper`, `ApplyWallpaper`, `RedeemWallpaper`, `DownloadWallpaper`

**EventMyWallpaperActions:** `AddWallpaper`

**EventPlaylistActions:** `StopPlaying`, `Mute`, `Chroma`

**EventSettingsActions:** `AutoLaunch`, `DuplicateMonitor`, `ScreenSaver`, `AutoLaunchRecord`, `SessionEnd`, `WallpaperPlay`, `WebLaunch`

**EventLabels:** `Enable`, `Resume`, `Disable`

**EventNotificationActions:** `NotificationClick`, `NotificationView`, `NotificationDimiss` (typo)

**Exception class:** `RazerDataException`

---

## 11. RazerAxon.DataAcquisition

**Purpose:** Telemetry implementation with local SQLite cache and Razer Kinesis (AWS Kinesis) backend.

**Namespace:** `RazerSequoia.DataAcquisition` (main), `RazerSequoia.DataAcquisition.RazerData` (Kinesis client), `RazerSequoia.DataAcquisition.Cache` (SQLite storage)

### Class: `DataAcquisitionManager` (implements `IDataAcquisition`, `IAsyncDisposable`)

**Dependencies:** `IUserManager`, `ISettingManager`, `IEnvironment`, `ISequoiaLogger`

**Init flow:**
1. Opens SQLite cache at `{DataSavedPath}/DataCollectionCache.db` (user dir)
2. Creates `KinesisClient` using `_settingManager.GetWebServiceDomain()`
3. If `realInit`:
   - Calls `_settingManager.TryRepairReg()`
   - Sends install/upgrade event
   - Sends auto-start setting event
   - Sends environment event (monitor list, OS version)

**SendEvent():**
- Creates `StorageData` with GUID event ID, app version, device fingerprint, Unix timestamp
- Stores in SQLite cache, then triggers async send via Kinesis
- If label is "LoadedPage", also calls `CrashReporterEntry.SendOpenUIEventAsync()`

**Registry keys:**
- `HKCU\Software\Razer\RazerAxon`:
  - `UUID` (string) - written with user ID
  - `ReportStatus` (string) - "0" means install event not yet sent
  - `ActionType` (string) - "install" or "upgrade"

**Install reporting:** Launches `RazerAxon.Reporter.exe` with `-install` or `-upgrade` argument.

**Rating page API:**
- URL: `https://bespoke-analytics.razerapi.com/api/v1/1100/app-rating/recommendation`
- Headers: `Bearer {userToken}`, `x-service-code: 1100`, `x-request-ts: {unix_ms}`
- Response: JWT, reads `enable` boolean from payload
- Service code `1100` = Razer Axon

### Class: `KinesisClient` (internal)

**Dependencies:** `Razer.Kinesis` library (`IRazerBigDataClient`, `RazerBigDataClient`, `RazerBigDataApps.Axon`)

- Creates `RazerBigDataClient` with app type `Axon` and credential provider
- `SendDataAsync()` - sends event via `_client.SendDataAsync` with session ID, user ID, token, fingerprint, timestamp, category, action, label, value, dimensions

### Class: `KinesisCredentialProvider` (implements `IRazerBigDataCredentialProvider`)

**STS endpoint:** `{apiDomainPath}/sts`

**Credential flow:**
1. Sends GET request to `/sts` with `uuid` and `access_token` params
2. Response contains: `ip`, `arn`, `token.AccessKeyId`, `token.SecretAccessKey`, `token.SessionToken`, `token.Expiration`
3. Returns `KinesisCredential` (AWS STS temporary credentials)

### SQLite Cache system

**Database:** `DataCollectionCache.db`

**Table:** `RazerEntry` (extends `StorageEntry`)
- Schema: `Id` (PK, auto-increment), `CreateTime` (DateTime), `Payload` (JSON string of `StorageData`)

**StorageData model:**
- `EventId`, `AppVersion`, `DeviceFingerprint`, `UnixTimestamp`, `Category`, `Action`, `Label`, `Value`, `Dimensions`

**Cache limits:**
- Database max: 1500 entries, shrinks by deleting oldest 500
- In-memory max: 150 entries, shrinks by removing oldest 50

**Queue system:** `BlockingCollection<Task>` with dedicated flush task for sequential DB operations.

**Linux port notes:**
- SQLite (`sqlite-net-pcl`) is cross-platform
- `Razer.Kinesis` (AWS Kinesis wrapper) is a proprietary Razer library - would need replacement or stub
- Registry reads need replacement
- `RazerAxon.Reporter.exe` is Windows-only
- `bespoke-analytics.razerapi.com` API is accessible cross-platform

---

## Cross-cutting observations

### Shared HMAC key
`j6l-aUmhCc@tN%T_` - used in both `PCHelper.GetSpecialFileName()` and `CrashReporterEntry` for Razer Analytics initialization.

### API domains
- Staging: `https://axon-api-staging.razer.com/v1`
- Analytics: `https://bespoke-analytics.razerapi.com`
- Dynamic: `_settingManager.GetWebServiceDomain()` for most API calls

### API endpoints (relative to dynamic domain)
- `/sts` - AWS STS credential exchange
- `/notification/newest` - notification polling
- `/wallpaper/central` - systray wallpapers

### External Razer libraries used
- `Razer.Analytics` - crash/error reporting
- `Razer.Kinesis` - AWS Kinesis telemetry
- `Razer.HardwareDetector` - hardware info (MAC, RAM)
- `Razer.Language` - i18n (`LanguageManager`)
- `RazerAxon.CommonUtility` / `RazerSequoia.CommonUtility` - shared utilities

### Device fingerprint formula
```
Base64("{DefaultMACAddress}_{VolumeSerialNumber}_{MachineGuid}")
```

### Key file paths
- `{logDir}/RazerAxon.log`, `{logDir}/RazerAxon.Player.log`
- `{CommonAppData}/Razer/Razer Central/Logs/Razer Central Service.log`
- `%LocalAppData%/NotificationTemp/`
- `{AppDir}/Axon.ico`
- `PathConstants.DataDir/DefaultNotification.webp`
- `PathConstants.LanguagesDir/` (language files)
- `{userDataDir}/DataCollectionCache.db`

### Key registry paths
- `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{D4E0AA57-2D20-4CEC-B397-4B8959298863}`
- `HKCU\Software\Razer\RazerAxon` (UUID, ReportStatus, ActionType)
- `HKCU\SOFTWARE\Classes\AppUserModelId\*` (toast notification identity)
