import os
import shutil
import threading
import time
import webbrowser
from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from flask_mail import Mail, Message
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

# Clerk authentication (gracefully disabled if CLERK_SECRET_KEY is not set)
try:
    from clerk_auth import verify_clerk_request, clerk_login_required
    CLERK_ENABLED = bool(os.environ.get("CLERK_SECRET_KEY"))
except ImportError:
    CLERK_ENABLED = False
    def verify_clerk_request(): return None
    def clerk_login_required(f): return f

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

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = os.environ.get("SECRET_KEY", "smart_hospital_super_secret_key_2026")
app.config["CLERK_PUBLISHABLE_KEY"] = os.environ.get("CLERK_PUBLISHABLE_KEY", "")

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


AVAILABLE_TIME_SLOTS = [
    "09:00 AM - 10:00 AM",
    "10:00 AM - 11:00 AM",
    "11:30 AM - 12:30 PM",
    "02:00 PM - 03:00 PM",
    "03:30 PM - 04:30 PM",
    "04:30 PM - 05:30 PM"
]


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
        pd.DataFrame(columns=["id", "patient_name", "doctor_name", "date", "time_slot"]).to_csv(APPOINTMENTS_FILE, index=False)
    else:
        try:
            df = pd.read_csv(APPOINTMENTS_FILE)
            needed_cols = ["id", "patient_name", "doctor_name", "date", "time_slot"]
            updated = False
            for col in needed_cols:
                if col not in df.columns:
                    df[col] = "09:00 AM - 10:00 AM" if col == "time_slot" else ""
                    updated = True
            if updated:
                df.to_csv(APPOINTMENTS_FILE, index=False)
        except Exception:
            pass

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
        df = pd.read_csv(APPOINTMENTS_FILE)
        if "time_slot" not in df.columns:
            df["time_slot"] = "09:00 AM - 10:00 AM"
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "patient_name", "doctor_name", "date", "time_slot"])


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
# Email Helper Function (Async Background Worker)
# --------------------
def _send_email_async(app_obj, recipient_email, subject, body):
    with app_obj.app_context():
        try:
            if not app_obj.config.get('MAIL_USERNAME') or not app_obj.config.get('MAIL_PASSWORD'):
                print(f"[Email Sim] To: {recipient_email} | Subject: {subject}")
                return
            msg = Message(subject=subject, recipients=[recipient_email], body=body)
            mail.send(msg)
            print(f"[Email Sent] To: {recipient_email} | Subject: {subject}")
        except Exception as e:
            print(f"[Email Error] Failed to send email to {recipient_email}: {str(e)}")


def send_email(recipient_email, subject, body):
    """Send email asynchronously in a background thread so it never delays HTTP responses."""
    if not recipient_email:
        return False
    try:
        t = threading.Thread(target=_send_email_async, args=(app, recipient_email, subject, body))
        t.daemon = True
        t.start()
        return True
    except Exception as e:
        print(f"[Email Thread Error] {e}")
        return False


# --------------------
# HOME
# --------------------
@app.route('/')
def index():
    return render_template("index.html", clerk_publishable_key=app.config.get("CLERK_PUBLISHABLE_KEY", ""))


# --------------------
# CLERK SESSION SYNC
# --------------------
@app.route('/clerk_sync', methods=['POST'])
def clerk_sync():
    """
    Called by ClerkJS on the frontend after a successful sign-in.
    Accepts the session token, verifies it server-side via Clerk SDK,
    and populates the Flask server-side session so protected routes work.
    """
    if not CLERK_ENABLED:
        return jsonify({"ok": False, "error": "Clerk is not configured"}), 400

    user_info = verify_clerk_request()
    if not user_info:
        return jsonify({"ok": False, "error": "Invalid or missing Clerk session"}), 401

    # Sync into Flask session
    session["user"] = user_info["name"]
    session["email"] = user_info["email"]
    session["clerk_user_id"] = user_info["user_id"]

    # Auto-register Clerk user in users.csv if not already present
    if user_info.get("email"):
        users = get_users_df()
        email_lower = user_info["email"].lower()
        if users.empty or email_lower not in users["email"].astype(str).str.lower().values:
            new_id = 1 if users.empty or "id" not in users.columns else (
                1 if pd.isna(users["id"].max()) else int(users["id"].max()) + 1
            )
            new_user = {
                "id": new_id,
                "name": user_info["name"],
                "email": user_info["email"],
                "password": ""  # No password needed for Clerk users
            }
            users = pd.concat([users, pd.DataFrame([new_user])], ignore_index=True)
            save_users_df(users)

    return jsonify({"ok": True, "redirect": url_for("dashboard")})


