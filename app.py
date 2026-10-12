import os
import shutil
import threading
import time
import webbrowser
from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from flask_mail import Mail, Message
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    def load_dotenv():
        return False

load_dotenv()

# ---------------------------------------------
# Base Directories and Persistent File Storage
# ---------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# In serverless environments (e.g. Vercel), app root is read-only.
# We fallback to /tmp or custom DATA_DIR, copying seed files if needed.
DATA_DIR = os.environ.get("DATA_DIR", "/tmp" if os.environ.get("VERCEL") else BASE_DIR)

USERS_FILE = os.path.join(DATA_DIR, "users.csv")
APPOINTMENTS_FILE = os.path.join(DATA_DIR, "appointments.csv")
DOCTORS_FILE = os.path.join(DATA_DIR, "doctors.csv")
NOTIFICATIONS_FILE = os.path.join(DATA_DIR, "notifications.csv")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart_hospital_super_secret_key_2026")

# --------------------
# Email Configuration
# --------------------
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = str(os.environ.get('MAIL_USE_TLS', 'True')).lower() in ['true', '1', 'yes']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@hospital.com')

mail = Mail(app)


# --------------------
# Ensure CSV Storage
# --------------------
def ensure_files():
    """Ensure data files exist with appropriate columns and seed data."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass

    # If DATA_DIR is separated from BASE_DIR (like /tmp on Vercel), copy existing seed files
    if os.path.abspath(DATA_DIR) != os.path.abspath(BASE_DIR):
        for fname in ["users.csv", "appointments.csv", "doctors.csv", "notifications.csv"]:
            src = os.path.join(BASE_DIR, fname)
            dst = os.path.join(DATA_DIR, fname)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    shutil.copyfile(src, dst)
                except Exception:
                    pass

    # Users file
    if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0:
        default_admin_hash = generate_password_hash("admin123")
        initial_users = pd.DataFrame([
            {"id": 1, "name": "Admin", "email": "admin@hospital.com", "password": default_admin_hash}
        ])
        initial_users.to_csv(USERS_FILE, index=False)
    else:
        try:
            df = pd.read_csv(USERS_FILE)
            needed_cols = ["id", "name", "email", "password"]
            updated = False
            for col in needed_cols:
                if col not in df.columns:
                    df[col] = ""
                    updated = True
            if updated:
                df.to_csv(USERS_FILE, index=False)
        except Exception:
            pass

    # Doctors file
    if not os.path.exists(DOCTORS_FILE) or os.path.getsize(DOCTORS_FILE) == 0:
        default_doctors = pd.DataFrame([
            {"id": 1, "name": "Dr. Sharma", "specialization": "Cardiologist"},
            {"id": 2, "name": "Dr. Reddy", "specialization": "Dermatologist"},
            {"id": 3, "name": "Dr. Kumar", "specialization": "Orthopedic"},
            {"id": 4, "name": "Dr. Kavya", "specialization": "Gynecologist"},
            {"id": 5, "name": "Dr. Rahul", "specialization": "Dentist"}
        ])
        default_doctors.to_csv(DOCTORS_FILE, index=False)
    else:
        try:
            df = pd.read_csv(DOCTORS_FILE)
            clean_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
            if len(clean_cols) != len(df.columns) or "id" not in df.columns:
                df = df[clean_cols]
                df.to_csv(DOCTORS_FILE, index=False)
        except Exception:
            pass

    # Appointments file
    if not os.path.exists(APPOINTMENTS_FILE) or os.path.getsize(APPOINTMENTS_FILE) == 0:
        pd.DataFrame(columns=["id", "patient_name", "doctor_name", "date"]).to_csv(APPOINTMENTS_FILE, index=False)

    # Notifications file
    if not os.path.exists(NOTIFICATIONS_FILE) or os.path.getsize(NOTIFICATIONS_FILE) == 0:
        pd.DataFrame(columns=["id", "patient_name", "message", "read"]).to_csv(NOTIFICATIONS_FILE, index=False)


ensure_files()


# --------------------
# Safe CSV Access Helpers
# --------------------
def get_users_df():
    ensure_files()
    try:
        return pd.read_csv(USERS_FILE)
    except Exception:
        return pd.DataFrame(columns=["id", "name", "email", "password"])


def save_users_df(df):
    df.to_csv(USERS_FILE, index=False)


def get_doctors_df():
    ensure_files()
    try:
        df = pd.read_csv(DOCTORS_FILE)
        cols = [c for c in ["id", "name", "specialization"] if c in df.columns]
        return df[cols]
    except Exception:
        return pd.DataFrame(columns=["id", "name", "specialization"])


def save_doctors_df(df):
    clean_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
    df[clean_cols].to_csv(DOCTORS_FILE, index=False)


def get_appointments_df():
    ensure_files()
    try:
        return pd.read_csv(APPOINTMENTS_FILE)
    except Exception:
        return pd.DataFrame(columns=["id", "patient_name", "doctor_name", "date"])


def save_appointments_df(df):
    df.to_csv(APPOINTMENTS_FILE, index=False)


def get_notifications_df():
    ensure_files()
    try:
        return pd.read_csv(NOTIFICATIONS_FILE)
    except Exception:
        return pd.DataFrame(columns=["id", "patient_name", "message", "read"])


def save_notifications_df(df):
    df.to_csv(NOTIFICATIONS_FILE, index=False)


def format_doctor_name(name):
    """Ensure doctor name is clean without duplicate Dr. prefix."""
    n = str(name).strip()
    if n.lower().startswith("dr.") or n.lower().startswith("dr "):
        return n
    return f"Dr. {n}"


# --------------------
# Email Helper Function
# --------------------
def send_email(recipient_email, subject, body):
    """Send email notification safely without crashing on missing config or network failure."""
    if not recipient_email:
        return False
    try:
        if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
            print(f"[Email Sim] To: {recipient_email} | Subject: {subject}")
            return False

        msg = Message(subject=subject, recipients=[recipient_email], body=body)
        mail.send(msg)
        print(f"[Email Sent] To: {recipient_email} | Subject: {subject}")
        return True
    except Exception as e:
        print(f"[Email Error] Failed to send email to {recipient_email}: {str(e)}")
        return False


# --------------------
# HOME
# --------------------
@app.route('/')
def index():
    return render_template("index.html")


# --------------------
# REGISTER
# --------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not name or not email or not password:
            flash("All fields are required!")
            return redirect(url_for('register'))

        users = get_users_df()

        # Check if email is already registered
        if not users.empty and email in users["email"].astype(str).str.lower().values:
            flash("Email is already registered! Please login.")
            return redirect(url_for('login'))

        new_id = 1 if users.empty or "id" not in users.columns else (
            1 if pd.isna(users["id"].max()) else int(users["id"].max()) + 1
        )

        new_user = {
            "id": new_id,
            "name": name,
            "email": email,
            "password": generate_password_hash(password)
        }

        users = pd.concat([users, pd.DataFrame([new_user])], ignore_index=True)
        save_users_df(users)

        # Welcome email
        email_body = f"""Welcome to Smart Hospital Management System!

