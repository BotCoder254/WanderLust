from bson import ObjectId
from datetime import datetime
import stripe
from flask import current_app

class Payment:
    def __init__(self, payment_data):
        self.payment_data = payment_data
        self.id = str(payment_data.get('_id'))
    
    @staticmethod
    def create_payment_intent(db, booking_id, amount, currency='usd'):
        """Create a payment intent with Stripe and store the initial payment record."""
        try:
            stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
            
            # Create payment intent with Stripe
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                metadata={'booking_id': str(booking_id)}
            )
            
            # Create payment record
            payment = {
                'booking_id': ObjectId(booking_id),
                'amount': amount,
                'currency': currency,
                'payment_method': None,
                'status': 'pending',
                'stripe_payment_intent_id': intent.id,
                'stripe_client_secret': intent.client_secret,
                'transaction_id': None,
                'refund_id': None,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            result = db.payments.insert_one(payment)
            payment['_id'] = result.inserted_id
            
            return Payment(payment)
        except Exception as e:
            raise Exception(f"Error creating payment intent: {str(e)}")
    
    @staticmethod
    def get_by_booking_id(db, booking_id):
        try:
            payment_data = db.payments.find_one({'booking_id': ObjectId(booking_id)})
            return Payment(payment_data) if payment_data else None
        except:
            return None
    
    @staticmethod
    def get_by_payment_intent_id(db, payment_intent_id):
        try:
            payment_data = db.payments.find_one({'stripe_payment_intent_id': payment_intent_id})
            return Payment(payment_data) if payment_data else None
        except:
            return None
    
    def confirm_payment(self, db, payment_method_id):
        """Confirm the payment with Stripe and update the payment record."""
        try:
            stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
            
            # Confirm the payment intent
            intent = stripe.PaymentIntent.confirm(
                self.payment_data['stripe_payment_intent_id'],
                payment_method=payment_method_id
            )
            
            if intent.status == 'succeeded':
                # Update payment record
                updates = {
                    'status': 'completed',
                    'payment_method': payment_method_id,
                    'transaction_id': intent.id,
                    'updated_at': datetime.utcnow()
                }
                
                db.payments.update_one(
                    {'_id': ObjectId(self.id)},
                    {'$set': updates}
                )
                
                # Update booking status
                db.bookings.update_one(
                    {'_id': self.payment_data['booking_id']},
                    {'$set': {'status': 'confirmed'}}
                )
                
                return True
            return False
        except Exception as e:
            raise Exception(f"Error confirming payment: {str(e)}")
    
    def process_refund(self, db, amount=None):
        """Process a refund through Stripe."""
        try:
            stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
            
            # If no amount specified, refund the full amount
            refund_amount = amount if amount else self.payment_data['amount']
            
            # Create refund in Stripe
            refund = stripe.Refund.create(
                payment_intent=self.payment_data['stripe_payment_intent_id'],
                amount=int(refund_amount * 100)  # Convert to cents
            )
            
            # Update payment record
            updates = {
                'status': 'refunded',
                'refund_id': refund.id,
                'updated_at': datetime.utcnow()
            }
            
            db.payments.update_one(
                {'_id': ObjectId(self.id)},
                {'$set': updates}
            )
            
            # Update booking status
            db.bookings.update_one(
                {'_id': self.payment_data['booking_id']},
                {'$set': {'status': 'cancelled'}}
            )
            
            return True
        except Exception as e:
            raise Exception(f"Error processing refund: {str(e)}")
    
    @staticmethod
    def get_revenue_report(db, start_date=None, end_date=None):
        """Generate a revenue report for completed payments."""
        match_stage = {
            'status': 'completed'
        }
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = start_date
            if end_date:
                date_filter['$lte'] = end_date
            match_stage['created_at'] = date_filter
        
        pipeline = [
            {'$match': match_stage},
            {
                '$group': {
                    '_id': {
                        'year': {'$year': '$created_at'},
                        'month': {'$month': '$created_at'}
                    },
                    'total_revenue': {'$sum': '$amount'},
                    'transaction_count': {'$sum': 1}
                }
            },
            {
                '$sort': {
                    '_id.year': -1,
                    '_id.month': -1
                }
            }
        ]
        
        return list(db.payments.aggregate(pipeline))
    
    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': str(self.payment_data['booking_id']),
            'amount': self.payment_data['amount'],
            'currency': self.payment_data['currency'],
            'payment_method': self.payment_data['payment_method'],
            'status': self.payment_data['status'],
            'transaction_id': self.payment_data['transaction_id'],
            'refund_id': self.payment_data['refund_id'],
            'created_at': self.payment_data['created_at'],
            'updated_at': self.payment_data['updated_at']
        } 