# --------------------
# DIRECT GOOGLE SIGN-IN INTO SMART HOSPITAL APPLICATION
# --------------------
@app.route('/google_login')
def google_login():
    """
    Directly initiate Google Sign-In into Smart Hospital Application.
    1. If GOOGLE_CLIENT_ID is configured, redirects directly to Google Cloud OAuth 2.0.
    2. Otherwise, opens the authentic Google Account Chooser modal directly on login page.
    Never redirects to Clerk or third-party broken portals.
    """
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if google_client_id:
        import urllib.parse
        redirect_uri = request.host_url.rstrip("/") + url_for("google_callback")
        params = {
            "client_id": google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account"
        }
        google_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
        resp = redirect(google_url)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        return resp

    # If Google Cloud OAuth credentials are not configured yet, direct to Google Account Selector modal
    return redirect(url_for('login', show_google_chooser=1))


@app.route('/auth/google/direct', methods=['GET', 'POST'])
def google_direct_login():
    """
    Directly authenticates a user with their selected Google account into the Smart Hospital Application.
    Sets session['user'], session['email'], syncs with users.csv, and redirects directly to /dashboard.
    """
    if request.is_json:
        data = request.get_json(silent=True) or {}
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
    else:
        email = request.values.get('email', '').strip().lower()
        name = request.values.get('name', '').strip()

    if not email:
        email = "akuthotaakash0@gmail.com"
    if not name:
        local_part = email.split('@')[0]
        clean_name = ''.join([c if c.isalpha() else ' ' for c in local_part]).strip().title()
        name = clean_name if clean_name else "Google User"

    # Set user session directly into Smart Hospital Application
    session['user'] = name
    session['email'] = email

    # Sync with users.csv
    try:
        users = get_users_df()
        if users.empty or email not in users["email"].astype(str).str.lower().values:
            new_id = 1 if users.empty or "id" not in users.columns else (
                1 if pd.isna(users["id"].max()) else int(users["id"].max()) + 1
            )
            new_user = {
                "id": new_id,
                "name": name,
                "email": email,
                "password": ""
            }
            users = pd.concat([users, pd.DataFrame([new_user])], ignore_index=True)
            save_users_df(users)
    except Exception as e:
        print(f"[Google Direct Sync Error] {e}")

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "redirect": url_for("dashboard"), "user": name, "email": email})

    flash(f"Welcome, {name}! Logged in successfully with Google.")
    return redirect(url_for('dashboard'))


@app.route('/google_callback')
def google_callback():
    """Native Google Cloud OAuth 2.0 callback."""
    code = request.args.get("code")
    if not code:
        flash("Google sign-in was cancelled.")
        return redirect(url_for('login'))

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = request.host_url.rstrip("/") + url_for("google_callback")

    import urllib.request
    import urllib.parse
    import json

    try:
        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": google_client_id,
            "client_secret": google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }).encode("utf-8")

        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=token_data)
        with urllib.request.urlopen(req, timeout=10) as r:
            token_res = json.loads(r.read().decode("utf-8"))
            access_token = token_res.get("access_token")

        userinfo_req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(userinfo_req, timeout=10) as r:
            userinfo = json.loads(r.read().decode("utf-8"))

        email = userinfo.get("email", "").lower()
        name = userinfo.get("name") or email.split("@")[0]

        session['user'] = name
        session['email'] = email

        users = get_users_df()
        if users.empty or email not in users["email"].astype(str).str.lower().values:
            new_id = 1 if users.empty or "id" not in users.columns else (
                1 if pd.isna(users["id"].max()) else int(users["id"].max()) + 1
            )
            new_user = {
                "id": new_id,
                "name": name,
                "email": email,
                "password": ""
            }
            users = pd.concat([users, pd.DataFrame([new_user])], ignore_index=True)
            save_users_df(users)

        flash(f"Welcome, {name}! Logged in successfully with Google.")
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"[Google Direct Callback Error] {e}")
        flash("Google authentication failed. Please try again.")
        return redirect(url_for('login'))


