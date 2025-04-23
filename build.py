import sys
import subprocess
import os
from pathlib import Path
import shutil
import platform

def check_macos_dependencies():
    """Check and install macOS dependencies using Homebrew"""
    try:
        subprocess.run(['brew', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing Homebrew...")
        subprocess.run(['/bin/bash', '-c', "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"])

    # Install wkhtmltopdf for PDF generation
    try:
        subprocess.run(['wkhtmltopdf', '--version'], check=True, capture_output=True)
        print("✓ wkhtmltopdf is installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing wkhtmltopdf...")
        subprocess.run(['brew', 'install', 'wkhtmltopdf'], check=True)

def install_requirements():
    """Install Python dependencies"""
    print("Installing Python requirements...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

def prepare_project_files():
    """Prepare necessary project files"""
    # Create required directories
    directories = ['downloads', 'static']
    for dir_name in directories:
        os.makedirs(dir_name, exist_ok=True)
        print(f"✓ Created directory: {dir_name}")

    # Copy required files
    files_to_copy = {
        'data_template.xlsx': 'data_template.xlsx',
        '.env': '.env'
    }

    for src, dest in files_to_copy.items():
        if os.path.exists(src):
            shutil.copy2(src, f'build/{dest}')
            print(f"✓ Copied {src} to build/")
        else:
            print(f"Warning: {src} not found")

def create_spec_file():
    """Create custom spec file for PyInstaller"""
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all necessary data
datas = [
    ('data_template.xlsx', '.'),
    ('.env', '.'),
    ('downloads', 'downloads'),
    ('static', 'static')
]

binaries = []
hiddenimports = [
    'pdfkit',
    'PIL',
    'selenium',
    'pandas',
    'openpyxl',
    'tenacity',
    'cffi',
    'selenium.webdriver',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    'selenium.common.exceptions',
    'selenium.webdriver.common.action_chains',
    'pkg_resources.py2_warn',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements'
]

# Collect additional dependencies
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['fetch_co.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook-runtime.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='customs_fetcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
    with open('customs_fetcher.spec', 'w') as f:
        f.write(spec_content)
    print("✓ Created PyInstaller spec file")

def create_runtime_hook():
    """Create a runtime hook for PyInstaller"""
    hook_content = '''
import os
import sys

def get_wkhtmltopdf_path():
    """Get the appropriate wkhtmltopdf path based on the platform"""
    if sys.platform == 'win32':
        return os.path.join('C:', 'Program Files (x86)', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
    elif sys.platform == 'darwin':
        return '/usr/local/bin/wkhtmltopdf'
    else:
        return '/usr/bin/wkhtmltopdf'

# Configure pdfkit to use the correct wkhtmltopdf path
import pdfkit
config = pdfkit.configuration(wkhtmltopdf=get_wkhtmltopdf_path())
'''
    with open('hook-runtime.py', 'w') as f:
        f.write(hook_content)
    print("✓ Created PyInstaller runtime hook")

def build_application():
    """Build the application"""
    try:
        # Create build directory
        os.makedirs('build', exist_ok=True)

        # Platform-specific preparations
        if sys.platform == 'darwin':  # macOS
            check_macos_dependencies()
        elif sys.platform == 'win32':  # Windows
            print("Please ensure wkhtmltopdf is installed from: https://wkhtmltopdf.org/downloads.html")
            input("Press Enter to continue after installing wkhtmltopdf...")

        # Install Python requirements
        install_requirements()

        # Prepare project files
        prepare_project_files()

        # Create runtime hook
        create_runtime_hook()

        # Create spec file
        create_spec_file()

        # Build using PyInstaller with minimal options
        print("\nBuilding application...")
        subprocess.run([
            'pyinstaller',
            'customs_fetcher.spec',
            '--clean',
            '--noconfirm'
        ], check=True)

        # Post-build cleanup and verification
        dist_dir = Path('dist')
        output_file = 'customs_fetcher.exe' if sys.platform == 'win32' else 'customs_fetcher'
        output_path = dist_dir / output_file

        if output_path.exists():
            print(f"\n✓ Build successful! Output file: {output_path}")

            # Copy necessary files to dist directory
            for file in ['data_template.xlsx', '.env']:
                if os.path.exists(file):
                    shutil.copy2(file, dist_dir / file)
                    print(f"✓ Copied {file} to dist/")

            # Create downloads directory in dist
            os.makedirs(dist_dir / 'downloads', exist_ok=True)
            print("✓ Created downloads directory in dist/")
        else:
            print("\n❌ Build failed: Output file not found")
            return False

        return True

    except Exception as e:
        print(f"\n❌ Build failed with error: {e}")
        return False

if __name__ == "__main__":
    print(f"Building for: {platform.system()} ({sys.platform})")
    success = build_application()
    sys.exit(0 if success else 1)



