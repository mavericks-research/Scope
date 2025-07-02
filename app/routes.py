from flask import Blueprint, render_template, request
from flask_login import login_required, current_user # Added current_user
from app.models import Video # Import Video model
from app import db # Import db instance if needed for complex queries, not for simple filter_by

frontend_bp = Blueprint('frontend', __name__)

@frontend_bp.route('/')
def home():
    # Serve public gallery as the main landing page
    public_videos = Video.query.filter_by(is_public=True).order_by(Video.created_at.desc()).all()
    return render_template('public_gallery.html', videos=public_videos, title="Welcome - Public Video Gallery")

@frontend_bp.route('/upload') # New route for the upload page
@login_required
def upload_page(): # Renamed from index to avoid confusion
    access_token = request.args.get('access_token')
    return render_template('index.html', access_token=access_token, title="Upload Video") # Pass title

@frontend_bp.route('/my-videos')
@login_required
def my_videos():
    user_videos = Video.query.filter_by(user_id=current_user.id).order_by(Video.created_at.desc()).all()
    return render_template('videos.html', videos=user_videos, title="My Videos")

@frontend_bp.route('/gallery')
def public_gallery():
    public_videos = Video.query.filter_by(is_public=True).order_by(Video.created_at.desc()).all()
    return render_template('public_gallery.html', videos=public_videos, title="Public Video Gallery")
