# Razer Central Service — IPC Protocol Reference

Reverse-engineered from decompiled .NET assemblies (v7.20.2.1109):
- `NacClient.dll` — client-side NAC connector
- `RcClientBase.dll` — pipe socket implementation
- `AccountManagerCommon.dll` — AccountManager commands & types
- `AccountManagerClient.dll` / `AccountManagerUiClient.dll` — client implementations
- `AccountManager.dll` — server-side handler
- `ActionServiceCommon.dll` — NAC commands, pipe names, service types
- `NotificationCommon.dll` — notification commands
- `UpdateCommon.dll` — update manager commands

---

## Wire Protocol

### Packet Format (from `ClientPipeSocket.Send`)

```
┌─────────────────────────────────────────────┐
│ Header (24 bytes, little-endian)            │
│   int32  version      = 2                   │
│   int32  serviceType  (RzServiceType enum)  │
│   int32  dataLength   (payload size)        │
│   int32  headerLength = 24                  │
│   int64  packetId     (incrementing, != 0)  │
├─────────────────────────────────────────────┤
│ Payload (dataLength bytes)                  │
│   uint32 command      (Commands enum)       │
│   int32  packetNumber (request sequence #)  │
│   byte[] commandData  (command-specific)    │
└─────────────────────────────────────────────┘
```

### Response Flags (in command uint32)

| Bit | Mask | Meaning |
|-----|------|---------|
| 31 | `0x80000000` | Response flag |
| 30 | `0x40000000` | Exception flag |
| 0-29 | `0x3FFFFFFF` | Command ID |

### String Encoding

Strings are encoded with .NET `BinaryWriter.Write(string)`:
7-bit encoded length prefix (LEB128 unsigned) followed by UTF-8 bytes.

### Exception Format

When exception flag is set, commandData contains:
```
uint32  ExceptionType  (0=General, 1=Cop, 2=NotImplemented)
string  message
int32   code           (only for Cop exceptions)
```

---

## Named Pipes

| Pipe | GUID | Direction | Used By |
|------|------|-----------|---------|
| Service | `{CD7C71F0-A5B9-4F24-897A-DF6E20E43B96}` | Client → Service | Axon, Synapse, Cortex |
| NAC | `{FC828A97-C116-453D-BD88-AD471496E03C}` | UI Client → Service | Razer Central GUI |
| NAC Client | `{E7A6CCA9-FF3F-4741-8E66-1127EE39471D}` + username | Service → NAC | Service launching NAC |

Debug variants use `{DBG-...}` prefix (disabled in production).

### Service Mutex

NAC running check: `Global\{63D31EEC-008F-43C9-A58E-ED6949B25A6C}` + username

---

## Service Types (multiplexing channels)

| Type | ID | Description |
|------|----|-------------|
| UpdateManager | 2 | Software updates |
| AccountManager | 4 | Auth, settings, profile, sync |
| Notifications | 5 | Push notifications |
| ActionCenter | 6 | UI commands (show, shutdown, systray) |

---

## AccountManager Commands (62 commands)

### Authentication

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| StartLogin | 1 | — | — | Begin login flow (triggers UI) |
| StartLogout | 2 | — | — | Begin logout |
| GetCurrentUser | 3 | — | RazerUser XML | Get current authenticated user |
| RefreshToken | 4 | — | LoginResult uint32 | Refresh JWT token |
| TryLogin | 44 | — | LoginResult uint32 | Auto-login attempt |
| TryAutoLoginAsGuest | 61 | — | LoginResult uint32 | Guest auto-login |
| StartUi | 43 | — | — | Launch Razer Central UI |
| UI_LoginAsGuest | 131072 | — | — | Login as guest |
| UI_CancelLogin | 131073 | — | — | Cancel login flow |
| WebApp_SetLoginSuccessFromWeb | 131094 | string (JSON) | string | **Inject token from web login** |
| UI_SetToken | 131101 | string | — | Set token directly |
| WebApp_GenerateToken | 131097 | — | string | Generate new token |
| WebApp_GetLastClientLoginUser | 131096 | — | string (JSON) | Last logged-in user details |
| GetTokenDuration | 262144 | — | double (seconds) | Token validity duration |
| SetTokenDuration | 262145 | double (seconds) | — | Set token duration |

