#!/usr/bin/env python3
"""
Razer Central Token Injector for Wine.

Injects a JWT token from razer-login.py into the running
RazerCentralService via its named pipe IPC protocol.
This allows Razer Axon to work with the original unmodified DLL.

Usage:
    razer-token-inject.py                # inject from saved token
    razer-token-inject.py --status       # check service status
    razer-token-inject.py --token FILE   # inject from specific file
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WINE_PREFIX = Path(os.environ.get("WINEPREFIX", Path.home() / ".wine"))
CONFIG_DIR = Path(os.environ.get(
    "RAZER_AXON_DIR", Path.home() / ".config/razer-axon"
))
CACHE_DIR = CONFIG_DIR / "cache"
INJECTOR_EXE = CACHE_DIR / "razer-token-inject.exe"

CS_SOURCE = r"""
using System;
using System.IO;
using System.IO.Pipes;
using System.Threading;

class TokenInjector
{
    static int packetNum = 1;

    static byte[] MakePayload(uint command, string data)
    {
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write(command);
            bw.Write(packetNum++);
            if (data != null) bw.Write(data);
            return ms.ToArray();
        }
    }

    static byte[] MakePacket(int serviceType, byte[] payload, long packetId)
    {
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write(2);
            bw.Write(serviceType);
            bw.Write(payload.Length);
            bw.Write(24);
            bw.Write(packetId);
            bw.Write(payload);
            return ms.ToArray();
        }
    }

    static void Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.Error.WriteLine("Usage: inject.exe <token_file>");
            Environment.Exit(1);
            return;
        }

        string tokenJson = File.ReadAllText(args[0]).Trim();
        Console.WriteLine("Token loaded (" + tokenJson.Length + " chars)");
        Console.WriteLine("Connecting to Razer Central Service...");

        using (var pipe = new NamedPipeClientStream(".",
            "{FC828A97-C116-453D-BD88-AD471496E03C}",
            PipeDirection.InOut, PipeOptions.None))
        {
            try { pipe.Connect(5000); Console.WriteLine("Connected!"); }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Failed to connect: " + ex.Message);
                Environment.Exit(1);
                return;
            }

            // WebApp_SetLoginSuccessFromWeb = 131094
            byte[] payload = MakePayload(131094, tokenJson);
            byte[] packet = MakePacket(4, payload, 1);
            pipe.Write(packet, 0, packet.Length);
            pipe.Flush();
            Console.WriteLine("Sent " + packet.Length + " bytes");

            byte[] buf = new byte[4096];
            try
            {
                Thread.Sleep(2000);
                int n = pipe.Read(buf, 0, buf.Length);
                if (n > 24)
                {
                    uint cmdRaw = BitConverter.ToUInt32(buf, 24);
                    bool isExc = (cmdRaw & 0x40000000u) != 0;
                    if (isExc)
                    {
                        using (var ms = new MemoryStream(buf, 28, n - 28))
                        using (var br = new BinaryReader(ms))
                        {
                            try { br.ReadUInt32(); Console.Error.WriteLine("Error: " + br.ReadString()); } catch {}
                        }
                        Environment.Exit(2);
                    }
                    else Console.WriteLine("Token injected successfully!");
                }
                else Console.WriteLine("Response: " + n + " bytes (ok)");
            }
            catch (Exception ex) { Console.WriteLine("Read: " + ex.Message); }
        }
    }
}
"""


def find_token_file():
    """Find the saved JWT token from razer-login.py."""
    candidates = [
        CONFIG_DIR / "wine_login_token.json",
        WINE_PREFIX / "drive_c/users" / os.environ.get("USER", "user")
        / "AppData/Local/Razer/RazerAxon/wine_login_token.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def build_injector():
    """Build the .NET injector exe (cached)."""
    if INJECTOR_EXE.exists():
        return True

    if not shutil.which("dotnet"):
        print("Error: 'dotnet' SDK not found. Install .NET SDK 6.0+.")
        return False

    import tempfile
    build_dir = Path(tempfile.mkdtemp(prefix="razer_inject_"))

    try:
        (build_dir / "Program.cs").write_text(CS_SOURCE)
        (build_dir / "inject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net6.0-windows</TargetFramework>
    <RuntimeIdentifier>win-x64</RuntimeIdentifier>
    <PublishSingleFile>true</PublishSingleFile>
    <SelfContained>true</SelfContained>
    <PublishTrimmed>true</PublishTrimmed>
    <EnableCompressionInSingleFile>true</EnableCompressionInSingleFile>
  </PropertyGroup>
</Project>
""")

        print("Building injector (first run only)...")
        result = subprocess.run(
            ["dotnet", "publish", "-c", "Release", "--nologo", "-v", "q"],
            cwd=build_dir, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            print(f"Build failed:\n{result.stderr}")
            return False

        exe = build_dir / "bin/Release/net6.0-windows/win-x64/publish/inject.exe"
        if not exe.exists():
            print("Build produced no output")
            return False

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe, INJECTOR_EXE)
        print(f"Cached at {INJECTOR_EXE}")
        return True

    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


