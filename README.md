# Razer Axon на Linux

Запуск [Razer Axon](https://www.razer.com/software/axon) на Linux через Wine — с поддержкой авторизации, фиксами панели задач и расшифровкой обоев.

## Что входит в комплект

| Файл | Описание |
|------|----------|
| `razer-login.py` | Авторизация в Razer ID без Razer Central |
| `razer-axon.sh` | Скрипт запуска с Wine/WebView2 и фиксами панели задач |
| `razer-axon-decrypt.py` | Извлечение зашифрованных видео-обоев |
| `patch/RazerAxon.UserManager.dll` | Патченная DLL — заменяет авторизацию через Razer Central на самостоятельный вход |

## Зависимости

- **Wine** (проверено с Wine 9.x / 10.x)
- **Python 3.10+**
- **PyGObject** с WebKit2 (`webkit2gtk-4.1`)
- **xdotool**, **xprop** (для фикса панели задач на X11)
- **7z** или **unzip** (для расшифровки обоев)

### Arch Linux / CachyOS

```bash
sudo pacman -S wine python-gobject webkit2gtk-4.1 xdotool xorg-xprop p7zip
```

### Ubuntu / Debian

```bash
sudo apt install wine python3-gi gir1.2-webkit2-4.1 xdotool x11-utils p7zip-full
```

### Fedora

```bash
sudo dnf install wine python3-gobject webkit2gtk4.1 xdotool xprop p7zip
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

### 2. Замена DLL UserManager

Оригинальная `RazerAxon.UserManager.dll` требует Razer Central (Windows-сервис) для авторизации. Патченная версия заменяет это на самостоятельный вход, читая токены из локального JSON-файла.

```bash
AXON_DIR="$WINEPREFIX/drive_c/Program Files (x86)/Razer/Razer Axon"

# Бэкап оригинала
cp "$AXON_DIR/RazerAxon.UserManager.dll" "$AXON_DIR/RazerAxon.UserManager.dll.orig"

# Применить патч
cp patch/RazerAxon.UserManager.dll "$AXON_DIR/"
```

### 3. Установка скриптов

```bash
cp razer-axon.sh razer-login.py razer-axon-decrypt.py ~/.local/bin/
chmod +x ~/.local/bin/razer-axon.sh ~/.local/bin/razer-login.py ~/.local/bin/razer-axon-decrypt.py
```

### 4. Вход в Razer ID

```bash
razer-login.py
```

Откроется окно WebKit со страницей входа Razer ID. После авторизации скрипт перехватывает JWT-токен и сохраняет его в `wine_login_token.json`, откуда его читает патченная DLL.

Вход проходит в два этапа:
1. **Этап 1** — Открывает id.razer.com как обычный сайт для входа
2. **Этап 2** — После обнаружения входа перезагружает страницу с «natasha bridge» shim для извлечения JWT-токена

### 5. Запуск Razer Axon

```bash
razer-axon.sh
```

## Использование

### Вход / обновление токена

```bash
razer-login.py            # Открыть окно входа
razer-login.py --status   # Проверить статус текущего токена
```

Токены истекают примерно через 24 часа. Перезапустите `razer-login.py` для обновления.

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
│ Razer Axon (Wine)                                   │
│                                                     │
│  RazerAxon.exe                                      │
│       │                                             │
│       ├── RazerAxon.UserManager.dll (ПАТЧ)          │
│       │       │                                     │
│       │       ├── Читает wine_login_token.json      │
│       │       └── Без зависимости от Razer Central  │
│       │                                             │
│       ├── WebView2 UI ──► axon-api.razer.com        │
│       │                                             │
│       └── WallpaperPlayerManager                    │
│               └── Расшифровка ZIP → воспроизведение  │
│                                                     │
├─────────────────────────────────────────────────────┤
│ Linux                                               │
│                                                     │
│  razer-login.py ──► id.razer.com ──► JWT-токен      │
│  razer-axon.sh ──► Wine + фиксы окружения/панели    │
│  razer-axon-decrypt.py ──► HMAC-SHA256 → unzip      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Подробности о патченной DLL

Оригинальная `RazerAxon.UserManager.dll` общается с Razer Central через именованные каналы (`NacClient`) для авторизации. Поскольку Razer Central не работает под Wine, патченная DLL:

- Убирает все зависимости от Razer Central / AccountManager
- Добавляет `RazerLoginForm` с WebView2 для прямого входа в Razer ID
- Хранит/загружает токены из `wine_login_token.json` в AppData
- Предоставляет тот же интерфейс `IUserManager` остальной части Razer Axon

Исходник скомпилирован из `/tmp/razer_usershim/` под `net6.0-windows`.

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

### Axon показывает пустое/белое окно
Убедитесь, что WebView2 runtime установлен в Wine:
```bash
# Установщик Axon должен сделать это автоматически, но если нет:
winetricks -q webview2
```

### Токен истёк
```bash
razer-login.py --status   # Проверить
razer-login.py            # Обновить
```

### Окно не видно в панели задач
Скрипт запуска исправляет это автоматически. Если проблема остаётся, убедитесь, что `xdotool` и `xprop` установлены.

### Расшифровка обоев не работает
Убедитесь, что `7z` или `unzip` установлен и поддерживает ZipCrypto.

## Лицензия

MIT
