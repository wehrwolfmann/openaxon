# Razer Axon - React Architecture Analysis

**Bundle version:** 2.6.2.0 (React 18.2.0)
**CDN base:** `https://axon-assets-cdn.razerzone.com/static/prod/2.6.2.0/`
**Webpack entry module:** 314
**Total webpack modules:** ~650
**Bundle size:** 4.8MB minified

---

## 1. Technology Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | React 18.2.0 (functional components + hooks dominant, some class components) |
| Routing | react-router-dom (HashRouter) |
| State management | React Context API (5 createContext calls, 25 useContext) + local useState (913 occurrences) |
| Animations | react-spring |
| Canvas/Editor | Fabric.js (114 references) |
| Tooltips | Tippy.js v6 (69 references) |
| Slider | rc-slider |
| Notification | Custom toast system (.info/.error/.success) |
| Event bus | Custom EventEmitter pattern |
| Desktop host | WebView2 (chrome.webview.hostObjects) |
| Analytics | Custom GA wrapper (SequoiaClientObj.ga) |
| Chroma SDK | Separate bundle (components_source.js, 692 lines) |
| i18n | Custom getMessage() system, 11 locales |

### Supported Locales
`en`, `de`, `es`, `fr`, `ja`, `ko`, `pt`, `ru`, `tw`, `zh-cn`, `zh-cht`

---

## 2. Application Shell & Component Hierarchy

```
<div class="sequoia-container">
  <HashRouter>
    <HeaderBar />                          // sequoia-header-title-bar
      +-- WindowControls (min/max/close)   // sequoia-bar-op min|max|normal|close
      +-- NavBar                           // sequoia-nav-bar
          +-- HistoryNav (prev/next)       // sequoia-nav-history prev|next
          +-- NavTabs                      // sequoia-nav-1 (x4)
          |   +-- "Axon" (Discover)        // NAV.DISCOVER
          |   +-- "Create"                 // NAV.CREATE_AI_NEW
          |   +-- "Community"              // NAV.HALL
          |   +-- "My Wallpaper"           // NAV.MYWALLPAER
          +-- SearchInput                  // sequoia-search-input-con
          +-- NotificationBell             // sequoia-notice
          +-- AccountMenu                  // sequoia-nav-account
    <MainContent />                        // sequoia-main
      +-- LeftSidebar                      // sequoia-left-container (width: 260px collapsed: 48px)
      |   +-- LeftBar toggle               // sequoia-left-bar
      |   +-- LeftMenu (categories)        // sequoia-left-menu
      |   +-- FollowList                   // sequoia-left-followlist
      +-- ContentArea                      // sequoia-content
      |   +-- <Switch> (route content)
      +-- PlaylistPanel                    // sequoia-playlist-panel
          +-- PlaylistBar                  // sequoia-playlist-bar
          +-- PlaylistScroll               // sequoia-playlist-scroll / sequoia-playlist-scroll-list
          +-- PlaylistSettings             // sequoia-playlist-setting
          +-- MonitorBar                   // sequoia-bar-monitor / sequoia-playlist-monitor
    <WallpaperDetailModal />               // sequoia-wallpaper-newmodal > sequoia-wallpaper-detail
    <SettingsModal />                       // sequoia-setting-content
    <CloseConfirmModal />                   // sequoia-close-confirm
    <OnboardingOverlay />                   // sequoia-boarding-new
    <ContextMenu />                         // sequoia-contex-menu / sequoia-contex-menu-2
    <Toast notifications />                 // sequoia-toast-*
  </HashRouter>
</div>
```

### Environment check
On render, the app calls `getIfPlayerEnvironmentSupported()`. If unsupported, renders a fallback `<EnvironmentNotSupported />` page instead of the main shell.

---

## 3. Route Map

### Top-Level Routes (defined in route config array)

