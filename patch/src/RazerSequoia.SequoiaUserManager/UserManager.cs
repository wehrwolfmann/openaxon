using System;
using System.Collections.Generic;
using System.Diagnostics;
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
		return Task.CompletedTask;
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
		return Task.CompletedTask;
	}

	public Task OpenFeedbackWindowAsync()
	{
		return Task.CompletedTask;
	}

	public Task OpenFeatureFeedbackWindowAsync()
	{
		return Task.CompletedTask;
	}

	public Task OpenSupportFeedbackWindowAsync()
	{
		return Task.CompletedTask;
	}

	public Task OpenCrashWindowAsync()
	{
		return Task.CompletedTask;
	}

	public Task OpenProfileWindowAsync()
	{
		try
		{
			var thread = new Thread(() =>
			{
				Application.EnableVisualStyles();
				Application.Run(new ProfileForm());
			});
			thread.SetApartmentState(ApartmentState.STA);
			thread.Start();
		}
		catch { }
		return Task.CompletedTask;
	}

	public Task OpenPasswordWindowAsync()
	{
		return Task.CompletedTask;
	}

	public Task OpenUpdateWindowAsync()
	{
		return Task.CompletedTask;
	}

	public static string GetNatashaStateDescription()
	{
		return "Service not found";
	}

	public void Dispose()
	{
	}
}
