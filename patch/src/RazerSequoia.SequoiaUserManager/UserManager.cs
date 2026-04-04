using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using RazerSequoia.ILogger;
using RazerSequoia.ISequoiaSettingManager;
using RazerSequoia.ISequoiaUserManager;
using RazerSequoia.ISequoiaUserManager.Models;

namespace RazerSequoia.SequoiaUserManager;

public class UserManager : IUserManager, IDisposable
{
	private readonly ISettingManager? _settingManager;

	private readonly ISequoiaLogger? _logger;

	private static readonly string PrefsFile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Razer", "RazerAxon", "wine_prefs.json");

	private readonly SequoiaFeedbackConfig _feedbackCfg;

	private NotifyIcon? _trayIcon;
	private Thread? _trayThread;
	private readonly List<SystrayWallpaper> _systrayWallpapers = new();

	public SequoiaUser? User { get; private set; }

	public SequoiaUserProfile? Profile { get; private set; }

	public string? Language { get; private set; }

	public ThemeNames Theme { get; private set; }

	public ISequoiaFeedbackConfig FeedbackConfig => (ISequoiaFeedbackConfig)(object)_feedbackCfg;

	public event EventHandler<UserChangedArgs>? UserChanged;

	public event EventHandler<ProfileChangedArgs>? ProfileChanged;

	public event EventHandler<LanguageChangedArgs>? LanguageChanged;

	public event EventHandler<ThemeChangedArgs>? ThemeChanged;

	public event EventHandler? LoggedOut;

	public event EventHandler<string>? OnSystrayOpenWallpaper;

	public event EventHandler OnUserExitAppTriggered;

	public event EventHandler? SystrayExitApp;

	public UserManager(string launchPath, ISettingManager settingManager, ISequoiaLogger? logger)
	{
		_settingManager = settingManager;
		_logger = logger;
		_feedbackCfg = new SequoiaFeedbackConfig(settingManager, (IUserManager?)(object)this, logger);
		LoadPrefs();
	}

	private void LoadPrefs()
	{
		//IL_0072: Unknown result type (might be due to invalid IL or missing references)
		try
		{
			if (File.Exists(PrefsFile))
			{
				JsonDocument jsonDocument = JsonDocument.Parse(File.ReadAllText(PrefsFile));
				if (jsonDocument.RootElement.TryGetProperty("language", out var value))
				{
					Language = value.GetString();
				}
				if (jsonDocument.RootElement.TryGetProperty("theme", out var value2))
				{
					Theme = (ThemeNames)((!Enum.TryParse<ThemeNames>(value2.GetString(), out ThemeNames result)) ? 1 : ((int)result));
				}
			}
		}
		catch
		{
		}
	}

	private void SavePrefs()
	{
		//IL_0026: Unknown result type (might be due to invalid IL or missing references)
		//IL_002b: Unknown result type (might be due to invalid IL or missing references)
		try
		{
			string directoryName = Path.GetDirectoryName(PrefsFile);
			if (!string.IsNullOrEmpty(directoryName))
			{
				Directory.CreateDirectory(directoryName);
			}
			string prefsFile = PrefsFile;
			string? language = Language;
			ThemeNames theme = Theme;
			File.WriteAllText(prefsFile, JsonSerializer.Serialize(new
			{
				language = language,
				theme = theme.ToString()
			}));
		}
		catch
		{
		}
	}

	public Task<SequoiaUser?> LoginAsync(TimeSpan timeout, CancellationToken ct)
	{
		var (text, text2, text3, text4, text5) = RazerLoginForm.LoadSavedToken();
		if (!string.IsNullOrEmpty(text) && !string.IsNullOrEmpty(text2))
		{
			User = new SequoiaUser(text2, text, (DateTime?)DateTime.UtcNow.AddDays(30.0), text3 ?? text2, false);
		}
		else
		{
			User = new SequoiaUser("guest-" + Guid.NewGuid().ToString("N").Substring(0, 8), "noAuth", (DateTime?)DateTime.UtcNow.AddDays(365.0), "guest@local", true);
		}

		// Fill profile from token file (avatarUrl, nickname saved by razer-login.py)
		Profile = new SequoiaUserProfile
		{
			NickName = !string.IsNullOrEmpty(text5) ? text5 : (text3 ?? text2 ?? "User"),
			AvatarUrl = !string.IsNullOrEmpty(text4) ? text4 : null
		};

		try
		{
			ISettingManager? settingManager = _settingManager;
			if (settingManager != null)
			{
				settingManager.SetCurrentUser((ISequoiaUser)(object)User);
			}
		}
		catch
		{
		}
		this.UserChanged?.Invoke(this, new UserChangedArgs(User));
		this.ProfileChanged?.Invoke(this, new ProfileChangedArgs(Profile));
		return Task.FromResult<SequoiaUser>(User);
	}

