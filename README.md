# Razer Axon Wallpaper Decryptor

Extract encrypted wallpaper videos from [Razer Axon](https://www.razer.com/software/axon).

## Background

Razer Axon stores downloaded wallpapers as **ZipCrypto-encrypted ZIP archives** disguised with `.mp4` extensions. Each archive contains the actual MP4 video wallpaper.

The password for each archive is derived using:

```
password = HMAC-SHA256(key, ResourceConfig.txt contents).hexdigest()
```

The HMAC key (`j6l-aUmhCc@tN%T_`) is hardcoded in Razer Axon's .NET assemblies (`RazerAxon.CommonUtility.dll`, `RazerAxon.EnvironmentManager.dll`).

## Requirements

- Python 3.10+
- `7z` (p7zip) or `unzip` in PATH

## Installation

```bash
git clone https://github.com/wehrwolfmann/razer-axon-decrypt.git
cd razer-axon-decrypt
chmod +x razer-axon-decrypt.py
```

## Usage

### Auto-scan and extract all wallpapers

```bash
./razer-axon-decrypt.py
```

By default, scans `~/RazerAxonWallpapers/` and extracts to `~/RazerAxonWallpapers/Extracted/`.

### Show passwords without extracting

```bash
./razer-axon-decrypt.py -p
```

### Custom directories

```bash
./razer-axon-decrypt.py -d /path/to/wallpapers -o /path/to/output
```

### Decrypt a single file

```bash
./razer-axon-decrypt.py -f wallpaper.mp4 -c ResourceConfig.txt -o ./output
```

## How it works

1. Scans the wallpaper directory for `ResourceConfig.txt` files
2. Checks if `SourceEncryptedTypes` is `"ZIP"`
3. Computes HMAC-SHA256 of the config file contents using the hardcoded key
4. Extracts the ZIP archive using the derived password

### Wallpaper directory structure

```
RazerAxonWallpapers/
  <wallpaper_id>/
    ResourceConfig.txt          # JSON config, used as HMAC message
    Resource/
      wallpaper_3840x2160.mp4   # ZipCrypto-encrypted ZIP archive
    ChromaPresets/
      *.chroma                  # Razer Chroma lighting profiles
```

## License

MIT
