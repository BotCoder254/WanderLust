from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
from bson import ObjectId
from werkzeug.security import generate_password_hash
import stripe
from flask_mail import Mail, Message

from config import Config
from models.user import User
from models.tour import Tour
from models.booking import Booking
from models.guide import Guide
from models.payment import Payment

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Initialize MongoDB
client = MongoClient(app.config['MONGODB_URI'])
db = client[app.config['DATABASE_NAME']]

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Flask-Mail
mail = Mail(app)

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(db, user_id)

# Context processor to add current datetime to all templates
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def send_email(to, subject, template, **kwargs):
    msg = Message(subject,
                 sender=app.config['MAIL_DEFAULT_SENDER'],
                 recipients=[to])
    msg.html = render_template(template, **kwargs)
    mail.send(msg)

def send_new_tour_notification(tour):
    # Get all verified users who have opted in for new tour notifications
    users = db.users.find({
        'is_verified': True,
        'email_preferences.new_tours': True
    })
    
    for user in users:
        try:
            send_email(
                user['email'],
                'New Tour Available!',
                'emails/new_tour_notification.html',
                user=User(user),
                tour=tour
            )
        except Exception as e:
            print(f"Failed to send email to {user['email']}: {str(e)}")

def send_payment_receipt(payment, booking):
    try:
        # Get user and tour details
        user = User.get_by_id(db, str(booking['user_id']))
        
        # Check if user wants payment receipts
        if not user.email_preferences.get('payment_receipts', True):
            return
            
        tour = Tour.get_by_id(db, str(booking['tour_id']))
        
        booking_data = {
            'user': user,
            'tour': tour,
            'start_date': booking['start_date'],
            'number_of_people': booking['number_of_people']
        }
        
        send_email(
            user.email,
            'Payment Receipt - Your Travel Booking',
            'emails/payment_receipt.html',
            booking=booking_data,
            payment=payment
        )
    except Exception as e:
        print(f"Failed to send payment receipt: {str(e)}")

def send_booking_reminder(booking):
    try:
        user = User.get_by_id(db, str(booking['user_id']))
        
        # Check if user wants booking reminders
        if not user.email_preferences.get('booking_reminders', True):
            return
            
        tour = Tour.get_by_id(db, str(booking['tour_id']))
        
        send_email(
            user.email,
            'Upcoming Tour Reminder',
            'emails/booking_reminder.html',
            user=user,
            tour=tour,
            booking=booking
        )
    except Exception as e:
        print(f"Failed to send booking reminder: {str(e)}")

# Routes
@app.route('/')
def index():
    tours = Tour.get_all(db)
    return render_template('index.html', tours=tours)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Email and password are required')
            return redirect(url_for('login'))
        
        user = User.get_by_email(db, email)
        
        if not user:
            flash('No account found with this email')
            return redirect(url_for('login'))
        
        if not user.check_password(password):
            flash('Invalid password')
            return redirect(url_for('login'))
        
        if not user.is_verified:
            flash('Please verify your email before logging in.')
            return redirect(url_for('login'))
        
        login_user(user)
        flash('Login successful!')
        
        if user.is_admin:
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validate required fields
        if not all([name, email, password, confirm_password]):
            flash('All fields are required')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))
        
        if User.get_by_email(db, email):
            flash('Email already registered')
            return redirect(url_for('register'))
        
        try:
            user = User.create(db, name, email, password)
            if user:
                # Generate verification token and send email
                token = user.generate_verification_token()
                verify_url = url_for('verify_email', token=token, _external=True)
                send_email(user.email,
                         'Verify Your Email',
                         'emails/verify_email.html',
                         user=user,
                         verify_url=verify_url)
                
                flash('Registration successful! Please check your email to verify your account.')
                return redirect(url_for('login'))
            else:
                flash('Registration failed. Please try again.')
        except Exception as e:
            flash(f'Error during registration: {str(e)}')
        
        return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/verify-email/<token>')
def verify_email(token):
    user = User.verify_email_token(db, token)
    if user:
        user.verify_email(db)
        flash('Your email has been verified! You can now log in.')
    else:
        flash('The verification link is invalid or has expired.')
    return redirect(url_for('login'))

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.get_by_email(db, email)
        
        if user:
            token = user.generate_reset_token()
            reset_url = url_for('reset_password', token=token, _external=True)
            send_email(user.email,
                     'Reset Your Password',
                     'emails/reset_password.html',
                     user=user,
                     reset_url=reset_url)
            
            flash('Check your email for instructions to reset your password.')
            return redirect(url_for('login'))
        
        flash('No account found with that email address.')
        return redirect(url_for('reset_password_request'))
    
    return render_template('reset_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user = User.verify_reset_token(db, token)
    if not user:
        flash('The password reset link is invalid or has expired.')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not password or not confirm_password:
            flash('Both password fields are required.')
            return redirect(url_for('reset_password', token=token))
        
        if password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('reset_password', token=token))
        
        user.set_password(db, password)
        flash('Your password has been reset. You can now log in.')
        return redirect(url_for('login'))
    
    return render_template('reset_password_confirm.html', token=token)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's booking history with tour details
    pipeline = [
        {
            '$match': {'user_id': ObjectId(current_user.id)}
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
            '$sort': {'created_at': -1}
        }
    ]
    bookings = list(db.bookings.aggregate(pipeline))
    
    # Calculate stats
    booking_count = len(bookings)
    upcoming_tours = [b for b in bookings if b['start_date'] > datetime.utcnow() and b['status'] == 'confirmed']
    upcoming_count = len(upcoming_tours)
    
    # Get review count
    review_count = db.reviews.count_documents({'user_id': ObjectId(current_user.id)})
    
    # Calculate total spent
    total_spent = sum(b['total_price'] for b in bookings if b['status'] in ['confirmed', 'completed'])
    
    # Get recent activities
    activities = get_user_activities(current_user.id)
    
    return render_template('dashboard.html',
                         booking_count=booking_count,
                         upcoming_count=upcoming_count,
                         review_count=review_count,
                         total_spent=total_spent,
                         upcoming_tours=upcoming_tours[:6],  # Show only 6 upcoming tours
                         recent_activities=activities)

