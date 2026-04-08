# Razer Axon WebView2 Host Objects -- Complete API Reference

Extracted from decompiled `RazerAxon.WebviewWindowManager.decompiled.cs` and `RazerAxon.IWebviewWindowManager.decompiled.cs`.

All host objects are exposed to JavaScript via WebView2's `AddHostObjectToScript`. JS accesses them as `chrome.webview.hostObjects.{name}`.

## Return Value Convention

All methods returning `string` use a standard JSON envelope:
```json
{"code": 0, "data": ...}
```
- `code = 0` -- success
- `code < 0` -- error (-1 generic, -2 parse/model error, -3 storage/operation error)

Async methods that take an `object callback` parameter invoke the callback from C# with the same JSON envelope via COM IDispatch interop (`Razer.DispatchInvoker.dll`).

---

## 1. DownloadManagerHostObject

**JS name:** `downloadMangerHostObject` (note: "Manger" typo in original)

**C# class:** `DownloadManagerHostObject` (line 1629)
**Implements:** `IDownloadManagerHostObject`, `IBaseHostObejct`

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `GetHostObjectName` | `() -> string` | `"downloadMangerHostObject"` | Returns the JS-accessible name |
| `AddDownloadTask` | `(string wallpaperId, int width, int height, string wallpaperWebItemSource, bool applyWhenEnd, bool addToPlayLstWhenEnd, int sourceType = 0, string playLstIdsStr = "")` -> `string` | JSON envelope (code 0/-1/-2/-3) | Adds a wallpaper download task. `wallpaperWebItemSource` is a JSON-serialized `WallPaperWebItem`. Deserializes the item, saves it to wallpaper manager, then creates a `DownloadItem` and enqueues it. `applyWhenEnd` applies the wallpaper after download; `addToPlayLstWhenEnd` adds to playlist. `playLstIdsStr` is JSON array of playlist IDs. Returns -1 for invalid params, -2 for model/duplicate errors, -3 for path errors. |
| `GetDownloadItems` | `() -> string` | JSON envelope with `List<DownloadItem>` | Returns all current download queue items |
| `PauseDownloadTask` | `(string wallpaperId) -> string` | JSON envelope | Pauses an active download |
| `ResumeDownloadTask` | `(string wallpaperId) -> string` | JSON envelope | Resumes a paused download |
| `RemoveDownloadTask` | `(string wallpaperId) -> string` | JSON envelope | Removes a download from the queue |
| `DownloadImage` | `(string saveFilePath, string wallpaperId, int width, int height, int sourceType, object callback) -> string` | Immediate: JSON envelope; async result via callback | Downloads a wallpaper image to `saveFilePath`. First checks if already installed locally (copies directly for jpg/png/bmp/webp/jpeg). Otherwise downloads from server. Callback receives the result asynchronously. |
| `RegisterDownloadStatusChangedHandler` | `(object callback) -> string` | JSON envelope | Registers JS callback for download status changes |
| `UnregisterDownloadStatusChangedHandler` | `() -> string` | JSON envelope | Unregisters the download status callback |

### Events (C# -> JS via callback)

- **OnDownloadStatusChanged**: Fires when any download status changes. Callback receives `List<DownloadItem>` in JSON envelope.

---

## 2. PlayListHostObejct

**JS name:** `playListHostObject`