#### LoginResult Enum
```
Success = 0, Canceled = 1, Failed = 2, RefreshFailed = 3,
FailedNoCredentials = 4, OtpRequired = 5, RefreshSucceeded = 6
```

#### LoginTypes Enum
```
Undefined = 0, Email = 1, Phone = 2, Facebook = 3, Google = 4, Twitch = 5
```

#### WebApp_SetLoginSuccessFromWeb Request Format

The JSON string (WebAppTokenInfo) sent via this command:
```json
{
  "convertFromGuest": false,
  "token": "eyJhbGciOiJFUzI1NiI...",
  "isOnline": true,
  "isGuest": false,
  "uuid": "RZR_...",
  "loginId": "user@example.com",
  "tokenExpiry": "2026-04-08T21:33:05.000Z",
  "stayLoggedIn": true
}
```

### Profile

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| GetUserProfile | 5 | — | RazerUserProfile XML | Get user profile |
| RefreshUserProfile | 41 | — | — | Refresh from server |
| WebApp_SetUserProfileFromWeb | 131093 | string (JSON) | — | Set profile from web |
| GetAccountCredentials | 42 | — | serialized | Get connected account credentials |

### Settings (Cloud Sync)

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| GetSettingList | 7 | string product, string path, uint type | RzSetting[] | List settings |
| GetSetting | 8 | string product, string path, string name, uint source, uint policy | RzSetting | Get single setting |
| SetSetting | 9 | string product, RzSetting, uint type | SaveResult uint32 | Save setting |
| DeleteSetting | 13 | string product, RzSetting, uint type | SaveResult uint32 | Delete setting |
| SettingDeleteAll | 31 | string product, string path, uint type | SaveResult uint32 | Delete all settings |
| SetSettingBaseAddress | 37 | string | — | Set setting base URL |
| GetSettingStatistics | 57 | — | serialized | Get sync statistics |
| StartSync | 14 | string product | — | Start cloud sync |
| CancelSync | 15 | — | — | Cancel sync |
| StartFileSync | 54 | string product | — | File-level sync |
| ResolveConflict | 12 | string product, RzSetting, uint type | SaveResult uint32 | Resolve sync conflict |
| GetLastSyncDate | 30 | string product | string (date) | Last sync timestamp |

#### SaveResult Enum
```
Success = 0, ServerNotAvailable = 1, ConflictDetected = 2,
Failed_Unknown = 3, Failed_OfflineMode = 4
```

### Connected Accounts (OAuth)

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| ConnectToAccount | 24 | int account, string[] permissions, bool force | — | Link Facebook/Google/Twitch |
| IsConnectedToAccount | 25 | int account | bool | Check if linked |
| RefreshAccountToken | 26 | int account | — | Refresh OAuth token |
| DisconnectFromAccount | 27 | int account | — | Unlink account |
| UI_ConnectedAccountComplete | 131090 | string | — | OAuth flow complete |
| UI_CreateLinkedAccount | 131091 | string | — | Create linked account |

### UI & Preferences

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| GetUiLanguage | 19 | — | string | Get UI language |
| UI_SetLanguage | 131089 | string | — | Set UI language |
| GetUiTheme | 50 | — | string | Get theme ("Dark") |
| SetUiTheme | 51 | string | — | Set theme |
| UI_GetMachineId | 131092 | — | string | Machine identifier |
| UI_GetGuestStatistics | 131098 | — | string | Guest usage stats |
| UI_UpdateCertificate | 131100 | string | — | Update cert |
| WebApp_DeleteCert | 131095 | — | — | Delete certificate |

### Feature Flags

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| FeatureEnabled | 52 | string clientId, string feature | bool | Check feature flag |
| SetFeature | 53 | string clientId, string feature, bool | — | Set feature flag |
| GetFeatureValue | 59 | string clientId, string feature | string | Get feature value |
| SetFeatureValue | 60 | string clientId, string feature, string value | — | Set feature value |

