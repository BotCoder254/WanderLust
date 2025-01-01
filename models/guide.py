from bson import ObjectId
from datetime import datetime

class Guide:
    def __init__(self, guide_data):
        self.guide_data = guide_data
        self.id = str(guide_data.get('_id'))
    
    @staticmethod
    def create(db, name, email, phone, languages, experience, specialties, image=None):
        guide = {
            'name': name,
            'email': email,
            'phone': phone,
            'languages': [lang.strip() for lang in languages.split(',')],
            'experience': int(experience),
            'specialties': [spec.strip() for spec in specialties.split(',')],
            'is_available': True,
            'image': image,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        result = db.guides.insert_one(guide)
        guide['_id'] = result.inserted_id
        return Guide(guide)
    
    @staticmethod
    def get_all(db):
        guides = db.guides.find().sort('created_at', -1)
        return [Guide(guide) for guide in guides]
    
    @staticmethod
    def get_by_id(db, guide_id):
        try:
            guide_data = db.guides.find_one({'_id': ObjectId(guide_id)})
            return Guide(guide_data) if guide_data else None
        except:
            return None
    
    @staticmethod
    def get_available(db, start_date, end_date):
        # Find guides who are not assigned to any tour during the date range
        pipeline = [
            {
                '$lookup': {
                    'from': 'schedules',
                    'localField': '_id',
                    'foreignField': 'guide_id',
                    'as': 'schedules'
                }
            },
            {
                '$match': {
                    'schedules': {
                        '$not': {
                            '$elemMatch': {
                                '$or': [
                                    {
                                        'start_date': {'$lte': end_date},
                                        'end_date': {'$gte': start_date}
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        ]
        guides = db.guides.aggregate(pipeline)
        return [Guide(guide) for guide in guides]
    
    def update(self, db, **kwargs):
        updates = {
            '$set': {
                key: value for key, value in kwargs.items()
                if key in [
                    'name', 'email', 'phone', 'languages',
                    'experience', 'specialties', 'is_available',
                    'image'
                ]
            }
        }
        updates['$set']['updated_at'] = datetime.utcnow()
        
        # Process languages and specialties if they're strings
        if 'languages' in updates['$set'] and isinstance(updates['$set']['languages'], str):
            updates['$set']['languages'] = [lang.strip() for lang in updates['$set']['languages'].split(',')]
        if 'specialties' in updates['$set'] and isinstance(updates['$set']['specialties'], str):
            updates['$set']['specialties'] = [spec.strip() for spec in updates['$set']['specialties'].split(',')]
        
        db.guides.update_one({'_id': ObjectId(self.id)}, updates)
    
    def delete(self, db):
        # Delete all schedules for this guide first
        db.schedules.delete_many({'guide_id': ObjectId(self.id)})
        # Then delete the guide
        db.guides.delete_one({'_id': ObjectId(self.id)})
    
    def get_schedule(self, db):
        pipeline = [
            {
                '$match': {
                    'guide_id': ObjectId(self.id)
                }
            },
            {
                '$lookup': {
                    'from': 'tours',
                    'localField': 'tour_id',
                    'foreignField': '_id',
                    'as': 'tour'
                }
            },
            {
                '$unwind': '$tour'
            },
            {
                '$sort': {
                    'start_date': 1
                }
            }
        ]
        return list(db.schedules.aggregate(pipeline))
    
    def assign_to_tour(self, db, tour_id, start_date, end_date):
        # Check if guide is already assigned during this period
        existing = db.schedules.find_one({
            'guide_id': ObjectId(self.id),
            '$or': [
                {
                    'start_date': {'$lte': end_date},
                    'end_date': {'$gte': start_date}
                }
            ]
        })
        
        if existing:
            raise ValueError('Guide is already assigned to a tour during this period')
        
        schedule = {
            'guide_id': ObjectId(self.id),
            'tour_id': ObjectId(tour_id),
            'start_date': start_date,
            'end_date': end_date,
            'created_at': datetime.utcnow()
        }
        
        db.schedules.insert_one(schedule)
        self.update(db, is_available=False)
    
    def remove_from_tour(self, db, tour_id, start_date, end_date):
        db.schedules.delete_one({
            'guide_id': ObjectId(self.id),
            'tour_id': ObjectId(tour_id),
            'start_date': start_date,
            'end_date': end_date
        })
        
        # If no more upcoming tours, mark as available
        upcoming_tours = db.schedules.find_one({
            'guide_id': ObjectId(self.id),
            'end_date': {'$gte': datetime.utcnow()}
        })
        
        if not upcoming_tours:
            self.update(db, is_available=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.guide_data['name'],
            'email': self.guide_data['email'],
            'phone': self.guide_data['phone'],
            'languages': self.guide_data['languages'],
            'experience': self.guide_data['experience'],
            'specialties': self.guide_data['specialties'],
            'is_available': self.guide_data['is_available'],
            'image': self.guide_data.get('image'),
            'created_at': self.guide_data['created_at'],
            'updated_at': self.guide_data['updated_at']
        } 