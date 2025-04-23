import pdfkit
import os
import platform
import subprocess
from pathlib import Path

class PDFGenerator:
    def __init__(self):
        """Initialize the PDF generator with appropriate wkhtmltopdf path"""
        self.wkhtmltopdf_path = self._get_wkhtmltopdf_path()
        self.config = None

        if self.wkhtmltopdf_path:
            self.config = pdfkit.configuration(wkhtmltopdf=self.wkhtmltopdf_path)
            print(f"Using wkhtmltopdf at: {self.wkhtmltopdf_path}")
        else:
            print("Using system default wkhtmltopdf path")

    def _get_wkhtmltopdf_path(self):
        """Find wkhtmltopdf executable path based on the platform"""
        system = platform.system()

        # Try to find in PATH first
        try:
            if system == "Windows":
                process = subprocess.run(["where", "wkhtmltopdf"],
                                        capture_output=True, text=True, check=True)
                return process.stdout.strip()
            else:  # macOS or Linux
                process = subprocess.run(["which", "wkhtmltopdf"],
                                        capture_output=True, text=True, check=True)
                return process.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Check common installation paths
        if system == "Windows":
            paths = [
                r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
                r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
            ]
        elif system == "Darwin":  # macOS
            paths = [
                "/usr/local/bin/wkhtmltopdf",
                "/opt/homebrew/bin/wkhtmltopdf",
            ]
        else:  # Linux
            paths = [
                "/usr/bin/wkhtmltopdf",
                "/usr/local/bin/wkhtmltopdf",
            ]

        for path in paths:
            if os.path.exists(path):
                return path

        return None

    def html_to_pdf(self, html_content, output_path, options=None):
        """Convert HTML string content to PDF file"""
        if options is None:
            options = {
                'page-size': 'A4',
                'margin-top': '10mm',
                'margin-right': '10mm',
                'margin-bottom': '10mm',
                'margin-left': '10mm',
                'encoding': 'UTF-8',
                'no-outline': None,
                'quiet': ''
            }

        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Generate PDF from HTML string
            if self.config:
                pdfkit.from_string(html_content, output_path, options=options, configuration=self.config)
            else:
                pdfkit.from_string(html_content, output_path, options=options)

            print(f"PDF successfully generated: {output_path}")
            return True, output_path
        except Exception as e:
            print(f"Failed to generate PDF: {e}")
            return False, str(e)

    def html_file_to_pdf(self, html_file_path, output_path, options=None):
        """Convert HTML file to PDF file"""
        if options is None:
            options = {
                'page-size': 'A4',
                'margin-top': '10mm',
                'margin-right': '10mm',
                'margin-bottom': '10mm',
                'margin-left': '10mm',
                'encoding': 'UTF-8',
                'no-outline': None,
                'quiet': ''
            }

        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Generate PDF from HTML file
            if self.config:
                pdfkit.from_file(html_file_path, output_path, options=options, configuration=self.config)
            else:
                pdfkit.from_file(html_file_path, output_path, options=options)

            print(f"PDF successfully generated: {output_path}")
            return True, output_path
        except Exception as e:
            print(f"Failed to generate PDF: {e}")
            return False, str(e)