@app.route('/dashboard/stats')
@login_required
def dashboard_stats():
    # Get user's booking stats
    pipeline = [
        {
            '$match': {'user_id': ObjectId(current_user.id)}
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
        }
    ]
    bookings = list(db.bookings.aggregate(pipeline))
    
    # Calculate stats
    booking_count = len(bookings)
    upcoming_count = len([b for b in bookings if b['start_date'] > datetime.utcnow() and b['status'] == 'confirmed'])
    review_count = db.reviews.count_documents({'user_id': ObjectId(current_user.id)})
    total_spent = sum(b['total_price'] for b in bookings if b['status'] in ['confirmed', 'completed'])
    
    return jsonify({
        'booking_count': booking_count,
        'upcoming_count': upcoming_count,
        'review_count': review_count,
        'total_spent': total_spent
    })

@app.route('/activity/recent')
@login_required
def recent_activities():
    # Get activities since the last check
    last_check = request.args.get('since')
    if last_check:
        last_check = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
        activities = get_user_activities(current_user.id, since=last_check)
    else:
        activities = get_user_activities(current_user.id, limit=5)
    
    return jsonify({
        'activities': [{
            'icon': activity['icon'],
            'description': activity['description'],
            'timestamp': activity['timestamp'].isoformat() + 'Z'
        } for activity in activities]
    })

@app.route('/notifications/check')
@login_required
def check_notifications():
    # Get unread notification count
    count = db.notifications.count_documents({
        'user_id': ObjectId(current_user.id),
        'read': False
    })
    return jsonify({'count': count})

def get_user_activities(user_id, since=None, limit=None):
    # Get activities from the last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(days=1)
    
    # Base pipeline for aggregation
    pipeline = [
        {
            '$match': {
                'user_id': ObjectId(user_id),
                'created_at': {'$gte': twenty_four_hours_ago}
            }
        },
        {'$sort': {'created_at': -1}}
    ]
    
    if limit:
        pipeline.append({'$limit': limit})
    
    # Get bookings
    bookings = list(db.bookings.aggregate(pipeline + [
        {
            '$lookup': {
                'from': 'tours',
                'localField': 'tour_id',
                'foreignField': '_id',
                'as': 'tour'
            }
        },
        {'$unwind': '$tour'},
        {
            '$project': {
                'type': {'$literal': 'booking'},
                'description': {'$concat': ['Booked tour: ', '$tour.name']},
                'timestamp': '$created_at',
                'icon': {'$literal': 'fa-ticket-alt'}
            }
        }
    ]))
    
    # Get reviews
    reviews = list(db.reviews.aggregate(pipeline + [
        {
            '$lookup': {
                'from': 'tours',
                'localField': 'tour_id',
                'foreignField': '_id',
                'as': 'tour'
            }
        },
        {'$unwind': '$tour'},
        {
            '$project': {
                'type': {'$literal': 'review'},
                'description': {'$concat': ['Reviewed tour: ', '$tour.name']},
                'timestamp': '$created_at',
                'icon': {'$literal': 'fa-star'}
            }
        }
    ]))
    
    # Combine all activities and sort by timestamp
    activities = bookings + reviews
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return activities

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get all tours
    tours = Tour.get_all(db, active_only=False)
    
    # Get dashboard stats
    total_users = db.users.count_documents({})
    total_bookings = db.bookings.count_documents({})
    active_bookings = db.bookings.count_documents({'status': 'confirmed'})
    
    # Calculate total revenue
    revenue_pipeline = [
        {'$match': {'status': {'$in': ['confirmed', 'completed']}}},
        {'$group': {'_id': None, 'total': {'$sum': '$total_price'}}}
    ]
    revenue_result = list(db.bookings.aggregate(revenue_pipeline))
    total_revenue = revenue_result[0]['total'] if revenue_result else 0
    
    return render_template('admin.html', 
                         tours=tours,
                         total_users=total_users,
                         total_bookings=total_bookings,
                         active_bookings=active_bookings,
                         total_revenue=total_revenue)

@app.route('/admin/tour/new', methods=['GET'])
@login_required
def admin_new_tour():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    return render_template('admin/tour_form.html', tour=None)

