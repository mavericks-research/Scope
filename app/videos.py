import os
import uuid
import os
import uuid
from flask import Blueprint, request, jsonify, current_app, send_file, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required, current_user # Added for session auth
from werkzeug.utils import secure_filename
from .models import Video, User
from . import db

videos_bp = Blueprint('videos', __name__)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@videos_bp.route('/upload_video', methods=['POST']) # Changed route to match form and plan
@jwt_required()
def upload_video_route(): # Renamed function to avoid conflict if we had an import named upload_video
    user_id_str = get_jwt_identity()
    try:
        user_id = int(user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user identity in token"}), 400

    if 'video' not in request.files: # Changed 'file' to 'video' to match form
        return jsonify({"msg": "No video file part"}), 400

    file = request.files['video'] # Changed 'file' to 'video'
    title = request.form.get('title')
    description = request.form.get('description')
    is_public_str = request.form.get('is_public', 'false') # Default to 'false' if not provided
    is_public = is_public_str.lower() == 'true'


    if not title:
        return jsonify({"msg": "Missing title"}), 400

    if file.filename == '':
        return jsonify({"msg": "No selected file"}), 400

    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        # Create a unique filename to prevent collisions and associate with video ID later if needed
        # For now, a simple unique name.
        # A more robust approach for local storage might involve user-specific or video-specific subdirectories.

        # Ensure user-specific upload directory exists
        user_upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(user_id))
        if not os.path.exists(user_upload_folder):
            os.makedirs(user_upload_folder)

        # Generate a unique name for the stored file to avoid conflicts
        unique_id = uuid.uuid4().hex
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        stored_filename = f"{unique_id}.{file_extension}"

        file_path = os.path.join(user_upload_folder, stored_filename)

        try:
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            new_video = Video(
                title=title,
                description=description,
                filename=original_filename, # Original filename from upload
                file_path=file_path, # Path where it's stored
                total_size=file_size,
                user_id=user_id,
                is_public=is_public # Set the visibility
            )
            db.session.add(new_video)
            db.session.commit()

            # It's good practice to return the ID of the created resource
            return jsonify({
                "msg": "Video uploaded successfully",
                "video_id": new_video.id,
                "title": new_video.title,
                "file_path": new_video.file_path
            }), 201

        except Exception as e:
            # Clean up uploaded file if database commit fails
            if os.path.exists(file_path):
                os.remove(file_path)
            db.session.rollback()
            current_app.logger.error(f"Error uploading video: {e}")
            return jsonify({"msg": "Error uploading video", "error": str(e)}), 500
    else:
        return jsonify({"msg": "File type not allowed"}), 400

def format_video_metadata(video):
    return {
        "id": video.id,
        "title": video.title,
        "description": video.description,
        "filename": video.filename,
        "file_path": video.file_path,
        "total_size": video.total_size,
        "user_id": video.user_id,
        "uploader_username": video.uploader.username, # Assuming 'uploader' relationship is loaded
        "created_at": video.created_at.isoformat(),
        "updated_at": video.updated_at.isoformat(),
        "is_processed": video.is_processed,
    }

@videos_bp.route('/<int:video_id>', methods=['GET'])
@jwt_required()
def get_video_metadata(video_id):
    video = Video.query.get(video_id)
    if not video:
        return jsonify({"msg": "Video not found"}), 404

    # Optionally, you might want to restrict access so users can only see their own videos
    # or make it public, depending on requirements. For now, any authenticated user can see any video metadata by ID.
    # current_user_identity_str = get_jwt_identity() # This is str(user.id)
    # current_user_id = int(current_user_identity_str)
    # if video.user_id != current_user_id:
    #     return jsonify({"msg": "Unauthorized to view this video's metadata"}), 403

    return jsonify(format_video_metadata(video)), 200

@videos_bp.route('/user', methods=['GET']) # Changed from /user_videos to /user for brevity
@jwt_required()
def get_user_videos():
    user_id_str = get_jwt_identity() # This is str(user.id)
    try:
        user_id = int(user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user identity in token"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404 # Should not happen if JWT is valid

    videos = Video.query.filter_by(user_id=user_id).order_by(Video.created_at.desc()).all()

    return jsonify([format_video_metadata(video) for video in videos]), 200

@videos_bp.route('/stream/<int:video_id>')
# @login_required # Removed to allow anonymous access to public video streams
def stream_video(video_id):
    video = Video.query.get_or_404(video_id)

    if not video.is_public:
        # Video is private, requires authentication and ownership
        if not current_user.is_authenticated:
            current_app.logger.warning(
                f"Anonymous user attempted to stream private video ID {video_id}."
            )
            abort(401) # Unauthorized - login required
        elif video.user_id != current_user.id:
            current_app.logger.warning(
                f"User {current_user.id} attempted to stream private video ID {video_id} owned by {video.user_id}."
            )
            abort(403) # Forbidden - user does not own video
    # If video is public, anyone can stream it (logged in or anonymous)

    if not os.path.exists(video.file_path):
        current_app.logger.error(f"Video file not found for video ID {video_id} at path {video.file_path}")
        abort(404) # Or perhaps 500 if this indicates an internal inconsistency

    # Determine mimetype (simple version, can be enhanced)
    mimetype = 'video/mp4' # Default
    if '.' in video.filename:
        ext = video.filename.rsplit('.', 1)[1].lower()
        if ext == 'webm':
            mimetype = 'video/webm'
        elif ext == 'ogv':
            mimetype = 'video/ogg'
        # Add other mimetypes as needed

    try:
        return send_file(video.file_path, mimetype=mimetype, as_attachment=False) # as_attachment=False for embedding
    except Exception as e:
        current_app.logger.error(f"Error sending file for video ID {video_id}: {e}")
        abort(500)

@videos_bp.route('/<int:video_id>/toggle-visibility', methods=['POST'])
@login_required # Ensure user is logged in
def toggle_video_visibility(video_id):
    video = Video.query.get_or_404(video_id)

    # Check if the current user is the owner of the video
    if video.user_id != current_user.id:
        current_app.logger.warning(f"User {current_user.id} attempted to toggle visibility for video {video.id} owned by {video.user_id}.")
        abort(403) # Forbidden

    try:
        video.is_public = not video.is_public
        db.session.commit()
        # flash(f"Video '{video.title}' is now {'public' if video.is_public else 'private'}.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling video visibility for video {video.id}: {e}")
        # flash("Error updating video visibility. Please try again.", "error")
        abort(500) # Or handle more gracefully, perhaps redirecting with an error message

    # Redirect back to the 'my_videos' page, or wherever is appropriate
    # For HTMX or JS-driven updates, you might return a JSON response or a partial template
    from flask import redirect, url_for, flash # Moved imports here to avoid circular dependency if this file grows
    flash(f"Video '{video.title}' visibility updated to {'Public' if video.is_public else 'Private'}.", "success")
    return redirect(url_for('frontend.my_videos'))
