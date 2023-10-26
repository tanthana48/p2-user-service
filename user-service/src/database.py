from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    _password_hash = db.Column("password", db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(80), unique=False, nullable=False)

    @property
    def password(self):
        raise AttributeError("Password is write-only.")

    @password.setter
    def password(self, password):
        self._password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self._password_hash, password)

class Video(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow())
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    s3_filename = db.Column(db.String(255), nullable=False)
    hls_filename = db.Column(db.String(255), nullable=True)
    thumbnail_filename = db.Column(db.String(255), nullable=True)

    user = db.relationship("User", backref="videos")
