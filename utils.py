from flask_socketio import SocketIO, emit
import json

socketio = None

def init_socketio(app):
    global socketio
    socketio = SocketIO(app,
                       cors_allowed_origins="*",
                       async_mode='eventlet',
                       logger=True,
                       engineio_logger=True)
    return socketio

def send_notification(message, type="info"):
    """Gửi thông báo đến client"""
    if socketio:
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, ensure_ascii=False)
            socketio.emit('notification', {
                'message': message,
                'type': type  # info, success, warning, error
            })
        except Exception as e:
            print(f"Lỗi khi gửi thông báo: {str(e)}")

def get_download_directory():
    """Trả về thư mục Downloads/ImgExtraction trong thư mục home của user"""
    import os
    import platform

    home = os.path.expanduser('~')
    base_dir = os.path.join(home, 'Downloads', 'ImgExtraction')

    # Tạo thư mục nếu chưa tồn tại
    if not os.path.exists(base_dir):
        try:
            os.makedirs(base_dir)
            print(f"Đã tạo thư mục download: {base_dir}")
        except Exception as e:
            print(f"Lỗi khi tạo thư mục download: {str(e)}")

    return base_dir
