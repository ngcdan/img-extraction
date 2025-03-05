import sys
import subprocess
import os
from pathlib import Path
import argparse

def install_requirements():
    """Install required packages"""
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

def build_application(show_console=True):
    """Build the application for current platform"""
    # Define main file and data files
    main_file = 'test_batch_process.py'

    # Collect all required data files
    data_files = [
        ('.env', '.'),
        ('driver-service-account.json', '.'),
        ('service_account_key.json', '.')
    ]

    # Basic PyInstaller options
    options = [
        '--onefile',              # Create a single executable
        '--clean',                # Clean PyInstaller cache
        '--noconfirm',           # Replace output directory without asking
        '--name', 'pdf_processor' # Output name
    ]

    # Platform specific options
    if sys.platform == 'win32':
        options.extend([
            '--uac-admin',        # Request admin privileges
            '--icon=static/icon.ico' if os.path.exists('static/icon.ico') else None
        ])

        # Add --noconsole only if show_console is False
        if not show_console:
            options.append('--noconsole')

    else:  # macOS
        options.extend([
            '--icon=static/icon.icns' if os.path.exists('static/icon.icns') else None
        ])

    # Add data files
    for src, dest in data_files:
        if os.path.exists(src):
            separator = ';' if sys.platform == 'win32' else ':'
            options.append(f'--add-data={src}{separator}{dest}')

    # Remove None values
    options = [opt for opt in options if opt is not None]

    # Build command
    command = ['pyinstaller'] + options + [main_file]

    # Print command for debugging
    print("Building with command:", ' '.join(command))

    # Create dist directory if it doesn't exist
    dist_dir = Path('dist')
    dist_dir.mkdir(exist_ok=True)

    # Run PyInstaller
    try:
        subprocess.run(command, check=True)
        output_file = 'pdf_processor.exe' if sys.platform == 'win32' else 'pdf_processor'
        console_status = "với console" if show_console else "không có console"
        print(f"\nBuild successful! Output file: dist/{output_file} ({console_status})")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build PDF Processor application')
    parser.add_argument('--no-console', action='store_true',
                      help='Hide console window in Windows build')
    args = parser.parse_args()

    print("Installing requirements...")
    install_requirements()

    print("\nBuilding application...")
    build_application(show_console=not args.no_console)