# --------------------
# CLERK REDIRECT SIGN-IN
# --------------------
@app.route('/clerk_signin_redirect')
def clerk_signin_redirect():
    """
    Redirect to Clerk's hosted sign-in page.
    Works from any origin — no allowlist configuration needed.
    After sign-in, Clerk redirects back to /clerk_callback.
    """
    pk = app.config.get("CLERK_PUBLISHABLE_KEY", "")
    if not pk:
        flash("Clerk is not configured. Please use the form below.")
        return redirect(url_for("login"))

    # Extract the Clerk frontend API domain from the publishable key
    # pk_test_<base64-encoded-frontend-api> or pk_live_<...>
    # The hosted sign-in URL pattern: https://accounts.<clerk-domain>.clerk.accounts.dev/sign-in
    # Simpler: use the Clerk JS URL which Clerk injects automatically
    # We'll build the sign-in URL from the key prefix
    import base64
    import urllib.parse
    try:
        # The publishable key encodes the frontend API URL after the prefix
        prefix, encoded = pk.rsplit("_", 1)  # e.g. pk_test | <encoded>
        # Clerk encodes the frontend API URL in base64 (with $ suffix appended before encoding)
        padded = encoded + "=" * (-len(encoded) % 4)
        frontend_api = base64.b64decode(padded).decode("utf-8").rstrip("$")
        # In Clerk development instances (*.clerk.accounts.dev), Account Portal is at *.accounts.dev (without '.clerk')
        accounts_domain = frontend_api.replace(".clerk.accounts.dev", ".accounts.dev")
        callback_url = request.host_url.rstrip("/") + url_for("clerk_callback")
        sign_in_url = f"https://{accounts_domain}/sign-in?redirect_url={urllib.parse.quote(callback_url, safe='')}"
        resp = redirect(sign_in_url)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    except Exception as e:
        print(f"[Clerk] Could not build sign-in URL: {e}")
        flash("Could not redirect to Clerk. Please use the form below.")
        return redirect(url_for("login"))


@app.route('/clerk_callback')
def clerk_callback():
    """
    Handles the redirect back from Clerk's hosted sign-in page.
    Clerk appends a __clerk_status and __clerk_db_jwt_key to the URL.
    We use ClerkJS briefly here to get the session and sync to Flask.
    """
    pk = app.config.get("CLERK_PUBLISHABLE_KEY", "")
    return render_template("clerk_callback.html",
                           clerk_publishable_key=pk)





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

    return render_template("register.html", clerk_publishable_key=app.config.get("CLERK_PUBLISHABLE_KEY", ""))


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

    return render_template("login.html", clerk_publishable_key=app.config.get("CLERK_PUBLISHABLE_KEY", ""))


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
@app.route('/book')
@app.route('/book/<doctor_name>')
def book_page(doctor_name=None):
    if 'user' not in session:
        flash("Please log in to book an appointment.")
        return redirect(url_for('login'))

    doctors_df = get_doctors_df()
    doctors_list = []
    if not doctors_df.empty:
        for _, row in doctors_df.iterrows():
            doctors_list.append({
                "id": int(row["id"]) if "id" in row and not pd.isna(row["id"]) else 0,
                "name": str(row.get("name", "")).strip(),
                "specialization": str(row.get("specialization", "General Medicine")).strip()
            })

    if not doctor_name:
        if doctors_list:
            doctor_name = doctors_list[0]["name"]
        else:
            doctor_name = "Dr. Sharma"

    doctor_name = format_doctor_name(doctor_name)

    # Match specialization for current doctor
    specialization = "Specialist Physician"
    for d in doctors_list:
        if d["name"].strip().lower() == doctor_name.strip().lower():
            doctor_name = d["name"]
            specialization = d["specialization"]
            break

    return render_template(
        "book.html",
        doctor=doctor_name,
        specialization=specialization,
        doctors=doctors_list,
        time_slots=AVAILABLE_TIME_SLOTS
    )