**C# class:** `PlayListHostObejct` (line 2000, note typo in class name)
**Implements:** `IPlayListHostObject`, `IBaseHostObejct`

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `GetHostObjectName` | `() -> string` | `"playListHostObject"` | Returns the JS-accessible name |
| `GetPlayLists` | `() -> string` | JSON envelope with `List<WebPlayListInfo>` | Gets all playlists for all monitors |
| `GetMonitorInfos` | `() -> string` | JSON envelope with `List<MonitorInfo>` | Gets information about connected monitors |
| `GetPlayListSetting` | `() -> string` | JSON envelope with `TmpPlayListSetting` `{IntervalMini, Order, IsCustomInterval}` | Gets playlist rotation settings. `IntervalMini` is in minutes (-1 = disabled). `Order` is "Ordered" or "Random". |
| `SetPlayListSetting` | `(int intervalMini, bool isCustomInterval, string order) -> string` | JSON envelope | Sets playlist rotation. `intervalMini` in minutes (converted to seconds internally, -1 = disabled). `order`: "Random" or "Ordered". |
| `AddToPlayList` | `(string monitorId, string wallpaperId, object callback) -> void` | Result via callback | **Async.** Adds a wallpaper to a monitor's playlist. Callback receives code 0 (success) or -3 (error). |
| `RemoveFromPlayList` | `(string monitorId, string wallpaperId, object callback) -> void` | Result via callback | **Async.** Removes a wallpaper from a monitor's playlist. |
| `ApplyWallPaper` | `(string wallpaperId, object callback, string monitorIdsStr = "") -> void` | Result via callback | **Async.** Applies a wallpaper. If `monitorIdsStr` is a JSON array of monitor IDs, adds to each specified monitor's playlist. Otherwise calls `ApplyWallPaper` on the playlist manager (applies to default/selected monitor). |
| `SetWallPaperIndex` | `(string monitorId, string wallpaperId, int newIndex) -> string` | JSON envelope | Reorders a wallpaper within a monitor's playlist |
| `SetPlayListSelected` | `(string monitorId) -> string` | JSON envelope | Sets which monitor's playlist is currently selected/active in the UI |
| `SetPlayListChromaEnabled` | `(string monitorId) -> string` | JSON envelope | Enables Chroma RGB effects for a monitor's playlist |
| `ClearPlayList` | `(string monitorId) -> string` | JSON envelope | Removes all wallpapers from a monitor's playlist |
| `SetPlayListMute` | `(string monitorId, bool isMute, int volume) -> string` | JSON envelope | Sets mute state and volume for a monitor's playlist |
| `StartPlay` | `(string monitorId) -> string` | JSON envelope | Starts wallpaper playback on a monitor |
| `StopPlay` | `(string monitorId) -> string` | JSON envelope | Stops wallpaper playback on a monitor |
| `SetScreenSaverEnable` | `(int isEnable) -> string` | JSON envelope | Enables/disables screen saver mode (1 = enable, 0 = disable) |
| `RegisterPlayListChangedHandlers` | `(object callback) -> string` | JSON envelope | Registers JS callback for playlist changes |
| `UnregisterPlayListChangedHandlers` | `() -> string` | JSON envelope | Unregisters the playlist callback |

### Events (C# -> JS via callback)

- **OnPlayListsChanged**: Fires when playlists change. Callback receives `List<WebPlayListInfo>` in JSON envelope.

---

## 3. UserManagerHostObejct

**JS name:** `userManagerHostObejct` (note typo preserved)

