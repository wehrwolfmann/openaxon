# Razer Axon API Reference

> Extracted from JS bundle `axon.f8e71bd23f616540077f.js` (v2.6.2.0) and Python clients.
> JS files in `/tmp/axon_assets/` are V8 code cache (compiled bytecode), not raw JS.
> Actual JS source served from: `https://axon-assets-cdn.razerzone.com/static/prod/2.6.2.0/`

## Base Configuration

| Key | Value |
|-----|-------|
| API Base URL | `https://axon-api.razer.com/v1` |
| Web App | `https://axon.razer.com` |
| CDN Assets | `https://axon-assets-cdn.razerzone.com` |
| API Version Header | `2.6.2.0` |
| HMAC Key | `j6l-aUmhCc@tN%T_` (SHA-256, for resource/download endpoints) |
| Auth Provider | `https://id.razer.com/` (Razer ID OAuth) |

## Authentication Methods

### Method 1: JWT Token Auth (Web/Electron app)
Used for most endpoints (gallery, favorites, artists, etc.)

```
Headers:
  Content-Type: application/json
  X-Version: 2.6.2.0
  X-Language: en
  Authorization: <token from login response>
```

The `Authorization` value is returned by the `/login` endpoint (not a Bearer token -- it's a raw string from `data.authorization`).

### Method 2: HMAC-SHA256 Auth (.NET desktop client)
Used for resource download and download-reporting endpoints.

```
Headers:
  UserID: <uuid>
  Authorization: HMAC-SHA256(<sorted_query_params>, key)
  Isguest: true|false
  Token: (empty string)
  Content-Type: application/x-www-form-urlencoded  (for POST)
  Accept: text/json, application/json

Signature:
  1. Sort params alphabetically by key
  2. Build raw query: key1=value1&key2=value2 (NOT url-encoded)
  3. HMAC-SHA256(raw_query, "j6l-aUmhCc@tN%T_")
  4. Hex-encode the digest -> Authorization header
  5. URL-encode values in the actual request URL/body
```

### Method 3: Window Object (Electron/CEF)
The desktop app exposes auth via `window.SequoiaInfo.authorization` and `window.SequoiaInfo.token`.

## Response Format

All endpoints return:
```json
{
  "code": 200,
  "data": { ... },
  "message": "optional error message"
}
```
`code: 200` = success.

---

## Endpoints

### 1. Authentication & User

#### POST /login
Exchange JWT token for API authorization.

| Field | Value |
|-------|-------|
| Auth | None (this creates auth) |
| Body | `{"token": "<jwt>", "is_guest": "false", "uuid": "<device-uuid>"}` |
| Response | `{authorization, user_id, country}` |

#### GET /user/setting
Get user preferences/settings.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /user/setting
Update user settings.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /user/setting/set
Set specific user setting.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /user/profiling
User activity analytics/profiling event.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 2. Wallpaper - Browse & Settings

#### GET /wallpaper/setting
Get wallpaper categories, filters, and configuration.

| Field | Value |
|-------|-------|
| Auth | JWT |
| Response | `{category: [{category_id, category_name, wallpaper_count}]}` |

#### GET /wallpaper/list
Browse wallpaper gallery with filters.

| Param | Type | Description |
|-------|------|-------------|
| `pi` | int | Page index (1-based) |
| `ps` | int | Page size (default 24) |
| `not_offical` | string | `"true"` -- include non-official |
| `category_id` | string | Filter by category |
| `effect_type` | string | Filter: `Static`, `Dynamic` |
| `favorite_only` | string | `"true"` for favorites only |
| `title` | string | Search query |
| `query_type` | string | `"2"` when searching by title |
| `artist_id` | string | Filter by artist |
| `order_by` | string | Sort order |
| `resolution` | string | Filter by resolution (e.g. `1920x1080`) |
| `paper_source` | string | `"community"` for community wallpapers |

| Field | Value |
|-------|-------|
| Auth | JWT |
| Response | `{count, list: [{wallpaper_id, title, thumbnail, type, effect_type, author_name, downloads, is_favorite, ...}]}` |

#### GET /wallpaper/detail
Get detailed info about a single wallpaper.

| Param | Type | Description |
|-------|------|-------------|
| `wallpaper_id` | string | Wallpaper ID |

| Field | Value |
|-------|-------|
| Auth | JWT |
| Response fields | `wallpaper_id, title, thumbnail, preview_pic, type, effect_type, category, author{author_name, author_icon}, downloads, is_favorite, is_redeemed, resolution[{resolution, width, height}], all_tags, audible, chroma_support, source, sharing` |

---

### 3. Wallpaper - Download

#### GET /wallpaper/resource
Get download URL for a wallpaper at a specific resolution.

| Param | Type | Description |
|-------|------|-------------|
| `wallpaper_id` | string | Wallpaper ID |
| `width` | string | Width in pixels |
| `height` | string | Height in pixels |
| `resource_type` | string | `"0"` |

| Field | Value |
|-------|-------|
| Auth | **HMAC** |
| Response | `{resource (download URL), resource_id, resource_sign (MD5), headers, cookies}` |

#### POST /wallpaper/downloaded
Report a completed download to the API.

| Param | Type | Description |
|-------|------|-------------|
| `wallpaper_id` | string | Wallpaper ID |
| `resource_id` | string | From resource response |

| Field | Value |
|-------|-------|
| Auth | **HMAC** |
| Body encoding | `application/x-www-form-urlencoded` |

---

### 4. Wallpaper - Favorites & Social

#### POST /wallpaper/favorite/add
Add wallpaper to favorites.

| Field | Value |
|-------|-------|
| Auth | JWT |
| Body | `{"wallpaper_id": "<id>"}` |

#### POST /wallpaper/favorite/cancel
Remove wallpaper from favorites.

| Field | Value |
|-------|-------|
| Auth | JWT |
| Body | `{"wallpaper_id": "<id>"}` |

#### POST /wallpaper/vote/{type}
Vote on a wallpaper. `{type}` = `up` or `cancel`.

| Field | Value |
|-------|-------|
| Auth | JWT |
| Body | `{"wallpaper_id": "<id>"}` |

#### POST /wallpaper/share
Share a wallpaper (generates sharing URL).

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/report
Report inappropriate wallpaper.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 5. Wallpaper - Redeem & Library

#### POST /wallpaper/redeem
Redeem a wallpaper (premium/locked content).

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/redeem/list
List user's redeemed wallpapers.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/redeem/banner
Get redeem banner/promotion info.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/redeem (by code)
Redeem wallpaper using a code. (Functions: `redeemByCode`, `redeemByCodeNew`)

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/wishlist/add
Add wallpaper to personal library.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/wishlist/cancel
Remove wallpaper from personal library.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /library/wishlist
Get user's library/wishlist.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 6. AI Generation

#### GET /wallpaper/generate/product
List available AI generation products.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/generate/model
List available AI models (Leonardo, HiDream, Luma, etc.).

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate
Generate AI wallpaper (text-to-image, normal mode).

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/image2image
Image-to-image AI generation.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/image2motion
Convert static image to motion wallpaper.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/image2video
Convert image to video.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/video
AI video generation.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/batch
Batch generation (Luma pipeline).

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/image2image/reference
Luma image reference generation.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/generate/info
Check generation status.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/generate/list
List user's generation orders.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/generate/details
Get all generation details for an order.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/generate/detail
Get single generation detail.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/deletedetail
Delete a specific generated item.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/delete
Delete an entire generation order.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/again
Re-run a generation with same params.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/upscale
Upscale a generated image.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/nobg
Remove background from generated image.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/alchemy
Sample/alchemy generation.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/generate/uploadurl
Get presigned URL for uploading source image.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/generate/uploadlist
List user's uploaded source images.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/uploaddelete
Delete an uploaded source image.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/upload
Upload/update image metadata.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /wallpaper/generate/existorder
Check if user has an active AI generation order.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/price
Calculate generation cost.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/suborder
Get canvas sub-order.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/suborder/save
Save canvas generation result.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/prompt
Get random AI prompt suggestion.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/canvas
Generate canvas wallpaper.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /wallpaper/generate/close
Close/cancel an AI generation order.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 7. Artists

#### GET /artist/list
Browse wallpaper artists.

| Param | Type | Description |
|-------|------|-------------|
| `pi` | int | Page index |
| `ps` | int | Page size |

| Field | Value |
|-------|-------|
| Auth | JWT |
| Response | `{count, list: [{artist_id, name, is_followed, ...}]}` |

#### GET /artist/detail
Get artist profile with bio, social links, stats.

| Param | Type | Description |
|-------|------|-------------|
| `artist_id` | string | Artist ID |

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /artist/followlist
Get list of artists the user follows.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /artist/follow/{type}
Follow or unfollow an artist. `{type}` = `add` or `cancel`.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /artist/apply
Apply to become a creator/artist.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 8. Collections & Series

#### GET /collection/list
List wallpaper collections.

| Param | Type | Description |
|-------|------|-------------|
| `pi` | int | Page index |
| `ps` | int | Page size |
| `artist_id` | string | Optional: filter by artist |

| Field | Value |
|-------|-------|
| Auth | JWT |
| Response | `{count, list: [{collection_name, ...}]}` |

#### GET /collection/detail
Get collection details and wallpapers.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /collection/followlist
Get collections the user follows.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /collection/follow/{type}
Follow/unfollow a collection. `{type}` = `add` or `cancel`.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 9. Community Feed

#### GET /feed/public
Browse public community feed (explore).

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/personal
Get user's own posts.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/personal/state
Get user profile/state info.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/followers
Get feed from followed users.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/detail
Get a single feed item.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /feed
Publish a new feed post.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### PUT /feed
Edit/update a feed post.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### DELETE /feed/personal
Delete user's own post.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### PUT /feed/personal
Set security/privacy settings on post.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/likes
Get liked feed items.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /feed/likes
Like a feed item.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### DELETE /feed/likes
Unlike a feed item.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /feed/report
Report a feed post.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/presets
Get style presets for feed posts.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/messages
Get user notifications/messages.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### PUT /feed/messages/read
Mark notifications as read.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /feed/messages/backlike
Like-back from notification.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /feed/messages/allbacklike
Like-back all notifications.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/board
Get community albums in feed.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/personal/board
Get user's personal albums in feed.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /feed/selections
Get discover/promoted selections.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 10. Social - Follows & Fans

#### POST /follows
Follow a user.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### DELETE /follows
Unfollow a user.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /followers
Get list of followers.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /fans
Get fans list.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /upvotes
Get upvote list.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 11. Albums (Boards/Playlists)

#### POST /board
Create a new album.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /board/list
List albums.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /board/info
Get album details.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /board/detail/list
Get wallpapers/papers in an album.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### PUT /board
Update album info.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### DELETE /board
Delete an album.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /board/follow
Follow an album.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### DELETE /board/follow
Unfollow an album.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /board/memberapply
Apply to join an album as contributor.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /board/memberapprove
Approve a member application.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /board/memberapply/list
List pending member applications.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /board/member/list
List album members.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### DELETE /board/member
Remove a member from album.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /board/wallpaper/selectlist
Get wallpapers available for adding to album.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /board/wallpaper/add
Add a wallpaper to an album.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /board/name/list
Get album names (for "add to album" dropdown).

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 12. Contests

#### GET /contest/list
List all contests.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /contest/openlist
List currently open contests.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /contest/detail
Get contest details.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /contest/participate
Join/submit to a contest.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /contest/vote/up
Vote for a contest entry.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /contest/vote/cancel
Cancel vote on a contest entry.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /contest/work/click
Track view/click on a contest work.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /contest/work/list
List works in a contest.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /contest/work/detail
Get contest work details.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /contest/userwork/list
Get user's own contest submissions.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /contest/otherwork/list
Get other works by same contestant.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /contest/work/report
Report a contest work.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /contest/work/remove
Remove user's own contest work.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /contest/award/list
List contest rewards/prizes.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /contest/award/claim
Claim a contest reward.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /contest/slivernotenogh
Get silver coin activity info (note: typo is in the original API).

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 13. Daily Challenges

#### GET /dailychallenge/list
Get daily challenge info.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /dailychallenge/staytunedbadges
Get "stay tuned" badge rewards for challenges.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 14. Leaderboard

#### GET /leaderboard/list
Get leaderboard data.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /leaderboard/toplist
Get top rankings.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /leaderboard/end/list
Get ended/past leaderboards.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /leaderboard/unclaim/list
Get unclaimed leaderboard rewards.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /leaderboard/awardclaim
Claim a leaderboard reward.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 15. Payment & Wallet

#### GET /wallet/balance
Get AI credits/silver coin balance.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /payment/pkg/list
Get available purchase packages (charge list).

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /payment
Get payment token for checkout.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /payment
Submit a payment request.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /payment/order/list
List payment order history.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /payment/order
Get single order status.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /payment/expired
Get expired payment items.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /payment/channel/list
Get available payment channels/methods.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### DELETE /payment
Cancel/delete a payment.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 16. Badges & Profile Customization

#### GET /badge/list
Get user's badges.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### PUT /badge/decorate
Set/display a badge on profile.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /badge/corner
Get badge corner display info.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /emoji/usage
Send/use an emoji.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 17. Discovery & Content

#### GET /discovery/index
Get main discover/home page data.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /spotlight/index
Get spotlight/featured content.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /spotlight/feed
Get spotlight feed items.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /compilation/index
Get curated compilations.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /explore/list
Get explore page promotions/banners.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 18. Notifications & System

#### GET /notification/splashscreen
Get splash screen notification/announcement.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /system/language
Get localization/language data.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 19. Tasks & Free Tokens

#### GET /task/openpage
Get free token claim info (daily open reward).

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /task/openpage/claim
Claim a free token/daily reward.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /task/contest/vote
Get contest vote task info.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 20. Spotify Integration

#### GET /spotify/auth
Get Spotify OAuth URL.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /spotify/token
Exchange Spotify auth code for token.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### GET /spotify/profile
Get Spotify user profile.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 21. Invites & Referrals

#### GET /invite
Get invite/referral page info.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /invite
Submit/confirm an invite code.

| Field | Value |
|-------|-------|
| Auth | JWT |

#### POST /invite/claim
Claim invite reward.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

### 22. Appeals

#### POST /appeal
Submit a content moderation appeal.

| Field | Value |
|-------|-------|
| Auth | JWT |

---

## Frontend Routes (Web App)

These are client-side routes in the Axon web app (from JS router):

| Route | Description |
|-------|-------------|
| `/browse` | Main gallery |
| `/artists` | Artist listing |
| `/followArtist` | Followed artists |
| `/followArtistDetail` | Artist detail (followed) |
| `/followSeries` | Followed series |
| `/followSeriesDetail` | Series detail (followed) |
| `/collections` | Collections listing |
| `/compilations` | Curated compilations |
| `/playlist` | Playlist view |
| `/playlist/followed` | Followed playlists |
| `/playlist/joined` | Joined playlists |
| `/myWallPaper` | User's wallpapers |
| `/myCreateWallPaper` | User's created wallpapers |
| `/myWorkshop` | User's workshop |
| `/hall` | Community hall |
| `/hall/all` | Hall - all |
| `/hall/follow` | Hall - following |
| `/hall/liked` | Hall - liked |
| `/hall/personal` | Hall - personal |
| `/communityAlbums` | Community albums |
| `/compaigns` | Campaigns |
| `/compaigns/daily` | Daily campaigns |
| `/compaigns/currentContest` | Current contest |
| `/compaigns/contestDetail` | Contest detail |
| `/compaigns/leaderboard` | Leaderboard |
| `/contest` | Contest |
| `/contestDetail` | Contest detail |
| `/leaderboard` | Leaderboard |
| `/challenge` | Challenge |
| `/create` | Create wallpaper |
| `/createAI` | AI wallpaper creator |
| `/createAINew` | New AI creator |
| `/createHtml` | HTML wallpaper creator |
| `/aiUpdate` | AI update page |

---

## CDN URL Patterns

| Pattern | Example |
|---------|---------|
| Thumbnails | `https://axon-assets-cdn.razerzone.com/thumbnail/{uuid}/{version}/{name}.jpg` |
| Previews | `https://axon-assets-cdn.razerzone.com/preview/{hash}.webp` |
| Playlists | `https://axon-assets-cdn.razerzone.com/playlist/{hash}.jpg` |
| Author icons | `https://axon-assets-cdn.razerzone.com/author/icon/{hash}.png` |
| Sharing page | `https://axon.razer.com/sharing/wallpaper?w={id}` |
| Legacy sharing | `https://axon.razer.com/wallpaper/sharingpage?w={id}&u={encoded_user}` |
| Chroma AI model | `/chroma/model.json` |
| Chroma class names | `/chroma/classNames.json` |

---

## Vuex/Redux Store Actions (from JS constants)

These are the state management actions that map to API calls:

```
LOGIN, TOKEN, WALLPAPER, MY_WALLPAPER, DETAIL, REDEEM, REDEEM_CODE,
ARTIST, ARTIST_DETAIL, ARTISTS, SERIES, SERIES_DETAIL,
ALBUM, ALBUMS, COMMUNITY, COMMUNITY_ALBUM, COLLECTION,
CONTEST, CONTEST_CURRENT, CONTESTDETAIL, CONTEST_TYPE, CONTEST_VOTE,
CAMPAIGNS, CAMPAIGNS_DAILY, CHALLENGE, LEADERBOARD, DAILY,
EXPLORE, HALL_FOLLOW, HALL_LIKES, HALL_PERSONAL,
FOLLOW_ARTIST, FOLLOW_PLAYLIST, FOLLOW_SERIES, JOIN_PLAYLIST,
FOLLOWER, FOLLOWERS, FOLLOWING, LIKED, UPVOTE, VOTE,
BADGES, CREATE_AI, CREATE_AI_NEW, CREATE_HTML, AI_UPDATE,
CLAIMED_TOKENS, NONE_TOKEN, HAD_CLAIMED, WAIT_CLAIM,
MYPLAYLIST, MYWORKSHOP, DELETE_MY_WORK, SUBMIT_RESULT, CLAIM_RESULT
```

---

## JS Function Names Mapping to API Calls

| Function | Likely Endpoint |
|----------|----------------|
| `getArtistList` | GET /artist/list |
| `getArtistDetail` | GET /artist/detail |
| `getArtistFollow` | GET /artist/followlist |
| `followArtist` | POST /artist/follow/{type} |
| `getCollectionList` | GET /collection/list |
| `getCollectionDetail` | GET /collection/detail |
| `getPaperList` | GET /wallpaper/list |
| `getPaperDetail` | GET /wallpaper/detail |
| `getPaperSetting` | GET /wallpaper/setting |
| `getResource` | GET /wallpaper/resource |
| `downloadComplete` | POST /wallpaper/downloaded |
| `toggleFavorite` | POST /wallpaper/favorite/{type} |
| `toggleVote` | POST /wallpaper/vote/{type} |
| `redeemPaper` | POST /wallpaper/redeem |
| `redeemByCode` | POST /wallpaper/redeem (with code) |
| `getRedeemList` | GET /wallpaper/redeem/list |
| `addToLibrary` | POST /wallpaper/wishlist/add |
| `deleteFromLibrary` | POST /wallpaper/wishlist/cancel |
| `getLibraryList` | GET /library/wishlist |
| `getUploadUrl` | GET /wallpaper/generate/uploadurl |
| `getUploadList` | GET /wallpaper/generate/uploadlist |
| `deleteUpload` | POST /wallpaper/generate/uploaddelete |
| `uploadImage` | POST /wallpaper/generate/upload |
| `getGenerateList` | GET /wallpaper/generate/list |
| `getGenerateStatus` | GET /wallpaper/generate/info |
| `getAllGenerateList` | GET /wallpaper/generate/details |
| `getAIDetail` | GET /wallpaper/generate/detail |
| `deleteAIOrder` | POST /wallpaper/generate/delete |
| `deleteAIPaper` | POST /wallpaper/generate/deletedetail |
| `getAiBalance` | GET /wallet/balance |
| `getModelList` | GET /wallpaper/generate/model |
| `getAlbumList` | GET /board/list |
| `getAlbumDetail` | GET /board/info |
| `getAlbumPaperList` | GET /board/detail/list |
| `getAlbumMembers` | GET /board/member/list |
| `getALbumListForAdd` | GET /board/name/list |
| `getPapersForAdd` | GET /board/wallpaper/selectlist |
| `applyAlbum` | POST /board/memberapply |
| `updateAlbum` | PUT /board |
| `deleteAlbum` | DELETE /board |
| `followAlbum` | POST /board/follow |
| `unfollowAlbum` | DELETE /board/follow |
| `deleteAlbumMember` | DELETE /board/member |
| `getContestList` | GET /contest/list |
| `getContestDetail` | GET /contest/detail |
| `getContestAllWork` | GET /contest/work/list |
| `getContestMyWork` | GET /contest/userwork/list |
| `getOtherWork` | GET /contest/otherwork/list |
| `voteContest` | POST /contest/vote/up |
| `claimReward` | POST /contest/award/claim |
| `getRewardList` | GET /contest/award/list |
| `getUnclaimList` | GET /leaderboard/unclaim/list |
| `claimLeaderboardReward` | POST /leaderboard/awardclaim |
| `getLeaderboardList` | GET /leaderboard/list |
| `getLeaderboardTopList` | GET /leaderboard/toplist |
| `getChargeList` | GET /payment/pkg/list |
| `getPaymentToken` | GET /payment |
| `requestPayment` | POST /payment |
| `getOrderList` | GET /payment/order/list |
| `getOrderStatus` | GET /payment/order |
| `getExpiredList` | GET /payment/expired |
| `deletePayment` | DELETE /payment |
| `getBadgeList` | GET /badge/list |
| `getBadgeCorner` | GET /badge/corner |
| `sendEmoji` | POST /emoji/usage |
| `getFansList` | GET /fans |
| `getLikeList` | GET /feed/likes |
| `getUpvoteList` | GET /upvotes |
| `getFollowList` | GET /followers |
| `getFollowFeedsList` | GET /feed/followers |
| `getFollowUserList` | GET /followers |
| `getPersonalFeeds` | GET /feed/personal |
| `getPersonalAlbumList` | GET /feed/personal/board |
| `getCommunityAlbumList` | GET /feed/board |
| `getCommunityDetail` | GET /feed/detail |
| `getNoticeList` | GET /feed/messages |
| `getUnReadNum` | GET /feed/messages (unread count) |
| `likeNotice` | POST /feed/messages/backlike |
| `likeAllNotice` | POST /feed/messages/allbacklike |
| `getDiscoverData` | GET /discovery/index |
| `getSpotlightData` | GET /spotlight/index |
| `getExploreProm` | GET /explore/list |
| `getCompilationsData` | GET /compilation/index |
| `getExploreList` | GET /explore/list |
| `getSplashscreen` | GET /notification/splashscreen |
| `getUserInfo` | GET /feed/personal/state |
| `getUserSetting` | GET /user/setting |
| `getShowFreeTokenInfo` | GET /task/openpage |
| `claimFreeToken` | POST /task/openpage/claim |
| `getVoteTask` | GET /task/contest/vote |
| `spotifyAuth` | GET /spotify/auth |
| `spotifyGetToken` | GET /spotify/token |
| `getSilverActivity` | GET /contest/slivernotenogh |
| `getSivlerDetail` | GET /contest/slivernotenogh (detail) |
| `getStayTunedBadges` | GET /dailychallenge/staytunedbadges |
| `getChallengeInfo` | GET /dailychallenge/list |
| `getOpenList` | GET /contest/openlist |
| `checkGuestLogin` | POST /login (is_guest=true) |
| `deletePublish` | DELETE /feed/personal |
| `deleteFollow` | DELETE /follows |

---

## Notes

1. **Two auth systems coexist**: JWT-based auth for most endpoints, HMAC-based auth for resource download endpoints. The desktop .NET client uses HMAC; the web app uses JWT.

2. **`not_offical` typo**: The API uses `not_offical` (missing 'i') as a parameter name. This is consistent across all clients.

3. **`paper` vs `wallpaper`**: In the JS codebase, "paper" is used interchangeably with "wallpaper" in function names (e.g., `getPaperList` calls `/wallpaper/list`).

4. **Pagination**: Most list endpoints use `pi` (page index, 1-based) and `ps` (page size) parameters.

5. **The older JS bundle** (`axon.5944b6ca33b199d68c11.js`, 3.3MB) contains the same endpoints plus some webpack sourcemap-related content. The newer bundle (`axon.f8e71bd23f616540077f.js`, 2.0MB) is the active one loaded by `index.html`. The only new function in the newer bundle is `getUnReadNum` and `sendUETEvent`.

6. **Braintree payment integration** is referenced in the HTML (commented out): `js.braintreegateway.com` for credit card, PayPal, and 3D Secure.

7. **The `REQUEST_URL` config** is initialized from `src/config/url` module (referenced as "init failure, src/config/urlx8" in error strings). The actual API base URL is not hardcoded as a literal string in the JS -- it's likely injected at build time or set via the Electron/CEF host.

8. **Chroma SDK**: The app includes ChromaSDK WebSocket integration (`ChromaSDKWS.js`) and AI-powered Chroma lighting (`ChromaAI6.js`) with TensorFlow.js for color prediction.
