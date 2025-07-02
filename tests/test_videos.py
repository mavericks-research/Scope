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


def test_upload_video_with_price_and_paid_flag(auth_data, db):
    """Test uploading a video and setting it as paid with a price."""
    client, access_token, _ = auth_data
    from decimal import Decimal
    data = {
        'title': 'Paid Content Video',
        'description': 'This video costs money.',
        'video': (io.BytesIO(b"paid content data"), "paid_content.mp4"),
        'is_public': 'true', # Can be public but paid
        'is_paid_unlock': 'true',
        'price': '19.99'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data',
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 201, f"Response: {response.data.decode()}"
    video_id = response.get_json()['video_id']
    video = Video.query.get(video_id)
    assert video is not None
    assert video.is_paid_unlock is True
    assert video.price == Decimal("19.99")
    # Cleanup
    if video and os.path.exists(video.file_path): os.remove(video.file_path)
    if video and not os.listdir(os.path.dirname(video.file_path)): os.rmdir(os.path.dirname(video.file_path))

def test_upload_video_paid_flag_without_price(auth_data, db):
    """Test uploading a video marked as paid but without providing a price."""
    client, access_token, _ = auth_data
    data = {
        'title': 'Paid No Price Video',
        'video': (io.BytesIO(b"paid no price data"), "paid_no_price.mp4"),
        'is_paid_unlock': 'true'
        # Missing 'price'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data',
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 400
    assert response.get_json()['msg'] == "Price is required for paid videos."

def test_upload_video_price_without_paid_flag(auth_data, db):
    """Test uploading a video with a price but not marked as paid."""
    client, access_token, _ = auth_data
    data = {
        'title': 'Price No Paid Flag Video',
        'video': (io.BytesIO(b"price no flag data"), "price_no_flag.mp4"),
        'price': '5.00'
        # Missing 'is_paid_unlock' or it's false
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data',
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 400
    assert response.get_json()['msg'] == "Video must be marked as 'require payment' to set a price."

def test_upload_video_invalid_price_format(auth_data, db):
    """Test uploading a paid video with an invalid price format."""
    client, access_token, _ = auth_data
    data = {
        'title': 'Invalid Price Video',
        'video': (io.BytesIO(b"invalid price data"), "invalid_price.mp4"),
        'is_paid_unlock': 'true',
        'price': 'not_a_number'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data',
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 400
    assert response.get_json()['msg'] == "Invalid price format."

def test_upload_video_price_too_low(auth_data, db):
    """Test uploading a paid video with a price below the minimum."""
    client, access_token, _ = auth_data
    data = {
        'title': 'Low Price Video',
        'video': (io.BytesIO(b"low price data"), "low_price.mp4"),
        'is_paid_unlock': 'true',
        'price': '0.10' # Assuming min is $0.50 as per route logic
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data',
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 400
    assert response.get_json()['msg'] == "Price must be at least $0.50."


def test_upload_video_default_private(auth_data, db):
    """Test that a video is private by default when is_public is not specified."""
    client, access_token, user_info = auth_data
    data = {
        'title': 'Default Private Video',
        'description': 'This video should be private.',
        'video': (io.BytesIO(b"private video data"), "default_private.mp4")
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data',
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 201
    video_id = response.get_json()['video_id']
    video = Video.query.get(video_id)
    assert video is not None
    assert video.is_public is False
    # Cleanup
    if os.path.exists(video.file_path): os.remove(video.file_path)
    if not os.listdir(os.path.dirname(video.file_path)): os.rmdir(os.path.dirname(video.file_path))


def test_upload_video_set_public(auth_data, db):
    """Test uploading a video and explicitly setting it to public."""
    client, access_token, user_info = auth_data
    data = {
        'title': 'Public Test Video',
        'description': 'This video is set to public.',
        'video': (io.BytesIO(b"public video data"), "test_public.mp4"),
        'is_public': 'true'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data',
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 201
    video_id = response.get_json()['video_id']
    video = Video.query.get(video_id)
    assert video is not None
    assert video.is_public is True
    # Cleanup
    if os.path.exists(video.file_path): os.remove(video.file_path)
    if not os.listdir(os.path.dirname(video.file_path)): os.rmdir(os.path.dirname(video.file_path))

def test_upload_video_set_explicitly_private(auth_data, db):
    """Test uploading a video and explicitly setting it to private."""
    client, access_token, user_info = auth_data
    data = {
        'title': 'Explicit Private Video',
        'description': 'This video is explicitly private.',
        'video': (io.BytesIO(b"explicit private data"), "explicit_private.mp4"),
        'is_public': 'false'
    }
    response = client.post('/videos/upload_video', data=data, content_type='multipart/form-data',
                           headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 201
    video_id = response.get_json()['video_id']
    video = Video.query.get(video_id)
    assert video is not None
    assert video.is_public is False
    # Cleanup
    if os.path.exists(video.file_path): os.remove(video.file_path)
    if not os.listdir(os.path.dirname(video.file_path)): os.rmdir(os.path.dirname(video.file_path))


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


# --- Tests for Video Streaming ---

def test_stream_private_video_unauthenticated(client, db, app):
    """Test streaming a private video by an unauthenticated user results in 401."""
    # User A (owner) signs up and uploads a private video
    signup_a_resp = client.post('/auth/signup', json={"username": "ownera_priv_stream", "email": "ownera_priv_stream@example.com", "password": "passworda"})
    assert signup_a_resp.status_code == 201
    jwt_login_a_resp = client.post('/auth/login', json={'identifier': 'ownera_priv_stream', 'password': 'passworda'})
    jwt_a = jwt_login_a_resp.get_json()['access_token']

    video_content = b"private stream data"
    upload_resp = client.post('/videos/upload_video', data={
        'title': "Owner A's Private Video",
        'video': (io.BytesIO(video_content), "video_a_private.mp4"),
        'is_public': 'false' # Explicitly private
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_a}"})
    assert upload_resp.status_code == 201
    video_a_id = upload_resp.get_json()['video_id']
    video_a_path = Video.query.get(video_a_id).file_path


    # Logout all users (clear session)
    client.get('/auth/logout', follow_redirects=True)

    # Unauthenticated client tries to stream User A's private video
    response = client.get(f'/videos/stream/{video_a_id}')
    assert response.status_code == 401 # Unauthorized as per new logic

    # Cleanup
    if os.path.exists(video_a_path): os.remove(video_a_path)
    if not os.listdir(os.path.dirname(video_a_path)): os.rmdir(os.path.dirname(video_a_path))


def test_stream_public_video_anonymous(client, db, app):
    """Test streaming a public video as an anonymous (unauthenticated) user."""
    # User A (owner) signs up and uploads a public video
    signup_a_resp = client.post('/auth/signup', json={"username": "ownera_pub_stream", "email": "ownera_pub_stream@example.com", "password": "passworda"})
    assert signup_a_resp.status_code == 201
    jwt_login_a_resp = client.post('/auth/login', json={'identifier': 'ownera_pub_stream', 'password': 'passworda'})
    jwt_a = jwt_login_a_resp.get_json()['access_token']

    video_content = b"public stream data"
    upload_resp = client.post('/videos/upload_video', data={
        'title': "Owner A's Public Video",
        'video': (io.BytesIO(video_content), "video_a_public.mp4"),
        'is_public': 'true' # Explicitly public
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_a}"})
    assert upload_resp.status_code == 201
    video_a_id = upload_resp.get_json()['video_id']
    video_a_path = Video.query.get(video_a_id).file_path

    # Logout all users (clear session)
    client.get('/auth/logout', follow_redirects=True)

    # Unauthenticated client tries to stream User A's public video
    response = client.get(f'/videos/stream/{video_a_id}')
    assert response.status_code == 200
    assert response.data == video_content
    assert response.content_type == 'video/mp4'

    # Cleanup
    if os.path.exists(video_a_path): os.remove(video_a_path)
    if not os.listdir(os.path.dirname(video_a_path)): os.rmdir(os.path.dirname(video_a_path))


def test_stream_video_non_existent(client, db): # No auth needed if video doesn't exist (404)
    """Test streaming a non-existent video ID."""
    # No login needed, as 404 should be returned before auth checks for non-existent entities.
    response = client.get('/videos/stream/99999') # Non-existent ID
    assert response.status_code == 404


def test_stream_private_video_unauthorized_other_user(client, db, app):
    """Test streaming another user's private video results in 403."""
    # User A (owner)
    signup_a_resp = client.post('/auth/signup', json={"username": "ownera_priv", "email": "ownera_priv@example.com", "password": "passworda"})
    assert signup_a_resp.status_code == 201
    jwt_login_a_resp = client.post('/auth/login', json={'identifier': 'ownera_priv', 'password': 'passworda'})
    jwt_a = jwt_login_a_resp.get_json()['access_token']

    upload_resp = client.post('/videos/upload_video', data={
        'title': "Owner A's Private Video",
        'video': (io.BytesIO(b"data a private"), "video_a_priv.mp4"),
        'is_public': 'false' # Explicitly private
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_a}"})
    assert upload_resp.status_code == 201
    video_a_id = upload_resp.get_json()['video_id']
    video_a_path = Video.query.get(video_a_id).file_path


    # User B (requester)
    signup_b_resp = client.post('/auth/signup', json={"username": "requesterb_priv", "email": "requesterb_priv@example.com", "password": "passwordb"})
    assert signup_b_resp.status_code == 201
    # Log in User B via form for session auth
    login_b_resp = client.post('/auth/login', data={'identifier': 'requesterb_priv', 'password': 'passwordb'}, follow_redirects=True)
    assert login_b_resp.status_code == 200

    # User B tries to stream User A's private video
    response = client.get(f'/videos/stream/{video_a_id}')
    assert response.status_code == 403 # Forbidden

    # Cleanup
    if os.path.exists(video_a_path): os.remove(video_a_path)
    if not os.listdir(os.path.dirname(video_a_path)): os.rmdir(os.path.dirname(video_a_path))


def test_stream_public_video_authenticated_non_owner(client, db, app):
    """Test streaming another user's public video as an authenticated user."""
    # User A (owner) uploads a public video
    signup_a_resp = client.post('/auth/signup', json={"username": "ownera_pub", "email": "ownera_pub@example.com", "password": "passworda"})
    assert signup_a_resp.status_code == 201
    jwt_login_a_resp = client.post('/auth/login', json={'identifier': 'ownera_pub', 'password': 'passworda'})
    jwt_a = jwt_login_a_resp.get_json()['access_token']

    video_content_public = b"public data from owner a"
    upload_resp = client.post('/videos/upload_video', data={
        'title': "Owner A's Public Video",
        'video': (io.BytesIO(video_content_public), "video_a_pub.mp4"),
        'is_public': 'true' # Explicitly public
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_a}"})
    assert upload_resp.status_code == 201
    video_a_id = upload_resp.get_json()['video_id']
    video_a_path = Video.query.get(video_a_id).file_path

    # User B (requester) signs up and logs in
    signup_b_resp = client.post('/auth/signup', json={"username": "requesterb_pub", "email": "requesterb_pub@example.com", "password": "passwordb"})
    assert signup_b_resp.status_code == 201
    login_b_resp = client.post('/auth/login', data={'identifier': 'requesterb_pub', 'password': 'passwordb'}, follow_redirects=True)
    assert login_b_resp.status_code == 200

    # User B tries to stream User A's public video
    response = client.get(f'/videos/stream/{video_a_id}')
    assert response.status_code == 200
    assert response.data == video_content_public
    assert response.content_type == 'video/mp4'

    # Cleanup
    if os.path.exists(video_a_path): os.remove(video_a_path)
    if not os.listdir(os.path.dirname(video_a_path)): os.rmdir(os.path.dirname(video_a_path))


def test_stream_private_video_success_owner(client, db, app):
    """Test successful private video streaming by the video owner."""
    # Signup and login user
    signup_resp = client.post('/auth/signup', json={"username": "streamowner_priv", "email": "streamowner_priv@example.com", "password": "password"})
    assert signup_resp.status_code == 201

    # Get JWT for upload
    jwt_login_resp = client.post('/auth/login', json={'identifier': 'streamowner_priv', 'password': 'password'})
    assert jwt_login_resp.status_code == 200
    jwt_token = jwt_login_resp.get_json()['access_token']

    # Upload a private video
    video_content = b"dummy mp4 private video content for streaming test"
    upload_resp = client.post('/videos/upload_video', data={
        'title': "Streamable Private Video",
        'video': (io.BytesIO(video_content), "stream_test_private.mp4"),
        'is_public': 'false' # Explicitly private
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_token}"})
    assert upload_resp.status_code == 201
    video_id = upload_resp.get_json()['video_id']
    video_path = Video.query.get(video_id).file_path


    # Log in via form for session auth to access streaming endpoint
    form_login_resp = client.post('/auth/login', data={'identifier': 'streamowner_priv', 'password': 'password'}, follow_redirects=True)
    assert form_login_resp.status_code == 200

    # Stream the video
    response = client.get(f'/videos/stream/{video_id}')
    assert response.status_code == 200
    assert response.content_type == 'video/mp4'
    assert response.data == video_content
    content_disposition = response.headers.get('Content-Disposition')
    assert content_disposition is not None
    assert content_disposition.startswith('inline; filename=')

    # Cleanup
    if os.path.exists(video_path): os.remove(video_path)
    if not os.listdir(os.path.dirname(video_path)): os.rmdir(os.path.dirname(video_path))


@pytest.mark.skip(reason="Need to mock os.path.exists for this test properly")
def test_stream_video_file_not_found_on_disk(client, db, app, mocker):
    """Test streaming when DB record exists but file is missing on disk."""
    # Signup and login user
    signup_resp = client.post('/auth/signup', json={"username": "diskerroruser", "email": "diskerror@example.com", "password": "password"})
    assert signup_resp.status_code == 201
    jwt_login_resp = client.post('/auth/login', json={'identifier': 'diskerroruser', 'password': 'password'})
    jwt_token = jwt_login_resp.get_json()['access_token']

    # Upload a video (file will be created)
    upload_resp = client.post('/videos/upload_video', data={
        'title': "Missing File Video", 'video': (io.BytesIO(b"data"), "missing.mp4")
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_token}"})
    assert upload_resp.status_code == 201
    video_id = upload_resp.get_json()['video_id']

    # Log in via form for session
    form_login_resp = client.post('/auth/login', data={'identifier': 'diskerroruser', 'password': 'password'}, follow_redirects=True)
    assert form_login_resp.status_code == 200

    # Mock os.path.exists to return False for this video's file_path
    video = Video.query.get(video_id)
    mocker.patch('os.path.exists', return_value=False) # This might be too broad.
    # A more targeted mock: mocker.patch('app.videos.os.path.exists', return_value=False)
    # And ensure it only returns False for video.file_path

    # For a more targeted mock, we might need to inspect video.file_path and mock specifically for it.
    # This simple mock will make all os.path.exists return False in the route.

    response = client.get(f'/videos/stream/{video_id}')
    assert response.status_code == 404 # As per current route logic


# --- Tests for Video Visibility Toggle ---

def test_toggle_video_visibility_owner(auth_data, db):
    """Test that the video owner can toggle video visibility."""
    client, access_token, user_info = auth_data
    user_id = user_info['id']

    # Upload a video, will be private by default
    upload_data = {
        'title': 'Toggle Test Video',
        'video': (io.BytesIO(b"toggle data"), "toggle.mp4")
    }
    upload_response = client.post('/videos/upload_video', data=upload_data, content_type='multipart/form-data',
                                  headers={"Authorization": f"Bearer {access_token}"})
    assert upload_response.status_code == 201
    video_id = upload_response.get_json()['video_id']

    video = Video.query.get(video_id)
    assert video.is_public is False # Initially private

    # Ensure clean session state then log in via form for session auth
    client.get('/auth/logout', follow_redirects=True) # Logout any existing session
    login_form_response = client.post('/auth/login', data={'identifier': user_info['username'], 'password': 'password123'}, follow_redirects=True)
    assert login_form_response.status_code == 200
    assert b"Logged in successfully!" in login_form_response.data


    # Toggle to public
    toggle_response_public = client.post(f'/videos/{video_id}/toggle-visibility', follow_redirects=True)
    assert toggle_response_public.status_code == 200 # Redirects to my_videos
    assert b"visibility updated to Public" in toggle_response_public.data # Check flash message
    db.session.refresh(video) # Refresh from DB
    assert video.is_public is True

    # Toggle back to private
    toggle_response_private = client.post(f'/videos/{video_id}/toggle-visibility', follow_redirects=True)
    assert toggle_response_private.status_code == 200
    assert b"visibility updated to Private" in toggle_response_private.data
    db.session.refresh(video)
    assert video.is_public is False

    # Cleanup
    if os.path.exists(video.file_path): os.remove(video.file_path)
    if not os.listdir(os.path.dirname(video.file_path)): os.rmdir(os.path.dirname(video.file_path))


def test_toggle_video_visibility_not_owner(auth_data, db):
    """Test that a non-owner cannot toggle video visibility."""
    client, owner_access_token, owner_info = auth_data # This is User1 (owner)

    # User1 (owner) uploads a video
    upload_data = {
        'title': 'Owner Video For Toggle Test',
        'video': (io.BytesIO(b"owner video data"), "owner_video.mp4")
    }
    upload_response = client.post('/videos/upload_video', data=upload_data, content_type='multipart/form-data',
                                  headers={"Authorization": f"Bearer {owner_access_token}"})
    assert upload_response.status_code == 201
    video_id = upload_response.get_json()['video_id']
    video = Video.query.get(video_id)
    initial_visibility = video.is_public

    # Create and log in User2 (non-owner)
    client.post('/auth/signup', json={"username": "nonowner", "email": "nonowner@example.com", "password": "password"})
    # Log in User2 via form for session auth
    login_resp_non_owner = client.post('/auth/login', data={'identifier': 'nonowner', 'password': 'password'}, follow_redirects=True)
    assert login_resp_non_owner.status_code == 200


    # User2 (non-owner) attempts to toggle visibility
    toggle_response = client.post(f'/videos/{video_id}/toggle-visibility')
    assert toggle_response.status_code == 403 # Forbidden

    db.session.refresh(video) # Refresh from DB
    assert video.is_public == initial_visibility # Visibility should not have changed

    # Cleanup for owner's video
    if os.path.exists(video.file_path): os.remove(video.file_path)
    user_upload_folder = os.path.dirname(video.file_path)
    if os.path.exists(user_upload_folder) and not os.listdir(user_upload_folder):
        os.rmdir(user_upload_folder)


def test_toggle_video_visibility_non_existent(auth_data, db):
    """Test toggling visibility for a video that does not exist."""
    client, _, user_info = auth_data
    # Ensure clean session state then log in via form for session auth
    client.get('/auth/logout', follow_redirects=True) # Logout any existing session
    login_form_response = client.post('/auth/login', data={'identifier': user_info['username'], 'password': 'password123'}, follow_redirects=True)
    assert login_form_response.status_code == 200
    assert b"Logged in successfully!" in login_form_response.data

    response = client.post('/videos/99999/toggle-visibility') # Non-existent video ID
    assert response.status_code == 404


def test_toggle_video_visibility_unauthenticated(client, db):
    """Test that an unauthenticated user cannot toggle visibility and is redirected."""
    # No need to upload a video, as auth check should happen first.
    # If a video ID is required for the route to resolve, it would be:
    # client.post('/videos/1/toggle-visibility', follow_redirects=False)
    # However, the endpoint itself is protected by @login_required
    response = client.post('/videos/1/toggle-visibility', follow_redirects=False) # Assuming video ID 1 might exist or not
    assert response.status_code == 302 # Redirect to login
    assert '/auth/login' in response.headers['Location']

# --- Tests for Paid Video Functionality ---
from decimal import Decimal # Import Decimal

def test_video_model_paid_fields(db, app):
    """Test that Video model's price and is_paid_unlock fields work."""
    from decimal import Decimal
    user = User(username="paiduser", email="paid@example.com", password="password")
    db.session.add(user)
    db.session.commit()

    video1 = Video(title="Free Video", filename="free.mp4", file_path="/fake/free.mp4", user_id=user.id)
    db.session.add(video1)
    db.session.commit()
    assert video1.price is None
    assert video1.is_paid_unlock is False

    video2 = Video(title="Paid Video", filename="paid.mp4", file_path="/fake/paid.mp4", user_id=user.id,
                   is_paid_unlock=True, price=Decimal("9.99"))
    db.session.add(video2)
    db.session.commit()
    assert video2.price == Decimal("9.99")
    assert video2.is_paid_unlock is True

def test_user_video_unlock_model(db, app):
    """Test creation of UserVideoUnlock records."""
    from app.models import UserVideoUnlock # Import locally if not at top
    user1 = User(username="unlockuser1", email="unlock1@example.com", password="password")
    user2 = User(username="unlockuser2", email="unlock2@example.com", password="password")
    db.session.add_all([user1, user2])
    db.session.commit()

    video = Video(title="Unlockable Video", filename="unlockable.mp4", file_path="/fake/unlockable.mp4", user_id=user1.id,
                  is_paid_unlock=True, price=Decimal("5.00"))
    db.session.add(video)
    db.session.commit()

    # User1 unlocks the video
    unlock_record = UserVideoUnlock(user_id=user1.id, video_id=video.id, stripe_payment_intent_id="pi_test123")
    db.session.add(unlock_record)
    db.session.commit()

    assert unlock_record.id is not None
    assert unlock_record.user_id == user1.id
    assert unlock_record.video_id == video.id
    assert unlock_record.stripe_payment_intent_id == "pi_test123"
    assert UserVideoUnlock.query.count() == 1

    retrieved_unlock = UserVideoUnlock.query.filter_by(user_id=user1.id, video_id=video.id).first()
    assert retrieved_unlock is not None
    assert retrieved_unlock.user == user1
    assert retrieved_unlock.video == video

    # Check unique constraint: User1 tries to unlock the same video again (should fail if we try to add another identical record)
    # This is usually caught at DB level. Application logic should prevent creating duplicates.
    duplicate_unlock_attempt = UserVideoUnlock(user_id=user1.id, video_id=video.id, stripe_payment_intent_id="pi_test456")
    db.session.add(duplicate_unlock_attempt)
    try:
        db.session.commit()
        # We shouldn't reach here if the unique constraint is working
        assert False, "Duplicate UserVideoUnlock record should not be allowed by unique constraint."
    except Exception as e: # Catch general IntegrityError or specific DB error
        db.session.rollback()
        print(f"Caught expected error for duplicate unlock: {e}")
        assert UserVideoUnlock.query.count() == 1 # Still only one record

    # User2 unlocks the same video - should be fine
    unlock_record_user2 = UserVideoUnlock(user_id=user2.id, video_id=video.id, stripe_payment_intent_id="pi_test789")
    db.session.add(unlock_record_user2)
    db.session.commit()
    assert UserVideoUnlock.query.count() == 2
