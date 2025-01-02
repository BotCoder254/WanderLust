from datetime import datetime, timedelta
from app import db, send_booking_reminder

def send_booking_reminders():
    """Send reminders for upcoming tours"""
    # Get bookings that start in 7 days
    reminder_date = datetime.utcnow() + timedelta(days=7)
    start_of_day = reminder_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = reminder_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Find confirmed bookings starting on the reminder date
    upcoming_bookings = db.bookings.find({
        'status': 'confirmed',
        'start_date': {
            '$gte': start_of_day,
            '$lte': end_of_day
        }
    })
    
    # Send reminders for each booking
    for booking in upcoming_bookings:
        try:
            send_booking_reminder(booking)
        except Exception as e:
            print(f"Failed to send reminder for booking {booking['_id']}: {str(e)}")

if __name__ == '__main__':
    send_booking_reminders() 