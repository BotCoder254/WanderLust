from bson import ObjectId
from datetime import datetime

class Booking:
    def __init__(self, booking_data):
        self.booking_data = booking_data
        self.id = str(booking_data.get('_id'))
    
    @staticmethod
    def create(db, user_id, tour_id, start_date, number_of_people, total_price):
        booking = {
            'user_id': ObjectId(user_id),
            'tour_id': ObjectId(tour_id),
            'start_date': start_date,
            'number_of_people': int(number_of_people),
            'total_price': float(total_price),
            'status': 'pending',  # pending, confirmed, completed, cancelled
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        result = db.bookings.insert_one(booking)
        booking['_id'] = result.inserted_id
        return Booking(booking)
    
    @staticmethod
    def get_user_bookings(db, user_id):
        bookings = db.bookings.find({'user_id': ObjectId(user_id)}).sort('created_at', -1)
        return [Booking(booking) for booking in bookings]
    
    @staticmethod
    def get_by_id(db, booking_id):
        try:
            booking_data = db.bookings.find_one({'_id': ObjectId(booking_id)})
            return Booking(booking_data) if booking_data else None
        except:
            return None
    
    def update_status(self, db, status):
        if status not in ['pending', 'confirmed', 'completed', 'cancelled']:
            raise ValueError('Invalid status')
        
        updates = {
            '$set': {
                'status': status,
                'updated_at': datetime.utcnow()
            }
        }
        db.bookings.update_one({'_id': ObjectId(self.id)}, updates)
    
    def cancel(self, db):
        self.update_status(db, 'cancelled')
    
    def confirm(self, db):
        self.update_status(db, 'confirmed')
    
    def complete(self, db):
        self.update_status(db, 'completed')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': str(self.booking_data['user_id']),
            'tour_id': str(self.booking_data['tour_id']),
            'start_date': self.booking_data['start_date'],
            'number_of_people': self.booking_data['number_of_people'],
            'total_price': self.booking_data['total_price'],
            'status': self.booking_data['status'],
            'created_at': self.booking_data['created_at'],
            'updated_at': self.booking_data['updated_at']
        } 