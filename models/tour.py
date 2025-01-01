from datetime import datetime
from bson import ObjectId

class Tour:
    def __init__(self, tour_data):
        self.tour_data = tour_data
        self._id = tour_data.get('_id')
        self.name = tour_data.get('name')
        self.description = tour_data.get('description')
        self.destination = tour_data.get('destination')
        self.price = tour_data.get('price', 0)
        self.duration = tour_data.get('duration', 0)
        self.start_date = tour_data.get('start_date')
        self.end_date = tour_data.get('end_date')
        self.highlights = tour_data.get('highlights', [])
        self.included_services = tour_data.get('included_services', [])
        self.add_ons = tour_data.get('add_ons', [])
        self.media = tour_data.get('media', [])
        self.rating = tour_data.get('rating', 0)
        self.review_count = tour_data.get('review_count', 0)
        self.max_participants = tour_data.get('max_participants', 20)
        self.current_bookings = tour_data.get('current_bookings', 0)
        self.created_at = tour_data.get('created_at', datetime.utcnow())
        self.updated_at = tour_data.get('updated_at', datetime.utcnow())
        self.is_active = tour_data.get('is_active', True)

    @staticmethod
    def create(db, **kwargs):
        tour_data = {
            'name': kwargs.get('name'),
            'description': kwargs.get('description'),
            'destination': kwargs.get('destination'),
            'price': float(kwargs.get('price', 0)),
            'duration': int(kwargs.get('duration', 1)),
            'start_date': kwargs.get('start_date'),
            'end_date': kwargs.get('end_date'),
            'highlights': kwargs.get('highlights', []),
            'included_services': kwargs.get('included_services', []),
            'add_ons': kwargs.get('add_ons', []),
            'media': kwargs.get('media', []),
            'rating': float(kwargs.get('rating', 0)),
            'review_count': int(kwargs.get('review_count', 0)),
            'max_participants': int(kwargs.get('max_participants', 20)),
            'current_bookings': int(kwargs.get('current_bookings', 0)),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'is_active': True
        }
        result = db.tours.insert_one(tour_data)
        tour_data['_id'] = result.inserted_id
        return Tour(tour_data)

    @staticmethod
    def get_by_id(db, tour_id):
        if isinstance(tour_id, str):
            tour_id = ObjectId(tour_id)
        tour_data = db.tours.find_one({'_id': tour_id})
        return Tour(tour_data) if tour_data else None

    @staticmethod
    def get_all(db, active_only=True, destination=None, price_range=None, sort_by=None):
        query = {'is_active': True} if active_only else {}
        
        if destination:
            query['destination'] = destination
        
        if price_range:
            min_price, max_price = price_range
            query['price'] = {'$gte': min_price, '$lte': max_price}
        
        sort_params = []
        if sort_by:
            if sort_by == 'price_asc':
                sort_params.append(('price', 1))
            elif sort_by == 'price_desc':
                sort_params.append(('price', -1))
            elif sort_by == 'duration_asc':
                sort_params.append(('duration', 1))
            elif sort_by == 'duration_desc':
                sort_params.append(('duration', -1))
            elif sort_by == 'date_asc':
                sort_params.append(('start_date', 1))
            elif sort_by == 'date_desc':
                sort_params.append(('start_date', -1))
        
        # Default sort by created_at if no sort specified
        if not sort_params:
            sort_params.append(('created_at', -1))
        
        tours = db.tours.find(query).sort(sort_params)
        return [Tour(tour_data) for tour_data in tours]

    @staticmethod
    def get_destinations(db):
        return sorted(db.tours.distinct('destination'))

    def update(self, db, **kwargs):
        updates = {
            'name': kwargs.get('name', self.name),
            'description': kwargs.get('description', self.description),
            'destination': kwargs.get('destination', self.destination),
            'price': float(kwargs.get('price', self.price)),
            'duration': int(kwargs.get('duration', self.duration)),
            'start_date': kwargs.get('start_date', self.start_date),
            'end_date': kwargs.get('end_date', self.end_date),
            'highlights': kwargs.get('highlights', self.highlights),
            'included_services': kwargs.get('included_services', self.included_services),
            'add_ons': kwargs.get('add_ons', self.add_ons),
            'media': kwargs.get('media', self.media),
            'max_participants': int(kwargs.get('max_participants', self.max_participants)),
            'updated_at': datetime.utcnow()
        }
        
        result = db.tours.update_one(
            {'_id': self._id},
            {'$set': updates}
        )
        
        if result.modified_count > 0:
            self.tour_data.update(updates)
            for key, value in updates.items():
                setattr(self, key, value)
            return True
        return False

    def delete(self, db):
        # Soft delete by setting is_active to False
        result = db.tours.update_one(
            {'_id': self._id},
            {
                '$set': {
                    'is_active': False,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    def to_dict(self):
        return {
            'id': str(self._id),
            'name': self.name,
            'description': self.description,
            'destination': self.destination,
            'price': self.price,
            'duration': self.duration,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'highlights': self.highlights,
            'included_services': self.included_services,
            'add_ons': self.add_ons,
            'media': self.media,
            'rating': self.rating,
            'review_count': self.review_count,
            'max_participants': self.max_participants,
            'current_bookings': self.current_bookings,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active
        } 