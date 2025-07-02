from flask import Blueprint, request, jsonify
from .models import User
from . import db, jwt
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"msg": "Missing username, email, or password"}), 400

    if User.query.filter_by(username=username).first() or \
       User.query.filter_by(email=email).first():
        return jsonify({"msg": "Username or email already exists"}), 409 # 409 Conflict

    new_user = User(username=username, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"msg": "User created successfully"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    identifier = data.get('identifier') # Can be username or email
    password = data.get('password')

    if not identifier or not password:
        return jsonify({"msg": "Missing identifier or password"}), 400

    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

    if user and user.check_password(password):
        # The identity should be simple (e.g., user_id) and a string. Store other info in additional_claims.
        additional_claims = {'username': user.username, 'email': user.email}
        access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "Bad username, email, or password"}), 401

@auth_bp.route('/protected', methods=['GET'])
@jwt_required()
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
