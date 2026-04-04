#!/usr/bin/env python3
"""
Razer Axon Login Helper

Two-phase login:
  Phase 1: Open id.razer.com as normal website — user logs in.
  Phase 2: After login detected (currentUserId in localStorage),
           reload with natasha bridge shim — SPA sees active session
           and sends JWT via SET_LOGIN_SUCCESS callback.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk, WebKit2

RAZER_ID_URL = "https://id.razer.com/"

WINEPREFIX = Path(os.environ.get("WINEPREFIX", Path.home() / ".wine"))
TOKEN_DIR = WINEPREFIX / "drive_c/users" / os.environ["USER"] / "AppData/Local/Razer/RazerAxon"
TOKEN_FILE = TOKEN_DIR / "wine_login_token.json"

# Phase 1: Check if user is logged in (poll localStorage)
CHECK_LOGIN_JS = """
(function() {
    return localStorage.getItem('currentUserId') || '';
})();
"""

# Phase 2: Natasha bridge shim — injected after login detected.
# SPA sees active session + callbackObjforjs → sends SET_LOGIN_SUCCESS with JWT.
NATASHA_BRIDGE_JS = r"""
(function() {
    window.callbackObjforjs = {
        onEvent: function(action, payload, callback) {
            var cb = (typeof callback === 'function') ? callback : function(){};
            switch (action) {
                case 'SET_WEBAPP_READY': cb('{"version":"1.0.0"}'); break;
                case 'GET_LANGUAGE':     cb('{"language":"en"}'); break;
                case 'GET_THEME':        cb('{"theme":"Dark"}'); break;
                case 'GET_LOGIN_STATUS': cb(JSON.stringify({isLoggedIn: true})); break;
                case 'IS_WINDOW_VISIBLE': cb('{"visible":true}'); break;
                case 'GET_MACHINE_ID_INFO': cb('{"machineId":"wine-linux"}'); break;
                case 'GET_LOGGED_USER_INFO':
                case 'GET_LAST_CLIENT_LOGIN_USER':
                case 'GET_GUEST_USER':
                case 'GET_GUEST_STATISTICS':
                    cb('{}'); break;
                case 'SET_WEB_PAGE':
                case 'SET_LOGIN_FAIL_FROM_WEB':
                case 'START_SSI_LOGIN':
                case 'CLOSE_SSI':
                    break;
                case 'START_LOGOUT':
                    setTimeout(function() {
                        if (typeof window.callJSFromClient === 'function')
                            window.callJSFromClient('SET_LOGOUT_COMPLETE', '{"reason":"reload"}');
                    }, 300);
                    break;
                case 'SET_LOGIN_SUCCESS_FROM_WEB':
                case 'SET_LOGIN_SUCCESS':
                    var data = (typeof payload === 'string') ? payload : JSON.stringify(payload);
                    window.webkit.messageHandlers.razerLogin.postMessage(data);
                    break;
            }
            return '';
        }
    };
    if (!window.callJSFromClient) {
        window.callJSFromClient = function(){};
    }
})();
"""


def save_token(token_data: dict) -> None:
    if isinstance(token_data, str):
        token_data = json.loads(token_data)

    token_record = {
        "convertFromGuest": token_data.get("convertFromGuest", False),
        "token": token_data.get("token", ""),
        "isOnline": True,
        "isGuest": token_data.get("isGuest", False),
        "uuid": token_data.get("uuid", ""),
        "loginId": token_data.get("loginId", ""),
        "tokenExpiry": token_data.get("tokenExpiry", ""),
        "stayLoggedIn": True,
        "avatarUrl": token_data.get("avatarUrl", ""),
        "nickname": token_data.get("nickname", ""),
    }

    if not token_record["tokenExpiry"] and token_record["token"]:
        try:
            import base64
            p = token_record["token"].split(".")[1]
            p += "=" * (4 - len(p) % 4)
            jwt_data = json.loads(base64.urlsafe_b64decode(p))
            if "exp" in jwt_data:
                exp_dt = datetime.fromtimestamp(jwt_data["exp"], tz=timezone.utc)
                token_record["tokenExpiry"] = exp_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except Exception:
            exp_dt = datetime.now(tz=timezone.utc) + timedelta(hours=24)
            token_record["tokenExpiry"] = exp_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(token_record, indent=2), encoding="utf-8")

    print(f"\nToken saved to {TOKEN_FILE}")
    print(f"  UUID:    {token_record['uuid']}")
    print(f"  LoginId: {token_record['loginId']}")
    print(f"  Expiry:  {token_record['tokenExpiry']}")
    print(f"  Guest:   {token_record['isGuest']}")


def show_current_token() -> None:
    if TOKEN_FILE.exists():
        try:
            data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            expiry = data.get("tokenExpiry", "")
            login_id = data.get("loginId", "")
            is_guest = data.get("isGuest", True)
            print(f"Current token: {login_id} (guest={is_guest}, expires={expiry})")
            if expiry:
                try:
                    exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                    now = datetime.now(tz=timezone.utc)
                    if exp_dt > now:
                        print(f"  Valid for: {exp_dt - now}")
                    else:
                        print(f"  EXPIRED {now - exp_dt} ago")
                except ValueError:
                    pass
        except (json.JSONDecodeError, OSError):
            pass
    else:
        print("No existing token found.")
    print()


class RazerLoginWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Razer Axon - Login")
        self.set_default_size(1024, 700)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", Gtk.main_quit)
        self._phase = 1
        self._login_done = False
        self._user_id = ""

        ctx = WebKit2.WebContext.get_default()
        self.webview = WebKit2.WebView.new_with_context(ctx)

        self.content_manager = self.webview.get_user_content_manager()

        # Message handler for Phase 2 token reception
        self.content_manager.register_script_message_handler("razerLogin")
        self.content_manager.connect("script-message-received::razerLogin",
                                     self._on_login_message)

        self.webview.connect("load-changed", self._on_load_changed)
        self.webview.connect("create", self._on_create_webview)

        settings = self.webview.get_settings()
        settings.set_property("enable-javascript", True)
        settings.set_property("enable-developer-extras", True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.webview)
        self.add(scrolled)

        # Persistent cookies
        cookie_mgr = ctx.get_cookie_manager()
        TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        cookie_mgr.set_persistent_storage(
            str(TOKEN_DIR / "webkit_cookies.db"),
            WebKit2.CookiePersistentStorage.SQLITE)

        # Phase 1: load without bridge
        print("  Phase 1: Waiting for login...")
        self.webview.load_uri(RAZER_ID_URL)

    def _on_load_changed(self, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            uri = webview.get_uri() or ""
            print(f"  [nav] {uri}")
            if self._phase == 1 and not self._login_done:
                # Start polling for currentUserId
                self._poll_login()
            elif self._phase == 2:
                print("  Phase 2: Waiting for token from natasha bridge...")

    def _poll_login(self):
        """Poll localStorage for currentUserId to detect login."""
        if self._login_done or self._phase != 1:
            return
        self.webview.evaluate_javascript(
            CHECK_LOGIN_JS, -1, None, None, None,
            self._on_poll_result, None)

    def _on_poll_result(self, webview, result, user_data):
        if self._login_done or self._phase != 1:
            return
        try:
            js_value = webview.evaluate_javascript_finish(result)
            user_id = js_value.to_string().strip()
            if user_id and user_id != "null" and user_id.startswith("RZR_"):
                self._user_id = user_id
                print(f"  [phase1] Login detected: {user_id}")
                self._start_phase2()
                return
        except Exception:
            pass
        # Retry in 1 second
        GLib.timeout_add(1000, self._poll_login)

    def _start_phase2(self):
        """Inject natasha bridge and reload to get JWT."""
        self._phase = 2
        print("  Phase 2: Reloading with natasha bridge...")

        # Add bridge script
        script = WebKit2.UserScript(
            NATASHA_BRIDGE_JS,
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.START,
            None, None,
        )
        self.content_manager.add_script(script)

        # Reload page — now with bridge
        self.webview.load_uri(RAZER_ID_URL)

    def _on_login_message(self, content_manager, js_result):
        """Receive JWT from natasha bridge (Phase 2)."""
        if self._login_done:
            return
        self._login_done = True
        data_str = js_result.get_js_value().to_string()
        print(f"  [phase2] Received token ({len(data_str)} bytes)")
        try:
            token_data = json.loads(data_str)
            if not token_data.get("uuid"):
                token_data["uuid"] = self._user_id
            self._token_data = token_data
            # Phase 3: extract profile from localStorage
            print("  Phase 3: Extracting profile...")
            self._fetch_profile()
        except json.JSONDecodeError as e:
            print(f"  [error] Parse error: {e}", file=sys.stderr)
            print(f"  [error] Data (first 500): {data_str[:500]}", file=sys.stderr)

    def _fetch_profile(self):
        """Extract avatar/nickname from Razer ID localStorage."""
        # Dump all localStorage keys and values to find profile data
        js = """(function() {
            var result = {};
            for (var i = 0; i < localStorage.length; i++) {
                var k = localStorage.key(i);
                result[k] = localStorage.getItem(k);
            }
            return JSON.stringify(result);
        })();"""
        self.webview.evaluate_javascript(
            js, -1, None, None, None,
            self._on_profile_result, None)

    def _on_profile_result(self, webview, result, user_data):
        profile_data = {}
        try:
            js_value = webview.evaluate_javascript_finish(result)
            raw = js_value.to_string()
            profile_data = json.loads(raw) if raw else {}
        except Exception as e:
            print(f"  [phase3] Could not extract profile: {e}")

        # Find current user's profile in the "users" array
        avatar_url = None
        nickname = None
        users_raw = profile_data.get("users", "")
        if users_raw:
            try:
                users = json.loads(users_raw)
                if isinstance(users, list):
                    for u in users:
                        if u.get("userId") == self._user_id:
                            avatar_url = u.get("avatar")
                            nickname = u.get("razerId")
                            break
                    # Fallback to first user if no match
                    if not avatar_url and users:
                        avatar_url = users[0].get("avatar")
                        nickname = nickname or users[0].get("razerId")
            except (json.JSONDecodeError, TypeError):
                pass

        if avatar_url:
            self._token_data["avatarUrl"] = avatar_url
            print(f"  [phase3] Avatar: {avatar_url}")
        if nickname:
            self._token_data["nickname"] = nickname
            print(f"  [phase3] Nickname: {nickname}")

        save_token(self._token_data)
        self._show_success(self._token_data.get("loginId", self._user_id))

    def _show_success(self, login_id):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Login successful!",
        )
        dialog.format_secondary_text(
            f"Logged in as: {login_id}\n"
            f"Token saved. Restart Razer Axon."
        )
        dialog.run()
        dialog.destroy()
        Gtk.main_quit()

    def _on_create_webview(self, webview, navigation_action):
        uri = navigation_action.get_request().get_uri()
        if uri:
            print(f"  [popup] {uri}")
            self.webview.load_uri(uri)
        return None


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: razer-login.py [--status]")
        print()
        print("Opens Razer ID login page. After login, saves token for Razer Axon.")
        print("  --status  Show current token status and exit")
        return

    show_current_token()

    if "--status" in sys.argv:
        return

    print(f"Opening {RAZER_ID_URL} ...")
    print("Log in with your Razer ID. The window will close automatically.\n")

    win = RazerLoginWindow()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