@app.route('/admin/tour/<tour_id>/edit', methods=['GET'])
@login_required
def admin_edit_tour(tour_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    tour = Tour.get_by_id(db, tour_id)
    if not tour:
        flash('Tour not found')
        return redirect(url_for('admin'))
    
    return render_template('admin/tour_form.html', tour=tour)

@app.route('/admin/add_tour', methods=['POST'])
@login_required
def admin_add_tour():
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Process basic information
        name = request.form.get('name')
        description = request.form.get('description')
        destination = request.form.get('destination')
        price = float(request.form.get('price'))
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
        
        # Calculate duration
        duration = (end_date - start_date).days + 1
        
        # Process highlights and services
        highlights = [line.strip() for line in request.form.get('highlights', '').split('\n') if line.strip()]
        included_services = [line.strip() for line in request.form.get('included_services', '').split('\n') if line.strip()]
        
        # Process add-ons
        addon_names = request.form.getlist('addon_names[]')
        addon_prices = request.form.getlist('addon_prices[]')
        add_ons = [
            {'name': name, 'price': float(price)}
            for name, price in zip(addon_names, addon_prices)
            if name and price
        ]
        
        # Process media files
        media_urls = []
        if 'media[]' in request.files:
            files = request.files.getlist('media[]')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    filename = timestamp + filename
                    file.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename))
                    media_urls.append(url_for('static', filename=f'uploads/{filename}'))
        
        # Create tour
        tour = Tour.create(
            db,
            name=name,
            description=description,
            destination=destination,
            price=price,
            duration=duration,
            start_date=start_date,
            end_date=end_date,
            highlights=highlights,
            included_services=included_services,
            add_ons=add_ons,
            media=media_urls
        )
        
        # Send notification to all users about the new tour
        send_new_tour_notification(tour)
        
        flash('Tour added successfully')
    except Exception as e:
        flash(f'Error adding tour: {str(e)}')
    
    return redirect(url_for('admin'))

@app.route('/admin/tour/<tour_id>', methods=['POST'])
@login_required
def admin_update_tour(tour_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    tour = Tour.get_by_id(db, tour_id)
    if not tour:
        return jsonify({'error': 'Tour not found'}), 404
    
    try:
        updates = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'destination': request.form.get('destination'),
            'price': float(request.form.get('price')),
            'start_date': datetime.strptime(request.form.get('start_date'), '%Y-%m-%d'),
            'end_date': datetime.strptime(request.form.get('end_date'), '%Y-%m-%d'),
            'highlights': [line.strip() for line in request.form.get('highlights', '').split('\n') if line.strip()],
            'included_services': [line.strip() for line in request.form.get('included_services', '').split('\n') if line.strip()]
        }
        
        # Process add-ons
        addon_names = request.form.getlist('addon_names[]')
        addon_prices = request.form.getlist('addon_prices[]')
        updates['add_ons'] = [
            {'name': name, 'price': float(price)}
            for name, price in zip(addon_names, addon_prices)
            if name and price
        ]
        
        # Process media files
        existing_media = request.form.getlist('existing_media[]')
        new_media_urls = []
        if 'media[]' in request.files:
            files = request.files.getlist('media[]')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    filename = timestamp + filename
                    file.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename))
                    new_media_urls.append(url_for('static', filename=f'uploads/{filename}'))
        
        updates['media'] = existing_media + new_media_urls
        updates['duration'] = (updates['end_date'] - updates['start_date']).days + 1
        
        tour.update(db, **updates)
        flash('Tour updated successfully')
    except Exception as e:
        flash(f'Error updating tour: {str(e)}')
    
    return redirect(url_for('admin'))

@app.route('/admin/tour/<tour_id>/delete', methods=['POST'])
@login_required
def admin_delete_tour(tour_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    tour = Tour.get_by_id(db, tour_id)
    if tour:
        tour.delete(db)
        flash('Tour deleted successfully')
    return redirect(url_for('admin'))

@app.route('/tour/<tour_id>')
def tour_details(tour_id):
    try:
        # Get complete tour details
        tour = db.tours.find_one({'_id': ObjectId(str(tour_id))})
        if not tour:
            flash('Tour not found')
            return redirect(url_for('tours'))
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 5  # Number of reviews per page
        
        # Get total number of reviews
        total_reviews = db.reviews.count_documents({'tour_id': ObjectId(str(tour_id))})
        total_pages = (total_reviews + per_page - 1) // per_page
        
        # Get reviews for this tour with user details
        reviews = list(db.reviews.aggregate([
            {'$match': {'tour_id': ObjectId(str(tour_id))}},
            {'$lookup': {
                'from': 'users',
                'localField': 'user_id',
                'foreignField': '_id',
                'as': 'user'
            }},
            {'$unwind': '$user'},
            {'$project': {
                'rating': 1,
                'review_text': 1,
                'created_at': 1,
                'user_name': '$user.name',
                'user_id': '$user._id'
            }},
            {'$sort': {'created_at': -1}},
            {'$skip': (page - 1) * per_page},
            {'$limit': per_page}
        ]))
        
        # Get booking statistics
        booking_stats = db.bookings.aggregate([
            {'$match': {'tour_id': ObjectId(str(tour_id))}},
            {'$group': {
                '_id': None,
                'total_bookings': {'$sum': 1},
                'total_people': {'$sum': '$number_of_people'}
            }}
        ])
        stats = next(booking_stats, {'total_bookings': 0, 'total_people': 0})
        
        # Add statistics to tour object
        tour['total_bookings'] = stats.get('total_bookings', 0)
        tour['total_people'] = stats.get('total_people', 0)
        
        # Calculate average rating from all reviews
        all_reviews = list(db.reviews.find({'tour_id': ObjectId(str(tour_id))}))
        if all_reviews:
            avg_rating = sum(review['rating'] for review in all_reviews) / len(all_reviews)
            tour['rating'] = round(avg_rating, 1)
            tour['review_count'] = len(all_reviews)
        else:
            tour['rating'] = 0
            tour['review_count'] = 0
        
        return render_template('tour_details.html', 
                             tour=tour, 
                             reviews=reviews,
                             current_page=page,
                             total_pages=total_pages,
                             now=datetime.now())
    except Exception as e:
        flash(f'Error loading tour details: {str(e)}')
        return redirect(url_for('tours'))

@app.route('/tour/<tour_id>/book', methods=['POST'])
@login_required
def book_tour(tour_id):
    if current_user.is_admin:
        flash('Admins cannot make bookings', 'error')
        return redirect(url_for('tour_details', tour_id=tour_id))
    
    try:
        tour = Tour.get_by_id(db, tour_id)
        if not tour:
            flash('Tour not found', 'error')
            return redirect(url_for('tours'))
        
        number_of_people = int(request.form.get('number_of_people', 1))
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        
        # Validate number of people
        if number_of_people < 1 or number_of_people > tour.max_participants:
            flash(f'Number of people must be between 1 and {tour.max_participants}', 'error')
            return redirect(url_for('tour_details', tour_id=tour_id))
        
        # Calculate total price
        total_price = tour.price * number_of_people
        
        # Create booking
        booking = Booking.create(
            db,
            user_id=current_user.id,
            tour_id=tour_id,
            start_date=start_date,
            number_of_people=number_of_people,
            total_price=total_price
        )
        
        # Store booking ID in session for payment
        if 'pending_booking_id' not in session:
            session['pending_booking_id'] = str(booking.id)
        
        # Redirect to payment page
        return redirect(url_for('process_payment'))
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('tour_details', tour_id=tour_id))

