import pytest
from app.models import User

def test_signup(client, db):
    """Test user signup."""
    response = client.post('/auth/signup', json={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123"
    })
    assert response.status_code == 201
    assert response.get_json()['msg'] == "User created successfully"

    user = User.query.filter_by(email="newuser@example.com").first()
    assert user is not None
    assert user.username == "newuser"

def test_signup_duplicate_username(client, db):
    """Test signup with a username that already exists."""
    client.post('/auth/signup', json={
        "username": "testuser",
        "email": "test1@example.com",
        "password": "password123"
    })
    response = client.post('/auth/signup', json={
        "username": "testuser", # Duplicate username
        "email": "test2@example.com",
        "password": "password456"
    })
    assert response.status_code == 409
    assert "Username or email already exists" in response.get_json()['msg']

def test_signup_duplicate_email(client, db):
    """Test signup with an email that already exists."""
    client.post('/auth/signup', json={
        "username": "anotheruser",
        "email": "test@example.com", # Will be used by auth_client fixture
        "password": "password123"
    })
    # Attempt to sign up again with the same email but different username
    response = client.post('/auth/signup', json={
        "username": "yetanotheruser",
        "email": "test@example.com", # Duplicate email
        "password": "password456"
    })
    # This will conflict with the user created by auth_client or the one above
    # Depending on execution order or if auth_client is used by this test directly.
    # For simplicity, assuming a clean state or that this email isn't the one from auth_client.
    # Let's ensure a unique user is created first for this test to be robust.
    client.post('/auth/signup', json={
        "username": "originaluser",
        "email": "original@example.com",
        "password": "password123"
    })
    response_dup_email = client.post('/auth/signup', json={
        "username": "otheruser",
        "email": "original@example.com", # Duplicate email
        "password": "password456"
    })
    assert response_dup_email.status_code == 409
    assert "Username or email already exists" in response_dup_email.get_json()['msg']


def test_signup_missing_fields(client):
    """Test signup with missing fields."""
    response = client.post('/auth/signup', json={
        "username": "someuser"
        # Missing email and password
    })
    assert response.status_code == 400
    assert "Missing username, email, or password" in response.get_json()['msg']

def test_login(client, db):
    """Test user login."""
    # First, create a user to log in with
    signup_data = {
        "username": "loginuser",
        "email": "login@example.com",
        "password": "password123"
    }
    client.post('/auth/signup', json=signup_data)

    # Attempt to log in
    login_data = {
        "identifier": "loginuser", # Can be username or email
        "password": "password123"
    }
    response = client.post('/auth/login', json=login_data)
    assert response.status_code == 200
    assert "access_token" in response.get_json()

def test_login_with_email(client, db):
    """Test user login using email as identifier."""
    signup_data = {
        "username": "emailuser",
        "email": "emailuser@example.com",
        "password": "password123"
    }
    client.post('/auth/signup', json=signup_data)

    login_data = {
        "identifier": "emailuser@example.com", # Using email
        "password": "password123"
    }
    response = client.post('/auth/login', json=login_data)
    assert response.status_code == 200
    assert "access_token" in response.get_json()

def test_login_wrong_password(client, db):
    """Test login with an incorrect password."""
    signup_data = {
        "username": "wrongpassuser",
        "email": "wrongpass@example.com",
        "password": "correctpassword"
    }
    client.post('/auth/signup', json=signup_data)

    login_data = {
        "identifier": "wrongpassuser",
        "password": "incorrectpassword"
    }
    response = client.post('/auth/login', json=login_data)
    assert response.status_code == 401
    assert "Bad username, email, or password" in response.get_json()['msg']

def test_login_nonexistent_user(client):
    """Test login for a user that does not exist."""
    login_data = {
        "identifier": "nosuchuser",
        "password": "password123"
    }
    response = client.post('/auth/login', json=login_data)
    assert response.status_code == 401
    assert response.get_json()['msg'] == "Bad username, email, or password"

