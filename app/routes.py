from flask import Blueprint, render_template, request
from flask_login import login_required, current_user # Added current_user
from app.models import Video, UserVideoUnlock # Import Video model and UserVideoUnlock
from app import db # Import db instance if needed for complex queries, not for simple filter_by

frontend_bp = Blueprint('frontend', __name__)

@frontend_bp.route('/')
def home():
    public_videos = Video.query.filter_by(is_public=True).order_by(Video.created_at.desc()).all()
    unlocked_video_ids = set()
    if current_user.is_authenticated:
        unlocks = UserVideoUnlock.query.filter_by(user_id=current_user.id).all()
        unlocked_video_ids = {unlock.video_id for unlock in unlocks}
    return render_template('public_gallery.html', videos=public_videos, title="Welcome - Public Video Gallery", unlocked_video_ids=unlocked_video_ids)

@frontend_bp.route('/upload') # New route for the upload page
@login_required
def upload_page(): # Renamed from index to avoid confusion
    access_token = request.args.get('access_token')
    return render_template('index.html', access_token=access_token, title="Upload Video") # Pass title

@frontend_bp.route('/my-videos')
@login_required
def my_videos():
    user_videos = Video.query.filter_by(user_id=current_user.id).order_by(Video.created_at.desc()).all()
    # For "My Videos", all videos are by the current user. We still need to know which of *their* paid videos they've "unlocked"
    # (though for owned videos, the concept of unlocking is moot unless they also consume content like others).
    # For now, let's assume owned videos are always "unlocked" for the owner.
    # The `unlocked_video_ids` is more relevant for videos they *don't* own.
    # However, to keep template logic consistent, we can pass it.
    unlocked_video_ids = set()
    unlocks = UserVideoUnlock.query.filter_by(user_id=current_user.id).all()
    unlocked_video_ids = {unlock.video_id for unlock in unlocks}
    # For owned videos, they are implicitly unlocked. If a video is theirs AND paid, they don't need to buy it.
    # The template logic will primarily use this for buy buttons on non-owned videos.
    return render_template('videos.html', videos=user_videos, title="My Videos", unlocked_video_ids=unlocked_video_ids)

@frontend_bp.route('/gallery')
def public_gallery():
    public_videos = Video.query.filter_by(is_public=True).order_by(Video.created_at.desc()).all()
    unlocked_video_ids = set()
    if current_user.is_authenticated:
        unlocks = UserVideoUnlock.query.filter_by(user_id=current_user.id).all()
        unlocked_video_ids = {unlock.video_id for unlock in unlocks}
    return render_template('public_gallery.html', videos=public_videos, title="Public Video Gallery", unlocked_video_ids=unlocked_video_ids)

@frontend_bp.route('/profile')
@login_required
def user_profile():
    # Pass current_user to the template, Flask-Login makes it available globally anyway,
    # but explicit can be clear.
    return render_template('profile.html', title="My Profile")
