import os
import datetime
import pandas as pd
from flask import has_app_context
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()
_flask_app = None


def _get_utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


# --------------------
# DATABASE MODELS
# --------------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=True, default="")
    created_at = db.Column(db.DateTime, default=_get_utc_now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "password": self.password or ""
        }


class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(150), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "specialization": self.specialization
        }


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_name = db.Column(db.String(150), nullable=False, index=True)
    doctor_name = db.Column(db.String(150), nullable=False, index=True)
    date = db.Column(db.String(50), nullable=False)
    time_slot = db.Column(db.String(50), nullable=False, default="09:00 AM - 10:00 AM")
    created_at = db.Column(db.DateTime, default=_get_utc_now)

    __table_args__ = (
        UniqueConstraint('doctor_name', 'date', 'time_slot', name='uq_doctor_date_timeslot'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "patient_name": self.patient_name,
            "doctor_name": self.doctor_name,
            "date": self.date,
            "time_slot": self.time_slot
        }


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_name = db.Column(db.String(150), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_get_utc_now)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_name": self.patient_name,
            "message": self.message,
            "read": self.read
        }


# --------------------
# CONFIG & INITIALIZATION
# --------------------
def get_database_url():
    """
    Returns properly formatted SQLAlchemy database URL.
    Checks all standard Vercel and Neon connection string keys.
    Converts legacy postgres:// to postgresql:// for modern SQLAlchemy compatibility.
    """
    candidates = [
        "DATABASE_URL",
        "POSTGRES_URL",
        "STORAGE_URL",
        "NEON_DATABASE_URL",
        "POSTGRES_URL_NON_POOLING",
        "POSTGRES_PRISMA_URL"
    ]
    for key in candidates:
        val = os.environ.get(key)
        if val and val.strip():
            url = val.strip()
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url

    # Also search any environment variable containing postgres/neon connection string
    for k, v in os.environ.items():
        if ("POSTGRES" in k.upper() or "DATABASE" in k.upper() or "STORAGE" in k.upper()) and "URL" in k.upper():
            if v and ("postgres" in v.lower() or "neon.tech" in v.lower()):
                url = v.strip()
                if url.startswith("postgres://"):
                    url = url.replace("postgres://", "postgresql://", 1)
                return url

    return None


def is_db_configured():
    """Check if PostgreSQL DATABASE_URL is configured."""
    return get_database_url() is not None


def init_database(app):
    """
    Initializes PostgreSQL if configured in environment, otherwise falls back to SQLite.
    Creates all tables and seeds existing CSV data if database is empty.
    """
    global _flask_app
    _flask_app = app

    db_url = get_database_url()
    if db_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
        print(f"[Database] Configured PostgreSQL from environment variable.")
    else:
        sqlite_path = os.path.join(app.root_path, "hospital_local.db")
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{sqlite_path}"
        print(f"[Database] PostgreSQL not configured. Using local SQLite/CSV fallback.")

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        try:
            db.create_all()
            seed_data_from_csv(app)
        except Exception as e:
            print(f"[Database Init Error] {e}")


def seed_data_from_csv(app):
    """Import existing CSV seed data into database if tables are empty."""
    try:
        # Seed Doctors
        if Doctor.query.count() == 0:
            doc_file = os.path.join(app.root_path, "doctors.csv")
            if os.path.exists(doc_file):
                df = pd.read_csv(doc_file)
                for _, row in df.iterrows():
                    d = Doctor(
                        id=int(row["id"]) if "id" in row and not pd.isna(row["id"]) else None,
                        name=str(row["name"]).strip(),
                        specialization=str(row["specialization"]).strip()
                    )
                    db.session.add(d)
                db.session.commit()
                print(f"[Database Seed] Seeded {len(df)} doctors into database.")

        # Seed Users
        if User.query.count() == 0:
            user_file = os.path.join(app.root_path, "users.csv")
            if os.path.exists(user_file):
                df = pd.read_csv(user_file)
                for _, row in df.iterrows():
                    u = User(
                        id=int(row["id"]) if "id" in row and not pd.isna(row["id"]) else None,
                        name=str(row["name"]).strip(),
                        email=str(row["email"]).strip().lower(),
                        password=str(row.get("password", "")) if not pd.isna(row.get("password")) else ""
                    )
                    db.session.add(u)
                db.session.commit()
                print(f"[Database Seed] Seeded {len(df)} users into database.")

        # Seed Appointments
        if Appointment.query.count() == 0:
            appt_file = os.path.join(app.root_path, "appointments.csv")
            if os.path.exists(appt_file):
                df = pd.read_csv(appt_file)
                for _, row in df.iterrows():
                    a = Appointment(
                        id=int(row["id"]) if "id" in row and not pd.isna(row["id"]) else None,
                        patient_name=str(row["patient_name"]).strip(),
                        doctor_name=str(row["doctor_name"]).strip(),
                        date=str(row["date"]).strip(),
                        time_slot=str(row.get("time_slot", "09:00 AM - 10:00 AM")).strip()
                    )
                    db.session.add(a)
                db.session.commit()
                print(f"[Database Seed] Seeded {len(df)} appointments into database.")
    except Exception as e:
        db.session.rollback()
        print(f"[Database Seed Error] {e}")


