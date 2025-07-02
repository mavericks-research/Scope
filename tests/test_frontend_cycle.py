import pytest
from app.models import User, Video
import io

def test_my_videos_logout_login_cycle(client, db): # Simplified, removed app fixture for now
    # 1. Signup User A
    signup_resp = client.post('/auth/signup', json={"username": "cycleuser", "email": "cycle@example.com", "password": "password"})
    assert signup_resp.status_code == 201, f"Signup failed: {signup_resp.data.decode()}"

    cycle_user = User.query.filter_by(username="cycleuser").first()
    assert cycle_user is not None, "User 'cycleuser' not found after signup."

    # 2. Login User A (form)
    login_resp1 = client.post('/auth/login', data={'identifier': 'cycleuser', 'password': 'password'}, follow_redirects=True)
    assert login_resp1.status_code == 200, f"First form login failed: {login_resp1.data.decode()}"
    assert login_resp1.request.path == '/', f"Not redirected to index after first login. Path: {login_resp1.request.path}"
    assert b"Logged in successfully!" in login_resp1.data, "Success flash for first login not found."

    # 3. Get JWT for User A and upload video
    jwt_resp = client.post('/auth/login', json={'identifier': 'cycleuser', 'password': 'password'})
    assert jwt_resp.status_code == 200, f"JWT login failed: {jwt_resp.data.decode()}"
    jwt_token = jwt_resp.get_json()['access_token']

    upload_resp = client.post('/videos/upload_video', data={'title': "Cycle Video", 'description': 'Test cycle video', 'video': (io.BytesIO(b"video_data_bytes"), "cycle_video.mp4")},
                content_type='multipart/form-data', headers={"Authorization": f"Bearer {jwt_token}"})
    assert upload_resp.status_code == 201, f"Video upload failed: {upload_resp.data.decode()}"

    # 4. Access /my-videos as User A - should see video
    my_videos_resp1 = client.get('/my-videos')
    assert my_videos_resp1.status_code == 200, f"/my-videos (1st time) failed: {my_videos_resp1.status_code}"
    assert b"Cycle Video" in my_videos_resp1.data, "Video not found in /my-videos (1st time)."

    # 5. Logout User A
    logout_resp = client.get('/auth/logout', follow_redirects=True)
    assert logout_resp.status_code == 200, f"Logout failed: {logout_resp.status_code}"
    assert b"You have been logged out." in logout_resp.data, "Logout flash message not found."
    assert logout_resp.request.path == '/auth/login', f"Not redirected to login after logout. Path: {logout_resp.request.path}"


    # 6. Login User A again (form)
    login_resp2 = client.post('/auth/login', data={'identifier': 'cycleuser', 'password': 'password'}, follow_redirects=True)
    assert login_resp2.status_code == 200, f"Second form login failed: {login_resp2.data.decode()}"
    assert login_resp2.request.path == '/', f"Not redirected to index after second login. Path: {login_resp2.request.path}"
    assert b"Logged in successfully!" in login_resp2.data, "Success flash for second login not found."

    # 7. Access /my-videos as User A again - SHOULD see video
    my_videos_resp2 = client.get('/my-videos')
    assert my_videos_resp2.status_code == 200, f"/my-videos (2nd time) failed: {my_videos_resp2.status_code}"
    assert b"Cycle Video" in my_videos_resp2.data, "Video not found in /my-videos (2nd time) after logout and re-login."
