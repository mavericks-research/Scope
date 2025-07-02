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
    # If sending form-data, 'video' would be (io.BytesIO(b"dummy video data"), "test.mp4")
    response = client.post('/videos/upload_video', data=data) # No auth header, updated endpoint
    assert response.status_code == 401
    # The message comes from flask_jwt_extended
    assert "Missing Authorization Header" in response.get_json()['msg'] or "Request does not contain an access token" in response.get_json()['msg']


def test_upload_video_success(auth_data, db):
    """Test successful video upload by an authenticated user."""
    client, access_token, user_info = auth_data
    user_id = user_info['id']
    data = {
        'title': 'My Test Video',
        'description': 'A description for my test video.',
        'video': (io.BytesIO(b"fake video data"), "test_video.mp4") # Changed 'file' to 'video'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data', # Updated endpoint
                           headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.data.decode()}"
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


def test_upload_video_missing_file(auth_data, db):
    """Test video upload request missing the file part."""
    client, access_token, _ = auth_data
    data = {
        'title': 'Video Without File',
        'description': 'Trying to upload metadata only.'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data', # Updated endpoint
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 400
    assert response.get_json()['msg'] == "No video file part" # Updated message

def test_upload_video_missing_title(auth_data, db):
    """Test video upload request missing the title."""
    client, access_token, _ = auth_data
    data = {
        'description': 'Video with no title.',
        'video': (io.BytesIO(b"fake video data"), "no_title_video.mp4") # Changed 'file' to 'video'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data', # Updated endpoint
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 400
    assert response.get_json()['msg'] == "Missing title"

def test_upload_video_invalid_file_type(auth_data, db):
    """Test video upload with an disallowed file extension."""
    client, access_token, _ = auth_data
    data = {
        'title': 'Invalid File Type Video',
        'description': 'This should not be allowed.',
        'video': (io.BytesIO(b"fake data"), "document.txt") # Changed 'file' to 'video'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data', # Updated endpoint
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 400
    assert response.get_json()['msg'] == "File type not allowed"


def test_get_video_metadata_requires_auth(client, db):
    """Test that getting video metadata requires authentication."""
    response = client.get('/videos/1') # Assuming video ID 1, auth is checked first
    assert response.status_code == 401
    assert "Request does not contain an access token" in response.get_json()['msg']


def test_get_video_metadata_not_found(auth_data, db):
    """Test getting metadata for a video that does not exist."""
    client, access_token, _ = auth_data
    response = client.get('/videos/9999', headers={"Authorization": f"Bearer {access_token}"}) # Non-existent video ID
    assert response.status_code == 404
    assert response.get_json()['msg'] == "Video not found"


def test_get_video_metadata_success(auth_data, db):
    """Test successfully getting metadata for an existing video."""
    client, access_token, user_info = auth_data
    user_id = user_info['id']
    # First, upload a video to get its ID and ensure it exists
    upload_data = {
        'title': 'Metadata Test Video',
        'description': 'Video for metadata test.',
        'video': (io.BytesIO(b"metadata video data"), "metadata.mp4") # Changed 'file' to 'video'
    }
    upload_response = client.post('/videos/upload_video', data=upload_data, content_type='multipart/form-data', # Updated endpoint
                                  headers={"Authorization": f"Bearer {access_token}"})
    assert upload_response.status_code == 201, f"Setup failed: {upload_response.data.decode()}"
    video_id = upload_response.get_json()['video_id']

    # Now, try to get its metadata
    response = client.get(f'/videos/{video_id}', headers={"Authorization": f"Bearer {access_token}"})
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


def test_get_user_videos_success(auth_data, db):
    """Test successfully getting all videos for the authenticated user."""
    client, access_token, user_info = auth_data
    user_id = user_info['id']
    user_username = user_info['username']

    # Upload a couple of videos for this user
    video_details = []
    for i in range(2):
        title = f'User Video {i+1}'
        upload_data = {
            'title': title,
            'description': f'Description for {title}',
            'video': (io.BytesIO(f"user video data {i+1}".encode('utf-8')), f"user_video_{i+1}.mp4") # Changed 'file' to 'video'
        }
        upload_response = client.post('/videos/upload_video', data=upload_data, content_type='multipart/form-data', # Updated endpoint
                                      headers={"Authorization": f"Bearer {access_token}"})
        assert upload_response.status_code == 201, f"Setup failed for {title}: {upload_response.data.decode()}"
        video_details.append(upload_response.get_json())

    # Get user's videos
    response = client.get('/videos/user', headers={"Authorization": f"Bearer {access_token}"})
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


def test_get_user_videos_empty(auth_data, db):
    """Test getting videos for a user who hasn't uploaded any."""
    client, access_token, _ = auth_data
    # auth_data is authenticated but assumed to have no videos yet for this specific test
    # The db fixture ensures a clean state for each test.
    response = client.get('/videos/user', headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    json_data = response.get_json()
    assert isinstance(json_data, list)
    assert len(json_data) == 0