def test_login_missing_fields(client):
    """Test login with missing password."""
    response = client.post('/auth/login', json={
        "identifier": "someuser"
        # Missing password
    })
    assert response.status_code == 400
    assert response.get_json()['msg'] == "Missing identifier or password"

def test_protected_route_requires_auth(client, db): # Added db fixture
    """Test that a protected route requires authentication."""
    response = client.get('/auth/protected')
    assert response.status_code == 401 # Unauthorized
    # Based on @jwt.unauthorized_loader in app/auth.py
    expected_msg = "Request does not contain an access token: Missing Authorization Header"
    assert response.get_json()['msg'] == expected_msg

def test_protected_route_with_auth(auth_data): # Changed from auth_client to auth_data
    """Test accessing a protected route with valid authentication."""
    client, access_token, user_info = auth_data

    # Debug: Check if user exists in DB right before request
    from app.models import User
    user_in_db = User.query.get(user_info['id'])
    print(f"User from DB before request: {user_in_db}, ID: {user_info['id']}")
    assert user_in_db is not None, "User not found in DB immediately before authenticated request"

    response = client.get('/auth/protected', headers={
        "Authorization": f"Bearer {access_token}"
    })
    # if response.status_code != 200: # Removed temporary debug print
    #     print("Response JSON for failed auth:", response.get_json())
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['logged_in_as']['username'] == user_info['username']
    assert json_data['logged_in_as']['email'] == user_info['email']
    assert json_data['logged_in_as']['id'] == user_info['id']


def test_invalid_token(client, db): # Added db fixture
    """Test accessing a protected route with an invalid token."""
    response = client.get('/auth/protected', headers={
        "Authorization": "Bearer invalidtoken123"
    })
    assert response.status_code == 401
    # Based on @jwt.invalid_token_loader in app/auth.py and PyJWT's error for "invalidtoken123"
    assert "Invalid token: Not enough segments" in response.get_json()['msg']

def test_expired_token(client, db, app):
    """Test accessing a protected route with an expired token."""
    # Create user and get a token
    signup_data = {"username": "expuser", "email": "exp@example.com", "password": "password"}
    client.post('/auth/signup', json=signup_data)
    login_resp = client.post('/auth/login', json={"identifier": "expuser", "password": "password"})
    access_token = login_resp.get_json()['access_token']
    pass # Placeholder for now, actual expiration testing needs more setup.