**C# class:** `UserManagerHostObejct` (line 2355)
**Implements:** `IUserManagerHostObejct`, `IBaseHostObejct`

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `GetHostObjectName` | `() -> string` | `"userManagerHostObejct"` | Returns the JS-accessible name |
| `GetUser` | `() -> string` | JSON envelope with `SequoiaUser` | Gets current user info (also refreshes user token) |
| `GetUserProfile` | `() -> string` | JSON envelope with user Profile object | Gets the user's profile |
| `GetUserBalance` | `(object callback) -> void` | Result via callback | **Async.** Gets user's zVault/currency balance. Callback receives `UserBalances` object. |
| `RegisterUserLoginHandler` | `(object callback) -> string` | JSON envelope | Registers callback for user login/change events |
| `UnregisterUserLoginHandler` | `() -> string` | JSON envelope | Unregisters user login callback |
| `ExitApp` | `() -> void` | (nothing) | Triggers application exit. Fires `AppExitTriggered` C# event. |
| `Logout` | `() -> void` | (nothing) | **Async.** Logs out the current user |
| `OpenFeedBack` | `(int type) -> void` | (nothing) | **Async.** Opens feedback window. `type`: 0 = general feedback, 1 = feature feedback, 2 = support feedback. |
| `OpenUpdate` | `() -> void` | (nothing) | **Async.** Opens the update/check-for-updates window |
| `OpenProfile` | `() -> void` | (nothing) | **Async.** Opens the user profile window |
| `OpenChangePassword` | `() -> void` | (nothing) | **Async.** Opens the change password window |
| `OpenUserZVaultWeb` | `() -> void` | (nothing) | Opens the zVault web page in the default browser. Gets URL from `_userManager.GetZVaultWebUrl()`. |
| `SendBigData` | `(string category, string action, string label, long value, string dimensions) -> void` | (nothing) | Sends analytics/telemetry event. `dimensions` is a JSON string of `Dict<string,string>`. |
| `GetIsNeedToToastRatingPage` | `(int ExpirationSeconds) -> string` | JSON envelope with bool | Checks if the app rating prompt should be shown (based on expiration) |
| `SetIsToastRatingPage` | `() -> string` | JSON envelope | Marks the rating page as shown (prevents future prompts) |
| `PrintLog` | `(string log) -> void` | (nothing) | Writes a log message from the UI layer to the C# logger |

### Events (C# -> JS via callback)

- **UserChanged**: Fires when user login state changes. Callback receives `SequoiaUser` in JSON envelope.

### C# Events (internal)

- **AppExitTriggered**: `EventHandler<EventArgs>` -- fired when `ExitApp()` is called from JS.

---

## 4. UserSettingHostObject

**JS name:** `userSettingHostObject`