	public string? GetUserToken()
	{
		SequoiaUser? user = User;
		if (user == null)
		{
			return null;
		}
		return user.Token;
	}

	public Task LogoutAsync()
	{
		try
		{
			Thread thread = new Thread((ThreadStart)delegate
			{
				Application.EnableVisualStyles();
				Application.Run((Form)(object)new RazerLoginForm());
			});
			thread.SetApartmentState(ApartmentState.STA);
			thread.Start();
		}
		catch
		{
		}
		return Task.CompletedTask;
	}

	public Task<UserBalances> GetUserBalancesAsync()
	{
		//IL_0000: Unknown result type (might be due to invalid IL or missing references)
		//IL_000a: Expected O, but got Unknown
		return Task.FromResult<UserBalances>(new UserBalances());
	}

	public Task SetLanguageAsync(string language)
	{
		//IL_001b: Unknown result type (might be due to invalid IL or missing references)
		//IL_0025: Expected O, but got Unknown
		Language = language;
		SavePrefs();
		this.LanguageChanged?.Invoke(this, new LanguageChangedArgs(language));
		return Task.CompletedTask;
	}

	public Task SetThemeAsync(ThemeNames theme)
	{
		//IL_0001: Unknown result type (might be due to invalid IL or missing references)
		//IL_001a: Unknown result type (might be due to invalid IL or missing references)
		//IL_001b: Unknown result type (might be due to invalid IL or missing references)
		//IL_0025: Expected O, but got Unknown
		Theme = theme;
		SavePrefs();
		this.ThemeChanged?.Invoke(this, new ThemeChangedArgs(theme));
		return Task.CompletedTask;
	}

	public Task EnsureSystrayAsync()
	{
		if (_trayIcon != null || _trayThread != null)
			return Task.CompletedTask;

		_trayThread = new Thread(() =>
		{
			Application.EnableVisualStyles();

			var icon = LoadTrayIcon();
			_trayIcon = new NotifyIcon
			{
				Icon = icon,
				Text = "Razer Axon",
				Visible = true,
				ContextMenuStrip = BuildTrayMenu(),
			};

			_trayIcon.MouseClick += (s, e) =>
			{
				if (e.Button == MouseButtons.Left)
					FireOpenWallpaper("");
			};

			Application.Run();
		});
		_trayThread.SetApartmentState(ApartmentState.STA);
		_trayThread.IsBackground = true;
		_trayThread.Start();

		return Task.CompletedTask;
	}

	private Icon LoadTrayIcon()
	{
		try
		{
			string iconPath = Path.Combine(
				Path.GetDirectoryName(typeof(UserManager).Assembly.Location) ?? "",
				"Axon.ico");
			if (File.Exists(iconPath))
				return new Icon(iconPath);
		}
		catch { }
		return SystemIcons.Application;
	}

	private ContextMenuStrip BuildTrayMenu()
	{
		var menu = new ContextMenuStrip();
		menu.BackColor = Color.FromArgb(30, 30, 30);
		menu.ForeColor = Color.FromArgb(68, 215, 88);

		var openItem = new ToolStripMenuItem("Razer Axon");
		openItem.Font = new Font(openItem.Font, FontStyle.Bold);
		openItem.Click += (s, e) => FireOpenWallpaper("");
		menu.Items.Add(openItem);

		menu.Items.Add(new ToolStripSeparator());

		var wallpaperPlaceholder = new ToolStripMenuItem("No wallpapers") { Enabled = false };
		wallpaperPlaceholder.Name = "wallpapers_placeholder";
		menu.Items.Add(wallpaperPlaceholder);

		menu.Items.Add(new ToolStripSeparator());

		var profileItem = new ToolStripMenuItem("Profile");
		profileItem.Click += (s, e) => OpenProfileWindowAsync();
		menu.Items.Add(profileItem);

		var exitItem = new ToolStripMenuItem("Exit");
		exitItem.Click += (s, e) => FireExit();
		menu.Items.Add(exitItem);

		return menu;
	}