@app.route('/payment')
@login_required
def process_payment():
    booking_id = session.get('pending_booking_id')
    if not booking_id:
        flash('No pending booking found', 'error')
        return redirect(url_for('tours'))
    
    booking = Booking.get_by_id(db, booking_id)
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('tours'))
    
    tour = Tour.get_by_id(db, str(booking.booking_data['tour_id']))
    if not tour:
        flash('Tour not found', 'error')
        return redirect(url_for('tours'))
    
    return render_template('payment.html', booking=booking.booking_data, tour=tour.tour_data)

@app.route('/payment/process', methods=['POST'])
@login_required
def process_payment_submit():
    booking_id = session.get('pending_booking_id')
    if not booking_id:
        flash('No pending booking found', 'error')
        return redirect(url_for('tours'))
    
    booking = Booking.get_by_id(db, booking_id)
    if not booking:
        flash('Booking not found', 'error')
        return redirect(url_for('tours'))
    
    try:
        # Create payment record
        payment = Payment.create_payment_intent(
            db,
            booking_id=booking_id,
            amount=booking.booking_data['total_price']
        )
        
        # Process the payment (in a real application, this would integrate with a payment provider)
        # For this example, we'll simulate a successful payment
        payment.confirm_payment(db, 'simulated_payment_method')
        
        # Clear the pending booking from session
        session.pop('pending_booking_id', None)
        
        flash('Payment processed successfully', 'success')
        return redirect(url_for('bookings'))
    except Exception as e:
        flash(f'Payment processing failed: {str(e)}', 'error')
        return redirect(url_for('process_payment'))