**C# class:** `UserSettingHostObject` (line 2719)
**Implements:** `IUserSettingHostObject`, `IBaseHostObejct`

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `GetHostObjectName` | `() -> string` | `"userSettingHostObject"` | Returns the JS-accessible name |
| `GetUserGeneralSetting` | `() -> string` | JSON envelope with `UserGeneralSetting` | Returns `{Language, WallPaperDirectory, AutoStartWithSystem, MinimizeWhenAutoStart, MaxVolume, IsShowNotification, IsExitDirectly}` |
| `SetLanguage` | `(string language) -> string` | JSON envelope | Sets UI language asynchronously |
| `SetAutoStartWithSystem` | `(bool enable) -> string` | JSON envelope | Enables/disables auto-start with Windows |
| `SetMinimizeWhenAutoStart` | `(bool enable) -> string` | JSON envelope | Start minimized when auto-started |
| `SetMaxVolume` | `(int volume) -> string` | JSON envelope | Sets maximum wallpaper audio volume |
| `SetSaveSourcePath` | `(string path) -> string` | JSON envelope | Sets the wallpaper download/save directory |
| `GetIsPauseWhenFullScreen` | `() -> string` | JSON envelope with bool | Whether to pause wallpaper when a window is fullscreen |
| `SetIsPauseWhenFullScreen` | `(bool enable) -> string` | JSON envelope | Set pause-on-fullscreen behavior |
| `GetIsPauseWhenD3DFullScreen` | `() -> string` | JSON envelope with bool | Whether to pause all wallpapers when D3D fullscreen (games) |
| `SetIsPauseWhenD3DFullScreen` | `(bool enable) -> string` | JSON envelope | Set pause-on-D3D-fullscreen behavior |
| `GetIsDuplicateSelectScreen` | `() -> string` | JSON envelope with bool | Whether duplicate mode is enabled for multi-monitor |
| `SetIsDuplicateSelectScreen` | `(bool enable) -> string` | JSON envelope | Set duplicate screen mode |
| `GetIsSpanSelectScreen` | `() -> string` | JSON envelope with bool | Whether span mode is enabled (wallpaper spans across monitors) |
| `SetIsSpanSelectScreen` | `(bool enable) -> string` | JSON envelope | Set span screen mode |
| `GetPlayMode` | `() -> string` | JSON envelope with string ("None"/"Span"/"Duplicate") | Gets the current multi-monitor play mode |
| `SetPlayMode` | `(string mode) -> string` | JSON envelope | Sets multi-monitor play mode. Values: "None", "Span", "Duplicate" |
| `GetScreenSaverEnabled` | `() -> string` | JSON envelope with bool | Whether screen saver feature is enabled |
| `SetScreenSaverEnabled` | `(bool enable) -> string` | JSON envelope | Enable/disable screen saver |
| `GetOnboardingIsShown` | `() -> string` | JSON envelope with bool | Whether onboarding has been shown |
| `SetOnboardingIsShown` | `() -> string` | JSON envelope | Mark onboarding as shown |
| `GetWhatsNewIsShown` | `() -> string` | JSON envelope with bool | Whether "what's new" page has been shown |
| `SetWhatsNewIsShown` | `() -> string` | JSON envelope | Mark "what's new" as shown |
| `GetIfPlayerEnvironmentSupported` | `() -> string` | JSON envelope with bool | Checks if the wallpaper player environment (GPU, etc.) is supported |
| `RegisterLanguageChangedHandler` | `(object callback) -> string` | JSON envelope | Registers callback for language change events |
| `UnregisterLanguageChangedHandler` | `() -> string` | JSON envelope | Unregisters language change callback |
| `GetIsShowNotification` | `() -> string` | JSON envelope with bool | Whether notifications are enabled |
| `SetIsShowNotification` | `(bool isShowNotification) -> string` | JSON envelope | Enable/disable notifications |
| `GetPcUniqueCode` | `() -> string` | JSON envelope with string | Gets a unique identifier for this PC |
| `GetDefaultApplyMonitorIds` | `() -> string` | JSON envelope with `List<string>` | Gets default monitor IDs for wallpaper application. Falls back to primary monitor if empty. |
| `SetDefaultApplyMonitorIds` | `(string ids) -> string` | JSON envelope | Sets default apply monitors. `ids` is a JSON array of monitor ID strings. |
| `OpenApplication` | `(string applicationName, string navigateUrlByDefault, string launchParams) -> string` | JSON envelope | Launches a third-party app. `applicationName` can be "razercortex" or `"Others;regKeyRoot;regKeyPath;valueName;is64bit"` format. Falls back to `navigateUrlByDefault` URL if app not installed. |
| `GetAppVersion` | `() -> string` | JSON envelope with version string | Gets the application version |
| `GetWallpaperPlayer` | `() -> string` | JSON envelope with string | Gets current wallpaper player engine name |
| `SetWallpaperPlayer` | `(string player) -> string` | JSON envelope | Sets wallpaper player. Values: "WindowsMediaFoundation" or "WebView2" |
| `GetWallpaperThirdpartInfo` | `(string thirdpartName) -> string` | JSON envelope with string | Gets third-party integration info. Currently only "Spotify" supported. |
| `SetWallpaperThirdpartInfo` | `(string thirdpartName, string content) -> string` | JSON envelope | Sets third-party integration info. Content is URL-decoded. Currently only "Spotify". |
| `SetIsExitDirectly` | `(int isExitDirectly) -> string` | JSON envelope | Sets whether clicking close exits the app directly (vs minimize to tray) |

### Events (C# -> JS via callback)

- **LanguageChanged**: Fires when language changes. Callback receives the language string in JSON envelope.

---

## 5. WallPaperManagerHostObejct

**JS name:** `wallpaperManagerHostObject`

