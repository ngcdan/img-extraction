import sys
import os
from flask import Flask, render_template, request, jsonify, send_file
import threading
from flask_cors import CORS
import time
from datetime import datetime
from utils import init_socketio, send_notification
from receipt_fetcher import initialize_chrome, process_download
from extract_info import process_file_content
import webbrowser

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

app = Flask(__name__,
    template_folder=resource_path('templates'),
    static_folder=resource_path('static')
)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = init_socketio(app)

# Global variables
driver = None
download_status = {
    'total': 0, 'current': 0, 'success': 0, 'failed': 0,
    'status': 'idle'  # idle, running, completed, error
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_download():
    global driver, download_status
    try:
        username = request.form.get('username')
        if not username or not username.strip().isdigit():
            return jsonify({'error': 'Invalid tax code'})

        so_tk = request.form.get('so_tk')
        driver = ensure_driver_is_active(driver)
        if not driver:
            return jsonify({'error': 'Unable to initialize Chrome'})

        reset_download_status()
        start_download_thread(username, so_tk)
        return jsonify({'status': 'started'})

    except Exception as e:
        handle_download_error(str(e))
        return jsonify({'error': f'Error starting download: {str(e)}'})

@app.route('/status')
def get_status():
    return jsonify(download_status)

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'File not found'})

        file = request.files['file']
        result = process_file_content(file)
        return jsonify(result)

    except Exception as e:
        print(f"Server error: {e}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

def ensure_driver_is_active(driver):
    if driver is None or not is_driver_alive(driver):
        driver = initialize_chrome()
        if driver:
            time.sleep(2)  # Wait for driver to fully start
    return driver

def is_driver_alive(driver):
    try:
        driver.current_url
        return True
    except:
        return False

def reset_download_status():
    global download_status
    download_status = {
        'total': 0, 'current': 0, 'success': 0, 'failed': 0,
        'status': 'running'
    }

def start_download_thread(username, so_tk):
    download_thread = threading.Thread(
        target=lambda: safe_process_download(username, so_tk)
    )
    download_thread.daemon = True
    download_thread.start()

def safe_process_download(username, so_tk):
    global driver, download_status
    try:
        process_download(driver, username, so_tk, download_status)
    except Exception as e:
        handle_download_error(str(e))

def handle_download_error(error_message):
    global driver, download_status
    print(f"Download error: {error_message}")
    send_notification(error_message, "error")
    download_status['status'] = 'error'
    if driver:
        try:
            driver.quit()
        except:
            pass
        driver = None

def close_specific_tabs(url_pattern):
    global driver
    if not driver:
        return

    try:
        current_handle = driver.current_window_handle
        for handle in driver.window_handles[:]:
            try:
                driver.switch_to.window(handle)
                if url_pattern in driver.current_url:
                    print(f"Closing tab: {driver.current_url}")
                    driver.close()
            except:
                continue

        remaining_handles = driver.window_handles
        if remaining_handles and current_handle not in remaining_handles:
            driver.switch_to.window(remaining_handles[0])

    except Exception as e:
        print(f"Error closing tabs: {e}")

def cleanup():
    global driver
    if driver:
        try:
            driver.quit()
        except:
            pass
        driver = None

def open_browser():
    webbrowser.open('http://localhost:8080')

if __name__ == '__main__':
    try:
        threading.Thread(target=initialize_chrome, daemon=True).start()
        import atexit
        atexit.register(cleanup)
        threading.Timer(2.0, open_browser).start()

        socketio.run(app,
            host='0.0.0.0',
            port=8080,
            debug=False,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        print(f"Error starting app: {e}")
        cleanup()
