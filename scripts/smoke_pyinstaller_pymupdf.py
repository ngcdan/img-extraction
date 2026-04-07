"""Smoke test: bundle a minimal pymupdf import via PyInstaller."""

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        entry = tmp_path / "smoke.py"
        entry.write_text("import fitz\nprint('pymupdf OK', fitz.__doc__[:30])\n")

        result = subprocess.run(
            [
                sys.executable, "-m", "PyInstaller",
                "--onefile", "--clean",
                "--distpath", str(tmp_path / "dist"),
                "--workpath", str(tmp_path / "build"),
                "--specpath", str(tmp_path),
                str(entry),
            ],
            check=False,
        )
        if result.returncode != 0:
            print("PyInstaller build FAILED")
            return 1

        binary = tmp_path / "dist" / ("smoke.exe" if sys.platform == "win32" else "smoke")
        out = subprocess.run([str(binary)], check=False, capture_output=True, text=True)
        print("BINARY OUTPUT:", out.stdout, out.stderr)
        return 0 if "pymupdf OK" in out.stdout else 1


if __name__ == "__main__":
    raise SystemExit(main())