# To run these tests:
# 1. Ensure pytest and pytest-flask are installed.
# 2. Navigate to the project root directory in your terminal.
# 3. Run the command: pytest
#
# If you encounter issues with "Request does not contain an access token",
# it might be due to how Flask-JWT-Extended handles missing tokens vs invalid tokens.
# The custom error handlers in app/auth.py should provide specific messages.
# For test_protected_route_requires_auth, the message is 'Request does not contain an access token: Missing Authorization Header'
# For test_invalid_token, the message is 'Invalid token: Not enough segments' (or other specific PyJWT error)
#
# In test_protected_route_requires_auth, the actual message from my handler is:
# {'msg': 'Request does not contain an access token: Missing Authorization Header', 'status': 401, 'sub_status': 44}
# So, assert "Missing Authorization Header" in response.get_json()['msg'] is more accurate.
#
# In test_invalid_token, for "Bearer invalidtoken123", the error is often "Not enough segments" or "Invalid header padding" from PyJWT.
# My handler wraps this. For instance, "Invalid token: Not enough segments".
# So, assert "Invalid token" in response.get_json()['msg'] is a good general check.
#
# The `auth_client` fixture in conftest.py handles user creation and login to provide an authenticated client.
# The `db` fixture ensures the database is cleaned up and recreated for each test function for isolation.
# The `app` fixture sets up the Flask application in a test configuration.
#
# Corrected assertion for missing token:
# test_protected_route_requires_auth:
# assert "Missing Authorization Header" in response.get_json()['msg']
#
# This was based on the custom error handler:
# @jwt.unauthorized_loader
# def missing_token_callback(error_string): # error_string is "Missing Authorization Header" by default
#     return jsonify({..., 'msg': f'Request does not contain an access token: {error_string}'}), 401
#
# So the check `assert "Missing token" in response.get_json()['msg']` might need adjustment
# to `assert "Missing Authorization Header" in response.get_json()['msg']` or similar.
# The default error_string for unauthorized_loader is "Missing Authorization Header".
# My code returns "Request does not contain an access token: Missing Authorization Header"
# So, the test should be:
# assert "Request does not contain an access token" in response.get_json()['msg']
# And also:
# assert "Missing Authorization Header" in response.get_json()['msg']
#
# Let's make it more specific for the test.
# The original `test_protected_route_requires_auth` had `assert "Missing token" in response.get_json()['msg']`.
# This should be `assert "Request does not contain an access token" in response.get_json()['msg']`
#
# For `test_invalid_token`, the message from the `invalid_token_loader` is `f'Invalid token: {error_string}'`.
# So `assert "Invalid token" in response.get_json().get('msg', '')` is correct.
#
# Re-checking `test_signup_duplicate_email`:
# The `auth_client` fixture is function-scoped, so it doesn't run for `test_signup_duplicate_email` unless specified.
# However, `db` fixture cleans up tables. The test should be self-contained.
# The original `test_signup_duplicate_email` was a bit convoluted. Simpler:
# 1. Create user1 (e.g., "userA", "emailA@example.com")
# 2. Attempt to create user2 with "emailA@example.com" -> Should fail.
#
# My signup logic:
# if User.query.filter_by(username=username).first() or \
#    User.query.filter_by(email=email).first():
#     return jsonify({"msg": "Username or email already exists"}), 409
# This is correct.
#
# The `db` fixture in `conftest.py` now does `_db.drop_all()` and `_db.create_all()` after each test,
# which means each test function starts with a clean database. This is good for isolation.
# The `auth_client` also creates a 'testuser'/'test@example.com'. If a test doesn't use `auth_client`
# but uses `client`, that user won't exist unless explicitly created by the test.
#
# For `test_signup_duplicate_email`, it's better to avoid relying on `auth_client`'s user.
# The current version of `test_signup_duplicate_email` creates "originaluser" / "original@example.com"
# and then tries to create "otheruser" / "original@example.com", which is a valid test for duplicate email.
#
# For `test_protected_route_requires_auth`, the assertion:
# `assert "Missing token" in response.get_json()['msg']`
# My error handler for missing token is: `f'Request does not contain an access token: {error_string}'`
# where `error_string` is often "Missing Authorization Header".
# So the assertion should be: `assert "Request does not contain an access token" in response.get_json()['msg']`
#
# I will update this in the file.
# The `test_invalid_token` assertion `assert "Invalid token" in response.get_json().get('msg', '')` is fine.
#
# Final check of conftest.py:
# The app fixture creates tables once per session.
# The db fixture yields the db and then cleans up (drops all, creates all) *after each function*.
# This means each test function gets a fresh set of tables.
# The auth_client fixture depends on `client` and `db`. It performs a signup and login.
# Since `db` cleans up after each test, the user created by `auth_client` will be gone before the next test
# that uses `auth_client` runs, and `auth_client` will recreate it. This is correct.
#
# One minor improvement: `test_signup_duplicate_username` should also use the `db` fixture to ensure table setup.
# All tests that interact with the DB should use the `db` fixture.
# `client` fixture implies `app` fixture, which sets up the app context and initial `db.create_all()`.
# The `db` fixture provides a fresh db for each test. So, `(client, db)` is a good pattern.
#
# `test_protected_route_requires_auth(client)`: `client` ensures app context. `db` is not strictly needed if not creating users.
# But since it's about auth, and auth might touch user lookup, having `db` is safer.
# Let's add `db` to its parameters.
#
# `test_invalid_token(client)`: Same, add `db`.
#
# `test_login_nonexistent_user(client)`: Add `db`.
#
# `test_signup_missing_fields(client)`: No db interaction, so `db` not needed.
# `test_login_missing_fields(client)`: No db interaction, so `db` not needed.
#
# The `user_lookup_callback` in `app/auth.py` does `User.query.get(user_id)`.
# So, any test that involves a JWT being validated (like `auth_client.get('/auth/protected')`
# or `client.get('/auth/protected', headers=...)`) will need the database to be active
# and potentially contain the user. The `db` fixture ensures this.
# The `auth_client` fixture ensures the user exists for its own requests.
# For `test_invalid_token`, the token is invalid before it gets to user lookup, but `db` is still good practice.
# For `test_protected_route_requires_auth`, no token is provided, so user lookup isn't reached. `db` not strictly needed here.
#
# Let's adjust the `test_protected_route_requires_auth` to use `auth_client` but then clear its auth header to test the unauthed case.
# Or, just use `client` which is unauthenticated. The current version is fine.
#
# The `test_protected_route_requires_auth` assertion should be:
# `assert "Request does not contain an access token" in response.get_json()['msg']`
# And it should also contain "Missing Authorization Header"
# `assert "Missing Authorization Header" in response.get_json()['msg']`
#
# Let's verify the exact message from the `unauthorized_loader`:
# `f'Request does not contain an access token: {error_string}'`
# Flask-JWT-Extended by default passes "Missing Authorization Header" as `error_string`.
# So the message is "Request does not contain an access token: Missing Authorization Header".
#
# The test for `test_protected_route_requires_auth` should be:
# `assert response.get_json()['msg'] == "Request does not contain an access token: Missing Authorization Header"`
#
# For `test_invalid_token`, using "Bearer invalidtoken123":
# PyJWT will raise an error like `DecodeError('Not enough segments')`.
# My `invalid_token_loader` will return `msg: f'Invalid token: {error_string}'`.
# So, `msg` will be "Invalid token: Not enough segments".
# `assert "Invalid token: Not enough segments" in response.get_json()['msg']` is more precise.
#
# I will update these assertions in the generated file.

