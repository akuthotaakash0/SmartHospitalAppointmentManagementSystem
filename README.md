# 🏥 Smart Hospital Appointment Management System

A full-stack healthcare web application built with **Flask**, **Pandas**, and **Bootstrap 5**, featuring **Clerk authentication**, a patient scheduling system, doctor directory, real-time in-app and email notifications, and an administrative control panel.

---

## ✨ Features

- **Patient Portal**:
  - Secure patient registration and authentication with cryptographic password hashing (`werkzeug.security`).
  - **Clerk SSO integration** — sign in/sign up with Google, GitHub, email, or magic links via [Clerk](https://clerk.com). Falls back to classic email/password when Clerk is not configured.
  - Specialist doctor directory (Cardiology, Dermatology, Orthopedics, Gynecology, Dentistry, etc.).
  - Appointment scheduling with automatic date validation.
  - Appointment history view with status tracking and patient-initiated appointment cancellation.
  - In-app notification alerts with one-click dismissal.
  - Automatic email notifications for account welcome, appointment booking, and cancellations.

- **Admin Control Panel**:
  - Protected admin portal with session authentication.
  - Doctor management: Add new specialists, edit doctor details, and remove doctors.
  - Centralized appointments dashboard with administrative cancellation capabilities (automatically alerts patient via in-app and email notification).
  - Admin master password update interface.

- **Cloud & Serverless Ready**:
  - Vercel Serverless Function entrypoint (`api/index.py`) and configuration (`vercel.json`).
  - Dynamic `DATA_DIR` path resolution for read-only serverless filesystems (`/tmp`).
  - Automatic seed initialization for zero-config deployments.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9+ installed
- Git

### 2. Installation
Clone the repository and install required packages:
```bash
git clone https://github.com/akuthotaakash0/SmartHospitalAppointmentManagementSystem.git
cd SmartHospitalAppointmentManagementSystem
pip install -r requirements.txt
```

### 3. Environment Variables (Optional)
Copy `.env.example` to `.env` to configure authentication, email alerts, or customize secrets:
```env
SECRET_KEY=your-random-secret-key
FLASK_DEBUG=False

# Clerk Authentication (Optional — classic login works without it)
# Get keys from https://dashboard.clerk.com → Your App → API Keys
CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
CLERK_SECRET_KEY=sk_test_xxxxx
CLERK_AUTHORIZED_PARTIES=http://localhost:5000,https://your-app.vercel.app

# Email Configuration (Optional - simulated in console if not set)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-hospital-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=noreply@hospital.com
```

> **Note:** If `CLERK_SECRET_KEY` is not set, the app runs in "legacy" mode with only email/password auth. The Clerk "Sign in with Clerk" button only appears when the publishable key is configured.

### 4. Run Locally
```bash
python app.py
```
Visit `http://localhost:5000` in your web browser.

**Default Administrator Credentials**:
- **Username / Email**: `admin` or `admin@hospital.com`
- **Password**: `admin123`

---

## 🧪 Running Automated Tests

Run the complete test suite with Python's built-in unittest framework:
```bash
python -m unittest discover tests
```

Tests cover:
- Home & health check routes
- User registration & path resolution across directories
- Duplicate email prevention
- Authentication & protected route redirects
- Appointment booking & patient cancellation workflow
- Admin doctor CRUD & administrative appointment cancellation

---

## ☁️ Deployment Guide

### Deploying to GitHub
```bash
git add .
git commit -m "Complete Smart Hospital Management System with Vercel deployment configuration"
git push origin main
```

### Deploying to Vercel
1. Go to [vercel.com](https://vercel.com) and log in.
2. Click **"Add New Project"** and select **"Import Git Repository"**.
3. Choose the `SmartHospitalAppointmentManagementSystem` repository.
4. Framework Preset: **Other** (Vercel automatically detects `vercel.json` and `api/index.py`).
5. (Optional) Under **Environment Variables**, add:
   - `SECRET_KEY`
   - `CLERK_PUBLISHABLE_KEY` (optional — enables Clerk SSO)
   - `CLERK_SECRET_KEY` (optional — enables Clerk SSO)
   - `CLERK_AUTHORIZED_PARTIES` (set to your Vercel URL, e.g. `https://your-app.vercel.app`)
   - `MAIL_USERNAME` (optional)
   - `MAIL_PASSWORD` (optional)
6. Click **Deploy**. Vercel will build and host the application globally.

---

## 📁 Project Structure

```
├── api/
│   └── index.py             # Vercel serverless WSGI entrypoint
├── static/
│   ├── hospital.jpg         # Hospital banner image
│   └── styles.css           # Healthcare design system & custom CSS
├── templates/
│   ├── index.html           # Landing page
│   ├── login.html           # User login portal (+ Clerk SSO)
│   ├── register.html        # Patient registration (+ Clerk sign-up)
│   ├── clerk_callback.html  # Clerk OAuth callback handler
│   ├── dashboard.html       # Patient dashboard & specialists
│   ├── book.html            # Appointment booking
│   ├── history.html         # Patient appointment history
│   ├── admin_login.html     # Admin authentication
│   ├── admin_dashboard.html # Admin control center
│   ├── change_admin_password.html
│   └── edit_doctor.html     # Doctor editing form
├── tests/
│   ├── test_registration.py # Working directory & registration tests
│   └── test_app.py          # End-to-end integration test suite
├── app.py                   # Main Flask application & routes
├── clerk_auth.py            # Clerk backend JWT verification & helpers
├── appointments.csv         # Appointments database
├── doctors.csv              # Doctors database
├── notifications.csv        # Notifications database
├── users.csv                # Users & admin credentials database
├── requirements.txt         # Python dependencies
├── vercel.json              # Vercel routing configuration
└── README.md                # Documentation
```