| Path | Key | Description |
|------|-----|-------------|
| `/` | spotlight | Home / Spotlight page (discover/browse wallpapers) |
| `/browse` | browse | Browse wallpapers with filters |
| `/collections` | collections | Curated wallpaper collections |
| `/artists` | artists | Artist directory |
| `/myWallPaper` | myWallPaper | User's downloaded/library wallpapers |
| `/create` | create | Legacy create wallpaper (upload) |
| `/myCreateWallPaper` | myCreateWallPaper | User's created wallpapers |
| `/createAI` | createAI | AI wallpaper generation |
| `/createAINew` | createAINew | AI wallpaper generation (new UI, same component) |
| `/aiUpdate` | aiUpdate | AI wallpaper update/edit |
| `/myWorkshop` | myWorkshop | Workshop management |
| `/followSeries` | followSeries | Followed series list |
| `/followSeriesDetail` | followSeriesDetail | Series detail page |
| `/followArtist` | followArtist | Followed artists list |
| `/followArtistDetail` | followArtistDetail | Artist detail page |
| `/createHtml` | createHtml | HTML/Canvas wallpaper creator |
| `/contest` | contest | Contest listing |
| `/contestDetail` | contestDetail | Contest detail + submissions |
| `/hall` | hall | Community hall (nested routes) |
| `/playlist` | playlist | Playlist management (nested routes) |
| `/compaigns` | compaigns | Campaigns hub (nested routes) |
| `/communityAlbums` | communityAlbums | Community albums |
| `/leaderboard` | leaderboard | Leaderboard |
| `/challenge` | challenge | Hashtag challenges |
| `*` | (404) | 404 page (sequoia-app-404) |

### Nested Routes

**`/hall/*` (Community Hall)**
| Sub-path | Description |
|----------|-------------|
| `/hall` (exact) | Community main/all feed |
| `/hall/follow` | Following feed |
| `/hall/liked` | Liked wallpapers |
| `/hall/personal` | Personal profile |
| `/hall/all` | All community content |

**`/playlist/*`**
| Sub-path | Description |
|----------|-------------|
| `/playlist` (exact) | My playlists |
| `/playlist/joined` | Joined playlists |
| `/playlist/followed` | Followed playlists |

**`/compaigns/*` (Campaigns)**
| Sub-path | Description |
|----------|-------------|
| `/compaigns` (exact) | Campaigns list |
| `/compaigns/contestDetail` | Contest detail within campaigns |
| `/compaigns/currentContest` | Current active contest |

---

## 4. State Management Architecture

### No Redux
The app does NOT use Redux (no createStore, combineReducers, or connect). State management is purely:

1. **React Context API** (5 contexts identified):
   - `LumaDataContext` - AI generation data (text2image, text2video)
   - Animation/spring context (react-spring internal)
   - Slider range context (rc-slider)
   - 2 more internal framework contexts

2. **Local component state** via `useState` (913 occurrences) - the dominant pattern

3. **useRef** (549 occurrences) - heavy use for DOM refs, scroll positions, timers, mutable state

4. **useReducer** (6 occurrences) - minimal usage, mostly in library code

5. **Custom EventEmitter** for cross-component communication

### Event Bus (EventEmitter Pattern)

Used extensively for decoupled communication between distant components:

| Event | Purpose |
|-------|---------|
| `NOTICE_GO_PERSONAL` | Navigate to personal profile (19 uses) |
| `REFRESH_PLAYLIST` | Reload playlist data (8 uses) |
| `SHOW_PLAYLIST_MODAL` | Open add-to-playlist modal (7 uses) |
| `SHOW_CREATE_MODAL` | Open creation modal (7 uses) |
| `SHOW_COMMUNITY_DETAIL` | Show wallpaper detail in community (7 uses) |
| `TUTORIAL_TC` | Terms & conditions in tutorial flow (7 uses) |
| `EXPLORE_BANNER_PERSONAL` | Navigate from explore banner to personal (6 uses) |
| `APPEAL_CREATION` | Appeal NSFW/moderation decision (6 uses) |
| `SHOW_UPSCALE_RESULT` | Show AI upscale result (4 uses) |
| `SHOW_MANAGE_MODAL` | Manage wallpaper modal (4 uses) |
| `RELOAD_UNCLAIM` | Reload unclaimed rewards (4 uses) |
| `NOTICE_GO_BADGES` | Navigate to badges section (4 uses) |
| `HIDE_CONTEST_WIN` | Dismiss contest win notification (4 uses) |
| `ALBUM_GO_DETAIL` | Navigate to album detail (4 uses) |
| `SHOW_CONTEST_VOTE` | Open voting modal |
| `SHOW_CLOSE_MODAL` | Show exit confirmation |
| `SHOW_AI_TUTORIAL` | AI generation tutorial overlay |
| `INVITE_FRIENDS` | Invite friends dialog |
| `EXPLORE_SCROLL` | Scroll event in explore view |
| `DELETE_MY_WORK` | Delete user's contest submission |
| `CLOSE_SPLASH_AWARD` | Dismiss splash award screen |
| `CHANGE_AI_TAB` | Switch AI generation tab |
| `ACCEPT_UPSCALE` | Accept upscaled result |
| `ACCEPT_TEXT2VIDEO` | Accept text-to-video result |
| `TUTORIAL_*` | Tutorial flow events |
| `SHOW_PAPER_MODAL` | Wallpaper properties modal |
| `SHOW_PAPER_DETAIL` | Wallpaper detail panel |
| `language_changed_*` | i18n language change propagation |
| `update-work` | Refresh contest work data |