**C# class:** `WallPaperManagerHostObejct` (line 3428, note typo in class name)
**Implements:** `IWallpaperManagerHostObject`, `IBaseHostObejct`

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `GetHostObjectName` | `() -> string` | `"wallpaperManagerHostObject"` | Returns the JS-accessible name |
| `GetAllItems` | `(bool removeUninstallItem = false) -> string` | JSON envelope with `List<WallPaperWebItem>` | Gets all wallpaper items in the library. If `removeUninstallItem` is true, excludes uninstalled items. |
| `GetWallpaperItem` | `(string wallpaperId) -> string` | JSON envelope with `WallPaperWebItem` | Gets a single wallpaper item by ID |
| `AddOrUpdateItem` | `(string wallPaperItem) -> string` | JSON envelope | Adds or updates a wallpaper item. `wallPaperItem` is a JSON-serialized `WallPaperWebItem`. |
| `AddOrUpdateItems` | `(string wallPaperItems) -> string` | JSON envelope | Batch add/update. `wallPaperItems` is a JSON array of `WallPaperWebItem`. |
| `AddLocalItem` | `(string title, string sourcePath, string author, string authorAvatar, string coverPath, string wallPaperType, string effectType, bool interactiveEnable, bool needCrop, int left, int top, int width, int height) -> string` | JSON envelope with `WallPaperWebItem` (the created item) | Adds a local wallpaper file. `wallPaperType`: "IMAGE", "VIDEO", or anything else = LOCALWEB. `effectType`: effect type string. `needCrop` + rect params for image cropping. `interactiveEnable` for web wallpaper interaction. |
| `ModifyLocalItem` | `(string wallpaperId, string title, string sourcePath, string author, string authorAvatar, string coverPath, string wallPaperType, string effectType, bool needCrop, int left, int top, int width, int height) -> string` | JSON envelope (result code) | Modifies an existing local wallpaper item |
| `Remove` | `(string wallpaperId, bool onlyRemovePlaySource = false) -> string` | JSON envelope | Removes a wallpaper. If `onlyRemovePlaySource` = true, only removes the play source files but keeps the library entry. |
| `CheckItemsStatus` | `(string ids) -> string` | JSON envelope with status list | Checks install/play status of wallpapers. `ids` is a comma-separated string of wallpaper IDs. |
| `AddOrModifyChromaEffects` | `(string wallpaperId, string stream) -> string` | JSON envelope | Adds/modifies Chroma RGB effect files for a wallpaper. `stream` is a base64-encoded ZIP archive containing chroma effect files. Empty stream clears effects. |
| `SaveTempLocalImg` | `(string localImgPath) -> string` | JSON envelope with string (temp path) | Copies a local image to a temp location for preview/editing. Returns the temp path. |
| `GetVideoPreviewImg` | `(string localVideoPath) -> string` | JSON envelope with string (preview image path) | Extracts a preview frame from a local video file. Returns path to the generated BMP. |
| `RemoveTempLocalImg` | `(string localImgPath) -> void` | (nothing) | **Async.** Deletes a temporary local image |
| `OpenWallPaperFileLocation` | `(string wallpaperId) -> void` | (nothing) | Opens Explorer at the wallpaper's file location. For web URLs, opens in browser. |
| `SetWallpaperItemPlaySetting` | `(string wallpaperId, string propertyname, object value) -> string` | JSON envelope | Sets a wallpaper's play setting. Supported `propertyname` values: **Properties:** `"is_chromaEnabled"` (bool), `"is_mute"` (bool). **Effects:** `"StaticImgFillMode"` ("Fit"/"Fill"/"Stretch"/"Center"/"Tile"), `"Brightness"` (int), `"Contrast"` (int), `"Hue"` (int), `"Saturation"` (int), `"PlayRate"` (int), `"WebInteraction"` (string). |
| `ResetVideoWallPaperEffects` | `(string wallpaperId) -> string` | JSON envelope | Resets all video effects (brightness, contrast, etc.) to defaults |
| `RegisterEventHandler` | `(object itemSettingChangedHandler, object itemsAddHandler, object itemsRemoveHandler) -> string` | JSON envelope | Registers three JS callbacks for wallpaper events |
| `UnRegisterEventHandler` | `() -> string` | JSON envelope | Unregisters all three wallpaper callbacks |

### Events (C# -> JS via callbacks)