def test_root_serves_gallery_and_protected_route_redirects(client, db):
    """
    Test that for an unauthenticated user:
    1. Accessing the root path (/) serves the public gallery (200).
    2. Accessing a protected path (e.g., /upload) redirects to login.
    3. The login page, when redirected to, loads successfully and contains expected content.
    """
    # 1. Test root path (/) serves public gallery
    response_root = client.get('/')
    assert response_root.status_code == 200
    root_content = response_root.data.decode()
    assert "Public Video Gallery" in root_content # Check for gallery title or specific content
    assert "Login" in root_content # Nav link for non-auth user
    assert "Sign Up" in root_content # Nav link for non-auth user

    # 2. Test protected route (/upload) redirects to login
    response_upload_unauthed = client.get('/upload', follow_redirects=False)
    assert response_upload_unauthed.status_code == 302  # Check for redirect

    # 3. Check the redirect location from protected route
    redirect_location = response_upload_unauthed.headers['Location']
    # For /upload, next should be /upload. url_for('frontend.upload_page') is '/upload'
    # werkzeug.urls.url_quote will make /upload become %2Fupload
    assert '/auth/login?next=%2Fupload' in redirect_location

    # 4. Follow the redirect to the login page
    response_login_page = client.get(redirect_location)
    assert response_login_page.status_code == 200  # Login page should load successfully

    # 5. Check for expected content on the login page
    login_page_content = response_login_page.data.decode()
    assert "Login" in login_page_content # From <title> or <h1>
    assert 'name="identifier"' in login_page_content # Check for identifier input field
    assert 'name="password"' in login_page_content  # Check for password input field
    assert 'type="submit"' in login_page_content # Check for submit button
    assert 'Or view <a href="/">Public Gallery</a>' in login_page_content # Check link back to gallery


