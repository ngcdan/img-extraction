import sys
import subprocess
import os
from pathlib import Path
import argparse
import shutil
import tempfile

def install_requirements():
    """Install required packages"""
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

def prepare_sensitive_files():
    """
    Chuẩn bị các file nhạy cảm bằng cách copy và đổi tên
    để ẩn mục đích sử dụng
    """
    sensitive_files = {
        'driver-service-account.json': 'data1.bin',
        'service-account-key.json': 'data2.bin'
        # Thêm các file nhạy cảm khác vào đây
        # 'your-sensitive-file.ext': 'data3.bin'
    }

    copied_files = []

    # Tạo thư mục build nếu chưa tồn tại
    build_dir = Path('build/sensitive')
    build_dir.mkdir(parents=True, exist_ok=True)

    for src, dest in sensitive_files.items():
        if os.path.exists(src):
            # Copy vào thư mục build với tên mới
            dest_path = build_dir / dest
            shutil.copy2(src, dest_path)
            # Thêm vào danh sách files để bundle
            copied_files.append((str(dest_path), '.'))
            print(f"Processed sensitive file: {src} -> {dest}")
        else:
            print(f"Warning: Sensitive file not found: {src}")

    return copied_files

def build_application(show_console=True):
    """Build the application for current platform"""
    # Define main file and data files
    main_file = 'test_batch_process.py'

    # Process sensitive files
    sensitive_data_files = prepare_sensitive_files()  # Removed temp_dir parameter

    # Collect all required data files
    data_files = []

    # Add required directories if they exist
    required_dirs = [
        ('templates', 'templates'),
        ('static', 'static')
    ]

    for src, dest in required_dirs:
        if os.path.exists(src) and os.path.isdir(src):
            data_files.append((src, dest))

    # Add .env if exists
    if os.path.exists('.env'):
        data_files.append(('.env', '.'))

    # Add sensitive files
    data_files.extend(sensitive_data_files)

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
        separator = ';' if sys.platform == 'win32' else ':'
        options.append(f'--add-data={src}{separator}{dest}')

    # Remove None values
    options = [opt for opt in options if opt is not None]

    # Build command
    command = ['pyinstaller'] + options + [main_file]

    # Print command for debugging
    print("\nBuilding with command:", ' '.join(command))

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
