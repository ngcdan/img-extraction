from flask_socketio import SocketIO, emit
import json

socketio = None

def init_socketio(app):
    global socketio
    # Thử dùng eventlet, nếu không được thì fallback về threading
    try:
        import eventlet
        async_mode = 'eventlet'
    except ImportError:
        async_mode = 'threading'  # Fallback an toàn cho PyInstaller
    socketio = SocketIO(app,
                       cors_allowed_origins="*",
                       async_mode=async_mode,
                       logger=True,
                       engineio_logger=True)
    print(f"SocketIO initialized with async_mode: {async_mode}")
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
