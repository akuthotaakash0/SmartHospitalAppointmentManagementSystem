import os
import unittest
import pandas as pd
from werkzeug.security import generate_password_hash
import app as app_module


class HospitalAppComprehensiveTests(unittest.TestCase):
    def setUp(self):
        app_module.ensure_files()
        self.client = app_module.app.test_client()

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Smart Hospital", response.get_data(as_text=True))

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data.get("status"), "ok")

    def test_unauthenticated_dashboard_redirects(self):
        # Protected route without login should redirect
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)

    def test_login_invalid_credentials(self):
        # Fresh client without prior flashes
        client = app_module.app.test_client()
        response = client.post("/login", data={"email": "nonexistent@test.com", "password": "wrong"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid credentials", response.get_data(as_text=True))

    def test_appointment_booking_and_cancellation(self):
        # Ensure a test patient exists
        users = app_module.get_users_df()
        test_patient = "Automated Test Patient"
        test_email = "auto_patient@example.com"
        if users.empty or test_email not in users["email"].values:
            new_id = 1 if users.empty else int(users["id"].max()) + 1
            new_u = pd.DataFrame([{
                "id": new_id,
                "name": test_patient,
                "email": test_email,
                "password": generate_password_hash("pass123")
            }])
            users = pd.concat([users, new_u], ignore_index=True)
            app_module.save_users_df(users)

        # Set session as logged in user
        with self.client.session_transaction() as sess:
            sess['user'] = test_patient
            sess['email'] = test_email

        # Book an appointment
        book_resp = self.client.post("/confirm", data={"doctor": "Dr. Sharma", "date": "2026-11-20"}, follow_redirects=True)
        self.assertEqual(book_resp.status_code, 200)
        self.assertIn("Appointment booked successfully", book_resp.get_data(as_text=True))

        # Check in appointments CSV
        appts = app_module.get_appointments_df()
        patient_appts = appts[appts["patient_name"] == test_patient]
        self.assertFalse(patient_appts.empty)
        appt_id = int(patient_appts.iloc[-1]["id"])

        # Cancel appointment
        cancel_resp = self.client.get(f"/delete_appointment/{appt_id}", follow_redirects=True)
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertIn("Appointment cancelled successfully", cancel_resp.get_data(as_text=True))

        # Check appointment removed
        appts_after = app_module.get_appointments_df()
        self.assertTrue(appts_after[appts_after["id"] == appt_id].empty)

        # Clean up test user, test appointments, & test notifications
        users = app_module.get_users_df()
        users = users[users["email"] != test_email]
        app_module.save_users_df(users)

        appts_cleanup = app_module.get_appointments_df()
        if not appts_cleanup.empty and "patient_name" in appts_cleanup.columns:
            appts_cleanup = appts_cleanup[appts_cleanup["patient_name"] != test_patient]
            app_module.save_appointments_df(appts_cleanup)

        notifs = app_module.get_notifications_df()
        if not notifs.empty and "patient_name" in notifs.columns:
            notifs = notifs[notifs["patient_name"] != test_patient]
            app_module.save_notifications_df(notifs)

    def test_admin_flow(self):
        # Try accessing admin dashboard without session
        resp = self.client.get("/admin_dashboard")
        self.assertEqual(resp.status_code, 302)

        # Admin login
        login_resp = self.client.post("/admin", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn("Admin Panel", login_resp.get_data(as_text=True))

        # Add doctor
        add_doc_resp = self.client.post("/add_doctor", data={"name": "Dr. Automated Test", "specialization": "Neurology"}, follow_redirects=True)
        self.assertEqual(add_doc_resp.status_code, 200)

        docs = app_module.get_doctors_df()
        added_doc = docs[docs["name"] == "Dr. Automated Test"]
        self.assertFalse(added_doc.empty)
        doc_id = int(added_doc.iloc[0]["id"])

        # Edit doctor
        edit_resp = self.client.post(f"/edit_doctor/{doc_id}", data={"name": "Dr. Automated Test", "specialization": "Neurosurgery"}, follow_redirects=True)
        self.assertEqual(edit_resp.status_code, 200)

        docs = app_module.get_doctors_df()
        updated_doc = docs[docs["id"] == doc_id]
        self.assertEqual(updated_doc.iloc[0]["specialization"], "Neurosurgery")

        # Delete doctor
        del_resp = self.client.get(f"/delete_doctor/{doc_id}", follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        docs = app_module.get_doctors_df()
        self.assertTrue(docs[docs["id"] == doc_id].empty)

    def test_reschedule_and_slip_flow(self):
        # Create a test patient
        test_patient = "Reschedule Patient"
        test_email = "resched_patient@example.com"
        users = app_module.get_users_df()
        if users.empty or test_email not in users["email"].values:
            new_id = 1 if users.empty else int(users["id"].max()) + 1
            new_u = pd.DataFrame([{
                "id": new_id,
                "name": test_patient,
                "email": test_email,
                "password": generate_password_hash("pass123")
            }])
            users = pd.concat([users, new_u], ignore_index=True)
            app_module.save_users_df(users)

        with self.client.session_transaction() as sess:
            sess['user'] = test_patient
            sess['email'] = test_email

        # 1. Book an appointment with specific time slot
        book_resp = self.client.post("/confirm", data={
            "doctor": "Dr. Sharma",
            "date": "2026-12-10",
            "time_slot": "10:00 AM - 11:00 AM"
        }, follow_redirects=True)
        self.assertEqual(book_resp.status_code, 200)
        self.assertIn("Appointment booked successfully", book_resp.get_data(as_text=True))

        appts = app_module.get_appointments_df()
        user_appt = appts[(appts["patient_name"] == test_patient) & (appts["date"] == "2026-12-10")]
        self.assertFalse(user_appt.empty)
        appt_id = int(user_appt.iloc[-1]["id"])
        self.assertEqual(user_appt.iloc[-1]["time_slot"], "10:00 AM - 11:00 AM")

        # 2. Prevent duplicate booking on same doctor, date & time slot
        dup_resp = self.client.post("/confirm", data={
            "doctor": "Dr. Sharma",
            "date": "2026-12-10",
            "time_slot": "10:00 AM - 11:00 AM"
        }, follow_redirects=True)
        self.assertIn("already booked", dup_resp.get_data(as_text=True))

        # 3. View Appointment Slip
        slip_resp = self.client.get(f"/appointment_slip/{appt_id}")
        self.assertEqual(slip_resp.status_code, 200)
        self.assertIn("Official Consultation Pass", slip_resp.get_data(as_text=True))
        self.assertIn("TOKEN #", slip_resp.get_data(as_text=True))

        # 4. Reschedule appointment to another date/slot
        resched_resp = self.client.post(f"/reschedule/{appt_id}", data={
            "date": "2026-12-15",
            "time_slot": "02:00 PM - 03:00 PM"
        }, follow_redirects=True)
        self.assertEqual(resched_resp.status_code, 200)
        self.assertIn("successfully rescheduled", resched_resp.get_data(as_text=True))

        appts_after = app_module.get_appointments_df()
        updated_appt = appts_after[appts_after["id"] == appt_id]
        self.assertEqual(updated_appt.iloc[0]["date"], "2026-12-15")
        self.assertEqual(updated_appt.iloc[0]["time_slot"], "02:00 PM - 03:00 PM")

        # Cleanup
        appts_after = appts_after[appts_after["id"] != appt_id]
        app_module.save_appointments_df(appts_after)

        users = app_module.get_users_df()
        users = users[users["email"] != test_email]
        app_module.save_users_df(users)

        notifs = app_module.get_notifications_df()
        if not notifs.empty and "patient_name" in notifs.columns:
            notifs = notifs[notifs["patient_name"] != test_patient]
            app_module.save_notifications_df(notifs)


if __name__ == "__main__":
    unittest.main()
