import bcrypt
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import os

JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key')

def hash_password(password):
    """加密密码"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """验证密码"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(user_id, username):
    """生成 JWT token"""
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def decode_token(token):
    """解析 JWT token"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except:
        return None

def token_required(f):
    """装饰器：需要登录才能访问"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': '未登录'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        data = decode_token(token)
        if not data:
            return jsonify({'error': 'Token 无效'}), 401
        
        request.user_id = data['user_id']
        request.username = data['username']
        return f(*args, **kwargs)
    
    return decorated