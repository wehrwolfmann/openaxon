#!/usr/bin/env python3
"""
Razer Axon Account Sync

Synchronizes wallpapers with your Razer Axon account:
- Login with saved JWT token
- Browse wallpaper gallery with categories, search, filters
- Download wallpapers directly (no Wine needed)
- View account favorites and toggle favorite status
- Browse artists and their wallpapers
- Show local wallpaper details from API
"""

import hashlib
import hmac
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import urllib.request
import urllib.error
import urllib.parse

log = logging.getLogger(__name__)

API_BASE = "https://axon-api.razer.com/v1"
API_VERSION = "2.6.2.0"
HMAC_KEY = b"j6l-aUmhCc@tN%T_"

CONFIG_DIR = Path(os.environ.get("RAZER_AXON_DIR", Path.home() / ".config/razer-axon"))
TOKEN_FILE = CONFIG_DIR / "token.json"

# Backward compat: fallback to Wine prefix if new path doesn't exist
_WINE_TOKEN = (Path(os.environ.get("WINEPREFIX", Path.home() / ".wine"))
               / "drive_c/users" / os.environ.get("USER", "user")
               / "AppData/Local/Razer/RazerAxon/wine_login_token.json")
if not TOKEN_FILE.exists() and _WINE_TOKEN.exists():
    TOKEN_FILE = _WINE_TOKEN

DEFAULT_OUTPUT = Path.home() / "RazerAxonWallpapers"


@dataclass
class WallpaperInfo:
    wallpaper_id: str
    title: str
    thumbnail: str = ""
    preview: str = ""
    wp_type: str = ""
    effect_type: str = ""
    category: str = ""
    author: str = ""
    downloads: int = 0
    is_favorite: bool = False
    is_redeemed: bool = False
    resolutions: list = field(default_factory=list)
    tags: str = ""
    audible: bool = False
    chroma_support: bool = False
    source: str = ""
    sharing: str = ""


@dataclass
class DownloadResource:
    url: str
    resource_id: str
    md5: str
    headers: dict | None = None
    cookies: dict | None = None


