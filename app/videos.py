import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from .models import Video, User
from . import db

videos_bp = Blueprint('videos', __name__)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@videos_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_video():
    current_user_identity = get_jwt_identity()
    user_id = current_user_identity.get('id')

    if 'file' not in request.files:
        return jsonify({"msg": "No file part"}), 400

    file = request.files['file']
    title = request.form.get('title')
    description = request.form.get('description')

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
                user_id=user_id
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
    # current_user_identity = get_jwt_identity()
    # if video.user_id != current_user_identity.get('id'):
    #     return jsonify({"msg": "Unauthorized to view this video's metadata"}), 403

    return jsonify(format_video_metadata(video)), 200

@videos_bp.route('/user', methods=['GET']) # Changed from /user_videos to /user for brevity
@jwt_required()
def get_user_videos():
    current_user_identity = get_jwt_identity()
    user_id = current_user_identity.get('id')

    user = User.query.get(user_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404 # Should not happen if JWT is valid

    videos = Video.query.filter_by(user_id=user_id).order_by(Video.created_at.desc()).all()

    return jsonify([format_video_metadata(video) for video in videos]), 200