### Miscellaneous

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| RegisterServiceCode | 18 | string | — | Register product service code |
| RegisterSocket | 45 | string productName, Version? | — | Register client socket |
| PushBigData | 17 | serialized | uint status | Upload telemetry data |
| RegisterPlugin | 28 | — | — | Register plugin |
| RegisterUnplug | 29 | — | — | Unregister plugin |
| GetDeviceInfo | 32 | — | serialized | Get device information |
| GetWallet | 58 | — | serialized | Get zVault wallet balance |
| SubmitFeedback | 11 | string (JSON) | string | Submit feedback (120s timeout) |
| StartAutoRegistration | 46 | — | — | Auto-register devices |
| StopAutoRegistration | 47 | — | — | Stop auto-registration |
| AutoRegistrationInterval_set | 48 | double | — | Set interval |
| AutoRegistrationInterval_get | 49 | — | double | Get interval |
| WebApp_GetLegacySoftwareCount | 131099 | — | int | Count of legacy Synapse 2 clients |

### Events (server → client broadcasts)

| Event | ID | Data | Description |
|-------|----|------|-------------|
| Event_Login | 65551 | RazerUser | Login complete |
| Event_LogoutComplete | 65552 | — | Logout done |
| Event_LogoutStarted | 65553 | — | Logout started |
| Event_ProfileUpdated | 65554 | RazerUserProfile | Profile changed |
| Event_SyncProgress | 65538 | progress data | Sync progress |
| Event_SyncComplete | 65539 | SyncResult | Sync finished |
| Event_UiLanguageChanged | 65541 | string | Language changed |
| Event_UiThemeChanged | 65547 | string | Theme changed |
| Event_ConnectedAccountConnected | 65542 | int account | OAuth account linked |
| Event_DisconnectFromAccountComplete | 65543 | int account | OAuth account unlinked |
| Event_GlobalSettingChanged | 65544 | setting data | Cloud setting changed |
| Event_FeatureChanged | 65548 | string | Feature flag changed |
| Event_FeatureValueChanged | 65558 | string | Feature value changed |
| Event_AccountConversionStarted | 65555 | — | Guest → full account |
| Event_AccountConversionComplete | 65556 | — | Conversion done |
| Event_AsyncConflict | 65557 | conflict data | Sync conflict |
| Event_TryAutoLoginAsGuest | 65559 | LoginResult | Auto guest login result |
| Event_LoupeDeckStarted | 65560 | — | Loupedeck integration |
| Event_LoupeDeckStopped | 65561 | — | Loupedeck stopped |
| Event_UI_ConnectedAccountRequest | 196610 | string | OAuth request from server |
| Event_UI_RefreshAccountTokenRequest | 196611 | string | Token refresh request |
| Event_UI_LoginStarted | 196612 | — | Login UI should show |
| Event_NacInitialized | 196613 | — | NAC is ready |
| Event_LegacySoftware_Detected | 196614 | int count | Legacy Synapse 2 detected |
| Event_UI_TokenRefreshRequested | 196615 | — | Token refresh needed |

#### LogoutReason Enum
```
Unknown = 0, UserInitiated = 1, Logoff = 2, TokenRefreshFailed = 3,
NoConnections = 4, AccountDeleted = 5, RemoteLogout = 6,
CertDeleted = 7, CertError = 8, NotStayLoggedIn = 9
```

---

## NacCommands — ActionCenter (22 commands)

### UI Control

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| Register | 1 | — | — | Register with NAC |
| Show | 2 | — | — | Show Razer Central window |
| ShowNotification | 3 | string (GUID) | — | Show specific notification |
| ShowUpdates | 4 | — | — | Show updates page |
| ShowPage | 15 | uint (RazerCentralPages) | — | Navigate to page |
| Shutdown | 5 | — | — | Shut down Razer Central |
| ShowUserPrompt | 22 | serialized | — | Show user prompt |

#### RazerCentralPages Enum
```
Undefined = 0, Profile = 1, Profile_Edit = 2, Account = 3,
Updates = 4, Feedback = 5, ChangePassword = 6, CreateAccount = 7
```

### System Tray

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| SetSystemTray | 7 | serialized | — | Configure system tray |
| SystemTrayItemAdded | 9 | serialized | — | Add tray menu item |
| SystemTrayItemRemoved | 8 | string id | — | Remove tray item |
| SystemTrayItemTextUpdated | 10 | string id, string text | — | Update item text |
| SystemTrayItemSubTextUpdated | 18 | string id, string text | — | Update sub-text |
| SystemTrayItemCheckedChanged | 11 | string id, bool | — | Toggle checkbox |
| SystemTrayItemCountChanged | 12 | string id, int | — | Update count |
| SystemTrayDisplayImageChanged | 13 | string id, bytes | — | Change icon |
| SystemTrayItemColorChanged | 14 | string id, color | — | Change color |
| ShowSystemTrayMessage | 17 | string title, string msg | — | Show balloon tip |

