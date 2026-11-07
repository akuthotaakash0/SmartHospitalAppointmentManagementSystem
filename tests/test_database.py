import unittest
from flask import Flask
from database import db, User, Doctor, Appointment, Notification, seed_data_from_csv


class DatabaseModelsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_user_creation_and_query(self):
        with self.app.app_context():
            u = User(name="Test Patient", email="patient@hospital.com", password="hash")
            db.session.add(u)
            db.session.commit()

            fetched = User.query.filter_by(email="patient@hospital.com").first()
            self.assertIsNotNone(fetched)
            self.assertEqual(fetched.name, "Test Patient")
            self.assertEqual(fetched.to_dict()["email"], "patient@hospital.com")

    def test_doctor_creation_and_query(self):
        with self.app.app_context():
            doc = Doctor(name="Dr. Mehta", specialization="Cardiology")
            db.session.add(doc)
            db.session.commit()

            fetched = Doctor.query.filter_by(name="Dr. Mehta").first()
            self.assertIsNotNone(fetched)
            self.assertEqual(fetched.specialization, "Cardiology")

    def test_appointment_double_booking_constraint(self):
        with self.app.app_context():
            a1 = Appointment(
                patient_name="Patient A",
                doctor_name="Dr. Sharma",
                date="2026-12-01",
                time_slot="09:00 AM - 10:00 AM"
            )
            db.session.add(a1)
            db.session.commit()

            # Attempt to add exact same doctor, date and time slot
            a2 = Appointment(
                patient_name="Patient B",
                doctor_name="Dr. Sharma",
                date="2026-12-01",
                time_slot="09:00 AM - 10:00 AM"
            )
            db.session.add(a2)
            with self.assertRaises(Exception):
                db.session.commit()
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
