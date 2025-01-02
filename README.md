# Wanderlust Travel Management System

<div align="center">
  <img src="static/images/logo.svg" alt="Wanderlust Logo" width="400"/>
  
  ![Python](https://img.shields.io/badge/python-v3.9-blue.svg)
  ![Flask](https://img.shields.io/badge/flask-v2.0.1-green.svg)
  ![MongoDB](https://img.shields.io/badge/mongodb-v4.4-green.svg)
  ![Docker](https://img.shields.io/badge/docker-v20.10-blue.svg)
  [![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
</div>

## 🌟 Features

- **User Authentication & Authorization**
  - Secure login and registration
  - Email verification
  - Password reset functionality
  - Role-based access control (Admin/User)

- **Tour Management**
  - Create and manage tour packages
  - Dynamic pricing
  - Media gallery support
  - Add-on services
  - Tour reviews and ratings

- **Booking System**
  - Secure payment processing with Stripe
  - Booking confirmation emails
  - Automated booking reminders
  - Booking status tracking

- **Email Notifications**
  - New tour announcements
  - Payment receipts
  - Booking reminders
  - Account verification
  - Password reset links

- **Admin Dashboard**
  - Tour management
  - User management
  - Booking overview
  - Payment tracking
  - Analytics dashboard

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose
- SMTP server for email notifications
- Stripe account for payments
- MongoDB (handled by Docker)

### Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/wanderlust.git
cd wanderlust
```

2. Create a `.env` file:
```bash
MONGODB_URI=mongodb://mongodb:27017/
DATABASE_NAME=travel_db
SECRET_KEY=your_secret_key
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret

# Email Configuration
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@example.com
MAIL_PASSWORD=your_password
MAIL_DEFAULT_SENDER=noreply@example.com
```

### Running with Docker

1. Build and start the services:
```bash
docker-compose build
docker-compose up -d
```

2. Access the application:
- Web Application: http://localhost:5000
- MongoDB: mongodb://localhost:27017
- Redis: redis://localhost:6379

### Services

The application runs the following services:
- Web Application (Flask)
- MongoDB Database
- Redis for task queue
- Celery worker for background tasks
- Celery beat for scheduled tasks

## 📝 API Documentation

### Authentication Endpoints
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `POST /auth/reset-password` - Password reset
- `GET /auth/verify-email/<token>` - Email verification

### Tour Endpoints
- `GET /tours` - List all tours
- `POST /admin/tours` - Create new tour (Admin)
- `PUT /admin/tours/<id>` - Update tour (Admin)
- `DELETE /admin/tours/<id>` - Delete tour (Admin)

### Booking Endpoints
- `POST /bookings` - Create booking
- `GET /bookings/<id>` - Get booking details
- `GET /user/bookings` - List user bookings

### Payment Endpoints
- `POST /payments/create-intent` - Create payment intent
- `POST /webhook/stripe` - Stripe webhook handler

## 🔒 Security

- Password hashing using Werkzeug
- JWT for API authentication
- CSRF protection
- Secure session handling
- Environment variable configuration
- Input validation and sanitization

## 📧 Email Templates

The system includes modern, responsive email templates for:
- Welcome emails
- Account verification
- Password reset
- Booking confirmations
- Tour reminders
- Payment receipts

## 🛠 Development

### Project Structure
```
wanderlust/
├── app/
│   ├── models/
│   ├── routes/
│   ├── static/
│   └── templates/
├── tests/
├── docker/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### Running Tests
```bash
docker-compose run web python -m pytest
```

### Code Style
The project follows PEP 8 guidelines. Run linting with:
```bash
docker-compose run web flake8
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📞 Support

For support, email support@wanderlust.com or create an issue in the repository. 