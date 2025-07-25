import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_login import LoginManager # Added
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
login_manager = LoginManager() # Added

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_secret_key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///./test.db') # Default to SQLite for easy setup if DATABASE_URL is not set
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'a_default_jwt_secret_key')
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads') # For local file storage
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max upload size (for now)

    # Ensure upload folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    login_manager.init_app(app) # Added
    login_manager.login_view = 'auth.login' # Or wherever your login route is

    # User loader function for Flask-Login
    from .models import User # Ensure User model is imported
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints (we'll create these later)
    # from .auth import auth_bp
    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .videos import videos_bp
    app.register_blueprint(videos_bp, url_prefix='/videos')

    from .routes import frontend_bp
    app.register_blueprint(frontend_bp, url_prefix='/')

    return app
