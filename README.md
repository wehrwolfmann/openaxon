# OpenAxon — Razer Axon на Linux

Запуск [Razer Axon](https://www.razer.com/software/axon) на Linux через Wine — с поддержкой авторизации, фиксами панели задач и расшифровкой обоев.

## Что входит в комплект

| Файл | Описание |
|------|----------|
| `razer-login.py` | Авторизация в Razer ID |
| `razer-token-inject.py` | Инжекция токена в Razer Central Service (для работы без патча DLL) |
| `razer-axon.sh` | Скрипт запуска с Wine/WebView2 и фиксами панели задач |
| `razer-axon-decrypt.py` | Извлечение зашифрованных видео-обоев |
| `patch/RazerAxon.UserManager.dll` | Патченная DLL (устаревший метод, см. ниже) |

## Зависимости

### Обязательные

- **Wine** (проверено с Wine 9.x / 10.x)
- **Python 3.10+**
- **PyGObject** с GTK4, libadwaita и WebKit2
- **xdotool**, **xprop** (для фикса панели задач на X11)
- **7z** или **unzip** (для расшифровки обоев)

### Опциональные

- **mpvpaper** — видео-обои на Wayland
- **xwinwrap** + **mpv** — видео-обои на X11
- **feh** — установка статичных обоев (fallback)

### Arch Linux / CachyOS

```bash
sudo pacman -S wine python-gobject gtk4 libadwaita webkit2gtk-4.1 xdotool xorg-xprop p7zip
```

### Ubuntu / Debian

```bash
sudo apt install wine python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit2-4.1 xdotool x11-utils p7zip-full
```

### Fedora

```bash
sudo dnf install wine python3-gobject gtk4 libadwaita webkit2gtk4.1 xdotool xprop p7zip
```

### openSUSE

```bash
sudo zypper install wine python3-gobject gtk4 libadwaita webkit2gtk3-soup2-devel xdotool xprop p7zip
```

### Void Linux

```bash
sudo xbps-install wine python3-gobject gtk4 libadwaita webkit2gtk41 xdotool xprop p7zip
```

### Gentoo

```bash
sudo emerge app-emulation/wine dev-python/pygobject gui-libs/gtk:4 gui-libs/libadwaita net-libs/webkit-gtk x11-misc/xdotool x11-apps/xprop app-arch/p7zip
```

### NixOS

```nix
# configuration.nix или home-manager
environment.systemPackages = with pkgs; [
  wineWowPackages.stable
  python3
  python3Packages.pygobject3
  gtk4
  libadwaita
  webkitgtk_4_1
  xdotool
  xorg.xprop
  p7zip
];
```

## Установка

### 1. Установка Razer Axon через Wine

```bash
# Скачать установщик
wget -O /tmp/RazerAxonInstaller.exe "https://rzr.to/axon"

# Установить
wine /tmp/RazerAxonInstaller.exe
```

Следуйте установщику. Путь по умолчанию: `C:\Program Files (x86)\Razer\Razer Axon`.

### 2. Регистрация Razer Central Service

Razer Axon использует Razer Central Service для авторизации. Зарегистрируйте его как Wine-сервис (один раз):

```bash
wine sc create RazerCentralService \
  binPath= "C:\Program Files (x86)\Razer\Razer Services\Razer Central\RazerCentralService.exe" \
  start= auto
```

Сервис будет запускаться автоматически при старте Wine.

### 3. Установка скриптов

```bash
cp razer-axon.sh razer-login.py razer-token-inject.py razer-axon-decrypt.py ~/.local/bin/
chmod +x ~/.local/bin/razer-axon.sh ~/.local/bin/razer-login.py ~/.local/bin/razer-token-inject.py ~/.local/bin/razer-axon-decrypt.py
```

### 4. Вход в Razer ID

```bash
# Получить токен
razer-login.py

# Инжектировать в Razer Central Service
razer-token-inject.py
```

`razer-login.py` открывает окно WebKit со страницей входа Razer ID. После авторизации скрипт перехватывает JWT-токен и сохраняет его.

`razer-token-inject.py` передаёт токен в Razer Central Service через named pipe IPC. При первом запуске автоматически собирает .NET-хелпер (требуется `dotnet` SDK 6.0+).

### 5. Запуск Razer Axon

```bash
razer-axon.sh
```

> **Примечание:** Вы также можете войти напрямую через интерфейс Axon — нажмите «Вход» в окне приложения. Токен-инжектор нужен только если прямой вход не работает.

### Альтернативный метод: патченная DLL (устаревший)

Если метод с Razer Central Service не работает, можно заменить `RazerAxon.UserManager.dll` патченной версией:

```bash
AXON_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"
cp "$AXON_DIR/RazerAxon.UserManager.dll" "$AXON_DIR/RazerAxon.UserManager.dll.orig"
cp patch/RazerAxon.UserManager.dll "$AXON_DIR/"
```

Этот метод убирает зависимость от Razer Central, но требует повторного применения после каждого обновления Axon.

## Использование

### Вход / обновление токена

```bash
razer-login.py            # Открыть окно входа
razer-login.py --status   # Проверить статус текущего токена
razer-token-inject.py     # Инжектировать токен в сервис
razer-token-inject.py --status  # Проверить состояние
```

Токены истекают примерно через 24 часа. Обновите через `razer-login.py`, затем `razer-token-inject.py`.

### Запуск

```bash
razer-axon.sh             # Запустить Razer Axon
```

Скрипт запуска:
- Устанавливает переменные окружения Wine для совместимости с WebView2
- Если Axon уже запущен, активирует существующее окно
- Реактивно исправляет видимость в панели задач (Wine устанавливает `WM_TRANSIENT_FOR`, что скрывает окно из панели задач — скрипт отслеживает это и удаляет атрибут)

### Расшифровка обоев

Razer Axon хранит скачанные обои как ZipCrypto-зашифрованные ZIP-архивы, замаскированные под `.mp4`.

```bash
# Автосканирование и извлечение всех обоев
razer-axon-decrypt.py

# Показать только пароли
razer-axon-decrypt.py -p

# Пробный запуск (без извлечения)
razer-axon-decrypt.py -n

# Пропустить уже извлечённые
razer-axon-decrypt.py -s

# Свои директории
razer-axon-decrypt.py -d /путь/к/обоям -o /путь/к/выходу

# Один файл
razer-axon-decrypt.py -f wallpaper.mp4 -c ResourceConfig.txt

# JSON-вывод (для автоматизации)
razer-axon-decrypt.py -j

# Английский интерфейс
razer-axon-decrypt.py --lang en

# Подробный вывод (debug)
razer-axon-decrypt.py -v
```

#### Как работает расшифровка

Пароль каждого обоя вычисляется из его `ResourceConfig.txt`:

```python
import hmac, hashlib
content = open("ResourceConfig.txt").read()
password = hmac.new(b"j6l-aUmhCc@tN%T_", content.encode(), hashlib.sha256).hexdigest()
```

HMAC-ключ захардкожен в .NET-сборках Razer Axon.

## Как это работает

### Архитектура

```
┌─────────────────────────────────────────────────────┐
│ Razer Axon (Wine) — оригинальные файлы, без патчей  │
│                                                     │
│  RazerAxon.exe                                      │
│       │                                             │
│       ├── RazerAxon.UserManager.dll (ОРИГИНАЛ)      │
│       │       └── NacClient ──► named pipe IPC      │
│       │                                             │
│       ├── WebView2 UI ──► axon-api.razer.com        │
│       │                                             │
│       └── WallpaperPlayerManager                    │
│               └── Расшифровка ZIP → воспроизведение  │
│                                                     │
│  RazerCentralService.exe (Wine-сервис)              │
│       ├── AccountManager ──► авторизация             │
│       ├── Named pipe IPC ──► связь с Axon           │
│       └── Razer API ──► manifest.razerapi.com       │
│                                                     │
├─────────────────────────────────────────────────────┤
│ Linux                                               │
│                                                     │
│  razer-login.py ──► id.razer.com ──► JWT-токен      │
│  razer-token-inject.py ──► pipe IPC ──► сервис      │
│  razer-axon.sh ──► Wine + фиксы окружения/панели    │
│  razer-axon-decrypt.py ──► HMAC-SHA256 → unzip      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Как работает авторизация

Razer Central Service (`RazerCentralService.exe`) запускается как Wine-сервис и слушает на named pipe `{FC828A97-C116-453D-BD88-AD471496E03C}`. Axon подключается к нему через `NacClient.dll` для получения токена авторизации.

`razer-token-inject.py` подключается к тому же pipe и отправляет команду `WebApp_SetLoginSuccessFromWeb` с JWT-токеном, полученным через `razer-login.py`. Это эмулирует веб-авторизацию через Razer Central GUI (который не отображается под Wine из-за ограничений WPF-рендеринга).

Все файлы Razer остаются оригинальными — никаких патчей бинарников.

### Формат токена

`~/.wine/drive_c/users/<USER>/AppData/Local/Razer/RazerAxon/wine_login_token.json`:

```json
{
  "convertFromGuest": false,
  "token": "eyJhbGciOiJFUzI1NiI...",
  "isOnline": true,
  "isGuest": false,
  "uuid": "RZR_...",
  "loginId": "user@example.com",
  "tokenExpiry": "2026-04-01T21:46:43.000Z",
  "stayLoggedIn": true
}
```

### Шифрование обоев

Обои в `~/RazerAxonWallpapers/<id>/Resource/` — это ZipCrypto-зашифрованные ZIP-архивы:

```
password = HMAC-SHA256("j6l-aUmhCc@tN%T_", ResourceConfig.txt).hexdigest()
```

## Решение проблем

### Axon показывает чёрное/пустое окно
Токен не инжектирован или истёк:
```bash
razer-login.py            # Обновить токен
razer-token-inject.py     # Инжектировать
```

### Razer Central Service не запускается
```bash
# Проверить статус
wine sc query RazerCentralService

# Перезапустить Wine (сервис стартует автоматически)
wineboot
```

### Кириллица в трее отображается квадратиками
```bash
wine reg add "HKCU\Software\Wine\Fonts\Replacements" /v "Segoe UI" /t REG_SZ /d "Tahoma" /f
```

### Токен истёк
```bash
razer-login.py --status   # Проверить
razer-login.py            # Обновить
razer-token-inject.py     # Инжектировать заново
```

### Окно не видно в панели задач
Скрипт запуска исправляет это автоматически. Если проблема остаётся, убедитесь, что `xdotool` и `xprop` установлены.

### Расшифровка обоев не работает
Убедитесь, что `7z` или `unzip` установлен и поддерживает ZipCrypto.

## Лицензия

MIT
