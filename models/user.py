from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app
import datetime

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data.get('_id'))
        self.user_data = user_data
        self._is_admin = user_data.get('is_admin', False)
        self._is_verified = user_data.get('is_verified', False)
        self._email_preferences = user_data.get('email_preferences', {
            'new_tours': True,
            'payment_receipts': True,
            'booking_reminders': True,
            'promotional': True
        })

    def get_id(self):
        return self.id

    @property
    def is_admin(self):
        return bool(self._is_admin)

    @property
    def is_verified(self):
        return bool(self._is_verified)

    @property
    def name(self):
        return self.user_data.get('name', '')

    @property
    def email(self):
        return self.user_data.get('email', '')

    @property
    def email_preferences(self):
        return self._email_preferences

    @classmethod
    def get_by_id(cls, db, user_id):
        try:
            user_data = db.users.find_one({'_id': ObjectId(user_id)})
            return cls(user_data) if user_data else None
        except:
            return None

    @classmethod
    def get_by_email(cls, db, email):
        user_data = db.users.find_one({'email': email})
        return cls(user_data) if user_data else None

    @staticmethod
    def create(db, name, email, password, is_admin=False):
        user = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password),
            'is_admin': is_admin,
            'is_verified': False,
            'created_at': datetime.datetime.utcnow(),
            'email_preferences': {
                'new_tours': True,
                'payment_receipts': True,
                'booking_reminders': True,
                'promotional': True
            }
        }
        result = db.users.insert_one(user)
        user['_id'] = result.inserted_id
        return User(user)
    
    def check_password(self, password):
        return check_password_hash(self.user_data['password'], password)

    def verify_email(self, db):
        db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$set': {'is_verified': True}}
        )
        self._is_verified = True

    def set_password(self, db, password):
        db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$set': {'password': generate_password_hash(password)}}
        )

    @staticmethod
    def generate_token(user_id, salt):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps(user_id, salt=salt)

    @staticmethod
    def verify_token(db, token, salt, expiration=3600):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            user_id = serializer.loads(token, salt=salt, max_age=expiration)
            return User.get_by_id(db, user_id)
        except (SignatureExpired, BadSignature):
            return None

    def generate_verification_token(self):
        return self.generate_token(self.id, 'email-verification-salt')

    def generate_reset_token(self):
        return self.generate_token(self.id, 'password-reset-salt')

    @staticmethod
    def verify_email_token(db, token):
        return User.verify_token(db, token, 'email-verification-salt')

    @staticmethod
    def verify_reset_token(db, token):
        return User.verify_token(db, token, 'password-reset-salt')

    def update_email_preferences(self, db, preferences):
        db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$set': {'email_preferences': preferences}}
        )
        self._email_preferences = preferences
 