- **OnWallpaperItemSettingChanged**: Fires when wallpaper settings change (effects, properties). `itemSettingChangedHandler` receives `List<WallPaperWebItem>`.
- **OnWallpaperItemAdded**: Fires when wallpapers are added to the library. `itemsAddHandler` receives `List<WallPaperWebItem>`.
- **OnWallpaperItemRemoved**: Fires when wallpapers are removed. `itemsRemoveHandler` receives `List<string>` (wallpaper IDs).

---

## 6. WindowActionHostObject

**JS name:** `windowActionHostObject`

**C# class:** `WindowActionHostObject` (line 4191)
**Implements:** `IWindowActionHostObject`, `IBaseHostObejct`

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `GetHostObjectName` | `() -> string` | `"windowActionHostObject"` | Returns the JS-accessible name |
| `SetMinimize` | `() -> string` | JSON envelope | Minimizes the window |
| `SetNormal` | `() -> string` | JSON envelope | Restores the window to normal state |
| `SetMax` | `() -> string` | JSON envelope | Maximizes the window |
| `CloseWindow` | `() -> string` | JSON envelope | Closes the window |
| `GetWindowState` | `() -> string` | JSON envelope with `WebWindowState` `{width, height, windowState, networkConnected}` | Gets current window dimensions, state ("Normal"/"Minimized"/"Maximized"), and network connectivity |
| `OpenFileDirectory` | `(string path) -> void` | (nothing) | Opens Explorer at the given file/directory path |
| `OpenWithDefaultBrowser` | `(string uri) -> void` | (nothing) | Opens a URL in the default browser |
| `CheckFileAccess` | `(string path) -> string` | JSON envelope with bool | Checks if the app has write permission to the given path |
| `OpenNewWindow` | `(string windowName, string Uri, int width, int height) -> void` | (nothing) | Opens a new child WebView2 window with the given URI and dimensions |
| `OpenPayWindow` | `(string uri, object closeCallback) -> void` | (nothing) | Opens a payment window (1280x720) with the given URI. `closeCallback` is invoked when the pay window closes, receiving the final URI. Truncates URI at "PaymentWall/Checkout" path. |
| `OpenLoginWindow` | `(string uri, object closeCallback) -> void` | (nothing) | Opens a login window (1280x720). `closeCallback` invoked on close with the URI. |
| `ShowOpenfileDialog` | `(string title, string filter, bool pickfolder, object callback) -> void` | Result via callback | Shows a file open dialog (or folder picker if `pickfolder` = true). Callback receives the selected file/folder path. `filter` uses Windows dialog filter format. |
| `ShowOpenSaveFileDialog` | `(string title, string filter, string defaultFileName, object callback) -> void` | Result via callback | Shows a save file dialog. Callback receives the chosen path. |
| `TryUploadLocalFile` | `(string filePath, int fileSizeLimitKb, object? uploadResultCallback) -> void` | Result via callback | **Async.** Uploads a local image file to Razer's server. Validates file exists, checks size limit (in KB), validates it's a valid image, gets a pre-signed S3 upload URL from `/wallpaper/creator/uploadurl`, uploads via PUT, then notifies server at `/wallpaper/generate/upload`. Callback receives upload info on success. Returns -2 for size limit exceeded or invalid format. |
| `SaveFileToLocal` | `(string filePath, string stream) -> string` | JSON envelope | Saves a base64-encoded byte stream to a local file |
| `SetStrToClipboard` | `(string content) -> string` | JSON envelope | Copies a string to the system clipboard |
| `TriggerNavigate` | `(string targetUri) -> void` | (nothing) | Triggers a navigation command to the registered navigate handler (internal routing) |
| `RegisterWindowStateChangedEvent` | `(object callback) -> string` | JSON envelope | Registers callback for window state changes (resize, minimize, maximize, network change) |
| `UnRegisterWindowStateChangedEvent` | `() -> string` | JSON envelope | Unregisters window state callback |
| `RegisterNavigateCommandEvent` | `(object callback) -> string` | JSON envelope | Registers callback for navigation commands (internal page routing) |
| `UnRegisterNavigateCommandEvent` | `() -> string` | JSON envelope | Unregisters navigate command callback |
| `RegisterNewWindowRequestEvent` | `(object callback) -> string` | JSON envelope | Registers callback for new window request events from WebView2 |
| `UnRegisterNewWindowRequestEvent` | `() -> string` | JSON envelope | Unregisters new window request callback |