### Feedback

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| SetFeedbackTemplate | 16 | serialized | — | Set feedback form |
| AddFeedbackDevice | 19 | serialized | — | Add device to feedback |
| RemoveFeedbackDevice | 20 | string | — | Remove device |
| ClearFeedbackDevices | 21 | — | — | Clear all devices |

### Events

| Event | ID | Data | Description |
|-------|----|------|-------------|
| Event_SystemTray_Clicked | 65536 | string id | Tray item clicked |
| Event_ExitApp | 65537 | — | Exit requested |
| Event_StartLogin | 65538 | — | Login UI requested |
| Event_Update_InstallComplete | 65539 | InstallCompleteEventArgs | Install finished |
| Callback_PromptComplete | 65540 | serialized | Prompt response |

---

## Notifications Commands (14 commands)

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| Subscribe | 1 | string app | — | Subscribe to notifications |
| Unsubscribe | 2 | string app | — | Unsubscribe |
| GetSubscriptions | 3 | — | string[] | List subscriptions |
| GetNotifications | 4 | — | Notification[] | Get all notifications |
| Dismiss | 5 | string id | — | Dismiss notification |
| DismissAll | 11 | — | — | Dismiss all |
| MarkAsRead | 6 | string id | — | Mark as read |
| ShowNotification | 7 | string id | — | Show notification UI |
| Pin | 8 | string id | — | Pin notification |
| CheckForNotifications | 9 | — | — | Check server for new |
| UpdateSubscriptions | 10 | string[] apps | — | Update subscriptions |
| Publish | 12 | Notification | — | Publish a notification |
| IsConnected | 13 | — | bool | Check connection status |

### Events

| Event | ID | Data | Description |
|-------|----|------|-------------|
| Event_NewNotifications | 65536 | Notification[] | New notifications arrived |
| Event_NotificationUpdated | 65537 | Notification | Notification state changed |
| Event_ConnectComplete | 65538 | — | Connected to notification server |
| Event_Disconnected | 65539 | — | Disconnected |

#### NotificationType Enum
```
Unknown = 0, All = 1, StorePromotion = 2, GamePromotion = 3,
SoftwarePromotion = 4, HardwarePromotion = 5, Information = 6, Other = 7
```

#### NotificationState Enum
```
Unknown = 0, Unread = 1, Read = 2, Dismissed = 4, Classified = 5, Expired = 6
```

#### NotificationApp Enum
```
Unknown = 0, All = 1, Comms = 2, Synapse = 3, Cortex = 4, SoftMiner = 5, Axon = 6
```

---

## UpdateManager Commands (39 commands)

### Updates

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| Register | 1 | serialized | — | Register product for updates |
| GetUpdates | 3 | — | Update[] | Get available updates |
| CheckForUpdates | 8 | — | — | Trigger update check |
| DownloadUpdate | 4 | string id | — | Start download |
| PauseDownload | 5 | string id | — | Pause download |
| CancelDownload | 9 | string id | — | Cancel download |
| InstallUpdates | 7 | string[] ids | — | Install updates |
| PostponeUpdates | 14 | — | — | Postpone updates |
| ShowUpdates | 6 | — | — | Show updates UI |

### Software Management

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| GetInstalledSoftware | 21 | — | InstalledApp[] | List installed Razer software |
| GetAvailableSoftware | 10 | — | AvailableApp[] | List available software |
| CheckForAvailableSoftware | 37 | — | — | Check for new software |
| DownloadNewSoftware | 12 | string id | — | Download new app |
| InstallNewSoftware | 13 | string id | — | Install new app |
| PauseSoftwareDownload | 22 | string id | — | Pause |
| CancelSoftwareDownload | 23 | string id | — | Cancel |

