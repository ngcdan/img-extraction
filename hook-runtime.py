
import os
import sys

def get_wkhtmltopdf_path():
    """Get the appropriate wkhtmltopdf path based on the platform"""
    if sys.platform == 'win32':
        return os.path.join('C:\\', 'Program Files (x86)', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
    elif sys.platform == 'darwin':
        return '/usr/local/bin/wkhtmltopdf'
    else:
        return '/usr/bin/wkhtmltopdf'

# Configure pdfkit to use the correct wkhtmltopdf path
import pdfkit
config = pdfkit.configuration(wkhtmltopdf=get_wkhtmltopdf_path())
