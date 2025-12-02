# 🌿 MindEase – A Mental Wellness Platform

MindEase is a modern mental wellness web application designed to connect clients with certified therapists. It provides a seamless experience for discovering therapists, booking sessions, managing appointments, and tracking wellness progress.

The platform is built using **Django**, **PostgreSQL**, **Docker**, and deployed on **DigitalOcean** with **Nginx** and **HTTPS** for production reliability.

---

## Tech Stack

### Backend
- Django (Python)
- Django ORM
- REST-ready architecture

### Database
- PostgreSQL

### DevOps / Deployment
- Docker & Docker Compose
- Nginx (reverse proxy)
- Gunicorn (WSGI server)
- DigitalOcean Droplet

### Frontend
- Django Templates
- HTML, CSS, JavaScript
- Bootstrap / Tailwind CSS

### Configuration
- `.env`-based environment variables

---

## Features

### User System
- Role-based accounts (Client & Therapist)
- Secure login, registration & logout
- Profile management

### Therapist Module
- Specialization-based profile
- Availability setup
- Appointment management dashboard

### Booking System
- Therapist availability checking
- Appointment booking & cancellation
- Status tracking

### Dashboards
- Client dashboard for managing sessions
- Therapist dashboard for viewing appointments

### Security
- HTTPS-enabled deployment
- Environment-based settings
- Secure user data handling

---

## 📁 Project Structure

```bash
MindEase/
├── Mind_Ease/            # Django project (settings, urls, wsgi)
├── accounts/             # Authentication & user management
├── bookings/             # Booking and scheduling logic
├── client/               # Client-side views, dashboard
├── therapists/           # Therapist-side portal, dashboard
├── home/                 # Landing page, homepage
├── resources/            # Static resource pages
├── templates/            # HTML templates
├── media/                # Uploaded files
│
├── deploy/
│   └── nginx/            # Production Nginx configs
│
├── scripts/              # Helper scripts (optional)
├── Dockerfile.prod       # Production Dockerfile
├── docker-compose.yml    # Docker services
├── requirements.txt      # Python dependencies
├── manage.py             # Django admin utility
├── .env                  # Environment variables (ignored)
└── README.md             # Project documentation
```
---

## ⚙️ Setup Instructions
1️⃣ Clone the repository
```
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```
2️⃣ Create a virtual environment
```
python -m venv venv
source venv/bin/activate      # Linux / Mac
venv\Scripts\activate         # Windows
```
3️⃣ Install requirements
```
pip install -r requirements.txt
```
4️⃣ Apply migrations
```
python manage.py migrate
```
5️⃣ Create a superuser
```
python manage.py createsuperuser
```
6️⃣ Run development server
```
python manage.py runserver
```
## ▶️ API Routes Visit:

Frontend:
http://127.0.0.1:8000/

Admin Panel:
http://127.0.0.1:8000/admin/

