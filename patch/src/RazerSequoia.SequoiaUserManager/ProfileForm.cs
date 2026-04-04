using System;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace RazerSequoia.SequoiaUserManager;

public class ProfileForm : Form
{
    private WebView2 _webView;

    private static readonly string DataDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Razer", "RazerAxon");

    private static readonly string TokenFile = Path.Combine(DataDir, "wine_login_token.json");
    private static readonly string PrefsFile = Path.Combine(DataDir, "wine_prefs.json");

    public ProfileForm()
    {
        Text = "Razer Axon \u2014 Profile";
        Width = 1280;
        Height = 800;
        StartPosition = FormStartPosition.CenterScreen;

        _webView = new WebView2();
        ((Control)_webView).Dock = DockStyle.Fill;
        Controls.Add((Control)(object)_webView);

        Load += async delegate
        {
            await InitWebView();
        };
    }

    private async Task InitWebView()
    {
        try
        {
            var env = await CoreWebView2Environment.CreateAsync(
                null,
                Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "Razer", "RazerAxon", "LoginWebView"),
                null);
            await _webView.EnsureCoreWebView2Async(env);

            // Load saved token to tell SPA the user is already logged in
            string tokenJson = "{}";
            try
            {
                if (File.Exists(TokenFile))
                    tokenJson = File.ReadAllText(TokenFile);
            }
            catch { }

            // Read language and theme from prefs
            string language = "English";
            string theme = "Dark";
            try
            {
                if (File.Exists(PrefsFile))
                {
                    var prefs = JsonDocument.Parse(File.ReadAllText(PrefsFile));
                    if (prefs.RootElement.TryGetProperty("language", out var lang))
                    {
                        string langCode = lang.GetString() ?? "en";
                        language = langCode switch
                        {
                            "ru" => "Russian",
                            "de" => "German",
                            "fr" => "French",
                            "es" => "Spanish",
                            "pt" => "Portuguese",
                            "ja" => "Japanese",
                            "ko" => "Korean",
                            "zh-CN" => "ChineseSimplified",
                            "zh-TW" => "ChineseTraditional",
                            "th" => "Thai",
                            _ => "English",
                        };
                    }
                    if (prefs.RootElement.TryGetProperty("theme", out var th))
                        theme = th.GetString() ?? "Dark";
                }
            }
            catch { }

            // Escape for embedding in JS string literal
            string escapedToken = JsonSerializer.Serialize(tokenJson);
            string escapedLang = JsonSerializer.Serialize(language);
            string escapedTheme = JsonSerializer.Serialize(theme);

            // Natasha bridge shim — reports user as logged in,
            // so SPA shows the full account/profile page
            string bridgeScript = @"
                (function() {
                    var tokenData = " + escapedToken + @";
                    var parsedToken = {};
                    try { parsedToken = JSON.parse(tokenData); } catch(e) {}
                    var userLang = " + escapedLang + @";
                    var userTheme = " + escapedTheme + @";

                    window.callbackObjforjs = {
                        onEvent: function(action, data, callback) {
                            var cb = (typeof callback === 'function') ? callback : function(){};
                            switch (action) {
                                case 'SET_WEBAPP_READY':
                                    cb('{""version"":""1.0.0""}');
                                    break;
                                case 'GET_LANGUAGE':
                                    cb(JSON.stringify({language: userLang}));
                                    break;
                                case 'GET_THEME':
                                    cb(JSON.stringify({theme: userTheme}));
                                    break;
                                case 'GET_LOGIN_STATUS':
                                    cb(JSON.stringify({isLoggedIn: true}));
                                    break;
                                case 'IS_WINDOW_VISIBLE':
                                    cb('{""visible"":true}');
                                    break;
                                case 'GET_MACHINE_ID_INFO':
                                    cb('{""machineId"":""wine-linux""}');
                                    break;
                                case 'GET_LOGGED_USER_INFO':
                                case 'GET_LAST_CLIENT_LOGIN_USER':
                                    cb(JSON.stringify(parsedToken));
                                    break;
                                case 'GET_GUEST_USER':
                                case 'GET_GUEST_STATISTICS':
                                    cb('{}');
                                    break;
                                case 'SET_WEB_PAGE':
                                case 'SET_LOGIN_FAIL_FROM_WEB':
                                case 'START_SSI_LOGIN':
                                case 'CLOSE_SSI':
                                    break;
                                case 'START_LOGOUT':
                                    setTimeout(function() {
                                        if (typeof window.callJSFromClient === 'function')
                                            window.callJSFromClient('SET_LOGOUT_COMPLETE', '{""reason"":""reload""}');
                                    }, 300);
                                    break;
                                case 'SET_LOGIN_SUCCESS_FROM_WEB':
                                case 'SET_LOGIN_SUCCESS':
                                    break;
                            }
                            return '';
                        }
                    };
                    if (!window.callJSFromClient) {
                        window.callJSFromClient = function(action, data) {
                            console.log('callJSFromClient: ' + action);
                        };
                    }
                })();
            ";

            await _webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(bridgeScript);
            _webView.CoreWebView2.Navigate("https://id.razer.com/");
        }
        catch (Exception ex)
        {
            MessageBox.Show("WebView2 init failed: " + ex.Message, "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            Close();
        }
    }
}
