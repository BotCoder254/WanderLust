from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from app import db, send_booking_reminder, check_expired_bookings

# Initialize Celery
celery = Celery('tasks', broker='redis://redis:6379/0')

# Configure Celery
celery.conf.update(
    timezone='UTC',
    enable_utc=True,
    beat_schedule={
        'send-booking-reminders': {
            'task': 'tasks.send_booking_reminders',
            'schedule': crontab(hour=9, minute=0)  # Run daily at 9 AM UTC
        },
        'check-expired-bookings': {
            'task': 'tasks.check_expired_bookings_task',
            'schedule': crontab(hour='*/1')  # Run every hour
        }
    }
)

@celery.task
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

@celery.task
def check_expired_bookings_task():
    """Check and update expired bookings"""
    try:
        check_expired_bookings()
    except Exception as e:
        print(f"Failed to check expired bookings: {str(e)}")

if __name__ == '__main__':
    celery.start() 