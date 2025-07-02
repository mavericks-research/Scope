import pytest
from app.models import User, Video, UserVideoUnlock # Assuming Video model is in app.models
from app import db as _db # To interact with database session if needed for setup
import io # For creating dummy file data
from decimal import Decimal # For checking price
import os # For file cleanup in tests

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
    # Default redirect after login is now to the upload page
    assert login_resp.request.path == '/upload', f"Not redirected to /upload after login. Current path: {login_resp.request.path}"
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
        assert title in content # Check title is present
        # Also check for the video tag and its src attribute
        # Need the video ID for this. Let's get it after upload.
        # This requires modifying the loop or storing video_ids.

    # Re-fetch videos from DB to get their IDs for src check
    owner_user = User.query.filter_by(email="video_owner@example.com").first()
    uploaded_videos = Video.query.filter_by(user_id=owner_user.id).all()

    for video_db_obj in uploaded_videos:
        expected_video_src = f'/videos/stream/{video_db_obj.id}'
        assert f'<video width="320" height="240" controls preload="metadata">' in content
        assert f'<source src="{expected_video_src}" type="video/mp4">' in content
        # Check if the title associated with this video_db_obj is one of the video_titles
        assert video_db_obj.title in video_titles


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
    assert "User A&#39;s Video" in content_a # Check title with HTML encoding

    # Check for video tag for User A's video
    usera_obj_final = User.query.filter_by(username="usera").first()
    video_a_final = Video.query.filter_by(user_id=usera_obj_final.id, title="User A's Video").first()
    assert video_a_final is not None, "User A's video not found in DB at final check"

    expected_video_a_src = f'/videos/stream/{video_a_final.id}'
    assert f'<video width="320" height="240" controls preload="metadata">' in content_a # Updated controls attribute
    assert f'<source src="{expected_video_a_src}" type="video/mp4">' in content_a

    assert "You haven't uploaded any videos yet." not in content_a


# --- Tests for Public Gallery and My Videos Visibility ---

def test_public_gallery_empty(client, db):
    """Test the public gallery when no public videos are available."""
    response = client.get('/gallery')
    assert response.status_code == 200
    content = response.data.decode()
    assert "Public Video Gallery" in content
    assert "No public videos available at the moment." in content

