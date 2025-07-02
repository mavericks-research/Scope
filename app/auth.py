from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from .models import User
from . import db, jwt
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from flask_login import login_user, logout_user, current_user # Added for Flask-Login

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['GET', 'POST']) # Added GET method
def signup():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            is_form_submission = False
        else: # Form submission
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            is_form_submission = True

        if not username or not email or not password:
            if is_form_submission:
                flash("Missing username, email, or password", 'danger')
                return redirect(url_for('auth.signup'))
            return jsonify({"msg": "Missing username, email, or password"}), 400

        if User.query.filter_by(username=username).first() or \
           User.query.filter_by(email=email).first():
            if is_form_submission:
                flash("Username or email already exists", 'danger')
                return redirect(url_for('auth.signup'))
            return jsonify({"msg": "Username or email already exists"}), 409 # 409 Conflict

        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        if is_form_submission:
            flash("Account created successfully! Please log in.", 'success')
            return redirect(url_for('auth.login'))
        return jsonify({"msg": "User created successfully"}), 201

    # For GET request, render the signup page
    return render_template('signup.html', title='Sign Up')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('frontend.index')) # Redirect if already logged in

    if request.method == 'POST':
        # This part handles the existing JWT login for API clients
        # It might also be used if the login form submits JSON via AJAX
        if request.is_json:
            data = request.get_json()
            identifier = data.get('identifier')
            password = data.get('password')

            if not identifier or not password:
                return jsonify({"msg": "Missing identifier or password"}), 400

            user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

            if user and user.check_password(password):
                # For JWT API login
                additional_claims = {'username': user.username, 'email': user.email}
                access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
                # For Flask-Login session (if submitting via form post that also wants a session)
                # login_user(user) # Consider if session login should happen here too
                return jsonify(access_token=access_token), 200
            else:
                return jsonify({"msg": "Bad username, email, or password"}), 401
        else: # Handles traditional form submission for Flask-Login
            identifier = request.form.get('identifier')
            password = request.form.get('password')
            remember = True if request.form.get('remember') else False

            if not identifier or not password:
                flash('Missing identifier or password', 'danger')
                return redirect(url_for('auth.login'))

            user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

            if user and user.check_password(password):
                login_user(user, remember=remember)
                next_page = request.args.get('next')
                flash('Logged in successfully!', 'success')

                # Generate JWT for client-side JavaScript
                additional_claims = {'username': user.username, 'email': user.email}
                access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)

                # Redirect to the next page (or frontend.index) and pass the token as a query parameter
                # Note: Passing tokens in URL is not ideal for security. Consider alternatives for production.
                target_url = next_page or url_for('frontend.index')
                if '?' in target_url:
                    return redirect(f"{target_url}&access_token={access_token}")
                else:
                    return redirect(f"{target_url}?access_token={access_token}")
            else:
                flash('Login Unsuccessful. Please check identifier and password', 'danger')
                return redirect(url_for('auth.login'))

    # For GET request, render the login page
    return render_template('login.html', title='Login')

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/protected', methods=['GET'])
@jwt_required() # This protects with JWT
def protected():
    user_id_str = get_jwt_identity() # This will be str(user.id)
    user = User.query.get(int(user_id_str)) # Convert back to int for query
    if not user:
        # This should ideally not happen if user_lookup_loader is working and token is valid
        return jsonify({"msg": "User not found for valid token"}), 404

    # Return the same structure as before for compatibility with current tests
    return jsonify(logged_in_as={'id': user.id, 'username': user.username, 'email': user.email}), 200

# Callback for loading a user from an access token
# This is used by Flask-JWT-Extended to check if a user exists in the database
@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    user_id_str = jwt_data["sub"] # "sub" is now str(user.id)
    if not user_id_str: # Basic check
        return None
    try:
        user_id = int(user_id_str)
    except ValueError: # If subject is not a valid integer string
        return None
    return User.query.get(user_id)

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({
        'status': 401,
        'sub_status': 42, # Custom sub-status code for expired token
        'msg': 'The token has expired'
    }), 401

@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    return jsonify({
        'status': 401,
        'sub_status': 43, # Custom sub-status code for invalid token
        'msg': f'Invalid token: {error_string}'
    }), 401

@jwt.unauthorized_loader
def missing_token_callback(error_string):
    return jsonify({
        'status': 401,
        'sub_status': 44, # Custom sub-status code for missing token
        'msg': f'Request does not contain an access token: {error_string}'
    }), 401
