from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mail import Mail, Message
import pandas as pd
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # python-dotenv not installed; continue without loading a .env file
    def load_dotenv():
        return False
from werkzeug.security import generate_password_hash, check_password_hash

# load environment variables from .env (if present)
load_dotenv()
import threading
import time
import webbrowser

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# --------------------
# Email Configuration
# --------------------
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', True)
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@hospital.com')

mail = Mail(app)




# --------------------
# Ensure CSV files
# --------------------
def ensure_files():
    if not os.path.exists("users.csv"):
        pd.DataFrame(columns=["id","name","email","password"]).to_csv("users.csv", index=False)

    if not os.path.exists("appointments.csv"):
        pd.DataFrame(columns=["id","patient_name","doctor_name","date"]).to_csv("appointments.csv", index=False)

    if not os.path.exists("doctors.csv"):
        pd.DataFrame(columns=["id","name","specialization"]).to_csv("doctors.csv", index=False)

    if not os.path.exists("notifications.csv"):
        pd.DataFrame(columns=["id","patient_name","message","read"]).to_csv("notifications.csv", index=False)

ensure_files()


# --------------------
# Email Helper Function
# --------------------
def send_email(recipient_email, subject, body):
    """Send email notification to user"""
    try:
        if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
            print(f"Email not configured. Would send: {subject} to {recipient_email}")
            return False
        
        msg = Message(subject=subject, recipients=[recipient_email], body=body)
        mail.send(msg)
        print(f"Email sent to {recipient_email}: {subject}")
        return True
    except Exception as e:
        print(f"Failed to send email to {recipient_email}: {str(e)}")
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
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        users = pd.read_csv("users.csv")
        new_id = 1 if users.empty else users["id"].max() + 1

        new_user = {
            "id": new_id,
            "name": request.form['name'],
            "email": request.form['email'],
            "password": generate_password_hash(request.form['password'])
        }

        users = pd.concat([users, pd.DataFrame([new_user])])
        users.to_csv("users.csv", index=False)

        # Send welcome email
        email_body = f"""
Welcome to Smart Hospital Management System!

Hi {request.form['name']},

Thank you for registering. Your account has been created successfully.

You can now:
- Login to your account
- View available doctors
- Book appointments
- Check your appointment history

To login, visit: http://your-hospital.com/login

If you have any questions, please contact us.

Best regards,
Smart Hospital Management System
"""
        send_email(request.form['email'], "Welcome to Smart Hospital", email_body)

        flash("Registration successful! Check your email for confirmation.")
        return redirect('/login')

    return render_template("register.html")





# --------------------
# LOGIN
# --------------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        users = pd.read_csv("users.csv")
        user = users[users["email"] == request.form['email']]

        if not user.empty and check_password_hash(user.iloc[0]["password"], request.form['password']):
            session['user'] = user.iloc[0]["name"]
            return redirect('/dashboard')
        else:
            flash("Invalid credentials!")

    return render_template("login.html")









# --------------------
# USER DASHBOARD
# --------------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    doctors = pd.read_csv("doctors.csv")
    appointments = pd.read_csv("appointments.csv")
    notifications = pd.read_csv("notifications.csv")
    
    # Get unread notifications for this user
    user_notifications = notifications[notifications["patient_name"] == session['user']]

    return render_template("dashboard.html",
                           doctors=doctors.values,
                           total_doctors=len(doctors),
                           total_appointments=len(appointments),
                           notifications=user_notifications.values)


# --------------------
# BOOK
# --------------------
@app.route('/book/<doctor_name>')
def book_page(doctor_name):
    return render_template("book.html", doctor=doctor_name)


@app.route('/confirm', methods=['POST'])
def confirm():
    appointments = pd.read_csv("appointments.csv")
    new_id = 1 if appointments.empty else appointments["id"].max() + 1

    new_data = {
        "id": new_id,
        "patient_name": session['user'],
        "doctor_name": request.form['doctor'],
        "date": request.form['date']
    }

    appointments = pd.concat([appointments, pd.DataFrame([new_data])])
    appointments.to_csv("appointments.csv", index=False)

    # Get patient email and send confirmation
    users = pd.read_csv("users.csv")
    patient = users[users["name"] == session['user']]
    if not patient.empty:
        patient_email = patient.iloc[0]["email"]
        email_body = f"""
Appointment Confirmed!

Dear {session['user']},

Your appointment has been successfully booked.

Appointment Details:
- Doctor: Dr. {request.form['doctor']}
- Date: {request.form['date']}
- Status: Confirmed

Please arrive 10 minutes before your appointment time.

If you need to cancel or reschedule, please visit your dashboard.

Best regards,
Smart Hospital Management System
"""
        send_email(patient_email, "Appointment Confirmed", email_body)

    return redirect('/history')


# --------------------
# HISTORY
# --------------------
@app.route('/history')
def history():
    appointments = pd.read_csv("appointments.csv")
    user_appointments = appointments[appointments["patient_name"] == session['user']]

    return render_template("history.html",
                           appointments=user_appointments.values)


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