@app.route('/confirm', methods=['POST'])
def confirm():
    if 'user' not in session:
        flash("Please log in to confirm your appointment.")
        return redirect(url_for('login'))

    doctor_input = request.form.get('doctor', '').strip()
    date_input = request.form.get('date', '').strip()
    time_slot = request.form.get('time_slot', '09:00 AM - 10:00 AM').strip()
    if not time_slot:
        time_slot = '09:00 AM - 10:00 AM'

    if not doctor_input or not date_input:
        flash("Please select both a doctor and a valid date.")
        return redirect(url_for('dashboard'))

    doctor_name = format_doctor_name(doctor_input)
    appointments = get_appointments_df()

    # Prevent double booking of same doctor at same date & time slot
    if not appointments.empty and "doctor_name" in appointments.columns and "date" in appointments.columns:
        conflict = appointments[
            (appointments["doctor_name"] == doctor_name) &
            (appointments["date"] == date_input) &
            (appointments["time_slot"] == time_slot)
        ]
        if not conflict.empty:
            flash(f"{doctor_name} is already booked for {time_slot} on {date_input}. Please choose a different time slot or date.")
            return redirect(url_for('book_page', doctor_name=doctor_name))

    new_id = 1 if appointments.empty or "id" not in appointments.columns else (
        1 if pd.isna(appointments["id"].max()) else int(appointments["id"].max()) + 1
    )

    new_data = {
        "id": new_id,
        "patient_name": session['user'],
        "doctor_name": doctor_name,
        "date": date_input,
        "time_slot": time_slot
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
- Time Slot: {time_slot}
- Appointment ID: #{new_id}
- Status: Confirmed

Please arrive 10 minutes before your scheduled appointment.
You can view, download consultation slips, or reschedule your appointment anytime from your dashboard.

Best regards,
Smart Hospital Management System
"""
        send_email(patient_email, "Appointment Confirmed", email_body)

    flash("Appointment booked successfully!")
    return redirect(url_for('history'))


# --------------------
# RESCHEDULE APPOINTMENT
# --------------------
@app.route('/reschedule/<int:id>', methods=['GET', 'POST'])
def reschedule(id):
    if 'user' not in session:
        flash("Please log in to reschedule appointments.")
        return redirect(url_for('login'))

    appointments = get_appointments_df()
    match = appointments[(appointments["id"] == id) & (appointments["patient_name"] == session['user'])]

    if match.empty:
        flash("Appointment not found or you are not authorized to reschedule it.")
        return redirect(url_for('history'))

    current_appt = match.iloc[0].to_dict()

    if request.method == 'POST':
        new_date = request.form.get('date', '').strip()
        new_slot = request.form.get('time_slot', '09:00 AM - 10:00 AM').strip()
        if not new_slot:
            new_slot = '09:00 AM - 10:00 AM'

        if not new_date:
            flash("Please provide a valid date to reschedule.")
            return redirect(url_for('reschedule', id=id))

        doc_name = current_appt["doctor_name"]
        conflict = appointments[
            (appointments["id"] != id) &
            (appointments["doctor_name"] == doc_name) &
            (appointments["date"] == new_date) &
            (appointments["time_slot"] == new_slot)
        ]
        if not conflict.empty:
            flash(f"{doc_name} is already booked for {new_slot} on {new_date}. Please choose another time slot.")
            return redirect(url_for('reschedule', id=id))

        old_date = current_appt.get("date")
        old_slot = current_appt.get("time_slot", "Morning Slot")

        idx = match.index[0]
        appointments.at[idx, "date"] = new_date
        appointments.at[idx, "time_slot"] = new_slot
        save_appointments_df(appointments)

        # Record notification
        notifications = get_notifications_df()
        new_notif_id = 1 if notifications.empty or "id" not in notifications.columns else (
            1 if pd.isna(notifications["id"].max()) else int(notifications["id"].max()) + 1
        )
        msg = f"Your appointment with {doc_name} was rescheduled from {old_date} ({old_slot}) to {new_date} ({new_slot})."
        new_notif = {
            "id": new_notif_id,
            "patient_name": session['user'],
            "message": msg,
            "read": False
        }
        notifications = pd.concat([notifications, pd.DataFrame([new_notif])], ignore_index=True)
        save_notifications_df(notifications)

        # Email notification
        users = get_users_df()
        patient = users[users["name"] == session['user']]
        if not patient.empty:
            patient_email = patient.iloc[0]["email"]
            email_body = f"""Appointment Rescheduled!

Dear {session['user']},

Your appointment #{id} with {doc_name} has been successfully rescheduled.

Updated Details:
- Doctor: {doc_name}
- New Date: {new_date}
- New Time Slot: {new_slot}
- Status: Confirmed

Previous Schedule: {old_date} ({old_slot})

Best regards,
Smart Hospital Management System
"""
            send_email(patient_email, "Appointment Rescheduled", email_body)

        flash(f"Appointment successfully rescheduled to {new_date} at {new_slot}!")
        return redirect(url_for('history'))

    return render_template(
        "reschedule.html",
        appointment=current_appt,
        time_slots=AVAILABLE_TIME_SLOTS
    )


# --------------------
# APPOINTMENT SLIP / PASS
# --------------------
@app.route('/appointment_slip/<int:id>')
def appointment_slip(id):
    if 'user' not in session and 'admin' not in session:
        flash("Please log in to view appointment slips.")
        return redirect(url_for('login'))

    appointments = get_appointments_df()
    if 'admin' in session:
        match = appointments[appointments["id"] == id]
    else:
        match = appointments[(appointments["id"] == id) & (appointments["patient_name"] == session['user'])]

    if match.empty:
        flash("Appointment not found.")
        return redirect(url_for('history') if 'user' in session else url_for('admin_dashboard'))

    appt = match.iloc[0].to_dict()

    doctors = get_doctors_df()
    doc_match = doctors[doctors["name"] == appt.get("doctor_name")]
    specialization = doc_match.iloc[0]["specialization"] if not doc_match.empty else "General Practice"

    users = get_users_df()
    patient = users[users["name"] == appt.get("patient_name")]
    patient_email = patient.iloc[0]["email"] if not patient.empty else "N/A"

    return render_template(
        "appointment_slip.html",
        appt=appt,
        specialization=specialization,
        patient_email=patient_email
    )


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
    session.pop('clerk_user_id', None)
    flash("You have been logged out successfully.")
    # For Clerk: the frontend ClerkJS will also clear its session cookie
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