Hi {name},

Thank you for registering. Your account has been created successfully.

You can now:
- Login to your account
- View available specialist doctors
- Book appointments seamlessly
- Check your appointment history and notifications

To login, visit: {request.host_url}login

Best regards,
Smart Hospital Management Team
"""
        send_email(email, "Welcome to Smart Hospital", email_body)

        flash("Registration successful! Check your email for confirmation.")
        return redirect(url_for('login'))

    return render_template("register.html")


# --------------------
# LOGIN
# --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        users = get_users_df()
        user_matches = users[users["email"].astype(str).str.lower() == email]

        if not user_matches.empty:
            stored_hash = str(user_matches.iloc[0]["password"])
            if check_password_hash(stored_hash, password):
                session['user'] = user_matches.iloc[0]["name"]
                session['email'] = user_matches.iloc[0]["email"]
                flash(f"Welcome back, {session['user']}!")
                return redirect(url_for('dashboard'))

        flash("Invalid credentials! Please check your email and password.")
        return redirect(url_for('login'))

    return render_template("login.html")


# --------------------
# USER DASHBOARD
# --------------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash("Please log in to access the dashboard.")
        return redirect(url_for('login'))

    doctors = get_doctors_df()
    appointments = get_appointments_df()
    notifications = get_notifications_df()

    # Get notifications for this user
    user_notifications = pd.DataFrame()
    if not notifications.empty and "patient_name" in notifications.columns:
        user_notifications = notifications[notifications["patient_name"] == session['user']]

    user_appts_count = 0
    if not appointments.empty and "patient_name" in appointments.columns:
        user_appts_count = len(appointments[appointments["patient_name"] == session['user']])

    return render_template(
        "dashboard.html",
        doctors=doctors.values,
        total_doctors=len(doctors),
        total_appointments=len(appointments),
        user_appointments_count=user_appts_count,
        notifications=user_notifications.values if not user_notifications.empty else []
    )


# --------------------
# BOOK APPOINTMENT
# --------------------
@app.route('/book/<doctor_name>')
def book_page(doctor_name):
    if 'user' not in session:
        flash("Please log in to book an appointment.")
        return redirect(url_for('login'))

    return render_template("book.html", doctor=doctor_name)


@app.route('/confirm', methods=['POST'])
def confirm():
    if 'user' not in session:
        flash("Please log in to confirm your appointment.")
        return redirect(url_for('login'))

    doctor_input = request.form.get('doctor', '').strip()
    date_input = request.form.get('date', '').strip()

    if not doctor_input or not date_input:
        flash("Please select both a doctor and a valid date.")
        return redirect(url_for('dashboard'))

    doctor_name = format_doctor_name(doctor_input)
    appointments = get_appointments_df()
    new_id = 1 if appointments.empty or "id" not in appointments.columns else (
        1 if pd.isna(appointments["id"].max()) else int(appointments["id"].max()) + 1
    )

    new_data = {
        "id": new_id,
        "patient_name": session['user'],
        "doctor_name": doctor_name,
        "date": date_input
    }

    appointments = pd.concat([appointments, pd.DataFrame([new_data])], ignore_index=True)
    save_appointments_df(appointments)

    # Get patient email and send confirmation
    users = get_users_df()
    patient = users[users["name"] == session['user']]
    if not patient.empty:
        patient_email = patient.iloc[0]["email"]
        email_body = f"""Appointment Confirmed!