### Global State via `window.SequoiaInfo`

| Property | Usage Count | Purpose |
|----------|-------------|---------|
| `uuid` | 48 | Current user unique ID |
| `is_guest` | 34 | Guest vs authenticated user flag |
| `pcCode` | 20 | PC unique hardware code |
| `networkConnected` | 13 | Network connectivity flag |
| `country` | 9 | User's country code |
| `token` | 4 | Auth token |
| `authorization` | 4 | Auth header value |
| `myWallpaperSiderHide` | 1 | Sidebar state persistence |

### LocalStorage Keys
- `{uuid}_close_axon` - Close/exit preferences (dontShowConfirm, exitApp)
- `{uuid}_music_tips` - Spotify integration tip shown flag
- Various per-user preference keys

---

## 5. Desktop <-> Web Bridge

### Architecture
The app runs inside a **WebView2** container (Microsoft Edge/Chromium). Communication uses `chrome.webview.hostObjects` proxy objects that call C# methods asynchronously.

### Bridge Initialization
On startup, if `chrome.webview.hostObjects.windowActionHostObject` exists, the app creates `window.SequoiaClientObj` - a facade wrapping all host object calls with async/await.

### Host Objects (C# Backend Services)

#### `windowActionHostObject` - Window Management
| Method | Purpose |
|--------|---------|
| `SetMinimize()` | Minimize window |
| `SetMax()` | Maximize window |
| `SetNormal()` | Restore window |
| `CloseWindow()` | Close window |
| `GetWindowState()` | Get current window state (MIN/MAX/NORMAL) |
| `RegisterWindowStateChangedEvent(cb)` | Listen for window state changes |
| `OpenWithDefaultBrowser(url)` | Open URL in system browser |
| `OpenLoginWindow()` | Open Razer ID login window |
| `OpenNewWindow(url)` | Open new webview window |
| `OpenPayWindow()` | Open payment/purchase window |
| `OpenFileDirectory(path)` | Open folder in file explorer |
| `ShowOpenfileDialog()` | Native file open dialog |
| `ShowOpenSaveFileDialog()` | Native save file dialog |
| `SaveFileToLocal(data)` | Save file to local filesystem |
| `SetStrToClipboard(str)` | Copy to clipboard |
| `TryUploadLocalFile()` | Upload local file |
| `CheckFileAccess(path)` | Check file permissions |
| `RegisterNavigateCommandEvent(cb)` | Listen for navigation commands from host |
| `RegisterNewWindowRequestEvent(cb)` | Intercept new window requests |

#### `wallpaperManagerHostObject` - Wallpaper Library
| Method | Purpose |
|--------|---------|
| `GetAllItems()` | Get all downloaded wallpapers |
| `GetWallpaperItem(id)` | Get single wallpaper details |
| `AddOrUpdateItem(data)` | Add/update wallpaper metadata |
| `AddOrUpdateItems(data)` | Bulk add/update |
| `AddLocalItem(data)` | Add local wallpaper file |
| `ModifyLocalItem(data)` | Edit local wallpaper metadata |
| `Remove(id)` | Delete wallpaper |
| `CheckItemsStatus(ids)` | Check download/availability status |
| `GetVideoPreviewImg(path)` | Extract video thumbnail |
| `SaveTempLocalImg(data)` | Save temporary preview image |
| `RemoveTempLocalImg(path)` | Clean up temp images |
| `OpenWallPaperFileLocation(path)` | Show file in explorer |
| `SetWallpaperItemPlaySetting(id, settings)` | Per-wallpaper play settings |
| `AddOrModifyChromaEffects(id, effects)` | Set Chroma RGB effects |
| `ResetVideoWallPaperEffects(id)` | Reset video effects to default |
| `RegisterEventHandler(cb)` | Listen for wallpaper library changes |