def inject_token(token_data: str):
    """Inject token via the Wine .NET helper."""
    wine_temp = WINE_PREFIX / "drive_c" / "temp"
    wine_temp.mkdir(parents=True, exist_ok=True)

    # Write token where Wine can read it
    token_path = wine_temp / "inject_token.json"
    token_path.write_text(token_data)

    # Copy injector exe to Wine-accessible path
    exe_dest = wine_temp / "razer-token-inject.exe"
    shutil.copy2(INJECTOR_EXE, exe_dest)

    try:
        result = subprocess.run(
            ["wine", str(exe_dest), r"C:\temp\inject_token.json"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "WINEDEBUG": "-all"}
        )
        print(result.stdout.strip())
        if result.stderr:
            real_errors = [l for l in result.stderr.splitlines()
                          if l and not l[0].isdigit() and "fixme:" not in l]
            if real_errors:
                print("\n".join(real_errors), file=sys.stderr)
        return result.returncode == 0
    finally:
        token_path.unlink(missing_ok=True)


def check_service():
    """Check if RazerCentralService is running."""
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    running = "RazerCentralService" in result.stdout
    print(f"RazerCentralService: {'running' if running else 'NOT running'}")
    if not running:
        print("Start with: wineboot && sleep 5  (service is set to auto-start)")
    return running


def main():
    parser = argparse.ArgumentParser(
        description="Inject JWT token into Razer Central Service (Wine)"
    )
    parser.add_argument("--status", action="store_true",
                       help="Check service status and token")
    parser.add_argument("--token", type=Path,
                       help="Path to token JSON file")
    parser.add_argument("--rebuild", action="store_true",
                       help="Force rebuild of injector binary")
    args = parser.parse_args()

    if args.status:
        check_service()
        token_file = args.token or find_token_file()
        if token_file:
            print(f"Token file: {token_file}")
            try:
                data = json.loads(token_file.read_text())
                print(f"  Login: {data.get('loginId', '?')}")
                print(f"  Expiry: {data.get('tokenExpiry', '?')}")
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print("No token found. Run razer-login.py first.")
        print(f"Injector: {'cached' if INJECTOR_EXE.exists() else 'not built'}")
        return

    if args.rebuild and INJECTOR_EXE.exists():
        INJECTOR_EXE.unlink()

    # Build injector if needed
    if not build_injector():
        sys.exit(1)

    # Find token
    token_file = args.token or find_token_file()
    if not token_file or not token_file.exists():
        print("No token found. Run razer-login.py first.")
        sys.exit(1)

    token_data = token_file.read_text().strip()
    try:
        parsed = json.loads(token_data)
        print(f"Token: {parsed.get('loginId', '?')} "
              f"(expires {parsed.get('tokenExpiry', '?')})")
    except json.JSONDecodeError:
        print("Invalid token file")
        sys.exit(1)

    if not check_service():
        sys.exit(1)

    print()
    if inject_token(token_data):
        print("\nDone! Razer Axon should now be authenticated.")
    else:
        print("\nInjection may have failed. Check Razer Central logs.")


if __name__ == "__main__":
    main()
