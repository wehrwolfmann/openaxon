using System;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace RazerSequoia.SequoiaUserManager;

public class RazerLoginForm : Form
{
	private WebView2 _webView;

	private static readonly string TokenFile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Razer", "RazerAxon", "wine_login_token.json");

	public string? ResultToken { get; private set; }

	public string? ResultUuid { get; private set; }

	public string? ResultLoginId { get; private set; }

	public bool LoginSuccess { get; private set; }

	public RazerLoginForm()
	{
		//IL_0036: Unknown result type (might be due to invalid IL or missing references)
		//IL_0040: Expected O, but got Unknown
		((Control)this).Text = "Razer ID - Login";
		((Control)this).Width = 1280;
		((Control)this).Height = 720;
		((Form)this).StartPosition = (FormStartPosition)1;
		((Form)this).FormBorderStyle = (FormBorderStyle)4;
		_webView = new WebView2();
		((Control)_webView).Dock = (DockStyle)5;
		((Control)this).Controls.Add((Control)(object)_webView);
		((Form)this).Load += async delegate
		{
			await InitWebView();
		};
	}

	private async Task InitWebView()
	{
		_ = 1;
		try
		{
			CoreWebView2Environment val = await CoreWebView2Environment.CreateAsync((string)null, Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Razer", "RazerAxon", "LoginWebView"), (CoreWebView2EnvironmentOptions)null);
			await _webView.EnsureCoreWebView2Async(val);
			_webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync("\n                    window.callbackObjforjs = {\n                        onEvent: function(action, data) {\n                            console.log('RazerID callback: ' + action);\n                            if (action === 'SET_LOGIN_SUCCESS_FROM_WEB' || action === 'SET_LOGIN_SUCCESS') {\n                                window.chrome.webview.postMessage(JSON.stringify({action: action, data: data}));\n                            }\n                            if (action === 'SET_LOGIN_FAIL_FROM_WEB') {\n                                console.log('Login failed');\n                            }\n                            if (action === 'GET_LANGUAGE') {\n                                return JSON.stringify({language: 'English'});\n                            }\n                            if (action === 'GET_THEME') {\n                                return JSON.stringify({theme: 'Dark'});\n                            }\n                            if (action === 'SET_WEBAPP_READY') {\n                                console.log('Razer ID ready, sending TRY_LOGIN');\n                                // After page is ready, tell it to show login form\n                                setTimeout(function() {\n                                    if (typeof callJSFromClient === 'function') {\n                                        callJSFromClient('TRY_LOGIN', '{}');\n                                    }\n                                }, 500);\n                            }\n                            if (action === 'GET_LOGIN_STATUS') {\n                                return JSON.stringify({isLoggedIn: false});\n                            }\n                            if (action === 'GET_LOGGED_USER_INFO') {\n                                return JSON.stringify({});\n                            }\n                            if (action === 'IS_WINDOW_VISIBLE') {\n                                return JSON.stringify({visible: true});\n                            }\n                            if (action === 'GET_MACHINE_ID_INFO') {\n                                return JSON.stringify({machineId: 'wine-linux'});\n                            }\n                            return '';\n                        }\n                    };\n                    // Also define callJSFromClient if the page expects it\n                    if (!window.callJSFromClient) {\n                        window.callJSFromClient = function(action, data) {\n                            console.log('callJSFromClient: ' + action);\n                        };\n                    }\n                ");
			_webView.CoreWebView2.WebMessageReceived += delegate(object? sender, CoreWebView2WebMessageReceivedEventArgs args)
			{
				//IL_014f: Unknown result type (might be due to invalid IL or missing references)
				try
				{
					JsonDocument.Parse(args.WebMessageAsJson.Trim('"').Replace("\\\"", "\"").Replace("\\\\", "\\"));
					string text = args.TryGetWebMessageAsString();
					if (text != null)
					{
						JsonDocument jsonDocument = JsonDocument.Parse(text);
						string @string = jsonDocument.RootElement.GetProperty("action").GetString();
						if (@string == "SET_LOGIN_SUCCESS_FROM_WEB" || @string == "SET_LOGIN_SUCCESS")
						{
							string string2 = jsonDocument.RootElement.GetProperty("data").GetString();
							if (string2 != null)
							{
								JsonElement rootElement = JsonDocument.Parse(string2).RootElement;
								ResultToken = (rootElement.TryGetProperty("token", out var value) ? value.GetString() : null);
								ResultUuid = (rootElement.TryGetProperty("uuid", out var value2) ? value2.GetString() : null);
								ResultLoginId = (rootElement.TryGetProperty("loginId", out var value3) ? value3.GetString() : null);
								LoginSuccess = true;
								File.WriteAllText(TokenFile, string2);
								MessageBox.Show("Login successful! Restart Razer Axon.", "Razer Axon", (MessageBoxButtons)0, (MessageBoxIcon)64);
								((Form)this).Close();
							}
						}
					}
				}
				catch (Exception ex2)
				{
					Console.WriteLine("Parse error: " + ex2.Message);
				}
			};
			_webView.CoreWebView2.Navigate("https://id.razer.com/");
		}
		catch (Exception ex)
		{
			MessageBox.Show("WebView2 init failed: " + ex.Message, "Error", (MessageBoxButtons)0, (MessageBoxIcon)16);
			((Form)this).Close();
		}
	}

	public static (string? token, string? uuid, string? loginId, string? avatarUrl, string? nickname) LoadSavedToken()
	{
		try
		{
			if (File.Exists(TokenFile))
			{
				JsonElement rootElement = JsonDocument.Parse(File.ReadAllText(TokenFile)).RootElement;
				return (
					token: rootElement.TryGetProperty("token", out var t) ? t.GetString() : null,
					uuid: rootElement.TryGetProperty("uuid", out var u) ? u.GetString() : null,
					loginId: rootElement.TryGetProperty("loginId", out var l) ? l.GetString() : null,
					avatarUrl: rootElement.TryGetProperty("avatarUrl", out var a) ? a.GetString() : null,
					nickname: rootElement.TryGetProperty("nickname", out var n) ? n.GetString() : null
				);
			}
		}
		catch
		{
		}
		return (token: null, uuid: null, loginId: null, avatarUrl: null, nickname: null);
	}
}