#### `playListHostObject` - Playlist & Playback
| Method | Purpose |
|--------|---------|
| `GetPlayLists()` | Get all playlists |
| `GetPlayListSetting()` | Get playlist global settings |
| `SetPlayListSetting(settings)` | Update playlist settings |
| `GetMonitorInfos()` | Get connected monitor information |
| `AddToPlayList(id, data)` | Add wallpaper to playlist |
| `RemoveFromPlayList(id, wallpaperId)` | Remove from playlist |
| `ClearPlayList(id)` | Clear all items in playlist |
| `SetPlayListSelected(id)` | Set active playlist |
| `SetPlayListMute(muted)` | Mute/unmute audio |
| `SetPlayListChromaEnabled(enabled)` | Toggle Chroma sync |
| `SetWallPaperIndex(index)` | Set current wallpaper in rotation |
| `ApplyWallPaper(id, monitors)` | Apply wallpaper to monitors |
| `StartPlay()` | Start wallpaper playback |
| `StopPlay()` | Stop wallpaper playback |
| `RegisterPlayListChangedHandlers(cb)` | Listen for playlist changes |

#### `downloadMangerHostObject` - Download Manager
| Method | Purpose |
|--------|---------|
| `AddDownloadTask(wallpaperId, url1, url2, meta, flag, hasChroma, type, chromaData)` | Start download |
| `GetDownloadItems()` | Get download queue/status |
| `PauseDownloadTask(id)` | Pause download |
| `ResumeDownloadTask(id)` | Resume download |
| `RemoveDownloadTask(id)` | Cancel/remove download |
| `DownloadImage(url)` | Download single image |
| `RegisterDownloadStatusChangedHandler(cb)` | Listen for download progress |

#### `userManagerHostObejct` - User & Account (note: typo "Obejct" is in original code)
| Method | Purpose |
|--------|---------|
| `GetUser()` | Get current user info |
| `GetUserProfile()` | Get user profile details |
| `GetUserBalance()` | Get silver/currency balance |
| `Logout()` | Sign out |
| `OpenProfile()` | Open Razer ID profile |
| `OpenChangePassword()` | Open password change |
| `OpenFeedBack()` | Open feedback form |
| `OpenUpdate()` | Open app update |
| `OpenUserZVaultWeb()` | Open zVault (Razer Gold) |
| `ExitApp()` | Quit application |
| `SendBigData(data)` | Analytics telemetry |
| `SendUETEvent(action, label, category, revenue, currency)` | UET tracking |
| `PrintLog(msg)` | Log to native console |
| `GetIsNeedToToastRatingPage()` | Check if rating prompt needed |
| `SetIsToastRatingPage(shown)` | Mark rating prompt as shown |

#### `userSettingHostObject` - Application Settings
| Method | Purpose |
|--------|---------|
| `GetAppVersion()` | Get app version string |
| `GetPcUniqueCode()` | Get hardware fingerprint |
| `GetUserGeneralSetting()` | Get all user settings |
| `GetPlayMode()` / `SetPlayMode()` | Wallpaper rotation mode |
| `GetWallpaperPlayer()` / `SetWallpaperPlayer()` | Video player engine |
| `GetDefaultApplyMonitorIds()` / `SetDefaultApplyMonitorIds()` | Default monitors |
| `GetIsPauseWhenFullScreen()` / `SetIsPauseWhenFullScreen()` | Pause on fullscreen app |
| `GetIsPauseWhenD3DFullScreen()` / `SetIsPauseWhenD3DFullScreen()` | Pause on D3D fullscreen |
| `GetIsDuplicateSelectScreen()` / `SetIsDuplicateSelectScreen()` | Duplicate across screens |
| `GetScreenSaverEnabled()` / `SetScreenSaverEnabled()` | Screen saver mode |
| `GetOnboardingIsShown()` / `SetOnboardingIsShown()` | Onboarding state |
| `GetWhatsNewIsShown()` / `SetWhatsNewIsShown()` | What's new dialog state |
| `SetAutoStartWithSystem(enabled)` | Launch on Windows startup |
| `SetMinimizeWhenAutoStart(enabled)` | Start minimized |
| `SetLanguage(lang)` | Set UI language |
| `SetSaveSourcePath(path)` | Wallpaper download directory |
| `SetMaxVolume(vol)` | Max audio volume |
| `SetIsExitDirectly(flag)` | Skip exit confirmation |
| `SetIsShowNotification(flag)` | Desktop notifications |
| `GetIfPlayerEnvironmentSupported()` | Check video playback capability |
| `GetWallpaperThirdpartInfo(key)` | Get 3rd party integration data (Spotify) |
| `SetWallpaperThirdpartInfo(key, val)` | Set 3rd party data |
| `OpenApplication(path)` | Launch external application |
| `RegisterLanguageChangedHandler(cb)` | Listen for system language changes |
| `CheckFileAccess(path)` | Verify file access permissions |

