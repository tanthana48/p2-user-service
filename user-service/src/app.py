import os
from flask import Flask
from flask_cors import CORS
from authentication.user_service import user_service
from uploading.video_uploading_service import video_uploading_service, register_socketio_events
from database import db, bcrypt
from flask_socketio import SocketIO

def create_app() -> Flask:
    """Create flask app."""
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")
    CORS(app)
    app.secret_key = os.environ.get("SECRET_KEY", 'your_secret_key')
    register_socketio_events(socketio)
    app.register_blueprint(user_service)
    app.register_blueprint(video_uploading_service)

    ums_db_name = os.environ.get("UMS_DB_NAME")
    ums_db_username = os.environ.get("UMS_DB_USERNAME")
    ums_db_password = os.environ.get("UMS_DB_PASSWORD")
    ums_db_port = os.environ.get("UMS_DB_PORT", 3306)
    ums_db_ip = os.environ.get("UMS_DB_IP")
    db_uri = f'mysql+pymysql://{ums_db_username}:{ums_db_password}@{ums_db_ip}:{ums_db_port}/{ums_db_name}'

    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    # socketio.init_app(app)

    db.init_app(app)
    bcrypt.init_app(app)

    with app.app_context():
        db.create_all()

    return app, socketio

app, socketio = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, debug=True)

