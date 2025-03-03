from flask_socketio import SocketIO, emit
import json

socketio = None

def init_socketio(app):
    global socketio
    socketio = SocketIO(app,
                       cors_allowed_origins="*",
                       async_mode='threading',
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