def with_app_context(func):
    """Decorator to ensure operations run inside a Flask application context."""
    def wrapper(*args, **kwargs):
        if not has_app_context() and _flask_app is not None:
            with _flask_app.app_context():
                return func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper


# --------------------
# DATABASE BRIDGES
# --------------------
@with_app_context
def db_get_users():
    try:
        users = User.query.all()
        if users:
            return pd.DataFrame([u.to_dict() for u in users])
    except Exception as e:
        print(f"[DB Users Query Error] {e}")
    return None


@with_app_context
def db_save_users(df):
    try:
        existing = {u.email: u for u in User.query.all()}
        for _, row in df.iterrows():
            email = str(row.get("email", "")).strip().lower()
            if not email:
                continue
            name = str(row.get("name", "")).strip()
            password = str(row.get("password", "")) if not pd.isna(row.get("password")) else ""
            if email in existing:
                u = existing[email]
                u.name = name
                if password:
                    u.password = password
            else:
                new_u = User(name=name, email=email, password=password)
                db.session.add(new_u)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[DB Users Save Error] {e}")


@with_app_context
def db_get_doctors():
    try:
        docs = Doctor.query.order_by(Doctor.id).all()
        if docs:
            return pd.DataFrame([d.to_dict() for d in docs])
    except Exception as e:
        print(f"[DB Doctors Query Error] {e}")
    return None


@with_app_context
def db_save_doctors(df):
    try:
        Doctor.query.delete()
        for _, row in df.iterrows():
            d = Doctor(
                id=int(row["id"]) if "id" in row and not pd.isna(row["id"]) else None,
                name=str(row.get("name", "")).strip(),
                specialization=str(row.get("specialization", "")).strip()
            )
            db.session.add(d)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[DB Doctors Save Error] {e}")


@with_app_context
def db_get_appointments():
    try:
        appts = Appointment.query.order_by(Appointment.id).all()
        if appts:
            return pd.DataFrame([a.to_dict() for a in appts])
    except Exception as e:
        print(f"[DB Appointments Query Error] {e}")
    return None


@with_app_context
def db_save_appointments(df):
    try:
        Appointment.query.delete()
        for _, row in df.iterrows():
            a = Appointment(
                id=int(row["id"]) if "id" in row and not pd.isna(row["id"]) else None,
                patient_name=str(row.get("patient_name", "")).strip(),
                doctor_name=str(row.get("doctor_name", "")).strip(),
                date=str(row.get("date", "")).strip(),
                time_slot=str(row.get("time_slot", "09:00 AM - 10:00 AM")).strip()
            )
            db.session.add(a)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[DB Appointments Save Error] {e}")


@with_app_context
def db_get_notifications():
    try:
        notifs = Notification.query.order_by(Notification.id.desc()).all()
        if notifs:
            return pd.DataFrame([n.to_dict() for n in notifs])
    except Exception as e:
        print(f"[DB Notifications Query Error] {e}")
    return None


@with_app_context
def db_save_notifications(df):
    try:
        Notification.query.delete()
        for _, row in df.iterrows():
            n = Notification(
                id=int(row["id"]) if "id" in row and not pd.isna(row["id"]) else None,
                patient_name=str(row.get("patient_name", "")).strip(),
                message=str(row.get("message", "")).strip(),
                read=bool(row.get("read", False))
            )
            db.session.add(n)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[DB Notifications Save Error] {e}")