	private void UpdateTrayWallpapers()
	{
		if (_trayIcon?.ContextMenuStrip == null) return;

		var menu = _trayIcon.ContextMenuStrip;
		if (menu.InvokeRequired)
		{
			menu.Invoke(new Action(UpdateTrayWallpapers));
			return;
		}

		int firstSep = -1;
		int secondSep = -1;
		for (int i = 0; i < menu.Items.Count; i++)
		{
			if (menu.Items[i] is ToolStripSeparator)
			{
				if (firstSep == -1) firstSep = i;
				else { secondSep = i; break; }
			}
		}

		if (firstSep >= 0 && secondSep > firstSep)
		{
			for (int i = secondSep - 1; i > firstSep; i--)
				menu.Items.RemoveAt(i);

			int insertAt = firstSep + 1;
			if (_systrayWallpapers.Count == 0)
			{
				var placeholder = new ToolStripMenuItem("No wallpapers") { Enabled = false };
				menu.Items.Insert(insertAt, placeholder);
			}
			else
			{
				foreach (var wp in _systrayWallpapers)
				{
					var item = new ToolStripMenuItem(wp.Name ?? wp.Id ?? "Wallpaper");
					string wpId = wp.Id ?? "";
					item.Click += (s, e) => FireOpenWallpaper(wpId);
					menu.Items.Insert(insertAt++, item);
				}
			}
		}
	}

	public void TriggeredExitApp()
	{
		this.OnUserExitAppTriggered?.Invoke(this, EventArgs.Empty);
	}

	public Task<string> GetZVaultWebUrl()
	{
		return Task.FromResult("https://zvault.razer.com");
	}

	public Task SetSystrayGamesAsync(IEnumerable<SystrayWallpaper> wallpapers)
	{
		_systrayWallpapers.Clear();
		_systrayWallpapers.AddRange(wallpapers);
		UpdateTrayWallpapers();
		return Task.CompletedTask;
	}

	public Task OpenFeedbackWindowAsync()
	{
		ShowWebPage("https://www.razer.com/contact-us", "Razer Axon \u2014 Feedback");
		return Task.CompletedTask;
	}

	public Task OpenFeatureFeedbackWindowAsync()
	{
		ShowWebPage("https://www.razer.com/contact-us", "Razer Axon \u2014 Feature Feedback");
		return Task.CompletedTask;
	}

	public Task OpenSupportFeedbackWindowAsync()
	{
		ShowWebPage("https://mysupport.razer.com/", "Razer Axon \u2014 Support");
		return Task.CompletedTask;
	}

	public Task OpenCrashWindowAsync()
	{
		ShowWebPage("https://www.razer.com/contact-us", "Razer Axon \u2014 Report");
		return Task.CompletedTask;
	}

	public Task OpenProfileWindowAsync()
	{
		ShowWebPage("https://id.razer.com/", "Razer Axon \u2014 Profile");
		return Task.CompletedTask;
	}

	public Task OpenPasswordWindowAsync()
	{
		ShowWebPage("https://id.razer.com/", "Razer Axon \u2014 Change Password");
		return Task.CompletedTask;
	}

	public Task OpenUpdateWindowAsync()
	{
		return Task.CompletedTask;
	}

	private void ShowWebPage(string url, string title)
	{
		try
		{
			var thread = new Thread(() =>
			{
				Application.EnableVisualStyles();
				Application.Run(new ProfileForm(url, title));
			});
			thread.SetApartmentState(ApartmentState.STA);
			thread.Start();
		}
		catch { }
	}

	internal void FireOpenWallpaper(string id) =>
		this.OnSystrayOpenWallpaper?.Invoke(this, id);

	internal void FireExit()
	{
		this.SystrayExitApp?.Invoke(this, EventArgs.Empty);
		this.OnUserExitAppTriggered?.Invoke(this, EventArgs.Empty);
	}

	public static string GetNatashaStateDescription()
	{
		return "Service not found";
	}

	public void Dispose()
	{
		if (_trayIcon != null)
		{
			_trayIcon.Visible = false;
			_trayIcon.Dispose();
			_trayIcon = null;
		}
	}
}
