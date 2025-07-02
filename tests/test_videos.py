import pytest
import os
import io
from app.models import Video, User

def test_upload_video_requires_auth(client, db):
    """Test that video upload endpoint requires authentication."""
    data = {
        'title': 'Test Video Unauth',
        'description': 'A video uploaded by an unauthenticated user.',
        # No file part needed as it should fail before file processing
    }
    # Missing 'file' part, but auth should be checked first.
    # If sending form-data, 'file' would be (io.BytesIO(b"dummy video data"), "test.mp4")
    response = client.post('/videos/upload', data=data) # No auth header
    assert response.status_code == 401
    assert "Request does not contain an access token" in response.get_json()['msg']


def test_upload_video_success(auth_client, db):
    """Test successful video upload by an authenticated user."""
    user_id = auth_client.user_data['id']
    data = {
        'title': 'My Test Video',
        'description': 'A description for my test video.',
        'file': (io.BytesIO(b"fake video data"), "test_video.mp4")
    }
    response = auth_client.post('/videos/upload', data=data, content_type='multipart/form-data')

    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['msg'] == "Video uploaded successfully"
    assert 'video_id' in json_data
    video_id = json_data['video_id']

    video = Video.query.get(video_id)
    assert video is not None
    assert video.title == 'My Test Video'
    assert video.user_id == user_id
    assert video.filename == "test_video.mp4" # Original filename
    assert os.path.exists(video.file_path) # Check if file was saved

    # Clean up the created file
    if os.path.exists(video.file_path):
        os.remove(video.file_path)
        # Clean up user-specific directory if empty
        user_upload_folder = os.path.dirname(video.file_path)
        if not os.listdir(user_upload_folder):
            os.rmdir(user_upload_folder)


def test_upload_video_missing_file(auth_client, db):
    """Test video upload request missing the file part."""
    data = {
        'title': 'Video Without File',
        'description': 'Trying to upload metadata only.'
    }
    response = auth_client.post('/videos/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.get_json()['msg'] == "No file part"

def test_upload_video_missing_title(auth_client, db):
    """Test video upload request missing the title."""
    data = {
        'description': 'Video with no title.',
        'file': (io.BytesIO(b"fake video data"), "no_title_video.mp4")
    }
    response = auth_client.post('/videos/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.get_json()['msg'] == "Missing title"

def test_upload_video_invalid_file_type(auth_client, db):
    """Test video upload with an disallowed file extension."""
    data = {
        'title': 'Invalid File Type Video',
        'description': 'This should not be allowed.',
        'file': (io.BytesIO(b"fake data"), "document.txt")
    }
    response = auth_client.post('/videos/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert response.get_json()['msg'] == "File type not allowed"


def test_get_video_metadata_requires_auth(client, db):
    """Test that getting video metadata requires authentication."""
    response = client.get('/videos/1') # Assuming video ID 1, auth is checked first
    assert response.status_code == 401
    assert "Request does not contain an access token" in response.get_json()['msg']


def test_get_video_metadata_not_found(auth_client, db):
    """Test getting metadata for a video that does not exist."""
    response = auth_client.get('/videos/9999') # Non-existent video ID
    assert response.status_code == 404
    assert response.get_json()['msg'] == "Video not found"


def test_get_video_metadata_success(auth_client, db):
    """Test successfully getting metadata for an existing video."""
    # First, upload a video to get its ID and ensure it exists
    user_id = auth_client.user_data['id']
    upload_data = {
        'title': 'Metadata Test Video',
        'description': 'Video for metadata test.',
        'file': (io.BytesIO(b"metadata video data"), "metadata.mp4")
    }
    upload_response = auth_client.post('/videos/upload', data=upload_data, content_type='multipart/form-data')
    assert upload_response.status_code == 201
    video_id = upload_response.get_json()['video_id']

    # Now, try to get its metadata
    response = auth_client.get(f'/videos/{video_id}')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['id'] == video_id
    assert json_data['title'] == 'Metadata Test Video'
    assert json_data['user_id'] == user_id
    assert json_data['filename'] == "metadata.mp4"

    # Clean up uploaded file
    video = Video.query.get(video_id)
    if video and os.path.exists(video.file_path):
        os.remove(video.file_path)
        user_upload_folder = os.path.dirname(video.file_path)
        if not os.listdir(user_upload_folder):
            os.rmdir(user_upload_folder)


def test_get_user_videos_requires_auth(client, db):
    """Test that getting user-specific videos requires authentication."""
    response = client.get('/videos/user')
    assert response.status_code == 401
    assert "Request does not contain an access token" in response.get_json()['msg']


def test_get_user_videos_success(auth_client, db):
    """Test successfully getting all videos for the authenticated user."""
    user_id = auth_client.user_data['id']
    user_username = auth_client.user_data['username']

    # Upload a couple of videos for this user
    video_details = []
    for i in range(2):
        title = f'User Video {i+1}'
        upload_data = {
            'title': title,
            'description': f'Description for {title}',
            'file': (io.BytesIO(f"user video data {i+1}".encode('utf-8')), f"user_video_{i+1}.mp4")
        }
        upload_response = auth_client.post('/videos/upload', data=upload_data, content_type='multipart/form-data')
        assert upload_response.status_code == 201
        video_details.append(upload_response.get_json())

    # Get user's videos
    response = auth_client.get('/videos/user')
    assert response.status_code == 200
    json_data = response.get_json()

    assert isinstance(json_data, list)
    assert len(json_data) == 2

    # Check if the retrieved videos match what was uploaded (titles and uploader)
    retrieved_titles = sorted([v['title'] for v in json_data])
    expected_titles = sorted([f'User Video {i+1}' for i in range(2)])
    assert retrieved_titles == expected_titles

    for video_meta in json_data:
        assert video_meta['user_id'] == user_id
        assert video_meta['uploader_username'] == user_username

    # Clean up uploaded files
    for video_info in video_details:
        video = Video.query.get(video_info['video_id'])
        if video and os.path.exists(video.file_path):
            os.remove(video.file_path)
            user_upload_folder = os.path.dirname(video.file_path)
            # Be careful if multiple tests run in parallel or share folders.
            # The conftest.py session-wide cleanup should handle the main test_uploads folder.
            # This per-test cleanup is for files created within the test.
            if os.path.exists(user_upload_folder) and not os.listdir(user_upload_folder):
                 os.rmdir(user_upload_folder)


def test_get_user_videos_empty(auth_client, db):
    """Test getting videos for a user who hasn't uploaded any."""
    # auth_client is authenticated but assumed to have no videos yet for this specific test
    # The db fixture ensures a clean state for each test.
    response = auth_client.get('/videos/user')
    assert response.status_code == 200
    json_data = response.get_json()
    assert isinstance(json_data, list)
    assert len(json_data) == 0