### Events (C# -> JS via callbacks)

- **OnWebviewWindowStateChanged**: Fires on window resize/state change and network connectivity change. Callback receives `WebWindowState` JSON.
- **OnNavigateCommandSended**: Fires when C# triggers a page navigation. Callback receives the command/URI string.
- **OnWebviewNewWindowRequest**: Fires when WebView2 requests to open a new window. Callback receives the requested URI.
- **OnPayWindowClosed**: Static event -- fires when a pay/login window closes. Callback receives the final URI.

---

## IWebviewWindowManager Interface

From `RazerAxon.IWebviewWindowManager.decompiled.cs`:

```csharp
public interface IWebviewWindowManager
{
    Task OpenWindowAsync(string windowName, EnumWebviewWindowTypes windowType, WebWindowStartupSettings setting);
    Task CloseWindowAsync(string windowName);
    Task CloseAllWindowAsync();
    void SetMainWindowHandler(Form owner);
}
```

**Window types:**
- `MainWindow`
- `ChildWindow`
- `ChildTransparentWindow`
- `PayWindow`
- `LoginWindow`

**Window startup settings:**
```csharp
public class WebWindowStartupSettings
{
    public string? StartupUri { get; set; }
    public int Width { get; set; }
    public int Height { get; set; }
    public string? WebServiceDomain { get; set; }
}
```

---

## Summary: JS Access Pattern

```javascript
// Access host objects from JavaScript in WebView2:
const download   = chrome.webview.hostObjects.downloadMangerHostObject;
const playlist   = chrome.webview.hostObjects.playListHostObject;
const user       = chrome.webview.hostObjects.userManagerHostObejct;
const settings   = chrome.webview.hostObjects.userSettingHostObject;
const wallpaper  = chrome.webview.hostObjects.wallpaperManagerHostObject;
const window_act = chrome.webview.hostObjects.windowActionHostObject;

// All sync methods return JSON: {"code": 0, "data": ...}
// Async methods take a callback as last param: function(jsonResult) { ... }

// Example:
let result = JSON.parse(await wallpaper.GetAllItems(true));
if (result.code === 0) {
    let items = result.data; // List of wallpaper items
}

// Async with callback:
playlist.ApplyWallPaper("wallpaper-id-123", function(result) {
    let parsed = JSON.parse(result);
    console.log(parsed.code);
}, '["monitor-id-1"]');
```

---

## Key Data Types (for Linux reimplementation)

### WallPaperWebItem
Serialized JSON object representing a wallpaper, exchanged between JS and C#. Contains at minimum: wallpaper ID, title, author, cover path, type, status, effects.

### WallPaperTypes
- `LOCALIMAGE`, `LOCALVIDEO`, `LOCALWEB` (local files)
- Standard types for downloaded wallpapers

### WallPaperStatusEnum
- `Uninstalled`, `Downloading`, `Installed`, `Playing`

### PlayModeEnums
- `None` -- independent per monitor
- `Span` -- wallpaper spans all monitors
- `Duplicate` -- same wallpaper on all monitors

### WallpaperEffectsEnum
- `Brightness`, `Contrast`, `Hue`, `Saturation`, `PlayRate`, `WallpaperFillingMode`, `WebInteraction`

### StaticImgFillModesEnum
- `Fit`, `Fill`, `Stretch`, `Center`, `Tile`

### WallpaperPlayers
- `WindowsMediaFoundation` -- native Windows media player
- `WebView2` -- browser-based renderer

### PlayOrders
- `Ordered`, `Random`