# --------------------
# ADMIN
# --------------------
@app.route('/admin', methods=['GET','POST'])
def admin():
    if request.method == 'POST':
        users = pd.read_csv("users.csv")

        admin_user = users[(users["email"]=="admin@hospital.com")]

        if not admin_user.empty and check_password_hash(
                admin_user.iloc[0]["password"],
                request.form['password']):

            session['admin'] = True
            return redirect('/admin_dashboard')
        else:
            flash("Invalid Admin Password")

    return render_template("admin_login.html")


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin')

    doctors = pd.read_csv("doctors.csv")
    appointments = pd.read_csv("appointments.csv")

    return render_template("admin_dashboard.html",
                           doctors=doctors.values,
                           appointments=appointments.values)


@app.route('/change_admin_password', methods=['GET','POST'])
def change_admin_password():
    if 'admin' not in session:
        return redirect('/admin')

    if request.method == 'POST':
        users = pd.read_csv("users.csv")

        new_password = generate_password_hash(request.form['new_password'])

        users.loc[users["email"]=="admin@hospital.com","password"] = new_password
        users.to_csv("users.csv", index=False)

        flash("Password updated successfully!")
        return redirect('/admin_dashboard')

    return render_template("change_admin_password.html")


@app.route('/add_doctor', methods=['POST'])
def add_doctor():
    doctors = pd.read_csv("doctors.csv")
    new_id = 1 if doctors.empty else doctors["id"].max()+1

    new_doc = {
        "id":new_id,
        "name":request.form['name'],
        "specialization":request.form['specialization']
    }

    doctors = pd.concat([doctors, pd.DataFrame([new_doc])])
    doctors.to_csv("doctors.csv", index=False)
    return redirect('/admin_dashboard')


@app.route('/edit_doctor/<int:id>', methods=['GET','POST'])
def edit_doctor(id):
    doctors = pd.read_csv("doctors.csv")

    if request.method=='POST':
        doctors.loc[doctors["id"]==id,"name"]=request.form['name']
        doctors.loc[doctors["id"]==id,"specialization"]=request.form['specialization']
        doctors.to_csv("doctors.csv", index=False)
        return redirect('/admin_dashboard')

    doctor = doctors[doctors["id"]==id].values[0]
    return render_template("edit_doctor.html", doctor=doctor)


@app.route('/delete_doctor/<int:id>')
def delete_doctor(id):
    doctors = pd.read_csv("doctors.csv")
    doctors = doctors[doctors["id"]!=id]
    doctors.to_csv("doctors.csv", index=False)
    return redirect('/admin_dashboard')

@app.route('/admin_delete_appointment/<int:id>')
def admin_delete_appointment(id):
    if 'admin' not in session:
        return redirect('/admin')

    appointments = pd.read_csv("appointments.csv")
    appointment = appointments[appointments["id"] == id]
    
    if not appointment.empty:
        patient_name = appointment.iloc[0]["patient_name"]
        doctor_name = appointment.iloc[0]["doctor_name"]
        
        # Get patient's email
        users = pd.read_csv("users.csv")
        patient = users[users["name"] == patient_name]
        patient_email = patient.iloc[0]["email"] if not patient.empty else None
        
        # Create notification for the patient
        notifications = pd.read_csv("notifications.csv")
        new_notif_id = 1 if notifications.empty else notifications["id"].max() + 1
        
        notification_message = f"Your appointment with Dr. {doctor_name} has been cancelled."
        new_notification = {
            "id": new_notif_id,
            "patient_name": patient_name,
            "message": notification_message,
            "read": False
        }
        
        notifications = pd.concat([notifications, pd.DataFrame([new_notification])])
        notifications.to_csv("notifications.csv", index=False)
        
        # Send email notification if email is available
        if patient_email:
            email_body = f"""
Dear {patient_name},

{notification_message}

Details:
- Doctor: Dr. {doctor_name}
- Reason: Appointment cancelled by hospital

Please contact us if you have any questions.

Best regards,
Smart Hospital Management System
"""
            send_email(patient_email, "Appointment Cancelled", email_body)
    
    appointments = appointments[appointments["id"] != id]
    appointments.to_csv("appointments.csv", index=False)

    return redirect('/admin_dashboard')


@app.route('/admin_logout')
def admin_logout():
    session.pop('admin',None)
    return redirect('/')


if __name__=="__main__":
    # Set debug mode based on environment variable (default: False for production)
    debug_mode = os.environ.get("FLASK_DEBUG", "False") == "True"
    
    # Dev helper: if OPEN_GOOGLE_TEST=1, open browser to the app's home page after startup
    if os.environ.get("OPEN_GOOGLE_TEST") == "1":
        def _open():
            time.sleep(1.5)
            try:
                webbrowser.open("http://localhost:5000/")
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
