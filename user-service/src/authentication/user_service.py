from flask import Flask, request, jsonify, Blueprint
from database import User, db
import jwt
import datetime
import random

user_service = Blueprint("user_service", __name__)

SECRET_KEY = 'your_secret_key'

BLACKLIST = {}

def cleanup_blacklist():
    current_time = datetime.datetime.utcnow()
    tokens_to_remove = [token for token, expiration in BLACKLIST.items() if expiration <= current_time]

    for token in tokens_to_remove:
        BLACKLIST.pop(token)
        print(f"Removed token: {token}")

def validate_token(token):
    print(f"Validating token: {token}") 
    print(f"Current BLACKLIST: {BLACKLIST}")  # Log the current blacklist

    # Call cleanup with a 1% chance
    if random.random() < 0.01:
        cleanup_blacklist()

    if token in BLACKLIST and datetime.datetime.utcnow() <= BLACKLIST[token]:
        return 'Token has been blacklisted'

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return 'Token has expired'
    except jwt.InvalidTokenError:
        return 'Invalid token'


def generate_token(user_id, roles=[]):
    payload = {
        'user_id': user_id, 
        'roles': roles, 
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # expires in 1 hour
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token


@user_service.route('/api/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization')
    if not token:
        print("Token is missing from the request headers.")
        return jsonify({'error': 'Token missing'}), 401

    payload = validate_token(token)
    if isinstance(payload, str):
        print(f"Token validation failed with error: {payload}")
        return jsonify({'error': payload}), 401

    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    BLACKLIST[token] = expiration_time
    
    return jsonify({'message': 'Logged out successfully'}), 200




@user_service.route('/api/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if 'username' in data and 'password' in data:
        
        # Check if the username already exists
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({'error': 'Username is already taken'}), 400
        
        # If the username doesn't exist, proceed with the registration
        new_user = User(
            username=data['username'], 
            password=data['password'], 
            email=data.get('email'),
            role=data.get('role', 'user')  # Assuming 'user' as a default role
        )
        db.session.add(new_user)
        db.session.commit()
        token = generate_token(new_user.id)
        return jsonify({'token': token}), 201

    else:
        return jsonify({'error': 'Invalid user data'}), 400



@user_service.route('/api/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if 'username' in data and 'password' in data:
        user = User.query.filter_by(username=data['username']).first()
        if user and user.check_password(data['password']):
            token = generate_token(user.id)
            return jsonify({'token': token}), 200
        return jsonify({'error': 'Invalid credentials'}), 401


@user_service.route('/api/users', methods=['GET'])
def get_users():
    all_users = User.query.all()
    user_list = [{'id': u.id, 'username': u.username, 'email': u.email, 'role': u.role} for u in all_users]
    return jsonify({'users': user_list})

@user_service.route('/api/whoami', methods=['GET'])
def whoami():
    tbearer, token = request.headers.get('Authorization').split()
    print("Token being sent:", token);
    if not token:
        return jsonify({'error': 'Token missing'}), 401

    payload = validate_token(token)
    if isinstance(payload, str):  # An error message was returned from validate_token
        return jsonify({'error': payload}), 401

    user = User.query.get(payload['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role
    })