def test_login_page_redirects_if_already_authenticated(client, db, auth_data):
    """Test that /auth/login redirects to home if user is already authenticated."""
    # auth_data provides a client that has just had a user ('testuser') signed up
    # and a JWT token retrieved. However, it does not establish a Flask-Login session.
    # We need to perform a form login first to establish the session.

    authed_client, _, user_info = auth_data

    # Perform a form login to establish session
    login_resp = authed_client.post('/auth/login', data={
        'identifier': user_info['username'],
        'password': 'password123' # Password from auth_data fixture
    }, follow_redirects=True)
    assert login_resp.status_code == 200 # Should be on /upload page

    # Now, with an active session, try to access /auth/login GET
    response_login_get = authed_client.get('/auth/login', follow_redirects=False)
    assert response_login_get.status_code == 302 # Should redirect
    # Should redirect to 'frontend.home' which is '/'
    assert response_login_get.headers['Location'] == '/'

    # Follow redirect to ensure it lands on the gallery page
    home_response = authed_client.get(response_login_get.headers['Location'])
    assert home_response.status_code == 200
    assert "Public Video Gallery" in home_response.data.decode()


# --- Tests for Web (Form-based) Signup ---

def test_get_signup_page(client, db):
    """Test that the signup page loads correctly."""
    response = client.get('/auth/signup')
    assert response.status_code == 200
    content = response.data.decode()
    assert "Sign Up" in content
    assert '<form method="POST" action="/auth/signup">' in content
    assert 'name="username"' in content
    assert 'name="email"' in content
    assert 'name="password"' in content

def test_signup_form_success(client, db):
    """Test successful user signup via web form."""
    response = client.post('/auth/signup', data={
        "username": "webformuser",
        "email": "webform@example.com",
        "password": "password123"
    }, follow_redirects=True) # Follow redirect to see flashed message on login page

    assert response.status_code == 200 # Should redirect to login page which is 200
    content = response.data.decode()
    assert "Account created successfully! Please log in." in content # Check for success flash message
    assert "Login" in content # Should be on the login page

    user = User.query.filter_by(email="webform@example.com").first()
    assert user is not None
    assert user.username == "webformuser"

def test_signup_form_duplicate_username(client, db):
    """Test signup via web form with a username that already exists."""
    # Create an initial user (can be via API or form, API is simpler for setup)
    client.post('/auth/signup', json={
        "username": "existingwebuser",
        "email": "existingweb@example.com",
        "password": "password123"
    })

    response = client.post('/auth/signup', data={
        "username": "existingwebuser", # Duplicate username
        "email": "anotherweb@example.com",
        "password": "password456"
    }, follow_redirects=True)

    assert response.status_code == 200 # Should redirect back to signup page which is 200
    content = response.data.decode()
    assert "Username or email already exists" in content # Check for error flash message
    assert "Sign Up" in content # Should be back on the signup page

def test_signup_form_duplicate_email(client, db):
    """Test signup via web form with an email that already exists."""
    client.post('/auth/signup', json={
        "username": "anotherwebuser",
        "email": "existingemail@example.com",
        "password": "password123"
    })

    response = client.post('/auth/signup', data={
        "username": "yetanotherwebuser",
        "email": "existingemail@example.com", # Duplicate email
        "password": "password456"
    }, follow_redirects=True)

    assert response.status_code == 200
    content = response.data.decode()
    assert "Username or email already exists" in content
    assert "Sign Up" in content

def test_signup_form_missing_fields(client, db):
    """Test signup via web form with missing fields."""
    response = client.post('/auth/signup', data={
        "username": "incompleteuser"
        # Missing email and password
    }, follow_redirects=True)

    assert response.status_code == 200
    content = response.data.decode()
    assert "Missing username, email, or password" in content
    assert "Sign Up" in content
