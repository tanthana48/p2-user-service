from flask import Flask

from authentication.user_service import user_service
from database import db


def create_app() -> Flask:
    """Create flask app."""
    app = Flask(__name__)
    app.secret_key = "your_secret_key"
    app.register_blueprint(user_service)

    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://dev:devpass@db/p2-database'

    with app.app_context():
        db.create_all()


    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
