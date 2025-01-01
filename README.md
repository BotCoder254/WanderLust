# 🌍 Wanderlust - Travel Management System

A modern travel management system built with Flask and MongoDB, featuring tour packages, bookings, reviews, and secure payments.

## ✨ Features

- 🔐 User Authentication & Authorization
- 👥 User Roles (Admin/Customer)
- 🎫 Tour Package Management
- 📅 Booking System
- 💳 Secure Payment Processing
- ⭐ Review & Rating System
- 📱 Responsive Design
- 🔔 Real-time Notifications

## 🚀 Tech Stack

- **Backend:** Python, Flask
- **Database:** MongoDB
- **Frontend:** HTML, TailwindCSS, JavaScript
- **Authentication:** Flask-Login
- **Payment:** Stripe Integration
- **Deployment:** Docker, Render

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/wanderlust.git
   cd wanderlust
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configurations
   ```

3. **Using Docker (Recommended)**
   ```bash
   docker-compose up --build
   ```

4. **Manual Setup**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows

   # Install dependencies
   pip install -r requirements.txt

   # Run the application
   flask run
   ```

## 💻 Development

1. **Database Migrations**
   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```

2. **Running Tests**
   ```bash
   python -m pytest
   ```

3. **Code Formatting**
   ```bash
   black .
   flake8
   ```

## 🌟 Usage

### Admin Account
- Email: admin@wanderlust.com
- Password: admin123

### Customer Account
- Email: customer@test.com
- Password: customer123

## 🚢 Deployment

### Using Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Use the following settings:
   - Environment: Docker
   - Build Command: `docker build -t wanderlust .`
   - Start Command: `docker run -p $PORT:8000 wanderlust`

### Environment Variables on Render

Required environment variables:
- `MONGODB_URI`
- `SECRET_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- Other variables from `.env`

## 📁 Project Structure

```
wanderlust/
├── app.py              # Application entry point
├── config.py           # Configuration settings
├── models/             # Database models
├── static/             # Static files (CSS, JS, images)
├── templates/          # HTML templates
├── utils/             # Utility functions
├── tests/             # Test files
├── Dockerfile         # Docker configuration
├── docker-compose.yml # Docker Compose configuration
└── requirements.txt   # Python dependencies
```

## 🔒 Security

- Password hashing using bcrypt
- CSRF protection
- Secure session handling
- Input validation and sanitization
- Rate limiting
- XSS protection

## 📝 API Documentation

### Authentication Endpoints
- POST `/auth/login`
- POST `/auth/register`
- POST `/auth/logout`

### Tour Endpoints
- GET `/tours`
- GET `/tour/<id>`
- POST `/tour` (Admin only)
- PUT `/tour/<id>` (Admin only)
- DELETE `/tour/<id>` (Admin only)

### Booking Endpoints
- GET `/bookings`
- POST `/tour/<id>/book`
- GET `/booking/<id>`
- PUT `/booking/<id>/cancel`

### Review Endpoints
- GET `/tour/<id>/reviews`
- POST `/tour/<id>/review`
- DELETE `/review/<id>` (Admin only)

## 🤝 Contributing

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- Your Name - Initial work - [YourGitHub](https://github.com/yourusername)

## 🙏 Acknowledgments

- TailwindCSS for the UI components
- Flask community for the excellent documentation
- MongoDB team for the robust database
- All contributors who have helped this project grow 