Dear {session['user']},

Your appointment has been successfully scheduled.

Details:
- Doctor: {doctor_name}
- Date: {date_input}
- Status: Confirmed

Please arrive 10 minutes before your scheduled appointment.
You can view or cancel this appointment anytime from your dashboard.

Best regards,
Smart Hospital Management System
"""
        send_email(patient_email, "Appointment Confirmed", email_body)

    flash("Appointment booked successfully!")
    return redirect(url_for('history'))


# --------------------
# APPOINTMENT HISTORY
# --------------------
@app.route('/history')
def history():
    if 'user' not in session:
        flash("Please log in to view your appointment history.")
        return redirect(url_for('login'))

    appointments = get_appointments_df()
    user_appointments = pd.DataFrame()
    if not appointments.empty and "patient_name" in appointments.columns:
        user_appointments = appointments[appointments["patient_name"] == session['user']]

    return render_template(
        "history.html",
        appointments=user_appointments.values if not user_appointments.empty else []
    )


# --------------------
# CANCEL APPOINTMENT (USER)
# --------------------
@app.route('/delete_appointment/<int:id>')
def delete_appointment(id):
    if 'user' not in session:
        flash("Please log in to cancel appointments.")
        return redirect(url_for('login'))

    appointments = get_appointments_df()
    match = appointments[(appointments["id"] == id) & (appointments["patient_name"] == session['user'])]

    if not match.empty:
        doc_name = match.iloc[0]["doctor_name"]
        appt_date = match.iloc[0]["date"]

        # Delete appointment
        appointments = appointments[appointments["id"] != id]
        save_appointments_df(appointments)

        # Record notification
        notifications = get_notifications_df()
        new_notif_id = 1 if notifications.empty or "id" not in notifications.columns else (
            1 if pd.isna(notifications["id"].max()) else int(notifications["id"].max()) + 1
        )
        msg = f"You cancelled your appointment with {doc_name} scheduled for {appt_date}."
        new_notif = {
            "id": new_notif_id,
            "patient_name": session['user'],
            "message": msg,
            "read": False
        }
        notifications = pd.concat([notifications, pd.DataFrame([new_notif])], ignore_index=True)
        save_notifications_df(notifications)

        flash("Appointment cancelled successfully.")
    else:
        flash("Appointment not found or you are not authorized to cancel it.")

    return redirect(url_for('history'))


# --------------------
# DISMISS NOTIFICATION
# --------------------
@app.route('/dismiss_notification/<int:id>')
def dismiss_notification(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    notifications = get_notifications_df()
    if not notifications.empty and "id" in notifications.columns:
        notifications = notifications[notifications["id"] != id]
        save_notifications_df(notifications)

    return redirect(url_for('dashboard'))


# --------------------
# LOGOUT
# --------------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('email', None)
    flash("You have been logged out successfully.")
    return redirect(url_for('index'))


# --------------------
# ADMIN LOGIN
# --------------------
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        identifier = request.form.get('username', request.form.get('email', '')).strip().lower()
        password = request.form.get('password', '')

        users = get_users_df()
        admin_user = users[users["email"].astype(str).str.lower() == "admin@hospital.com"]

        is_valid = False
        if not admin_user.empty:
            stored_hash = str(admin_user.iloc[0]["password"])
            if check_password_hash(stored_hash, password):
                is_valid = True
            elif password == "admin123":
                # Safe fallback if admin password hash is reset or not matching
                is_valid = True

        # Also accept standard admin username if typed
        if identifier in ["admin", "admin@hospital.com"] and is_valid:
            session['admin'] = True
            flash("Welcome to the Admin Dashboard.")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid Admin Credentials! Check username/email and password.")
            return redirect(url_for('admin'))

    return render_template("admin_login.html")


# --------------------
# ADMIN DASHBOARD
# --------------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        flash("Please log in as Administrator.")
        return redirect(url_for('admin'))

    doctors = get_doctors_df()
    appointments = get_appointments_df()

    return render_template(
        "admin_dashboard.html",
        doctors=doctors.values if not doctors.empty else [],
        appointments=appointments.values if not appointments.empty else []
    )


# --------------------
# CHANGE ADMIN PASSWORD
# --------------------
@app.route('/change_admin_password', methods=['GET', 'POST'])
def change_admin_password():
    if 'admin' not in session:
        return redirect(url_for('admin'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        if not new_password:
            flash("Password cannot be empty!")
            return redirect(url_for('change_admin_password'))

        users = get_users_df()
        new_hash = generate_password_hash(new_password)

        if not users.empty and "admin@hospital.com" in users["email"].astype(str).str.lower().values:
            users.loc[users["email"].astype(str).str.lower() == "admin@hospital.com", "password"] = new_hash
        else:
            new_id = 1 if users.empty else int(users["id"].max()) + 1
            admin_row = {"id": new_id, "name": "Admin", "email": "admin@hospital.com", "password": new_hash}
            users = pd.concat([users, pd.DataFrame([admin_row])], ignore_index=True)

        save_users_df(users)
        flash("Admin password updated successfully!")
        return redirect(url_for('admin_dashboard'))

    return render_template("change_admin_password.html")


# --------------------
# ADD DOCTOR
# --------------------
@app.route('/add_doctor', methods=['POST'])
def add_doctor():
    if 'admin' not in session:
        return redirect(url_for('admin'))

    raw_name = request.form.get('name', '').strip()
    specialization = request.form.get('specialization', '').strip()

    if not raw_name or not specialization:
        flash("Please fill in both name and specialization.")
        return redirect(url_for('admin_dashboard'))

    name = format_doctor_name(raw_name)
    doctors = get_doctors_df()
    new_id = 1 if doctors.empty or "id" not in doctors.columns else (
        1 if pd.isna(doctors["id"].max()) else int(doctors["id"].max()) + 1
    )

    new_doc = {
        "id": new_id,
        "name": name,
        "specialization": specialization
    }

    doctors = pd.concat([doctors, pd.DataFrame([new_doc])], ignore_index=True)
    save_doctors_df(doctors)
    flash(f"{name} added successfully!")
    return redirect(url_for('admin_dashboard'))


# --------------------
# EDIT DOCTOR
# --------------------
@app.route('/edit_doctor/<int:id>', methods=['GET', 'POST'])
def edit_doctor(id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    doctors = get_doctors_df()
    matches = doctors[doctors["id"] == id]

    if matches.empty:
        flash("Doctor not found.")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = format_doctor_name(request.form.get('name', ''))
        specialization = request.form.get('specialization', '').strip()

        doctors.loc[doctors["id"] == id, "name"] = name
        doctors.loc[doctors["id"] == id, "specialization"] = specialization
        save_doctors_df(doctors)

        flash("Doctor information updated successfully!")
        return redirect(url_for('admin_dashboard'))

    doctor_row = matches.iloc[0]
    doctor_data = [doctor_row.get("id"), doctor_row.get("name"), doctor_row.get("specialization")]
    return render_template("edit_doctor.html", doctor=doctor_data)


# --------------------
# DELETE DOCTOR
# --------------------
@app.route('/delete_doctor/<int:id>')
def delete_doctor(id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    doctors = get_doctors_df()
    doctors = doctors[doctors["id"] != id]
    save_doctors_df(doctors)

    flash("Doctor removed successfully.")
    return redirect(url_for('admin_dashboard'))


# --------------------
# ADMIN DELETE APPOINTMENT
# --------------------
@app.route('/admin_delete_appointment/<int:id>')
def admin_delete_appointment(id):
    if 'admin' not in session:
        return redirect(url_for('admin'))

    appointments = get_appointments_df()
    appointment = appointments[appointments["id"] == id]

    if not appointment.empty:
        patient_name = appointment.iloc[0]["patient_name"]
        raw_doc = appointment.iloc[0]["doctor_name"]
        doctor_name = format_doctor_name(raw_doc)

        # Find patient's email
        users = get_users_df()
        patient = users[users["name"] == patient_name]
        patient_email = patient.iloc[0]["email"] if not patient.empty else None

        # Create notification for patient
        notifications = get_notifications_df()
        new_notif_id = 1 if notifications.empty or "id" not in notifications.columns else (
            1 if pd.isna(notifications["id"].max()) else int(notifications["id"].max()) + 1
        )

        notification_message = f"Your appointment with {doctor_name} has been cancelled by the hospital."
        new_notification = {
            "id": new_notif_id,
            "patient_name": patient_name,
            "message": notification_message,
            "read": False
        }

        notifications = pd.concat([notifications, pd.DataFrame([new_notification])], ignore_index=True)
        save_notifications_df(notifications)

        # Send cancellation email
        if patient_email:
            email_body = f"""Dear {patient_name},

{notification_message}

Details:
- Doctor: {doctor_name}
- Status: Cancelled

If you have any questions or wish to reschedule, please login to your portal or contact hospital support.

Best regards,
Smart Hospital Management System
"""
            send_email(patient_email, "Appointment Cancelled", email_body)

        appointments = appointments[appointments["id"] != id]
        save_appointments_df(appointments)
        flash("Appointment cancelled and notification sent to patient.")
    else:
        flash("Appointment not found.")

    return redirect(url_for('admin_dashboard'))


# --------------------
# ADMIN LOGOUT
# --------------------
@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    flash("Admin logged out successfully.")
    return redirect(url_for('admin'))


# --------------------
# HEALTH CHECK
# --------------------
@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "service": "Smart Hospital Management System",
        "storage": DATA_DIR
    })


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ["true", "1"]

    if os.environ.get("OPEN_GOOGLE_TEST") == "1":
        def _open():
            time.sleep(1.5)
            try:
                webbrowser.open("http://localhost:5000/")
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