---

## 6. Key Component Specifications

### 6.1 Spotlight/Discover Page (`/`)
- Landing page with banner carousel, wallpaper grid
- Category-based filtering
- Wallpaper cards with hover preview
- "Go Top" button (sequoia-go-top)
- Onboarding overlay for first-time users

### 6.2 Browse Page (`/browse`)
- Filter bar (sequoia-filter): type, resolution, sort order, search
- Wallpaper grid with infinite scroll (onScroll handler)
- Search input with close button (sequoia-search-input-con)
- Sort dropdown (sequoia-search-sort)
- Radio group filter for wallpaper types (Image/Motion/Video/All)

### 6.3 Wallpaper Detail Modal
- Opens as overlay modal (sequoia-wallpaper-newmodal)
- Left panel: wallpaper preview (image/video)
- Right panel: metadata, actions
  - Title, description, creator info (sequoia-wallpaper-creator)
  - Tags (sequoia-wallpaper-tag)
  - Like/wishlist/share buttons
  - Download button with monitor selection
  - Apply to desktop button
  - Report button
  - Chroma effect toggle
  - Properties panel (resolution, type, etc.)
- Spotify source detection and special handling
- NSFW content appeal flow

### 6.4 AI Creation Pages (`/createAI`, `/createAINew`, `/aiUpdate`)
- `LumaDataContext` provider for generation state
- Generation types: `TEXT2IMAGE`, `TEXT2VIDEO`
- Sub-features:
  - Text-to-Image generation
  - Image-to-Image (reference-based)
  - Image-to-Motion conversion
  - Image-to-Video generation
  - AI Upscaler (4 styles: CI, GE, CG, 2D)
  - Prompt helper/improver/random
- Upload panel for source images
- Canvas editor (Fabric.js) for HTML wallpapers
- Tutorial overlay flow (6 steps)
- NSFW detection and appeal system

### 6.5 Community Hall (`/hall/*`)
- Tabbed view: All / Following / Liked / Personal
- User profile cards with follow/unfollow
- Badge system (sequoia-challenge)
- Activity feed
- Personal page with follower count
- Social sharing (Facebook, Twitter, Reddit, Weibo)

### 6.6 Playlist Panel (persistent bottom/side panel)
- Always visible when wallpapers are in playlist
- Horizontal scrollable thumbnail list (drag & drop reorder)
- Per-wallpaper controls:
  - Mute audio (sequoia-playlist-paper-mute)
  - Delete from playlist (sequoia-playlist-paper-delete)
  - Broken wallpaper indicator (sequoia-playlist-paper-broken)
- Global controls:
  - Play/Stop
  - Volume slider (rc-slider, 0-100)
  - Chroma toggle
  - Playlist settings (rotation timing, shuffle)
  - Monitor assignment
- Current wallpaper highlight (sequoia-playlist-cur-mask)
- Share playlist (sequoia-playlist-share)

### 6.7 Settings Modal
- Sections:
  - **General** (sequoia-setting-general): language, auto-start, minimize on start, exit behavior, notifications
  - **Display** (sequoia-setting-display): monitor configuration, screen list
  - **Performance** (sequoia-setting-performance): pause on fullscreen, pause on D3D, wallpaper player engine
  - **About** (sequoia-setting-about): version info, open source notices, legal links
  - **Tutorial** (sequoia-setting-tutorial): replay tutorial
  - **Path** (sequoia-setting-path): download location
  - **Screen Chroma** (sequoia-setting-screen-chroma): per-monitor Chroma settings
  - **Screen Mute** (sequoia-setting-screen-mute): per-monitor audio settings