def test_public_gallery_with_public_and_private_videos(client, db, app):
    """Test the public gallery displays only public videos."""
    # User A uploads a public video
    signup_a_resp = client.post('/auth/signup', json={"username": "gallery_usera", "email": "gallery_usera@example.com", "password": "password"})
    assert signup_a_resp.status_code == 201
    jwt_login_a_resp = client.post('/auth/login', json={'identifier': 'gallery_usera', 'password': 'password'})
    jwt_a = jwt_login_a_resp.get_json()['access_token']

    client.post('/videos/upload_video', data={
        'title': "Public Gallery Video", 'video': (io.BytesIO(b"public_gallery_data"), "public.mp4"), 'is_public': 'true'
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_a}"})

    # User B uploads a private video
    signup_b_resp = client.post('/auth/signup', json={"username": "gallery_userb", "email": "gallery_userb@example.com", "password": "password"})
    assert signup_b_resp.status_code == 201
    jwt_login_b_resp = client.post('/auth/login', json={'identifier': 'gallery_userb', 'password': 'password'})
    jwt_b = jwt_login_b_resp.get_json()['access_token']

    client.post('/videos/upload_video', data={
        'title': "Private Gallery Video", 'video': (io.BytesIO(b"private_gallery_data"), "private.mp4"), 'is_public': 'false'
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_b}"})

    # Access public gallery (anonymous)
    response = client.get('/gallery')
    assert response.status_code == 200
    content = response.data.decode()
    assert "Public Video Gallery" in content
    assert "Public Gallery Video" in content
    assert "Private Gallery Video" not in content
    assert "No public videos available at the moment." not in content

    # Verify video stream link is present for the public video
    public_video_obj = Video.query.filter_by(title="Public Gallery Video").first()
    assert public_video_obj is not None
    assert public_video_obj.is_public is True
    expected_public_src = f'/videos/stream/{public_video_obj.id}'
    assert f'<source src="{expected_public_src}" type="video/mp4">' in content


def test_my_videos_shows_visibility_and_toggle_button(client, db, app):
    """Test /my-videos shows visibility status and toggle button for owner."""
    # 1. Create and log in user
    signup_resp = client.post('/auth/signup', json={"username": "visibility_user", "email": "visibility@example.com", "password": "password"})
    assert signup_resp.status_code == 201
    jwt_login_resp = client.post('/auth/login', json={'identifier': 'visibility_user', 'password': 'password'})
    jwt_token = jwt_login_resp.get_json()['access_token']
    form_login_resp = client.post('/auth/login', data={'identifier': 'visibility_user', 'password': 'password'}, follow_redirects=True)
    assert form_login_resp.status_code == 200

    # 2. Upload one public and one private video
    # Public
    upload_public_resp = client.post('/videos/upload_video', data={
        'title': "My Public Test Video", 'video': (io.BytesIO(b"public data"), "public_test.mp4"), 'is_public': 'true'
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_token}"})
    assert upload_public_resp.status_code == 201
    public_video_id = upload_public_resp.get_json()['video_id']

    # Private (default)
    upload_private_resp = client.post('/videos/upload_video', data={
        'title': "My Default Private Video", 'video': (io.BytesIO(b"private data"), "private_test.mp4")
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_token}"})
    assert upload_private_resp.status_code == 201
    private_video_id = upload_private_resp.get_json()['video_id']

    # 3. Access /my-videos
    response = client.get('/my-videos')
    assert response.status_code == 200
    content = response.data.decode()

    # Title strings
    public_title = "My Public Test Video"
    private_title = "My Default Private Video"

    # Find the starting index of each video's block by its title
    idx_public_video = content.find(f"<h3>{public_title}</h3>")
    idx_private_video = content.find(f"<h3>{private_title}</h3>")

    assert idx_public_video != -1, f"'{public_title}' not found in content"
    assert idx_private_video != -1, f"'{private_title}' not found in content"

    # Define a reasonable end for each block (e.g., start of the next item or end of list)
    # This is still a bit fragile if structure changes drastically.
    # For simplicity, we'll check for status and button within a certain range after title.

    # Check Public Video ("My Public Test Video")
    start_search_public = idx_public_video
    # Find where its list item might end, e.g., before the next <li> or end of </ul>
    end_search_public_li = content.find("</li>", start_search_public)
    public_video_block = content[start_search_public : end_search_public_li if end_search_public_li != -1 else len(content)]

    assert "<p><strong>Status:</strong> Public</p>" in public_video_block
    assert f'<form method="POST" action="/videos/{public_video_id}/toggle-visibility"' in public_video_block
    assert "Make Private</button>" in public_video_block
    assert "Make Public</button>" not in public_video_block # Important negative check

    # Check Private Video ("My Default Private Video")
    start_search_private = idx_private_video
    end_search_private_li = content.find("</li>", start_search_private)
    private_video_block = content[start_search_private : end_search_private_li if end_search_private_li != -1 else len(content)]

    assert "<p><strong>Status:</strong> Private</p>" in private_video_block
    assert f'<form method="POST" action="/videos/{private_video_id}/toggle-visibility"' in private_video_block
    assert "Make Public</button>" in private_video_block
    assert "Make Private</button>" not in private_video_block # Important negative check


def test_toggle_visibility_from_my_videos_page(client, db, app):
    """Test toggling visibility via the button on /my-videos page and see update."""
    # 1. Create user, log in (form and JWT)
    signup_resp = client.post('/auth/signup', json={"username": "toggler_user", "email": "toggler@example.com", "password": "password"})
    assert signup_resp.status_code == 201
    jwt_login_resp = client.post('/auth/login', json={'identifier': 'toggler_user', 'password': 'password'})
    jwt_token = jwt_login_resp.get_json()['access_token']
    form_login_resp = client.post('/auth/login', data={'identifier': 'toggler_user', 'password': 'password'}, follow_redirects=True)
    assert form_login_resp.status_code == 200

    # 2. Upload a video (will be private by default)
    upload_resp = client.post('/videos/upload_video', data={
        'title': "Toggle Me Video", 'video': (io.BytesIO(b"toggle me data"), "toggle_me.mp4")
    }, content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_token}"})
    assert upload_resp.status_code == 201
    video_id = upload_resp.get_json()['video_id']

    # 3. Access /my-videos, verify it's private
    response_before_toggle = client.get('/my-videos')
    content_before = response_before_toggle.data.decode()

    video_title_str = "Toggle Me Video"
    idx_video_before = content_before.find(f"<h3>{video_title_str}</h3>")
    assert idx_video_before != -1, f"Title '{video_title_str}' not found in content_before"
    # Ensure we are looking within the correct list item
    end_idx_li_before = content_before.find("</li>", idx_video_before)
    block_before = content_before[idx_video_before : end_idx_li_before if end_idx_li_before != -1 else len(content_before)]

    assert "<p><strong>Status:</strong> Private</p>" in block_before
    assert "Make Public</button>" in block_before

    # 4. Click the "Make Public" button (POST to toggle-visibility)
    toggle_response = client.post(f'/videos/{video_id}/toggle-visibility', follow_redirects=True)
    assert toggle_response.status_code == 200
    assert toggle_response.request.path == '/my-videos' # Should redirect back
    content_after_toggle = toggle_response.data.decode()
    assert b"visibility updated to Public" in toggle_response.data # Flash message

    idx_video_after = content_after_toggle.find(f"<h3>{video_title_str}</h3>")
    assert idx_video_after != -1, f"Title '{video_title_str}' not found in content_after_toggle"
    end_idx_li_after = content_after_toggle.find("</li>", idx_video_after)
    block_after = content_after_toggle[idx_video_after : end_idx_li_after if end_idx_li_after != -1 else len(content_after_toggle)]

    assert "<p><strong>Status:</strong> Public</p>" in block_after
    assert "Make Private</button>" in block_after

    # 5. Toggle it back to Private
    toggle_back_response = client.post(f'/videos/{video_id}/toggle-visibility', follow_redirects=True)
    assert toggle_back_response.status_code == 200
    content_final = toggle_back_response.data.decode()
    assert b"visibility updated to Private" in toggle_back_response.data # Flash message

    idx_video_final = content_final.find(f"<h3>{video_title_str}</h3>")
    assert idx_video_final != -1, f"Title '{video_title_str}' not found in content_final"
    end_idx_li_final = content_final.find("</li>", idx_video_final)
    block_final = content_final[idx_video_final : end_idx_li_final if end_idx_li_final != -1 else len(content_final)]

    assert "<p><strong>Status:</strong> Private</p>" in block_final
    assert "Make Public</button>" in block_final


# --- Tests for Paid Video Frontend Display ---

def test_public_gallery_shows_unlock_button_for_paid_video_anonymous(client, db, app):
    """Test anonymous users see unlock button for a paid video in public gallery."""
    owner = User(username="paid_owner_anon", email="paid_owner_anon@example.com", password="password")
    db.session.add(owner)
    db.session.commit()
    Video.query.delete() # Clear other videos for cleaner test
    paid_video = Video(title="Paid Video For Anon", user_id=owner.id, filename="pv_anon.mp4", file_path="/f/pv_anon.mp4",
                       is_public=True, is_paid_unlock=True, price=Decimal("7.50"))
    db.session.add(paid_video)
    db.session.commit()

    response = client.get('/') # Root is now public gallery
    assert response.status_code == 200
    content = response.data.decode()

    assert "Paid Video For Anon" in content
    assert 'Unlock for $7.50' in content # Check button text and price
    assert '<video' not in content # Video player should be hidden

def test_public_gallery_shows_unlock_button_for_paid_video_logged_in_unlocked(client, db, app, auth_data):
    """Test logged-in (non-owner) user sees unlock button if video not unlocked."""
    owning_client, _, owner_info = auth_data # This is user1 ('testuser')

    # Create another user who will be the owner of the paid video
    video_owner = User(username="video_owner_gallery", email="vog@example.com", password="password")
    db.session.add(video_owner)
    db.session.commit()

    Video.query.delete() # Clear other videos
    paid_video = Video(title="Paid Video For LoggedIn", user_id=video_owner.id, filename="pv_lin.mp4", file_path="/f/pv_lin.mp4",
                       is_public=True, is_paid_unlock=True, price=Decimal("12.00"))
    db.session.add(paid_video)
    db.session.commit()

    # Log in as 'testuser' (who does not own or unlocked the video yet)
    # auth_data already returns a client authenticated via JWT. For session auth on frontend:
    client.get('/auth/logout', follow_redirects=True) # Clear any previous session
    login_resp = client.post('/auth/login', data={'identifier': owner_info['username'], 'password': 'password123'}, follow_redirects=True)
    assert login_resp.status_code == 200

    response = client.get('/')
    assert response.status_code == 200
    content = response.data.decode()

    assert "Paid Video For LoggedIn" in content
    assert 'Unlock for $12.00' in content
    assert video_owner.username in content # Check uploader info is still there
    assert '<video' not in content # Video player should be hidden

def test_public_gallery_shows_video_if_paid_and_unlocked(client, db, app, auth_data):
    """Test logged-in user sees video player if they have unlocked the paid video."""
    client_viewer, _, viewer_info = auth_data # This is 'testuser'

    video_owner = User(username="video_owner_gallery2", email="vog2@example.com", password="password")
    db.session.add(video_owner)
    db.session.commit()

    Video.query.delete()
    paid_video = Video(title="Unlocked Paid Video", user_id=video_owner.id, filename="pv_unlocked.mp4", file_path="/f/pv_unlocked.mp4",
                       is_public=True, is_paid_unlock=True, price=Decimal("3.33"))
    db.session.add(paid_video)
    db.session.commit()

    # Create an unlock record for 'testuser' (viewer)
    unlock = UserVideoUnlock(user_id=viewer_info['id'], video_id=paid_video.id, stripe_payment_intent_id="pi_fake_unlock")
    db.session.add(unlock)
    db.session.commit()

    # Log in as 'testuser'
    client.get('/auth/logout', follow_redirects=True)
    login_resp = client.post('/auth/login', data={'identifier': viewer_info['username'], 'password': 'password123'}, follow_redirects=True)
    assert login_resp.status_code == 200

    response = client.get('/')
    assert response.status_code == 200
    content = response.data.decode()

    assert "Unlocked Paid Video" in content
    assert 'Unlock for' not in content # Unlock button should be hidden
    assert '<video' in content # Video player should be visible
    assert f'src="/videos/stream/{paid_video.id}"' in content

def test_public_gallery_shows_video_if_paid_and_owned(client, db, app, auth_data):
    """Test logged-in user (owner) sees video player for their own paid video."""
    client_owner, access_token, owner_info = auth_data # 'testuser' is the owner

    # 'testuser' uploads a paid video
    # Need JWT for upload, but session for viewing the gallery page as owner
    Video.query.delete()
    paid_video_data = {
        'title': 'My Own Paid Video',
        'video': (io.BytesIO(b"owner_paid_data"), "owner_paid.mp4"),
        'is_public': 'true',
        'is_paid_unlock': 'true',
        'price': '5.50'
    }
    upload_resp = client_owner.post('/videos/upload_video', data=paid_video_data, content_type='multipart/form-data',
                                   headers={"Authorization": f"Bearer {access_token}"})
    assert upload_resp.status_code == 201
    owned_paid_video_id = upload_resp.get_json()['video_id']

    # Log in as owner via form session
    client_owner.get('/auth/logout', follow_redirects=True)
    login_resp = client_owner.post('/auth/login', data={'identifier': owner_info['username'], 'password': 'password123'}, follow_redirects=True)
    assert login_resp.status_code == 200

    response = client_owner.get('/')
    assert response.status_code == 200
    content = response.data.decode()

    assert "My Own Paid Video" in content
    assert 'Unlock for' not in content
    assert '<video' in content
    assert f'src="/videos/stream/{owned_paid_video_id}"' in content

    # Clean up the created file
    video_obj = Video.query.get(owned_paid_video_id)
    if video_obj and os.path.exists(video_obj.file_path):
        os.remove(video_obj.file_path)
        user_upload_folder = os.path.dirname(video_obj.file_path)
        if os.path.exists(user_upload_folder) and not os.listdir(user_upload_folder):
            os.rmdir(user_upload_folder)


def test_profile_page_loads_authenticated(client, auth_data):
    """Test that the /profile page loads for an authenticated user."""
    authed_client, _, user_info = auth_data

    # Perform a form login to establish session for Flask-Login protected route
    login_resp = authed_client.post('/auth/login', data={
        'identifier': user_info['username'],
        'password': 'password123' # Password from auth_data fixture
    }, follow_redirects=True)
    assert login_resp.status_code == 200

    response = authed_client.get('/profile')
    assert response.status_code == 200
    content = response.data.decode()
    assert f"Username:</strong> {user_info['username']}" in content
    assert "Add Bank Account via Plaid</button>" in content
    assert 'id="add-bank-account-button"' in content
    assert 'src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"' in content

def test_profile_page_redirects_unauthenticated(client):
    """Test that /profile redirects to login if user is not authenticated."""
    response = client.get('/profile', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login?next=%2Fprofile' in response.headers['Location']


def test_my_videos_page_shows_set_price(client, db, app, auth_data):
    """Test that 'My Videos' page shows the set price for owned paid videos."""
    client_owner, access_token, owner_info = auth_data

    # Upload a paid video
    video_data = {
        'title': 'My Priced Video',
        'video': (io.BytesIO(b"my_priced_data"), "my_priced.mp4"),
        'is_public': 'true',
        'is_paid_unlock': 'true',
        'price': '19.99'
    }
    upload_resp = client_owner.post('/videos/upload_video', data=video_data, content_type='multipart/form-data',
                                   headers={"Authorization": f"Bearer {access_token}"})
    assert upload_resp.status_code == 201
    video_id = upload_resp.get_json()['video_id']

    # Log in via form session
    client_owner.get('/auth/logout', follow_redirects=True)
    login_resp = client_owner.post('/auth/login', data={'identifier': owner_info['username'], 'password': 'password123'}, follow_redirects=True)
    assert login_resp.status_code == 200

    # Access "My Videos" page
    response = client_owner.get('/my-videos')
    assert response.status_code == 200
    content = response.data.decode()

    assert "My Priced Video" in content
    assert "Set Price:</strong> $19.99" in content # Check for the displayed price

    # Clean up
    video_obj = Video.query.get(video_id)
    if video_obj and os.path.exists(video_obj.file_path):
        os.remove(video_obj.file_path)
        user_upload_folder = os.path.dirname(video_obj.file_path)
        if os.path.exists(user_upload_folder) and not os.listdir(user_upload_folder):
            os.rmdir(user_upload_folder)
