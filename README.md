# NudeScope
NudeScope

## Running the Application

Follow these steps to set up and run the application locally.

### Prerequisites

1.  **Python 3.x**: Ensure you have Python 3 installed.
2.  **Virtual Environment (Recommended)**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

### Environment Configuration

The application requires certain environment variables to be set. A `.env` file is used to manage these variables for local development.

1.  **Create a `.env` file** in the project root by copying the example or creating a new one.
    ```
    DEBUG=True
    SECRET_KEY='your_very_secret_flask_key'  # Change this!
    DATABASE_URL='sqlite:///./nudescopedev.db' # Or your PostgreSQL/MySQL connection string
    JWT_SECRET_KEY='your_very_secret_jwt_key' # Change this!
    UPLOAD_FOLDER='uploads' # Optional: Default is 'uploads' in the project root
    ```
    - `DEBUG`: Set to `True` for development mode, `False` for production.
    - `SECRET_KEY`: A strong, unique secret key for Flask session management and security.
    - `DATABASE_URL`: Connection string for your database. Defaults to SQLite. For PostgreSQL, it might look like `postgresql://user:password@host:port/dbname`.
    - `JWT_SECRET_KEY`: A strong, unique secret key for JWT token generation.
    - `UPLOAD_FOLDER`: The directory where uploaded files will be stored. If not specified, it defaults to an `uploads` folder in the project root, which will be created if it doesn't exist.
    - `FLASK_APP`: (Optional if using `python manage.py`) Specifies the application instance for Flask CLI commands. Typically `FLASK_APP=manage:app` or `FLASK_APP=app:create_app()`.
    - `FLASK_ENV`: (Optional if using `python manage.py`) Sets the environment. Use `development` for development mode (enables debugger, reloader). `production` is the default if not set. The `DEBUG` variable in `.env` also controls debug mode when running via `python manage.py`.

    **Important**: For production, ensure `DEBUG` is `False` (or `FLASK_ENV` is `production`) and use strong, unique values for `SECRET_KEY` and `JWT_SECRET_KEY`.

### Database Setup

This application uses Flask-Migrate to manage database schemas.

1.  **Initialize the database (if setting up for the first time)**:
    If the `migrations` folder does not exist or you are setting up the database from scratch:
    ```bash
    flask db init
    ```
    *This step is usually only needed once.*

2.  **Create migrations**:
    After making changes to your models in `app/models.py`, create a new migration script:
    ```bash
    flask db migrate -m "Your descriptive migration message"
    ```

3.  **Apply migrations**:
    Apply the generated migrations to your database:
    ```bash
    flask db upgrade
    ```
    This command should also be run when you first set up the project to create all tables based on existing migrations.

### Running the Development Server

Once the dependencies are installed, environment variables are configured, and the database is set up, you can start the Flask development server:

```bash
python manage.py
```

The application will typically be available at `http://127.0.0.1:5000/`.

## Testing

This project uses [Pytest](https://docs.pytest.org/) for testing the Flask application.

### Prerequisites

Before running the tests, ensure you have the necessary dependencies installed.

1.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

2.  **Install dependencies:**
    The project's dependencies, including those required for testing, are listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```
    This will install `pytest`, `pytest-flask`, and other necessary packages.

### Environment Configuration

The test environment is largely configured by `tests/conftest.py`. Specifically:
- A separate SQLite database (`test_app.db`) is used for tests and is created and torn down automatically.
- A test-specific JWT secret key (`test-jwt-secret-key`) and Flask secret key (`test-secret-key`) are set.
- A test-specific upload folder (`test_uploads`) is created and cleaned up.

You generally do not need to set up a separate `.env` file for testing unless you have specific overrides not covered by `conftest.py`.

### Running Tests

To run the tests, navigate to the project root directory (the one containing `manage.py` and `tests/`) and execute the following command:

```bash
pytest
```
Alternatively, you can use:
```bash
python -m pytest
```

Pytest will automatically discover and run the tests located in the `tests/` directory. The output will indicate the number of tests passed, failed, or skipped, along with any errors.

### Test Coverage

The tests aim to cover the following main areas:
-   **Authentication**: User signup, login, token generation, and protected route access.
-   **Video Operations**: Video uploading, metadata retrieval, and listing user-specific videos, including authorization checks for these operations.

The tests ensure that API endpoints behave as expected, handle valid and invalid inputs correctly, and that authentication and authorization mechanisms are enforced. Fixtures in `tests/conftest.py` are used to set up the application context, test client, and manage database state for test isolation.
