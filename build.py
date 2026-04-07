"""PyInstaller build script for customs-receipt-bot v5.

Packages ``src/customs_bot`` as a single-file executable using the
``__main__.py`` entry point.
"""

import sys
import subprocess
import os
from pathlib import Path
import argparse
import shutil
from PIL import Image


# ---------------------------------------------------------------------------
# Icon helpers
# ---------------------------------------------------------------------------

def convert_to_ico(jpg_path: str, ico_path: Path) -> bool:
    """Convert JPG to ICO format."""
    try:
        img = Image.open(jpg_path)
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(ico_path, format="ICO", sizes=icon_sizes)
        return True
    except Exception as e:
        print(f"Error converting to ICO: {e}")
        return False


def convert_to_icns(jpg_path: str, icns_path: Path) -> bool:
    """Convert JPG to ICNS format for macOS."""
    try:
        img = Image.open(jpg_path)
        img = img.resize((1024, 1024))
        img.save(icns_path, format="ICNS")
        return True
    except Exception as e:
        print(f"Error converting to ICNS: {e}")
        return False


def prepare_icon() -> Path | None:
    """Prepare icon files from avatar.jpg."""
    avatar_path = "avatar.jpg"
    if not os.path.exists(avatar_path):
        print("Warning: avatar.jpg not found")
        return None

    static_dir = Path("static")
    static_dir.mkdir(exist_ok=True)

    icon_path = None
    if sys.platform == "win32":
        icon_path = static_dir / "icon.ico"
        if convert_to_ico(avatar_path, icon_path):
            print(f"Created icon at: {icon_path}")
    else:
        icon_path = static_dir / "icon.icns"
        if convert_to_icns(avatar_path, icon_path):
            print(f"Created icon at: {icon_path}")

    return icon_path


# ---------------------------------------------------------------------------
# Sensitive-file bundling
# ---------------------------------------------------------------------------

def prepare_sensitive_files() -> list[tuple[str, str]]:
    """Copy and rename sensitive files so their purpose is obfuscated."""
    sensitive_files = {
        "driver-service-account.json": "data1.bin",
        "accounts.json": "accounts.json",
        ".env": ".env",
    }

    copied_files: list[tuple[str, str]] = []

    build_dir = Path("build/sensitive")
    build_dir.mkdir(parents=True, exist_ok=True)

    for src, dest in sensitive_files.items():
        if os.path.exists(src):
            dest_path = build_dir / dest
            shutil.copy2(src, dest_path)
            copied_files.append((str(dest_path), "."))
            print(f"Processed sensitive file: {src} -> {dest}")
        else:
            print(f"Warning: Sensitive file not found: {src}")

    return copied_files


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def install_package() -> None:
    """Install the project in editable mode with build extras."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[build]"],
        check=True,
    )


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_application(show_console: bool = True) -> None:
    """Build the application for the current platform."""
    # v5: use the package entry-point module
    main_file = "src/customs_bot/__main__.py"

    icon_path = prepare_icon()
    sensitive_data_files = prepare_sensitive_files()

    data_files: list[tuple[str, str]] = []

    # Bundle the entire src/customs_bot package so PyInstaller can find it
    if os.path.isdir("src/customs_bot"):
        data_files.append(("src/customs_bot", "customs_bot"))

    # Legacy bridge: chrome_manager.py is still imported at runtime
    if os.path.exists("chrome_manager.py"):
        data_files.append(("chrome_manager.py", "."))
    if os.path.exists("utils.py"):
        data_files.append(("utils.py", "."))

    # Static assets
    for src, dest in [("templates", "templates"), ("static", "static")]:
        if os.path.isdir(src):
            data_files.append((src, dest))

    if os.path.exists(".env"):
        data_files.append((".env", "."))

    data_files.extend(sensitive_data_files)

    # PyInstaller options
    options = [
        "--onefile",
        "--clean",
        "--noconfirm",
        "--name", "customs-bot",
        # Tell PyInstaller where to find the package
        "--paths", "src",
    ]

    if sys.platform == "win32":
        options.append("--uac-admin")
        if icon_path:
            options.append(f"--icon={icon_path}")
        if not show_console:
            options.append("--noconsole")
    else:
        if icon_path:
            options.append(f"--icon={icon_path}")

    separator = ";" if sys.platform == "win32" else ":"
    for src, dest in data_files:
        options.append(f"--add-data={src}{separator}{dest}")

    command = ["pyinstaller"] + options + [main_file]

    print("\nBuilding with command:", " ".join(command))

    Path("dist").mkdir(exist_ok=True)

    try:
        subprocess.run(command, check=True)
        output_file = "customs-bot.exe" if sys.platform == "win32" else "customs-bot"
        console_status = "with console" if show_console else "without console"
        print(f"\nBuild successful! Output: dist/{output_file} ({console_status})")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build customs-receipt-bot executable")
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Hide console window in Windows build",
    )
    args = parser.parse_args()

    print("Installing package...")
    install_package()

    print("\nBuilding application...")
    build_application(show_console=not args.no_console)
