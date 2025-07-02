from . import db
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from flask_login import UserMixin # Added

class User(db.Model, UserMixin): # Added UserMixin
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # Increased length for stronger hashes
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.set_password(password)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(200), nullable=False) # Original name of the uploaded file
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploader = db.relationship('User', backref=db.backref('videos', lazy=True))
    is_public = db.Column(db.Boolean, nullable=False, default=False) # Added for video visibility
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Path to the stored file (local or object storage key)
    # For local storage, this could be 'uploads/user_id/video_id/filename.mp4'
    # For MinIO, this would be the object key.
    file_path = db.Column(db.String(512), nullable=False)
    total_size = db.Column(db.BigInteger, nullable=True) # Total size of the video in bytes
    is_processed = db.Column(db.Boolean, default=False) # Flag to indicate if video processing (encoding) is done
    # Future fields for chunking:
    # upload_id = db.Column(db.String(100), nullable=True, unique=True) # Unique ID for this upload session
    # total_chunks = db.Column(db.Integer, nullable=True)
    # uploaded_chunks_count = db.Column(db.Integer, default=0)
    # is_complete = db.Column(db.Boolean, default=False) # True when all chunks are uploaded

    def __repr__(self):
        return f'<Video {self.title}>'
