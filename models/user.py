from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data.get('_id'))
        self.user_data = user_data
        self._is_admin = user_data.get('is_admin', False)

    def get_id(self):
        return self.id

    @property
    def is_admin(self):
        return bool(self._is_admin)

    @property
    def name(self):
        return self.user_data.get('name', '')

    @property
    def email(self):
        return self.user_data.get('email', '')

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
            'is_admin': is_admin
        }
        result = db.users.insert_one(user)
        user['_id'] = result.inserted_id
        return User(user)
    
    def check_password(self, password):
        return check_password_hash(self.user_data['password'], password) 