class AxonAPI:
    """Client for Razer Axon API."""

    def __init__(self):
        self.authorization = ""
        self.user_id = ""
        self.country = ""
        self._uuid = ""
        self._is_guest = False

    def _request(self, method: str, endpoint: str, params: dict | None = None,
                 body: dict | None = None) -> dict | None:
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = json.dumps(body).encode() if body else None
        headers = {
            "Content-Type": "application/json",
            "X-Version": API_VERSION,
            "X-Language": "en",
        }
        if self.authorization:
            headers["Authorization"] = self.authorization

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            log.error("HTTP %d for %s %s", e.code, method, endpoint)
            try:
                return json.loads(e.read())
            except Exception:
                return None
        except Exception as e:
            log.error("Request failed: %s", e)
            return None

    def _hmac_request(self, method: str, endpoint: str,
                      params: dict) -> dict | None:
        """Make a request using HMAC-SHA256 auth (like the .NET client)."""
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        sorted_params = sorted(params.items(), key=lambda x: x[0])

        # HMAC signature from raw (non-encoded) query string
        raw_qs = "&".join(f"{k}={v}" for k, v in sorted_params)
        auth_hash = hmac.new(HMAC_KEY, raw_qs.encode(), hashlib.sha256).hexdigest()

        # URL-encoded query string
        encoded_qs = "&".join(
            f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params
        )

        headers = {
            "UserID": self._uuid,
            "Authorization": auth_hash,
            "Isguest": "true" if self._is_guest else "false",
            "Token": "",
            "accept": "text/json, application/json",
        }

        if method == "GET":
            url = f"{url}?{encoded_qs}"
            data = None
        else:
            data = encoded_qs.encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            log.error("HTTP %d for %s %s", e.code, method, endpoint)
            try:
                return json.loads(e.read())
            except Exception:
                return None
        except Exception as e:
            log.error("Request failed: %s", e)
            return None

    def get(self, endpoint: str, params: dict | None = None) -> dict | None:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, body: dict | None = None) -> dict | None:
        return self._request("POST", endpoint, body=body or {})

    def login(self, jwt_token: str, uuid: str, is_guest: bool = False) -> bool:
        """Exchange JWT for API authorization token."""
        resp = self.post("login", {
            "token": jwt_token,
            "is_guest": str(is_guest).lower(),
            "uuid": uuid,
        })
        if not resp or resp.get("code") != 200:
            log.error("Login failed: %s", resp)
            return False

        data = resp["data"]
        self.authorization = data["authorization"]
        self.user_id = str(data.get("user_id", ""))
        self.country = data.get("country", "")
        self._uuid = uuid
        self._is_guest = is_guest
        log.info("Logged in: user_id=%s country=%s", self.user_id, self.country)
        return True

    def login_from_token_file(self) -> bool:
        """Login using saved token file, with auto-refresh if expired."""
        if not TOKEN_FILE.exists():
            log.error("Token file not found: %s", TOKEN_FILE)
            log.error("Run razer-login to authenticate.")
            return False

        # Check if token needs refresh
        token_data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        expiry = token_data.get("tokenExpiry", "")
        if expiry:
            try:
                from datetime import datetime, timedelta, timezone
                exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                if datetime.now(tz=timezone.utc) + timedelta(hours=1) >= exp_dt:
                    log.info("Token expired or expiring soon, attempting refresh...")
                    if self._try_silent_refresh():
                        # Re-read refreshed token
                        token_data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
                    else:
                        log.warning("Silent refresh failed. Run razer-login to re-authenticate.")
            except (ValueError, ImportError):
                pass

        jwt = token_data.get("token", "")
        uuid = token_data.get("uuid", "")
        is_guest = token_data.get("isGuest", False)

        if not jwt or not uuid:
            log.error("Invalid token file — missing token or uuid")
            return False

        return self.login(jwt, uuid, is_guest)

    @staticmethod
    def _try_silent_refresh() -> bool:
        """Attempt headless token refresh via razer-login."""
        import subprocess
        script = Path(__file__).parent / "razer-login.py"
        if not script.exists():
            return False
        try:
            result = subprocess.run(
                [sys.executable, str(script), "--refresh"],
                capture_output=True, text=True, timeout=20,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── Gallery ──────────────────────────────────────────────────────

    def get_categories(self) -> list[dict]:
        """Get wallpaper categories."""
        resp = self.get("wallpaper/setting")
        if not resp or resp.get("code") != 200:
            return []
        return resp["data"].get("category", [])

    def get_wallpaper_list(self, *, page: int = 1, page_size: int = 24,
                           category_id: str = "", effect_type: str = "",
                           favorite_only: bool = False, search: str = "",
                           artist_id: str = "", order_by: str = "",
                           resolution: str = "") -> dict | None:
        """Browse wallpaper gallery with filters."""
        params: dict = {"pi": str(page), "ps": str(page_size), "not_offical": "true"}
        if category_id:
            params["category_id"] = category_id
        if effect_type:
            params["effect_type"] = effect_type
        if favorite_only:
            params["favorite_only"] = "true"
        if search:
            params["title"] = search
            params["query_type"] = "2"
        if artist_id:
            params["artist_id"] = artist_id
        if order_by:
            params["order_by"] = order_by
        if resolution:
            params["resolution"] = resolution

        resp = self.get("wallpaper/list", params)
        if not resp or resp.get("code") != 200:
            return None
        return resp["data"]

    def get_wallpaper_detail(self, wallpaper_id: str | int) -> WallpaperInfo | None:
        """Get detailed info about a wallpaper."""
        resp = self.get("wallpaper/detail", {"wallpaper_id": str(wallpaper_id)})
        if not resp or resp.get("code") != 200:
            return None

        d = resp["data"]
        author = d.get("author", {})
        return WallpaperInfo(
            wallpaper_id=str(d.get("wallpaper_id", "")),
            title=d.get("title", ""),
            thumbnail=d.get("thumbnail", ""),
            preview=d.get("preview_pic", ""),
            wp_type=d.get("type", ""),
            effect_type=d.get("effect_type", ""),
            category=d.get("category", ""),
            author=author.get("author_name", ""),
            downloads=d.get("downloads", 0),
            is_favorite=bool(d.get("is_favorite", 0)),
            is_redeemed=bool(d.get("is_redeemed", 0)),
            resolutions=[r["resolution"] for r in d.get("resolution", [])],
            tags=d.get("all_tags", ""),
            audible=d.get("audible", "0") == "1",
            chroma_support=bool(d.get("chroma_support", 0)),
            source=d.get("source", ""),
            sharing=d.get("sharing", ""),
        )

    # ── Download ─────────────────────────────────────────────────────

    def get_resource(self, wallpaper_id: str | int, width: int,
                     height: int) -> DownloadResource | None:
        """Get download URL for a wallpaper (uses HMAC auth like .NET client)."""
        resp = self._hmac_request("GET", "wallpaper/resource", {
            "wallpaper_id": str(wallpaper_id),
            "width": str(width),
            "height": str(height),
            "resource_type": "0",
        })
        if not resp or resp.get("code") != 200:
            log.error("Failed to get resource: %s", resp)
            return None

        d = resp["data"]
        return DownloadResource(
            url=d.get("resource", ""),
            resource_id=d.get("resource_id", ""),
            md5=d.get("resource_sign", ""),
            headers=d.get("headers"),
            cookies=d.get("cookies"),
        )

    def report_downloaded(self, wallpaper_id: str | int,
                          resource_id: str) -> bool:
        """Report a wallpaper download to the API."""
        resp = self._hmac_request("POST", "wallpaper/downloaded", {
            "wallpaper_id": str(wallpaper_id),
            "resource_id": resource_id,
        })
        return resp is not None and resp.get("code") == 200

    # ── Favorites ────────────────────────────────────────────────────

    def toggle_favorite(self, wallpaper_id: str | int, add: bool = True) -> bool:
        """Add or remove a wallpaper from favorites."""
        action = "add" if add else "cancel"
        resp = self.post(f"wallpaper/favorite/{action}", {
            "wallpaper_id": str(wallpaper_id),
        })
        return resp is not None and resp.get("code") == 200

    # ── Artists ───────────────────────────────────────────────────────

    def get_artist_list(self, *, page: int = 1, page_size: int = 24) -> dict | None:
        """Get list of wallpaper artists."""
        resp = self.get("artist/list", {"pi": str(page), "ps": str(page_size)})
        if not resp or resp.get("code") != 200:
            return None
        return resp["data"]

    def get_artist_detail(self, artist_id: str) -> dict | None:
        """Get artist detail."""
        resp = self.get("artist/detail", {"artist_id": artist_id})
        if not resp or resp.get("code") != 200:
            return None
        return resp["data"]

    # ── Local wallpapers ─────────────────────────────────────────────

    def get_local_wallpaper_ids(self) -> list[str]:
        """Find wallpaper IDs from local WallpaperSource directory."""
        source_dir = (Path(os.environ.get("WINEPREFIX", Path.home() / ".wine"))
                      / "drive_c/users" / os.environ.get("USER", "user")
                      / "AppData/Local/Razer/RazerAxon/WallpaperSource")
        if not source_dir.exists():
            return []

        ids = set()
        skip = {"Extracted", "RazerAxonWallPapers", "ResourceTmp"}
        for d in source_dir.iterdir():
            if d.is_dir() and d.name not in skip:
                name = d.name
                for suffix_len in (8, 7):
                    if len(name) > suffix_len:
                        candidate = name[:-suffix_len]
                        if candidate.isdigit():
                            ids.add(candidate)
                            break
        return sorted(ids)


# ── CLI output ───────────────────────────────────────────────────────

def print_categories(api: AxonAPI) -> None:
    categories = api.get_categories()
    if not categories:
        print("Failed to fetch categories")
        return

    print(f"\n{'ID':<6} {'Category':<25} {'Count':>6}")
    print("-" * 40)
    for cat in categories:
        cat_id = cat.get("category_id", "") or "all"
        name = cat.get("category_name", "")
        count = cat.get("wallpaper_count", 0)
        print(f"{cat_id:<6} {name:<25} {count:>6}")


def print_gallery(api: AxonAPI, args: list[str]) -> None:
    page = 1
    page_size = 20
    category_id = ""
    effect_type = ""
    favorite_only = False
    search = ""
    artist_id = ""
    resolution = ""

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-p", "--page") and i + 1 < len(args):
            page = int(args[i + 1]); i += 2
        elif arg in ("-n", "--count") and i + 1 < len(args):
            page_size = int(args[i + 1]); i += 2
        elif arg in ("-c", "--category") and i + 1 < len(args):
            category_id = args[i + 1]; i += 2
        elif arg in ("-t", "--type") and i + 1 < len(args):
            effect_type = args[i + 1]; i += 2
        elif arg in ("-s", "--search") and i + 1 < len(args):
            search = args[i + 1]; i += 2
        elif arg in ("-a", "--artist") and i + 1 < len(args):
            artist_id = args[i + 1]; i += 2
        elif arg in ("-r", "--resolution") and i + 1 < len(args):
            resolution = args[i + 1]; i += 2
        elif arg in ("-f", "--favorites"):
            favorite_only = True; i += 1
        else:
            i += 1

    data = api.get_wallpaper_list(
        page=page, page_size=page_size,
        category_id=category_id, effect_type=effect_type,
        favorite_only=favorite_only, search=search,
        artist_id=artist_id, resolution=resolution,
    )
    if not data:
        print("Failed to fetch wallpaper list")
        return

    total = data.get("count", 0)
    items = data.get("list") or []
    total_pages = (total + page_size - 1) // page_size

    filters = []
    if search:
        filters.append(f'search="{search}"')
    if category_id:
        filters.append(f"category={category_id}")
    if effect_type:
        filters.append(f"type={effect_type}")
    if favorite_only:
        filters.append("favorites")
    if artist_id:
        filters.append(f"artist={artist_id}")
    if resolution:
        filters.append(f"res={resolution}")
    filter_str = f" ({', '.join(filters)})" if filters else ""

    print(f"\nWallpapers: {total} total, page {page}/{total_pages}{filter_str}")
    print(f"{'ID':<8} {'Title':<30} {'Author':<18} {'Type':<8} {'DL':>8} {'Fav':>4}")
    print("-" * 80)

    for wp in items:
        fav = "*" if wp.get("is_favorite") else ""
        dl = wp.get("downloads", 0) if "downloads" in wp else ""
        author = wp.get("author_name", "")[:17]
        title = wp.get("title", "")[:29]
        wp_type = wp.get("type", "")
        print(f"{wp['wallpaper_id']:<8} {title:<30} {author:<18} {wp_type:<8} {dl:>8} {fav:>4}")

    if total_pages > 1:
        print(f"\nPage {page}/{total_pages}. Use --page N to navigate.")


def print_local_wallpapers(api: AxonAPI) -> None:
    ids = api.get_local_wallpaper_ids()
    if not ids:
        print("No local wallpapers found")
        return

    print(f"\nLocal wallpapers ({len(ids)}):")
    print(f"{'ID':<8} {'Title':<30} {'Author':<20} {'Type':<8} {'Fav':>4}")
    print("-" * 75)

    for wid in ids:
        info = api.get_wallpaper_detail(wid)
        if info:
            fav = "*" if info.is_favorite else ""
            print(f"{info.wallpaper_id:<8} {info.title:<30} {info.author:<20} {info.wp_type:<8} {fav:>4}")
        else:
            print(f"{wid:<8} (unknown)")


def print_wallpaper_detail(api: AxonAPI, wallpaper_id: str) -> None:
    info = api.get_wallpaper_detail(wallpaper_id)
    if not info:
        print(f"Wallpaper {wallpaper_id} not found")
        return

    print(f"\n  Title:       {info.title}")
    print(f"  ID:          {info.wallpaper_id}")
    print(f"  Type:        {info.wp_type} ({info.effect_type})")
    print(f"  Author:      {info.author}")
    print(f"  Downloads:   {info.downloads:,}")
    print(f"  Favorite:    {'Yes' if info.is_favorite else 'No'}")
    print(f"  Redeemed:    {'Yes' if info.is_redeemed else 'No'}")
    print(f"  Resolutions: {', '.join(info.resolutions)}")
    print(f"  Tags:        {info.tags}")
    print(f"  Audio:       {'Yes' if info.audible else 'No'}")
    print(f"  Chroma:      {'Yes' if info.chroma_support else 'No'}")
    print(f"  Source:      {info.source}")
    if info.sharing:
        print(f"  Share:       {info.sharing}")
    print(f"  Thumbnail:   {info.thumbnail}")
    print(f"  Preview:     {info.preview}")


def download_wallpaper(api: AxonAPI, wallpaper_id: str, args: list[str]) -> None:
    resolution = ""
    output_dir = DEFAULT_OUTPUT
    extract = True

    i = 0
    while i < len(args):
        if args[i] in ("-r", "--resolution") and i + 1 < len(args):
            resolution = args[i + 1]; i += 2
        elif args[i] in ("-o", "--output") and i + 1 < len(args):
            output_dir = Path(args[i + 1]); i += 2
        elif args[i] in ("--no-extract",):
            extract = False; i += 1
        else:
            i += 1

    # Get wallpaper details for available resolutions
    info = api.get_wallpaper_detail(wallpaper_id)
    if not info:
        print(f"Wallpaper {wallpaper_id} not found")
        return

    print(f"\n  {info.title} by {info.author}")
    print(f"  Type: {info.wp_type} ({info.effect_type})")
    print(f"  Available: {', '.join(info.resolutions)}")

    # Pick resolution
    if not resolution:
        # Default to highest resolution
        resolution = info.resolutions[-1] if info.resolutions else "1920x1080"
    if resolution not in info.resolutions:
        print(f"  Resolution {resolution} not available. Choose from: {', '.join(info.resolutions)}")
        return

    width, height = resolution.split("x")
    print(f"  Downloading {resolution}...")

    # Get download URL
    resource = api.get_resource(wallpaper_id, int(width), int(height))
    if not resource or not resource.url:
        print("  Failed to get download URL")
        return

    # Download
    wp_dir = output_dir / f"{wallpaper_id}"
    wp_dir.mkdir(parents=True, exist_ok=True)
    zip_path = wp_dir / f"{resolution}.zip"

    req = urllib.request.Request(resource.url)
    if resource.headers:
        for k, v in resource.headers.items():
            req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(zip_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        mb = downloaded / 1024 / 1024
                        total_mb = total / 1024 / 1024
                        print(f"\r  {mb:.1f}/{total_mb:.1f} MB ({pct}%)", end="", flush=True)
            print()
    except Exception as e:
        print(f"  Download failed: {e}")
        return

    # Verify MD5
    if resource.md5:
        import hashlib as hl
        file_md5 = hl.md5(zip_path.read_bytes()).hexdigest()
        if file_md5 != resource.md5:
            print(f"  MD5 mismatch: expected {resource.md5}, got {file_md5}")
        else:
            print(f"  MD5 verified: {file_md5}")

    # Report download
    api.report_downloaded(wallpaper_id, resource.resource_id)

    print(f"  Saved: {zip_path}")

    # Extract if requested
    if extract:
        _extract_and_decrypt(zip_path, wp_dir)


def _extract_and_decrypt(zip_path: Path, wp_dir: Path) -> None:
    """Extract CDN ZIP and decrypt the inner wallpaper archive."""
    import zipfile

    if not zipfile.is_zipfile(zip_path):
        print(f"  Not a valid ZIP: {zip_path}")
        return

    # CDN ZIP is not encrypted — extract it
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(wp_dir)
        print(f"  Extracted {len(zf.namelist())} files")

    # Now decrypt inner wallpaper (Resource/*.mp4 etc.)
    config_path = wp_dir / "ResourceConfig.txt"
    if not config_path.exists():
        print(f"  No ResourceConfig.txt — nothing to decrypt")
        return

    try:
        from axon import parse_resource_config, derive_password, extract
    except ImportError:
        print("  Cannot import axon.py — run from project directory to decrypt,")
        print("  or use: razer-axon-decrypt.py -d", wp_dir)
        return

    parsed = parse_resource_config(config_path)
    if parsed is None:
        return
    content, config = parsed

    source_str = config.get("Source", "")
    if not source_str or config.get("SourceEncryptedTypes", "").upper() != "ZIP":
        print("  Not an encrypted wallpaper")
        return

    from pathlib import PureWindowsPath
    source = PureWindowsPath(source_str)
    archive = wp_dir / Path(*source.parts)

    if not archive.exists():
        print(f"  Archive not found: {archive}")
        return

    password = derive_password(content)
    extract_dir = wp_dir / "Extracted"
    if extract(archive, password, extract_dir):
        # List extracted media files
        media = [f for f in extract_dir.rglob("*") if f.is_file()
                 and f.suffix.lower() in (".mp4", ".webm", ".jpg", ".png", ".gif")]
        if media:
            print(f"  Decrypted:")
            for f in media:
                print(f"    {f}")


def print_artists(api: AxonAPI, args: list[str]) -> None:
    page = 1
    page_size = 20

    i = 0
    while i < len(args):
        if args[i] in ("-p", "--page") and i + 1 < len(args):
            page = int(args[i + 1]); i += 2
        elif args[i] in ("-n", "--count") and i + 1 < len(args):
            page_size = int(args[i + 1]); i += 2
        else:
            i += 1

    data = api.get_artist_list(page=page, page_size=page_size)
    if not data:
        print("Failed to fetch artists")
        return

    total = data.get("count", 0)
    artists = data.get("list") or []
    total_pages = (total + page_size - 1) // page_size

    print(f"\nArtists: {total} total, page {page}/{total_pages}")
    print(f"{'ID':<6} {'Name':<25} {'Followed':>8}")
    print("-" * 42)

    for a in artists:
        followed = "*" if a.get("is_followed") else ""
        print(f"{a['artist_id']:<6} {a['name']:<25} {followed:>8}")


def print_favorite_toggle(api: AxonAPI, wallpaper_id: str, action: str) -> None:
    add = action != "remove"
    if api.toggle_favorite(wallpaper_id, add=add):
        print(f"{'Added to' if add else 'Removed from'} favorites: {wallpaper_id}")
    else:
        print(f"Failed to {'add to' if add else 'remove from'} favorites")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: razer-sync.py [command] [args]")
        print()
        print("Commands:")
        print("  gallery [opts]        Browse wallpaper gallery")
        print("    -p, --page N          Page number (default: 1)")
        print("    -n, --count N         Items per page (default: 20)")
        print("    -c, --category ID     Filter by category ID")
        print("    -t, --type TYPE       Filter by type (Static/Dynamic)")
        print("    -s, --search QUERY    Search by title")
        print("    -a, --artist ID       Filter by artist ID")
        print("    -r, --resolution RES  Filter by resolution (e.g. 1920x1080)")
        print("    -f, --favorites       Show only favorites")
        print("  download <id> [opts]  Download a wallpaper")
        print("    -r, --resolution RES  Resolution (default: highest)")
        print("    -o, --output DIR      Output directory (default: ~/RazerAxonWallpapers)")
        print("    --no-extract          Don't extract ZIP after download")
        print("  categories            List wallpaper categories")
        print("  artists [opts]        List wallpaper artists")
        print("    -p, --page N          Page number")
        print("    -n, --count N         Items per page")
        print("  detail <id>           Show wallpaper details")
        print("  fav <id>              Add wallpaper to favorites")
        print("  unfav <id>            Remove wallpaper from favorites")
        print("  local                 Show local wallpapers with account info")
        print("  status                Show login status")
        print()
        print("Requires razer-login.py to be run first for authentication.")
        return

    api = AxonAPI()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "gallery"
    cmd_args = sys.argv[2:]

    if cmd == "status":
        if TOKEN_FILE.exists():
            data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            print(f"  Login:  {data.get('loginId', '?')}")
            print(f"  UUID:   {data.get('uuid', '?')}")
            print(f"  Expiry: {data.get('tokenExpiry', '?')}")
            print(f"  Nick:   {data.get('nickname', '?')}")
        else:
            print("Not logged in. Run razer-login.py first.")
        return

    print("Logging in...")
    if not api.login_from_token_file():
        print("Login failed. Run razer-login.py to refresh token.")
        sys.exit(1)
    print(f"Logged in (user_id={api.user_id}, country={api.country})")

    if cmd == "categories":
        print_categories(api)
    elif cmd == "gallery":
        print_gallery(api, cmd_args)
    elif cmd == "download":
        if not cmd_args:
            print("Usage: razer-sync.py download <wallpaper_id> [opts]")
            sys.exit(1)
        download_wallpaper(api, cmd_args[0], cmd_args[1:])
    elif cmd == "artists":
        print_artists(api, cmd_args)
    elif cmd == "local":
        print_local_wallpapers(api)
    elif cmd == "detail":
        if not cmd_args:
            print("Usage: razer-sync.py detail <wallpaper_id>")
            sys.exit(1)
        print_wallpaper_detail(api, cmd_args[0])
    elif cmd == "fav":
        if not cmd_args:
            print("Usage: razer-sync.py fav <wallpaper_id>")
            sys.exit(1)
        print_favorite_toggle(api, cmd_args[0], "add")
    elif cmd == "unfav":
        if not cmd_args:
            print("Usage: razer-sync.py unfav <wallpaper_id>")
            sys.exit(1)
        print_favorite_toggle(api, cmd_args[0], "remove")
    else:
        print(f"Unknown command: {cmd}")
        print("Run with --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
