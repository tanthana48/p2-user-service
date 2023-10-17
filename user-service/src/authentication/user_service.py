from flask import Flask, request, jsonify, Blueprint
from database import User, db
import jwt

user_service = Blueprint("user_service", __name__)

SECRET_KEY = 'your_secret_key'

BLACKLIST = set()


def generate_token(user_id, roles=[]):
    payload = {'user_id': user_id, 'roles': roles}
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

def validate_token(token):
    if token in BLACKLIST:
        return 'Token has been blacklisted'

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return 'Token has expired'
    except jwt.InvalidTokenError:
        return 'Invalid token'

@user_service.route('/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'Token missing'}), 401

    payload = validate_token(token)
    if isinstance(payload, str):
        return jsonify({'error': payload}), 401

    BLACKLIST.add(token)
    return jsonify({'message': 'Logged out successfully'}), 200

@user_service.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if 'username' in data and 'password' in data:
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


@user_service.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if 'username' in data and 'password' in data:
        user = User.query.filter_by(username=data['username']).first()
        if user and user.check_password(data['password']):
            token = generate_token(user.id)
            return jsonify({'token': token}), 200
        return jsonify({'error': 'Invalid credentials'}), 401


@user_service.route('/users', methods=['GET'])
def get_users():
    all_users = User.query.all()
    user_list = [{'id': u.id, 'username': u.username, 'email': u.email} for u in all_users]
    return jsonify({'users': user_list})

@user_service.route('/whoami', methods=['GET'])
def whoami():
    token = request.headers.get('Authorization')
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

