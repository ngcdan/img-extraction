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

    # Create build directory if it doesn't exist
    os.makedirs('build', exist_ok=True)

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

def create_runtime_hook():
    """Create runtime hook for PyInstaller"""
    hook_content = '''
# Runtime hook for PyInstaller
import os
import sys
import importlib.util

# Add missing modules to sys.modules
missing_modules = [
    'win32api', 'win32con', 'win32gui', 'ctypes.wintypes'
]

for module in missing_modules:
    try:
        if importlib.util.find_spec(module) and module not in sys.modules:
            __import__(module)
            print(f"Runtime hook: Successfully imported {module}")
    except (ImportError, ModuleNotFoundError):
        print(f"Runtime hook: Module {module} not available")
'''
    with open('hook-runtime.py', 'w') as f:
        f.write(hook_content)
    print("✓ Created PyInstaller runtime hook")

def create_spec_file():
    """Create custom spec file for PyInstaller"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

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

if sys.platform == 'win32':
    hiddenimports.extend([
        'win32api',
        'win32con',
        'win32gui',
        'ctypes.wintypes',
        'win32com.client'
    ])

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
)'''

    # Add sys import to the beginning of the spec file
    spec_content = "import sys\n" + spec_content

    with open('customs_fetcher.spec', 'w') as f:
        f.write(spec_content)
    print("✓ Created PyInstaller spec file")

def build_application():
    """Build the application"""
    try:
        # Platform-specific preparations
        if sys.platform == 'darwin':  # macOS
            check_macos_dependencies()
        elif sys.platform == 'win32':  # Windows
            print("Checking if wkhtmltopdf is installed...")
            try:
                # Try to run wkhtmltopdf to check if it's installed
                subprocess.run(['wkhtmltopdf', '--version'],
                             check=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
                print("✓ wkhtmltopdf is installed")
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("wkhtmltopdf is not installed. Please install from: https://wkhtmltopdf.org/downloads.html")
                print("After installation, add it to your PATH or specify its location in pdf_generator.py")
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

        # Use a more verbose command for better debugging
        pyinstaller_cmd = [
            sys.executable,
            '-m',
            'PyInstaller',
            'customs_fetcher.spec',
            '--clean',
            '--noconfirm',
            '--log-level=DEBUG'
        ]

        # Print command for debugging
        print(f"Running command: {' '.join(pyinstaller_cmd)}")

        # Run PyInstaller with subprocess to capture all output
        process = subprocess.run(
            pyinstaller_cmd,
            check=False,  # Don't raise exception on non-zero return code
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Print output for debugging
        print("STDOUT:")
        print(process.stdout)

        print("STDERR:")
        print(process.stderr)

        if process.returncode != 0:
            print(f"PyInstaller returned with error code: {process.returncode}")
            return False

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
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print(f"Building for: {platform.system()} ({sys.platform})")
    success = build_application()
    sys.exit(0 if success else 1)