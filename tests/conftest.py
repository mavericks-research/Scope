import os
import pytest
from app import create_app, db as _db

# Override the DATABASE_URL for testing
os.environ['DATABASE_URL'] = 'sqlite:///./test_app.db'
# Ensure JWT_SECRET_KEY is set for tests, can be a simple one for testing
os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret-key'
os.environ['SECRET_KEY'] = 'test-secret-key'
# Ensure UPLOAD_FOLDER is set and exists for tests
TEST_UPLOAD_FOLDER = os.path.join(os.getcwd(), 'test_uploads')
os.environ['UPLOAD_FOLDER'] = TEST_UPLOAD_FOLDER


@pytest.fixture(scope='session')
def app():
    """Session-wide test `Flask` application."""
    # Create app with test config
    app = create_app()

    # Ensure the test upload folder exists
    if not os.path.exists(TEST_UPLOAD_FOLDER):
        os.makedirs(TEST_UPLOAD_FOLDER)

    with app.app_context():
        # _db.drop_all() # Ensure a clean database state if it exists from previous failed run
        _db.create_all() # Create tables

    yield app

    # Clean up database and upload folder after test session
    with app.app_context():
        _db.session.remove()
        _db.drop_all()

    if os.path.exists(TEST_UPLOAD_FOLDER):
        # Remove test files and folder
        for root, dirs, files in os.walk(TEST_UPLOAD_FOLDER, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(TEST_UPLOAD_FOLDER)

    if os.path.exists('test_app.db'):
        os.remove('test_app.db')


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    """Session-wide database."""
    with app.app_context():
        yield _db
        # Clean up database after each test function
        _db.session.remove()
        # Dropping and recreating tables for each test ensures isolation
        # For faster tests, one might use transactions and rollbacks,
        # but create_all/drop_all is simpler for now.
        _db.drop_all()
        _db.create_all()


@pytest.fixture
def runner(app, client):
    """A test runner for CLI commands."""
    return app.test_cli_runner()


@pytest.fixture
def auth_data(client, db): # Renamed from auth_client
    """Provides an authenticated client, access token, and user info."""
    from app.models import User # Import here to avoid circular dependency if models import db from app

    # Create a test user
    signup_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    }
    signup_response = client.post('/auth/signup', json=signup_data)
    # It's possible the user already exists if a previous test failed mid-way and db cleanup didn't run
    # or if this fixture is called multiple times without db cleanup in between (though db fixture should handle this).
    # For robustness, we can check for 201 or 409 (if user already exists from a previous fixture run within the same test if not careful)
    # However, with function-scoped db fixture, user should be new each time.
    assert signup_response.status_code == 201, f"Signup failed in auth_data fixture. Status: {signup_response.status_code}, Response: {signup_response.data}"


    # Log in the test user
    login_data = {
        "identifier": "testuser",
        "password": "password123"
    }
    login_response = client.post('/auth/login', json=login_data)
    assert login_response.status_code == 200, f"Login failed in auth_data fixture. Status: {login_response.status_code}, Response: {login_response.data}"
    token_data = login_response.get_json()
    assert token_data is not None, "Login response JSON is None in auth_data fixture"
    access_token = token_data.get('access_token')
    assert access_token is not None, "Access token is None in auth_data fixture"

    # Retrieve user from DB to get the actual ID
    user = User.query.filter_by(username="testuser").first()
    assert user is not None, "User 'testuser' not found in DB after signup in auth_data fixture"

    user_info = {'username': user.username, 'email': user.email, 'id': user.id}

    return client, access_token, user_info