@app.route('/tours')
def tours():
    # Get filter parameters
    destination = request.args.get('destination')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort_by = request.args.get('sort', 'price_asc')
    page = request.args.get('page', 1, type=int)
    per_page = 9  # Number of tours per page
    
    # Build price range filter
    price_range = None
    if min_price is not None and max_price is not None:
        price_range = (min_price, max_price)
    
    # Get all tours with filters
    all_tours = Tour.get_all(
        db,
        destination=destination,
        price_range=price_range,
        sort_by=sort_by
    )
    
    # Calculate pagination
    total_tours = len(all_tours)
    total_pages = (total_tours + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    tours = all_tours[start_idx:end_idx]
    
    # Get all available destinations for filter dropdown
    destinations = Tour.get_destinations(db)
    
    return render_template(
        'tours.html',
        tours=tours,
        destinations=destinations,
        current_page=page,
        total_pages=total_pages,
        current_filters={
            'destination': destination,
            'min_price': min_price,
            'max_price': max_price,
            'sort': sort_by
        }
    )

@app.route('/admin/bookings')
@login_required
def admin_bookings():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    # First, check and clean up expired bookings
    check_expired_bookings()
    
    # Get only confirmed/completed bookings
    bookings = list(db.bookings.aggregate([
        {
            '$match': {
                'status': {'$in': ['confirmed', 'completed']}
            }
        },
        {
            '$lookup': {
                'from': 'users',
                'localField': 'user_id',
                'foreignField': '_id',
                'as': 'user'
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
            '$unwind': '$user'
        },
        {
            '$unwind': '$tour'
        },
        {
            '$sort': {'created_at': -1}
        },
        {
            '$project': {
                'user_name': '$user.name',
                'user_email': '$user.email',
                'tour_name': '$tour.name',
                'tour_destination': '$tour.destination',
                'number_of_people': 1,
                'total_price': 1,
                'status': 1,
                'created_at': 1,
                'start_date': 1
            }
        }
    ]))
    
    return render_template('admin/bookings.html', bookings=bookings)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get all users with their booking counts
    pipeline = [
        {
            '$lookup': {
                'from': 'bookings',
                'localField': '_id',
                'foreignField': 'user_id',
                'as': 'bookings'
            }
        },
        {
            '$addFields': {
                'booking_count': {'$size': '$bookings'}
            }
        },
        {
            '$project': {
                'bookings': 0,
                'password': 0
            }
        }
    ]
    
    users = list(db.users.aggregate(pipeline))
    return render_template('admin/users.html', users=users)

@app.route('/bookings')
@login_required
def bookings():
    # Check for expired bookings first
    check_expired_bookings()
    
    # Get user's bookings with tour details
    user_bookings = list(db.bookings.aggregate([
        {
            '$match': {
                'user_id': ObjectId(current_user.id)
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
            '$sort': {'created_at': -1}
        }
    ]))
    
    # Create notification for expired bookings
    for booking in user_bookings:
        if booking.get('status') == 'expired' and not booking.get('notification_sent'):
            create_notification(
                user_id=current_user.id,
                title='Booking Expired',
                message=f'Your booking for {booking["tour"]["name"]} has expired due to pending payment.',
                type='booking_expired'
            )
            # Mark notification as sent
            db.bookings.update_one(
                {'_id': booking['_id']},
                {'$set': {'notification_sent': True}}
            )
    
    return render_template('bookings.html', bookings=user_bookings)

def create_notification(user_id, title, message, type):
    notification = {
        'user_id': ObjectId(user_id),
        'title': title,
        'message': message,
        'type': type,
        'created_at': datetime.utcnow(),
        'read': False
    }
    db.notifications.insert_one(notification)

@app.route('/notifications')
@login_required
def notifications():
    # Get user's notifications
    notifications = list(db.notifications.find(
        {'user_id': ObjectId(current_user.id)}
    ).sort('created_at', -1))
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    notification_id = request.form.get('notification_id')
    
    if notification_id:
        # Mark specific notification as read
        db.notifications.update_one(
            {'_id': ObjectId(notification_id)},
            {'$set': {'read': True}}
        )
    else:
        # Mark all notifications as read
        db.notifications.update_many(
            {'user_id': ObjectId(current_user.id)},
            {'$set': {'read': True}}
        )
    
    return jsonify({'success': True})

@app.route('/notifications/delete', methods=['POST'])
@login_required
def delete_notification():
    notification_id = request.form.get('notification_id')
    
    if notification_id:
        db.notifications.delete_one({
            '_id': ObjectId(notification_id),
            'user_id': ObjectId(current_user.id)
        })
    
    return jsonify({'success': True})

@app.route('/profile')
@login_required
def profile():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page

    # Get total booking count for pagination
    booking_count = db.bookings.count_documents({'user_id': current_user.id})
    total_pages = (booking_count + per_page - 1) // per_page

    # Get paginated bookings with tour details
    bookings = list(db.bookings.aggregate([
        {'$match': {'user_id': current_user.id}},
        {'$sort': {'created_at': -1}},
        {'$skip': skip},
        {'$limit': per_page},
        {'$lookup': {
            'from': 'tours',
            'localField': 'tour_id',
            'foreignField': '_id',
            'as': 'tour'
        }},
        {'$unwind': '$tour'}
    ]))

    return render_template('profile.html',
                         bookings=bookings,
                         booking_count=booking_count,
                         current_page=page,
                         total_pages=total_pages,
                         email_preferences=current_user.email_preferences)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    try:
        updates = {
            'name': request.form.get('name'),
            'email': request.form.get('email')
        }
        
        if request.form.get('password'):
            if request.form.get('password') != request.form.get('confirm_password'):
                flash('Passwords do not match')
                return redirect(url_for('profile'))
            updates['password'] = generate_password_hash(request.form.get('password'))
        
        db.users.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': updates}
        )
        flash('Profile updated successfully')
    except Exception as e:
        flash(f'Error updating profile: {str(e)}')
    
    return redirect(url_for('profile'))

@app.route('/admin/user/<user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    # Don't allow deleting self
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    try:
        db.users.delete_one({'_id': ObjectId(user_id)})
        return jsonify({'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/user/<user_id>/update-role', methods=['POST'])
@login_required
def admin_update_user_role(user_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Don't allow modifying self
    if user_id == current_user.id:
        flash('Cannot modify your own role')
        return redirect(url_for('admin_users'))
    
    action = request.form.get('action')
    if action not in ['promote', 'demote']:
        flash('Invalid action')
        return redirect(url_for('admin_users'))
    
    try:
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'is_admin': action == 'promote'}}
        )
        flash(f'User {"promoted to" if action == "promote" else "demoted from"} admin successfully')
    except Exception as e:
        flash(f'Error updating user role: {str(e)}')
    
    return redirect(url_for('admin_users'))

@app.route('/booking/<booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    try:
        # Get the booking
        booking = db.bookings.find_one({
            '_id': ObjectId(booking_id),
            'user_id': ObjectId(current_user.id)
        })
        
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Check if booking can be cancelled (not in the past and status is confirmed)
        if booking['status'] != 'confirmed' or booking['start_date'] <= datetime.utcnow():
            return jsonify({'error': 'Booking cannot be cancelled'}), 400
        
        # Update booking status
        db.bookings.update_one(
            {'_id': ObjectId(booking_id)},
            {
                '$set': {
                    'status': 'cancelled',
                    'cancelled_at': datetime.utcnow()
                }
            }
        )
        
        # Update tour's current bookings count
        db.tours.update_one(
            {'_id': booking['tour_id']},
            {'$inc': {'current_bookings': -booking['number_of_people']}}
        )
        
        return jsonify({'message': 'Booking cancelled successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/guides')
@login_required
def admin_guides():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    guides = Guide.get_all(db)
    return render_template('admin/guides.html', guides=guides)

@app.route('/admin/guide/add', methods=['POST'])
@login_required
def admin_add_guide():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    try:
        # Handle image upload
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename))
                image_url = url_for('static', filename=f'uploads/{filename}')

        guide = Guide.create(
            db,
            name=request.form.get('name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            languages=request.form.get('languages'),
            experience=request.form.get('experience'),
            specialties=request.form.get('specialties'),
            image=image_url
        )
        flash('Guide added successfully')
    except Exception as e:
        flash(f'Error adding guide: {str(e)}')
    
    return redirect(url_for('admin_guides'))

@app.route('/admin/guide/<guide_id>/update', methods=['POST'])
@login_required
def admin_update_guide(guide_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    guide = Guide.get_by_id(db, guide_id)
    if not guide:
        flash('Guide not found')
        return redirect(url_for('admin_guides'))
    
    try:
        # Handle image upload
        image_url = guide.guide_data.get('image')  # Keep existing image by default
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename))
                image_url = url_for('static', filename=f'uploads/{filename}')

        guide.update(
            db,
            name=request.form.get('name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            languages=request.form.get('languages'),
            experience=request.form.get('experience'),
            specialties=request.form.get('specialties'),
            image=image_url
        )
        flash('Guide updated successfully')
    except Exception as e:
        flash(f'Error updating guide: {str(e)}')
    
    return redirect(url_for('admin_guides'))

@app.route('/admin/guide/<guide_id>')
@login_required
def admin_get_guide(guide_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    guide = Guide.get_by_id(db, guide_id)
    if not guide:
        return jsonify({'error': 'Guide not found'}), 404
    
    return jsonify(guide.to_dict())

@app.route('/admin/guide/<guide_id>/schedule')
@login_required
def admin_guide_schedule(guide_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    guide = Guide.get_by_id(db, guide_id)
    if not guide:
        return jsonify({'error': 'Guide not found'}), 404
    
    try:
        schedules = guide.get_schedule(db)
        return jsonify({
            'schedules': [{
                'tour': {
                    'name': schedule['tour']['name'],
                    'destination': schedule['tour']['destination']
                },
                'start_date': schedule['start_date'],
                'end_date': schedule['end_date']
            } for schedule in schedules]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/guide/<guide_id>/assign', methods=['POST'])
@login_required
def admin_assign_guide(guide_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    guide = Guide.get_by_id(db, guide_id)
    if not guide:
        return jsonify({'error': 'Guide not found'}), 404
    
    try:
        tour_id = request.form.get('tour_id')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
        
        guide.assign_to_tour(db, tour_id, start_date, end_date)
        return jsonify({'message': 'Guide assigned successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/guide/<guide_id>/unassign', methods=['POST'])
@login_required
def admin_unassign_guide(guide_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    guide = Guide.get_by_id(db, guide_id)
    if not guide:
        return jsonify({'error': 'Guide not found'}), 404
    
    try:
        tour_id = request.form.get('tour_id')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
        
        guide.remove_from_tour(db, tour_id, start_date, end_date)
        return jsonify({'message': 'Guide unassigned successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/booking/<booking_id>/payment', methods=['POST'])
@login_required
def create_payment(booking_id):
    try:
        booking = db.bookings.find_one({'_id': ObjectId(booking_id)})
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Check if payment already exists
        existing_payment = Payment.get_by_booking_id(db, booking_id)
        if existing_payment and existing_payment.payment_data['status'] == 'completed':
            return jsonify({'error': 'Payment already completed'}), 400
        
        # Create or get payment intent
        if existing_payment:
            client_secret = existing_payment.payment_data['stripe_client_secret']
        else:
            payment = Payment.create_payment_intent(db, booking_id, booking['total_price'])
            client_secret = payment.payment_data['stripe_client_secret']
        
        return jsonify({
            'clientSecret': client_secret,
            'publicKey': app.config['STRIPE_PUBLIC_KEY']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError as e:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400
    
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        
        # Update payment and booking status
        payment = Payment.get_by_payment_intent_id(db, payment_intent['id'])
        if payment:
            payment.confirm_payment(db, payment_intent['payment_method'])
            
            # Get booking details and send receipt
            booking = db.bookings.find_one({'_id': payment.payment_data['booking_id']})
            if booking:
                send_payment_receipt(payment.payment_data, booking)
    
    return jsonify({'received': True})

@app.route('/admin/payments')
@login_required
def admin_payments():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Get all payments with booking and user details
    pipeline = [
        {
            '$lookup': {
                'from': 'bookings',
                'localField': 'booking_id',
                'foreignField': '_id',
                'as': 'booking'
            }
        },
        {
            '$unwind': '$booking'
        },
        {
            '$lookup': {
                'from': 'users',
                'localField': 'booking.user_id',
                'foreignField': '_id',
                'as': 'user'
            }
        },
        {
            '$unwind': '$user'
        },
        {
            '$lookup': {
                'from': 'tours',
                'localField': 'booking.tour_id',
                'foreignField': '_id',
                'as': 'tour'
            }
        },
        {
            '$unwind': '$tour'
        },
        {
            '$sort': {'created_at': -1}
        }
    ]
    
    payments = list(db.payments.aggregate(pipeline))
    return render_template('admin/payments.html', payments=payments)

@app.route('/admin/payment/<payment_id>/refund', methods=['POST'])
@login_required
def admin_refund_payment(payment_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        payment_data = db.payments.find_one({'_id': ObjectId(payment_id)})
        if not payment_data:
            return jsonify({'error': 'Payment not found'}), 404
        
        payment = Payment(payment_data)
        amount = float(request.form.get('amount', 0))
        
        if payment.process_refund(db, amount if amount > 0 else None):
            return jsonify({'message': 'Refund processed successfully'})
        return jsonify({'error': 'Failed to process refund'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reports/revenue')
@login_required
def admin_revenue_report():
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('index'))
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    
    report_data = Payment.get_revenue_report(db, start_date, end_date)
    return render_template('admin/revenue_report.html', report_data=report_data)

def initialize_database():
    # Create admin user if not exists
    admin_user = db.users.find_one({'email': Config.ADMIN_EMAIL})
    if not admin_user:
        admin_password = generate_password_hash(Config.ADMIN_PASSWORD)
        db.users.insert_one({
            'email': Config.ADMIN_EMAIL,
            'password': admin_password,
            'role': 'admin',
            'name': 'Admin User',
            'created_at': datetime.utcnow(),
            'is_active': True
        })
        print(f"Admin user created successfully with email: {Config.ADMIN_EMAIL}")
        
    # Create test customer if not exists
    test_customer = db.users.find_one({'email': 'customer@test.com'})
    if not test_customer:
        customer_password = generate_password_hash('customer123')
        db.users.insert_one({
            'email': 'customer@test.com',
            'password': customer_password,
            'role': 'customer',
            'name': 'Test Customer',
            'created_at': datetime.utcnow(),
            'is_active': True,
            'preferred_destinations': ['Paris', 'Tokyo', 'New York'],
            'phone': '+1234567890'
        })
        print("Test customer created successfully with email: customer@test.com")

@app.route('/reviews')
@login_required
def reviews():
    # Get user's reviews with tour details
    pipeline = [
        {
            '$match': {'user_id': ObjectId(current_user.id)}
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
            '$sort': {'created_at': -1}
        }
    ]
    reviews = list(db.reviews.aggregate(pipeline))
    
    # Get bookings that can be reviewed (completed but not yet reviewed)
    reviewable_bookings = db.bookings.aggregate([
        {
            '$match': {
                'user_id': ObjectId(current_user.id),
                'status': 'completed'
            }
        },
        {
            '$lookup': {
                'from': 'reviews',
                'let': {'booking_id': '$_id'},
                'pipeline': [
                    {
                        '$match': {
                            '$expr': {'$eq': ['$booking_id', '$$booking_id']}
                        }
                    }
                ],
                'as': 'review'
            }
        },
        {
            '$match': {'review': {'$size': 0}}
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
        }
    ])
    
    return render_template('reviews.html', 
                         reviews=reviews, 
                         reviewable_bookings=list(reviewable_bookings))

@app.route('/review/add', methods=['POST'])
@login_required
def add_review():
    try:
        booking_id = request.form.get('booking_id')
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment')
        
        if not all([booking_id, rating, comment]):
            return jsonify({'error': 'All fields are required'}), 400
        
        # Verify the booking exists and belongs to the user
        booking = db.bookings.find_one({
            '_id': ObjectId(booking_id),
            'user_id': ObjectId(current_user.id),
            'status': 'completed'
        })
        
        if not booking:
            return jsonify({'error': 'Invalid booking'}), 404
        
        # Check if review already exists
        existing_review = db.reviews.find_one({'booking_id': ObjectId(booking_id)})
        if existing_review:
            return jsonify({'error': 'Review already exists'}), 400
        
        # Create the review
        review = {
            'booking_id': ObjectId(booking_id),
            'tour_id': booking['tour_id'],
            'user_id': ObjectId(current_user.id),
            'rating': rating,
            'comment': comment,
            'created_at': datetime.utcnow()
        }
        db.reviews.insert_one(review)
        
        # Update tour rating
        pipeline = [
            {
                '$match': {'tour_id': booking['tour_id']}
            },
            {
                '$group': {
                    '_id': None,
                    'avg_rating': {'$avg': '$rating'},
                    'count': {'$sum': 1}
                }
            }
        ]
        rating_stats = list(db.reviews.aggregate(pipeline))
        
        if rating_stats:
            db.tours.update_one(
                {'_id': booking['tour_id']},
                {
                    '$set': {
                        'rating': rating_stats[0]['avg_rating'],
                        'review_count': rating_stats[0]['count']
                    }
                }
            )
        
        flash('Review added successfully')
        return redirect(url_for('reviews'))
    except Exception as e:
        flash(f'Error adding review: {str(e)}')
        return redirect(url_for('reviews'))

@app.route('/review/<review_id>/edit', methods=['POST'])
@login_required
def edit_review(review_id):
    try:
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment')
        
        if not all([rating, comment]):
            return jsonify({'error': 'All fields are required'}), 400
        
        # Verify the review exists and belongs to the user
        review = db.reviews.find_one({
            '_id': ObjectId(review_id),
            'user_id': ObjectId(current_user.id)
        })
        
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        # Update the review
        db.reviews.update_one(
            {'_id': ObjectId(review_id)},
            {
                '$set': {
                    'rating': rating,
                    'comment': comment,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        # Update tour rating
        pipeline = [
            {
                '$match': {'tour_id': review['tour_id']}
            },
            {
                '$group': {
                    '_id': None,
                    'avg_rating': {'$avg': '$rating'},
                    'count': {'$sum': 1}
                }
            }
        ]
        rating_stats = list(db.reviews.aggregate(pipeline))
        
        if rating_stats:
            db.tours.update_one(
                {'_id': review['tour_id']},
                {
                    '$set': {
                        'rating': rating_stats[0]['avg_rating'],
                        'review_count': rating_stats[0]['count']
                    }
                }
            )
        
        flash('Review updated successfully')
        return redirect(url_for('reviews'))
    except Exception as e:
        flash(f'Error updating review: {str(e)}')
        return redirect(url_for('reviews'))

@app.route('/review/<review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    try:
        # Verify the review exists and belongs to the user
        review = db.reviews.find_one({
            '_id': ObjectId(review_id),
            'user_id': ObjectId(current_user.id)
        })
        
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        # Delete the review
        db.reviews.delete_one({'_id': ObjectId(review_id)})
        
        # Update tour rating
        pipeline = [
            {
                '$match': {'tour_id': review['tour_id']}
            },
            {
                '$group': {
                    '_id': None,
                    'avg_rating': {'$avg': '$rating'},
                    'count': {'$sum': 1}
                }
            }
        ]
        
        result = list(db.reviews.aggregate(pipeline))
        if result:
            db.tours.update_one(
                {'_id': review['tour_id']},
                {'$set': {
                    'rating': result[0]['avg_rating'],
                    'review_count': result[0]['count']
                }}
            )
        else:
            # No reviews left, reset rating and count
            db.tours.update_one(
                {'_id': review['tour_id']},
                {'$set': {
                    'rating': 0,
                    'review_count': 0
                }}
            )
        
        flash('Review deleted successfully')
        return redirect(url_for('reviews'))
    except Exception as e:
        flash(f'Error deleting review: {str(e)}')
        return redirect(url_for('reviews'))

@app.route('/payments')
@login_required
def payments():
    # Get user's payment history with booking and tour details
    pipeline = [
        {
            '$match': {'user_id': ObjectId(current_user.id)}
        },
        {
            '$lookup': {
                'from': 'bookings',
                'localField': 'booking_id',
                'foreignField': '_id',
                'as': 'booking'
            }
        },
        {
            '$unwind': '$booking'
        },
        {
            '$lookup': {
                'from': 'tours',
                'localField': 'booking.tour_id',
                'foreignField': '_id',
                'as': 'tour'
            }
        },
        {
            '$unwind': '$tour'
        },
        {
            '$sort': {'created_at': -1}
        }
    ]
    payments = list(db.payments.aggregate(pipeline))
    
    return render_template('payments.html', payments=payments)

@app.route('/tour/<tour_id>/review', methods=['POST'])
@login_required
def submit_review(tour_id):
    if current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admins cannot submit reviews'})
    
    try:
        # Get the review data
        rating = int(request.form.get('rating'))
        review_text = request.form.get('review_text', '').strip()
        
        # Validate the data
        if not rating or rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'})
        
        if not review_text:
            return jsonify({'success': False, 'message': 'Review text is required'})
        
        # Check if user has already reviewed this tour
        existing_review = db.reviews.find_one({
            'user_id': current_user.id,
            'tour_id': ObjectId(tour_id)
        })
        
        if existing_review:
            # Update existing review
            db.reviews.update_one(
                {'_id': existing_review['_id']},
                {
                    '$set': {
                        'rating': rating,
                        'review_text': review_text,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
        else:
            # Create new review
            db.reviews.insert_one({
                'user_id': current_user.id,
                'tour_id': ObjectId(tour_id),
                'rating': rating,
                'review_text': review_text,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            })
        
        # Update tour's average rating
        reviews = list(db.reviews.find({'tour_id': ObjectId(tour_id)}))
        if reviews:
            avg_rating = sum(review['rating'] for review in reviews) / len(reviews)
            db.tours.update_one(
                {'_id': ObjectId(tour_id)},
                {
                    '$set': {
                        'rating': round(avg_rating, 1),
                        'review_count': len(reviews)
                    }
                }
            )
        
        return jsonify({
            'success': True,
            'message': 'Review submitted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error submitting review: {str(e)}'
        })

@app.route('/tour/<tour_id>/review/<review_id>/delete', methods=['POST'])
@login_required
def admin_delete_review(tour_id, review_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Delete the review
        db.reviews.delete_one({'_id': ObjectId(review_id)})
        
        # Update tour rating and review count
        pipeline = [
            {'$match': {'tour_id': ObjectId(tour_id)}},
            {'$group': {
                '_id': None,
                'avg_rating': {'$avg': '$rating'},
                'count': {'$sum': 1}
            }}
        ]
        
        result = list(db.reviews.aggregate(pipeline))
        if result:
            db.tours.update_one(
                {'_id': ObjectId(tour_id)},
                {'$set': {
                    'rating': result[0]['avg_rating'],
                    'review_count': result[0]['count']
                }}
            )
        else:
            # No reviews left, reset rating and count
            db.tours.update_one(
                {'_id': ObjectId(tour_id)},
                {'$set': {
                    'rating': 0,
                    'review_count': 0
                }}
            )
        
        flash('Review deleted successfully')
        return redirect(url_for('tour_details', tour_id=tour_id))
        
    except Exception as e:
        flash(f'Error deleting review: {str(e)}')
        return redirect(url_for('tour_details', tour_id=tour_id))

def check_expired_bookings():
    # Find and update bookings that are more than 24 hours old and still pending
    twenty_four_hours_ago = datetime.utcnow() - timedelta(days=1)
    four_days_ago = datetime.utcnow() - timedelta(days=4)
    
    # Update expired pending bookings
    db.bookings.update_many(
        {
            'status': 'pending',
            'created_at': {'$lt': twenty_four_hours_ago}
        },
        {
            '$set': {
                'status': 'expired',
                'updated_at': datetime.utcnow()
            }
        }
    )
    
    # Delete bookings that are expired and older than 4 days
    db.bookings.delete_many({
        'status': 'expired',
        'created_at': {'$lt': four_days_ago}
    })

# Add route for updating email preferences
@app.route('/profile/email-preferences', methods=['POST'])
@login_required
def update_email_preferences():
    try:
        preferences = {
            'new_tours': bool(request.form.get('new_tours')),
            'payment_receipts': bool(request.form.get('payment_receipts')),
            'booking_reminders': bool(request.form.get('booking_reminders')),
            'promotional': bool(request.form.get('promotional'))
        }
        
        current_user.update_email_preferences(db, preferences)
        flash('Email preferences updated successfully')
    except Exception as e:
        flash(f'Error updating email preferences: {str(e)}')
    
    return redirect(url_for('profile'))

if __name__ == '__main__':
    # Initialize the database
    initialize_database()
    app.run(debug=True) 