### Modules (Plugins)

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| AddModule | 2 | serialized | — | Register module |
| GetOptionalModules | 24 | — | Module[] | List optional modules |
| GetInstalledOptionalModules | 32 | — | Module[] | List installed |
| GetAvailableOptionalModules | 33 | — | Module[] | List available |
| DownloadModule | 25 | string id | — | Download module |
| InstallModules | 26 | string[] ids | — | Install modules |
| RemoveModule | 34 | string id | — | Remove module |
| UninstallModules | 35 | string[] ids | — | Uninstall modules |
| PauseModuleDownload | 28 | string id | — | Pause |
| CancelModuleDownload | 29 | string id | — | Cancel |

### Devices & Endpoints

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| RegisterDevices | 15 | serialized | — | Register devices |
| UnregisterDevices | 16 | string[] ids | — | Unregister |
| ClearRegisteredDevices | 17 | — | — | Clear all |
| GetRegisteredDevices | 18 | — | Device[] | List devices |
| GetRegisteredProducts | 36 | — | Product[] | List products |
| RegisterForUpdates | 27 | string product, string endpoint | — | Register for updates |
| SetEndpoint | 31 | string product, string url | — | Set update endpoint |
| GetEndpointDetails | 38 | string product | EndpointDetails | Get endpoint info |
| GetEndpointDetailsEx | 39 | string product | EndpointDetailsEx | Extended endpoint info |

### Settings

| Command | ID | Request | Response | Description |
|---------|----|---------|----------|-------------|
| Setting_SetDownloadAutomatically | 131072 | bool | — | Auto-download updates |
| Setting_GetDownloadAutomatically | 131073 | — | bool | Get auto-download |
| Setting_SetUpdateInterval | 131074 | int | — | Update check interval |
| Setting_GetUpdateInterval | 131075 | — | int | Get interval |
| Setting_SetCheckAutomatically | 131076 | bool | — | Auto-check for updates |
| Setting_GetCheckAutomatically | 131077 | — | bool | Get auto-check |
| Setting_GetMaxDownloadSpeed | 131078 | — | int | Max download speed |
| Setting_SetMaxDownloadSpeed | 131079 | int | — | Set max speed |

### Events

| Event | ID | Data | Description |
|-------|----|------|-------------|
| Event_DownloadProgress | 65536 | progress data | Download progress |
| Event_DownloadComplete | 65537 | result | Download finished |
| Event_InstallComplete | 65538 | result | Install finished |
| Event_UpdatesAvailable | 65539 | Update[] | Updates found |
| Event_PrepareForUpdate | 65540 | — | Preparing to update |
| Event_InstallStarted | 65549 | — | Install started |
| Event_CheckingForUpdates | 65550 | — | Checking for updates |
| Event_ModuleDownloadProgress | 65545 | progress | Module download progress |
| Event_ModuleDownloadComplete | 65546 | result | Module download done |
| Event_ModuleInstallStart | 65541 | — | Module install started |
| Event_ModuleInstallComplete | 65542 | result | Module install done |
| Event_OptionalModuleInstallStart | 65547 | — | Optional module install |
| Event_OptionalModuleInstallComplete | 65548 | result | Optional module done |
| Event_OptionalModuleUninstallStart | 65551 | — | Uninstall started |
| Event_OptionalModuleUninstallComplete | 65552 | result | Uninstall done |
| Event_NewAppsAvailable | 65553 | — | New apps found |
| Event_EndpointChange | 65554 | — | Endpoint changed |
| Event_TournamentInstallerProgress | 65543 | progress | Tournament installer |
| Event_TournamentInstallerComplete | 65544 | result | Tournament done |

#### DownloadResult Enum
```
Success = 0, Failed_NetworkError = 1, Failed_CRC = 2,
Failed_Unknown = 3, Canceled = 4
```

---

## RazerUser Serialization

Serialized as XML (`IRazerSerializable`):
```xml
<RazerUser>
  <ID>RZR_028043504ff8b39bcd7dda0a7fea</ID>
  <Token>eyJhbGciOiJFUzI1NiI...</Token>
  <LoginId>user@example.com</LoginId>
  <AccessToken>...</AccessToken>
  <ServerIp>...</ServerIp>
  <Verified>true</Verified>
  <AccessTokenExpirationDate>2026-04-08T21:33:05Z</AccessTokenExpirationDate>
  <IsNewlyCreated>false</IsNewlyCreated>
  <IsGuest>false</IsGuest>
</RazerUser>
```
