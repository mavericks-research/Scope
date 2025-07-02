import pytest
from app.models import User, Video # Assuming Video model is in app.models
from app import db as _db # To interact with database session if needed for setup
import io # For creating dummy file data

# Helper function to get flashed messages (if needed, though direct content check is often simpler)
# def get_flashed_messages(client):
#     return [msg[1] for msg in client.get('/_flashes').json] # Requires custom flashes endpoint or session inspection

def test_my_videos_unauthenticated(client):
    """Test that /my-videos redirects to login if user is not authenticated."""
    response = client.get('/my-videos', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']

def test_my_videos_authenticated_no_videos(client, db): # Removed auth_data
    """Test /my-videos for an authenticated user with no videos."""
    # 1. Create user for this test
    signup_resp = client.post('/auth/signup', json={
        "username": "no_videos_user",
        "email": "no_videos_user@example.com",
        "password": "password123"
    })
    assert signup_resp.status_code == 201, f"Signup failed: {signup_resp.data.decode()}"

    # 2. Log in this user via form
    login_resp = client.post('/auth/login', data={
        'identifier': 'no_videos_user',
        'password': 'password123'
    }, follow_redirects=True)

    assert login_resp.status_code == 200, f"Login failed: {login_resp.data.decode()}"
    assert login_resp.request.path == '/', f"Not redirected to index after login. Current path: {login_resp.request.path}"
    assert b"Logged in successfully!" in login_resp.data, "Login success flash message not found."

    # 3. Access /my-videos
    response = client.get('/my-videos')
    assert response.status_code == 200, f"Accessing /my-videos failed. Status: {response.status_code}. Location: {response.location if response.location else 'N/A'}"
    content = response.data.decode()
    assert "My Uploaded Videos" in content
    assert "You haven't uploaded any videos yet." in content

def test_my_videos_authenticated_with_videos(client, db, app): # Removed auth_data
    """Test /my-videos for an authenticated user with uploaded videos."""

    # 1. Create and log in user for form session
    signup_resp = client.post('/auth/signup', json={
        "username": "video_owner",
        "email": "video_owner@example.com",
        "password": "password123"
    })
    assert signup_resp.status_code == 201, f"Signup failed: {signup_resp.data.decode()}"

    # Log in via form to establish Flask-Login session
    form_login_resp = client.post('/auth/login', data={
        'identifier': 'video_owner',
        'password': 'password123'
    }, follow_redirects=True)
    assert form_login_resp.status_code == 200, f"Form login failed: {form_login_resp.data.decode()}"
    assert b"Logged in successfully!" in form_login_resp.data, "Login success flash message not found in form login."

    # Also get a JWT for this user to upload videos via API
    # (as the uploader script uses JWT)
    jwt_login_resp = client.post('/auth/login', json={
        'identifier': 'video_owner',
        'password': 'password123'
    })
    assert jwt_login_resp.status_code == 200, f"JWT login failed: {jwt_login_resp.data.decode()}"
    jwt_access_token = jwt_login_resp.get_json()['access_token']

    # 2. Upload some videos for this user via the API endpoint using JWT
    video_titles = ["My First Video", "Another Great Clip"]
    for i, title in enumerate(video_titles):
        upload_data = {
            'title': title,
            'description': f'Description for {title}',
            'video': (io.BytesIO(f"dummy video data {i}".encode('utf-8')), f"test_video_{i}.mp4")
        }
        # Use JWT token for the API upload
        upload_response = client.post('/videos/upload_video', data=upload_data, content_type='multipart/form-data',
                                      headers={"Authorization": f"Bearer {jwt_access_token}"})
        assert upload_response.status_code == 201, f"Failed to upload {title}: {upload_response.data.decode()}"

    # Now access the /my-videos page (which uses Flask-Login session)
    response = client.get('/my-videos')
    assert response.status_code == 200
    content = response.data.decode()

    assert "My Uploaded Videos" in content
    for title in video_titles:
        assert title in content
    assert "You haven't uploaded any videos yet." not in content

    # Cleanup: Manually remove video files if necessary, though test db should handle records.
    # Videos are stored with unique names in user-specific folders.
    # The test teardown in conftest.py should remove the test_uploads folder.


def test_my_videos_isolation(client, db, app): # Removed auth_data
    """Test that /my-videos only shows videos for the logged-in user."""

    # --- User A Setup ---
    # Signup User A
    signup_a_resp = client.post('/auth/signup', json={
        "username": "usera", "email": "usera@example.com", "password": "passworda"
    })
    assert signup_a_resp.status_code == 201, f"Signup User A failed: {signup_a_resp.data.decode()}"

    # Get JWT for User A to upload video
    jwt_login_a_resp = client.post('/auth/login', json={
        'identifier': 'usera', 'password': 'passworda'
    })
    assert jwt_login_a_resp.status_code == 200
    jwt_a = jwt_login_a_resp.get_json()['access_token']

    # Upload video for User A using JWT
    upload_resp_a = client.post('/videos/upload_video', data={
        'title': "User A's Video", 'description': 'Video by A.',
        'video': (io.BytesIO(b"video data A"), "video_a.mp4")
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_a}"})
    assert upload_resp_a.status_code == 201, f"Upload for User A failed: {upload_resp_a.data.decode()}"

    # Diagnostic: Verify User A's video is in DB
    usera_obj = User.query.filter_by(username="usera").first()
    assert usera_obj is not None
    video_a_db = Video.query.filter_by(user_id=usera_obj.id, title="User A's Video").first()
    assert video_a_db is not None, "User A's video not found in DB after upload"
    print(f"\n[DIAGNOSTIC User A Setup] User A ID: {usera_obj.id}, Video A Title: {video_a_db.title}, Video User ID: {video_a_db.user_id}")

    # --- User B Setup ---
    # Signup User B
    signup_b_resp = client.post('/auth/signup', json={
        "username": "userb", "email": "userb@example.com", "password": "passwordb"
    })
    assert signup_b_resp.status_code == 201, f"Signup User B failed: {signup_b_resp.data.decode()}"

    # Login User B (Form-based for session)
    login_b_resp = client.post('/auth/login', data={
        'identifier': 'userb', 'password': 'passwordb'
    }, follow_redirects=True)
    assert login_b_resp.status_code == 200, f"Form login for User B failed: {login_b_resp.data.decode()}"
    assert b"Logged in successfully!" in login_b_resp.data

    # Access /my-videos as User B
    response_b = client.get('/my-videos')
    assert response_b.status_code == 200
    content_b = response_b.data.decode()
    assert "My Uploaded Videos" in content_b
    assert "User A's Video" not in content_b  # Crucial: User B should not see User A's video
    assert "You haven't uploaded any videos yet." in content_b # User B has uploaded no videos

    # --- Verify User A can see their video ---
    # Logout User B (important: client maintains session state)
    client.get('/auth/logout', follow_redirects=True)

    # Login User A (Form-based for session)
    login_a_resp = client.post('/auth/login', data={
        'identifier': 'usera', 'password': 'passworda'
    }, follow_redirects=True)
    assert login_a_resp.status_code == 200, f"Form login for User A failed: {login_a_resp.data.decode()}"
    assert b"Logged in successfully!" in login_a_resp.data

    # Diagnostic: Check User A's videos in DB before accessing the route
    usera_obj_again = User.query.filter_by(username="usera").first() # Should be the same usera_obj
    assert usera_obj_again is not None
    videos_for_usera_in_db = Video.query.filter_by(user_id=usera_obj_again.id).all()
    print(f"\n[DIAGNOSTIC User A Re-Login] Expecting User A ID: {usera_obj_again.id}. Videos in DB for User A: {[v.title for v in videos_for_usera_in_db]}")

    # Access /my-videos as User A
    response_a = client.get('/my-videos')
    assert response_a.status_code == 200
    content_a = response_a.data.decode()
    assert "My Uploaded Videos" in content_a
    assert "User A's Video" in content_a
    assert "You haven't uploaded any videos yet." not in content_a