### 6.8 Collections (`/collections`)
- Collection cards with cover image (sequoia-collection-item)
- Collection detail view (sequoia-collection-item-detail)
- Follow/unfollow collection
- Wallpaper list within collection (sequoia-collection-papers)
- Toolbar with sorting (sequoia-collection-toolbar)

### 6.9 Artists (`/artists`)
- Artist grid (sequoia-artists-list)
- Artist card (sequoia-artist-item) with avatar, description
- Artist detail page: recommendations, wallpaper list
- Follow artist button

### 6.10 Contest/Campaigns System
- Contest listing (sequoia-contest)
- Contest detail with work submissions
- Voting system (up vote, cancel vote)
- Leaderboard with award claiming
- Contest share functionality
- Work submission and removal

### 6.11 Context Menu (Right-Click)
- Two-level context menu (sequoia-contex-menu, sequoia-contex-menu-2)
- Menu items: Add to favorites, remove from favorites, cancel download, copy, add to playlist, export, etc.
- Separator support (sequoia-contex-menu-separate)

### 6.12 My Wallpaper Library (`/myWallPaper`)
- Grid of downloaded wallpapers (sequoia-mywallpaper)
- Multi-select with multi-download (sequoia-multi-download)
- Upload wallpaper (sequoia-wallpaper-upload)
- Cover change (sequoia-cover-change, sequoia-cover-rotate, sequoia-cover-upload)
- Delete confirmation (sequoia-library-delete-confirm)
- Local file management (add, modify, remove)

### 6.13 Redeem System
- Silver currency redemption (sequoia-wallpaper-redeem)
- Redeem by code (sequoia-code-form, sequoia-code-modal)
- Cost display (sequoia-redeem-cost)
- Banner integration (/wallpaper/redeem/banner)

### 6.14 Onboarding Flow
- Multi-step overlay (sequoia-boarding-new, steps 1-5)
- Step 1: AI generation prompt
- Steps 3-5: Interactive tutorial
- Razer ID login integration
- GA tracking: "On Boarding" category

---

## 7. API Endpoints

### Wallpaper
- `GET /wallpaper/list` - Browse wallpapers
- `GET /wallpaper/detail` - Wallpaper details
- `GET /wallpaper/downloaded` - Download status
- `POST /wallpaper/favorite/` - Like/unlike
- `GET /wallpaper/resource` - Resource URLs
- `POST /wallpaper/report` - Report wallpaper
- `POST /wallpaper/share` - Share tracking
- `POST /wallpaper/vote/` - Vote on wallpaper
- `GET /wallpaper/setting` - Wallpaper settings
- `POST /wallpaper/wishlist/add` - Add to wishlist
- `POST /wallpaper/wishlist/cancel` - Remove from wishlist
- `GET /wallpaper/canvas` - Canvas/HTML wallpaper data

### AI Generation
- `POST /wallpaper/generate` - Generate from prompt
- `POST /wallpaper/generate/again` - Regenerate
- `POST /wallpaper/generate/image2image` - Image-to-image
- `POST /wallpaper/generate/image2image/reference` - Reference-based
- `POST /wallpaper/generate/image2motion` - Image-to-motion
- `POST /wallpaper/generate/image2video` - Image-to-video
- `POST /wallpaper/generate/upscale` - AI upscale
- `POST /wallpaper/generate/alchemy` - Alchemy generation
- `POST /wallpaper/generate/batch` - Batch generation
- `POST /wallpaper/generate/video` - Video generation
- `GET /wallpaper/generate/list` - Generation history
- `GET /wallpaper/generate/detail` - Generation result
- `GET /wallpaper/generate/details` - Batch details
- `GET /wallpaper/generate/info` - Generation info
- `GET /wallpaper/generate/model` - Available models
- `GET /wallpaper/generate/price` - Token pricing
- `GET /wallpaper/generate/product` - Products
- `POST /wallpaper/generate/upload` - Upload source image
- `GET /wallpaper/generate/uploadurl` - Pre-signed upload URL
- `GET /wallpaper/generate/uploadlist` - Uploaded images
- `DELETE /wallpaper/generate/uploaddelete` - Delete upload
- `POST /wallpaper/generate/prompt` - Prompt enhancement
- `GET /wallpaper/generate/existorder` - Check pending orders
- `POST /wallpaper/generate/suborder` - Submit generation order
- `POST /wallpaper/generate/suborder/save` - Save order
- `POST /wallpaper/generate/close` - Close generation
- `DELETE /wallpaper/generate/delete` - Delete generation
- `DELETE /wallpaper/generate/deletedetail` - Delete detail
- `POST /wallpaper/generate/nobg` - Remove background

