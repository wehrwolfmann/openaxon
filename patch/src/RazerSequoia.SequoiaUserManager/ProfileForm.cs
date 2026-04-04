using System;
using System.Drawing;
using System.IO;
using System.Net.Http;
using System.Windows.Forms;
using RazerSequoia.ISequoiaUserManager;
using RazerSequoia.ISequoiaUserManager.Models;

namespace RazerSequoia.SequoiaUserManager;

public class ProfileForm : Form
{
    private static readonly HttpClient _httpClient = new HttpClient();

    public ProfileForm(SequoiaUserProfile profile, SequoiaUser user)
    {
        Text = "Razer Axon — Profile";
        Width = 400;
        Height = 320;
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        BackColor = Color.FromArgb(30, 30, 30);

        var avatarBox = new PictureBox
        {
            Width = 80,
            Height = 80,
            Left = 160,
            Top = 20,
            SizeMode = PictureBoxSizeMode.Zoom,
            BackColor = Color.FromArgb(50, 50, 50),
        };
        Controls.Add(avatarBox);

        // Load avatar async
        if (!string.IsNullOrEmpty(profile?.AvatarUrl))
        {
            try
            {
                var bytes = _httpClient.GetByteArrayAsync(profile.AvatarUrl).Result;
                using var ms = new MemoryStream(bytes);
                avatarBox.Image = Image.FromStream(ms);
            }
            catch { }
        }

        var nickLabel = new Label
        {
            Text = profile?.NickName ?? "Unknown",
            ForeColor = Color.FromArgb(68, 215, 88),
            Font = new Font("Segoe UI", 16, FontStyle.Bold),
            AutoSize = false,
            Width = 360,
            Height = 35,
            Left = 20,
            Top = 115,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        Controls.Add(nickLabel);

        var emailLabel = new Label
        {
            Text = user?.Account ?? "",
            ForeColor = Color.FromArgb(180, 180, 180),
            Font = new Font("Segoe UI", 10),
            AutoSize = false,
            Width = 360,
            Height = 25,
            Left = 20,
            Top = 150,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        Controls.Add(emailLabel);

        var idLabel = new Label
        {
            Text = "ID: " + (user?.Id ?? ""),
            ForeColor = Color.FromArgb(120, 120, 120),
            Font = new Font("Segoe UI", 9),
            AutoSize = false,
            Width = 360,
            Height = 20,
            Left = 20,
            Top = 180,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        Controls.Add(idLabel);

        var guestLabel = new Label
        {
            Text = (user?.IsGuest == true) ? "Guest account" : "Razer ID",
            ForeColor = Color.FromArgb(100, 100, 100),
            Font = new Font("Segoe UI", 9),
            AutoSize = false,
            Width = 360,
            Height = 20,
            Left = 20,
            Top = 205,
            TextAlign = ContentAlignment.MiddleCenter,
        };
        Controls.Add(guestLabel);

        var closeBtn = new Button
        {
            Text = "OK",
            Width = 100,
            Height = 35,
            Left = 150,
            Top = 240,
            FlatStyle = FlatStyle.Flat,
            BackColor = Color.FromArgb(68, 215, 88),
            ForeColor = Color.Black,
            Font = new Font("Segoe UI", 10, FontStyle.Bold),
        };
        closeBtn.Click += (s, e) => Close();
        Controls.Add(closeBtn);
    }
}
