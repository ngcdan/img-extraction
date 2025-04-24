import sys
import subprocess
import os
from pathlib import Path
import shutil
import platform
import logging
import time
from typing import List, Tuple

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('build.log')
    ]
)

class BuildError(Exception):
    """Custom exception for build errors"""
    pass

class BuildManager:
    def __init__(self):
        self.platform = sys.platform
        self.dist_dir = Path('dist')
        self.build_dir = Path('build')
        self.required_files = ['data_template.xlsx', '.env']
        self.required_dirs = ['downloads', 'static']

    def verify_environment(self) -> Tuple[bool, List[str]]:
        """Verify all required components are present"""
        missing = []

        # Check Python version
        if sys.version_info < (3, 8):
            missing.append(f"Python 3.8+ required (current: {sys.version})")

        # Check required files
        for file in self.required_files:
            if not os.path.exists(file):
                missing.append(f"Missing required file: {file}")

        # Check wkhtmltopdf installation
        try:
            subprocess.run(['wkhtmltopdf', '--version'],
                         check=True, capture_output=True)
        except:
            missing.append("wkhtmltopdf not installed or not in PATH")

        return len(missing) == 0, missing

    def clean_build_directories(self):
        """Safely clean build directories"""
        paths_to_clean = ['build', 'dist', '__pycache__']
        for path in paths_to_clean:
            try:
                if os.path.exists(path):
                    shutil.rmtree(path)
                    logging.info(f"Cleaned {path} directory")
            except Exception as e:
                logging.warning(f"Failed to clean {path}: {e}")

    def install_dependencies(self):
        """Install and verify dependencies"""
        try:
            # Upgrade pip
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'],
                         check=True, capture_output=True)

            # Install requirements with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                                 check=True, capture_output=True)
                    break
                except subprocess.CalledProcessError as e:
                    if attempt == max_retries - 1:
                        raise BuildError(f"Failed to install requirements: {e}")
                    time.sleep(2)

            logging.info("Successfully installed all dependencies")
        except Exception as e:
            raise BuildError(f"Dependency installation failed: {e}")

    def prepare_build_environment(self):
        """Prepare build environment with error handling"""
        try:
            # Create necessary directories
            for dir_name in self.required_dirs:
                os.makedirs(dir_name, exist_ok=True)
                logging.info(f"Created directory: {dir_name}")

            # Copy required files to build directory
            os.makedirs('build', exist_ok=True)
            for file in self.required_files:
                if os.path.exists(file):
                    shutil.copy2(file, f'build/{file}')
                    logging.info(f"Copied {file} to build/")
                else:
                    raise BuildError(f"Required file missing: {file}")

        except Exception as e:
            raise BuildError(f"Failed to prepare build environment: {e}")

    def run_pyinstaller(self) -> bool:
        """Run PyInstaller with improved error handling"""
        try:
            cmd = [
                sys.executable,
                '-m',
                'PyInstaller',
                'customs_fetcher.spec',
                '--clean',
                '--noconfirm',
                '--log-level=DEBUG'
            ]

            logging.info(f"Running PyInstaller command: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            # Log output
            if process.stdout:
                logging.info("PyInstaller STDOUT:\n" + process.stdout)
            if process.stderr:
                logging.warning("PyInstaller STDERR:\n" + process.stderr)

            if process.returncode != 0:
                raise BuildError(f"PyInstaller failed with return code {process.returncode}")

            return True

        except Exception as e:
            raise BuildError(f"PyInstaller execution failed: {e}")

    def verify_build_output(self):
        """Verify build output and copy necessary files"""
        try:
            output_file = 'customs_fetcher.exe' if self.platform == 'win32' else 'customs_fetcher'
            output_path = self.dist_dir / output_file

            if not output_path.exists():
                raise BuildError("Build output file not found")

            # Verify file size
            size = output_path.stat().st_size
            if size < 1000000:  # Less than 1MB
                raise BuildError(f"Build output suspiciously small: {size} bytes")

            # Copy additional files
            for file in self.required_files:
                if os.path.exists(file):
                    shutil.copy2(file, self.dist_dir / file)
                    logging.info(f"Copied {file} to dist/")

            # Create necessary directories in dist
            for dir_name in self.required_dirs:
                os.makedirs(self.dist_dir / dir_name, exist_ok=True)
                logging.info(f"Created {dir_name} directory in dist/")

            logging.info(f"Build verified successfully: {output_path}")
            return True

        except Exception as e:
            raise BuildError(f"Build verification failed: {e}")

    def build(self) -> bool:
        """Main build process with comprehensive error handling"""
        try:
            logging.info(f"Starting build process for {platform.system()} ({self.platform})")

            # Verify environment
            is_valid, missing = self.verify_environment()
            if not is_valid:
                raise BuildError(f"Environment verification failed:\n" + "\n".join(missing))

            # Clean previous build
            self.clean_build_directories()

            # Install dependencies
            self.install_dependencies()

            # Prepare environment
            self.prepare_build_environment()

            # Run PyInstaller
            self.run_pyinstaller()

            # Verify output
            self.verify_build_output()

            logging.info("Build completed successfully!")
            return True

        except BuildError as e:
            logging.error(f"Build failed: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during build: {e}")
            return False

if __name__ == "__main__":
    builder = BuildManager()
    success = builder.build()
    sys.exit(0 if success else 1)