### Redemption
- `GET /wallpaper/redeem/list` - Redeemable items
- `GET /wallpaper/redeem/banner` - Redeem banner
- `POST /wallpaper/redeem` - Redeem wallpaper
- `POST /wallpaper/redeem/bycode` - Redeem by code
- `POST /redeem/bycode` - Alternative code redemption

### Collections
- `GET /collection/list` - List collections
- `GET /collection/detail` - Collection detail
- `POST /collection/follow/` - Follow/unfollow collection
- `GET /collection/followlist` - Followed collections

### Artists
- `GET /artist/list` - List artists
- `GET /artist/detail` - Artist detail
- `POST /artist/follow/` - Follow/unfollow artist
- `GET /artist/followlist` - Followed artists
- `POST /artist/apply` - Apply as artist

### Community Boards
- `GET /board/list` - List boards
- `GET /board/info` - Board info
- `GET /board/detail/list` - Board detail list
- `POST /board/follow` - Follow board
- `GET /board/member/list` - Board members
- `POST /board/memberapply` - Apply for membership
- `GET /board/memberapply/list` - Membership applications
- `POST /board/memberapprove` - Approve member
- `GET /board/name/list` - Board names
- `POST /board/wallpaper/add` - Add wallpaper to board
- `GET /board/wallpaper/selectlist` - Wallpapers to select from

### Social
- `GET /follows` - Following list
- `GET /followers` - Followers list

### Contest
- `GET /contest/list` - Contest list
- `GET /contest/openlist` - Open contests
- `GET /contest/detail` - Contest detail
- `GET /contest/work/list` - Contest submissions
- `GET /contest/work/detail` - Submission detail
- `POST /contest/participate` - Join contest
- `POST /contest/vote/up` - Upvote work
- `POST /contest/vote/cancel` - Cancel vote
- `POST /contest/work/click` - Track work view
- `POST /contest/work/remove` - Remove submission
- `POST /contest/work/report` - Report submission
- `GET /contest/otherwork/list` - Other works by user
- `GET /contest/userwork/list` - User's contest works
- `GET /contest/award/list` - Contest awards
- `POST /contest/award/claim` - Claim award
- `GET /contest/slivernotenogh` - Silver insufficiency check

### Leaderboard
- `GET /leaderboard/list` - Leaderboard
- `GET /leaderboard/toplist` - Top users
- `GET /leaderboard/end/list` - Ended leaderboards
- `GET /leaderboard/unclaim/list` - Unclaimed rewards
- `POST /leaderboard/awardclaim` - Claim leaderboard award

### User
- `GET /user/profiling` - User profiling
- `GET /user/setting` - User settings
- `POST /user/setting/set` - Update setting

### Other
- `GET /badge/list` - Available badges
- `GET /badge/corner` - Badge corner display
- `POST /badge/decorate` - Set badge decoration
- `GET /silver/detail` - Silver currency detail
- `GET /notification/splashscreen` - Splash screen data

---

## 8. Analytics Categories

The app tracks extensive analytics via `SequoiaClientObj.ga(category, action, label)`:

| Category | Description |
|----------|-------------|
| `Spotlight` | Home page interactions |
| `Browse` | Browsing: click, search, sort, filter, type, refresh |
| `Collection` | Collection views, artist pages |
| `Community` | Social: like, follow, share, emoji, claim |
| `CommunityExplore` | Community exploration |
| `Contest` | Contest participation, voting, banner clicks |
| `CreateWithAI` | AI generation: prompt, generate, publish |
| `TextToImage` | Text-to-image specific |
| `TextToVideo` / `TextVideo` | Text-to-video specific |
| `ImageToMotion` | Image-to-motion specific |
| `Upscaler` | AI upscaler usage |
| `RealtimeCanvas` | Canvas editor interactions |
| `CreateChroma` | Chroma effect creation |
| `Add Chroma Effect` | Chroma RGB effect actions |
| `Wallpaper` | Wallpaper: apply, download, share, like |
| `Playlist` | Playlist management |
| `LibraryPlaylist` | Library playlist interactions |
| `Upload` | Wallpaper upload |
| `Custom` | Custom wallpaper creation |
| `Settings` | Settings changes |
| `Navigation` | Nav bar clicks |
| `Creators` | Creator pages |
| `Series` | Series views |
| `Compilations` | Compilation views |
| `HashtagChallenges` | Challenge participation |
| `SilverRedeem` | Silver redemption |
| `TopUp` | Currency top-up |
| `Ads` | Ad impressions, clicks, closes |
| `Spotify` | Spotify integration |
| `Splash` | Splash screen |
| `On Boarding` | Onboarding flow |
| `Rating` | App rating prompt |
| `MinimizePopup` | Minimize to tray popup |
| `WhatsNew` | What's new dialog |
| `Banner` | Banner clicks |
| `Promot` | Promoted content |

---

## 9. Chroma SDK Integration (components_source.js)

Separate 692-line unminified script for Razer Chroma RGB visualization.

### Supported Devices
- **Keyboard** (extended layout with underglow, 50 underglow LEDs + full key matrix)
- **Mouse** (left/right sides 7 LEDs each + scrollwheel + logo)
- **Mousepad** (15 LEDs)
- **Headset** (5 LEDs)
- **Keypad** (5x4 matrix + 1 extra LED)
- **ChromaLink** (5 LEDs)

### Architecture
- `deviceMaps[]` - array of device map objects
- Each device has SVG-based visualization using `findLeds()` to locate LED elements by CSS class
- Animation playback: `ChromaAnimation.getAnimation(name)` loads `.chroma` animation files
- Frame-by-frame rendering: `displayChroma(obj)` iterates through all 6 device types
- Color format: BGR integer -> `rgb(r,g,b)` CSS string
- Keyboard uses RZKEY hash: `(row << 8) | column` for LED addressing
- BlackWidow V4 specific keys: M1-M5, Knob, Media keys

### Key Functions
- `drawKeyboard()`, `drawMouse()`, `drawMousepad()`, `drawHeadset()`, `drawKeypad()`, `drawChromaLink()`
- `displayChroma(obj)` - master render function, called per frame
- `setupMap*()` - one-time LED discovery from SVG DOM
- Animation file naming: `{effectName}_{DeviceType}.chroma`

---

## 10. Wallpaper Content Types

| Type Constant | Description |
|--------------|-------------|
| `ONLYIMAGE` | Static image wallpaper |
| `ONLYMOTION` | Motion/animated wallpaper |
| `ONLYVEDIO` | Video wallpaper (note: typo "VEDIO" is in original) |
| `NOLIMIT` | Any type accepted |
| `Generate` | AI-generated wallpaper |

### Wallpaper Sources
- Community uploaded
- AI generated (text2image, image2motion, image2video, upscale)
- Spotify integration (album art as wallpaper)
- Local files
- Redeemed (silver currency)
- Contest submissions
- Curated collections/series

---

## 11. Key Architectural Notes for Recreation

1. **No Redux** - all state is local (useState/useRef) with EventEmitter for cross-component communication
2. **HashRouter** - the app uses hash-based routing (`#/path`), not HTML5 history
3. **WebView2 bridge** is essential - the entire playback/download/system integration goes through `chrome.webview.hostObjects`
4. **SequoiaClientObj** is the JS-side facade over native methods - all native calls go through this object
5. **Fabric.js** is used for the canvas-based wallpaper editor (HTML wallpapers)
6. **The app is i18n-ready** with 11 locales, using a `getMessage(key)` function
7. **Toast notifications** use a custom implementation (`.info()`, `.error()`, `.success()`)
8. **Drag & drop** in playlist panel for reordering wallpapers
9. **Infinite scroll** pattern on browse/listing pages using scroll event listeners on `.sequoia-main.show`
10. **CSS class prefix** is consistently `sequoia-*` across all components
11. **Typos preserved in API**: `userManagerHostObejct` (not Object), `ONLYVEDIO` (not VIDEO), `compaigns` (not campaigns)
