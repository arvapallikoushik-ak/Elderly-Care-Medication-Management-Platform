import unittest
import sqlite3
import os
import tempfile
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

# Set up test environment before importing app
import app

class TestElderCare(unittest.TestCase):
    def setUp(self):
        """Create a temporary database for isolated testing."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.test_dir) / "test_eldercare.db"
        # Monkey patch app.DB_PATH to use isolated test DB
        self.orig_db_path = app.DB_PATH
        app.DB_PATH = self.test_db_path
        app.init_db()

    def tearDown(self):
        """Clean up temporary test database."""
        app.DB_PATH = self.orig_db_path
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_password_hashing(self):
        """Test PBKDF2 password hashing and salt verification."""
        pwd = "securepassword123"
        hashed = app.hash_password(pwd)
        self.assertIn("$", hashed)
        self.assertTrue(app.verify_password(pwd, hashed))
        self.assertFalse(app.verify_password("wrongpassword", hashed))
        self.assertFalse(app.verify_password("", hashed))

    def test_database_initialization(self):
        """Test all required tables and columns are created."""
        with app.db() as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            required = ["users", "medicines", "dose_logs", "appointments", "alerts", "vitals", "care_notes"]
            for req in required:
                self.assertIn(req, tables, f"Table {req} must exist")

    def test_demo_users_created(self):
        """Test default demo users (elder, family, caregiver) are seeded."""
        with app.db() as conn:
            users = conn.execute("SELECT username, role, display_name FROM users").fetchall()
            usernames = {u["username"]: u for u in users}
            self.assertIn("elder", usernames)
            self.assertIn("family", usernames)
            self.assertIn("caregiver", usernames)
            self.assertEqual(usernames["elder"]["role"], "Elder")

    def test_medicines_seed_and_retrieval(self):
        """Test seeded medicines are present and queryable."""
        meds = app.get_medicines("home1")
        self.assertGreaterEqual(len(meds), 3)
        med_names = [m["name"] for m in meds]
        self.assertIn("Amlodipine", med_names)
        self.assertIn("Metformin", med_names)

    def test_due_items_calculation(self):
        """Test computation of scheduled doses for today."""
        items = app.get_due_items("home1", on_date=date.today())
        self.assertGreater(len(items), 0)
        first_item = items[0]
        self.assertIn("name", first_item)
        self.assertIn("dosage", first_item)
        self.assertIn("due_time", first_item)
        self.assertIn(first_item["status"], ["Pending", "Taken", "Missed"])

    def test_mark_dose_status(self):
        """Test marking a dose as Taken, Skipped, and resetting to Pending."""
        items = app.get_due_items("home1", on_date=date.today())
        self.assertTrue(len(items) > 0)
        target = items[0]
        med_id = target["medicine_id"]
        due_time = target["due_time"]
        today_str = date.today().isoformat()

        # Mark Taken
        app.mark_dose_status(med_id, today_str, due_time, "Taken", "Alex (Elder)")
        updated_items = app.get_due_items("home1", on_date=date.today())
        taken_item = next(x for x in updated_items if x["medicine_id"] == med_id and x["due_time"] == due_time)
        self.assertEqual(taken_item["status"], "Taken")
        self.assertEqual(taken_item["marked_by"], "Alex (Elder)")

        # Mark Skipped with Note
        app.mark_dose_status(med_id, today_str, due_time, "Skipped", "Alex (Elder)", note="Doctor advised pause")
        updated_items = app.get_due_items("home1", on_date=date.today())
        skipped_item = next(x for x in updated_items if x["medicine_id"] == med_id and x["due_time"] == due_time)
        self.assertEqual(skipped_item["status"], "Skipped")
        self.assertEqual(skipped_item["note"], "Doctor advised pause")

        # Undo to Pending
        app.mark_dose_status(med_id, today_str, due_time, "Pending", "Alex (Elder)")
        updated_items = app.get_due_items("home1", on_date=date.today())
        pending_item = next(x for x in updated_items if x["medicine_id"] == med_id and x["due_time"] == due_time)
        self.assertEqual(pending_item["status"], "Pending")

    def test_vitals_recording_and_water(self):
        """Test recording blood pressure, heart rate, and water glass tracking."""
        # Test water tracking
        initial_water = app.get_today_water("home1")
        app.update_today_water("home1", initial_water + 2, "Alex (Elder)")
        self.assertEqual(app.get_today_water("home1"), initial_water + 2)

        # Test vitals row insertion
        with app.db() as conn:
            conn.execute("""
                INSERT INTO vitals(household, recorded_by, recorded_at, systolic, diastolic, glucose, heart_rate, mood, water_glasses)
                VALUES('home1', 'Tester', '2026-11-15 10:00:00', 120, 80, 95, 72, 'Good', 4)
            """)
            row = conn.execute("SELECT * FROM vitals WHERE recorded_by='Tester'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["systolic"], 120)
            self.assertEqual(row["diastolic"], 80)
            self.assertEqual(row["glucose"], 95)
            self.assertEqual(row["heart_rate"], 72)

    def test_appointments_and_google_calendar_url(self):
        """Test appointment scheduling and Google Calendar link generation."""
        tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
        with app.db() as conn:
            conn.execute("""
                INSERT INTO appointments(doctor, purpose, appt_date, appt_time, location, created_by, household, status)
                VALUES('Dr. Adams', 'Dental Checkup', ?, '11:00', 'Dental Care Suite 1', 'Jordan', 'home1', 'Scheduled')
            """, (tomorrow_str,))
            appt = conn.execute("SELECT * FROM appointments WHERE doctor='Dr. Adams'").fetchone()
            self.assertIsNotNone(appt)
            self.assertEqual(appt["status"], "Scheduled")

        url = app.make_gcal_url("Dr. Adams", tomorrow_str, "11:00", "Dental Checkup", "Dental Care Suite 1")
        self.assertTrue(url.startswith("https://calendar.google.com/calendar/render?action=TEMPLATE"))
        self.assertIn("Dr.+Adams", url)

    def test_sos_and_alerts(self):
        """Test SOS creation, active alert detection, and resolution."""
        # Check no unresolved SOS initially or log a new one
        app.log_alert("SOS", "Emergency alert test", "home1")
        active = app.get_active_sos("home1")
        self.assertIsNotNone(active)
        self.assertEqual(active["alert_type"], "SOS")
        self.assertEqual(active["resolved"], 0)

        # Resolve SOS
        with app.db() as conn:
            conn.execute("UPDATE alerts SET resolved=1 WHERE id=?", (active["id"],))
        resolved = app.get_active_sos("home1")
        self.assertIsNone(resolved)

    def test_care_notes(self):
        """Test shared caregiver and family notice board."""
        with app.db() as conn:
            conn.execute(
                "INSERT INTO care_notes(household, author, role, note, created_at) VALUES(?,?,?,?,?)",
                ("home1", "Jordan", "Caregiver", "Blood sugar tested 98 after breakfast.", "2026-11-15 10:30")
            )
            note = conn.execute("SELECT * FROM care_notes WHERE author='Jordan' ORDER BY id DESC LIMIT 1").fetchone()
            self.assertIsNotNone(note)
            self.assertIn("Blood sugar", note["note"])

if __name__ == "__main__":
    unittest.main()

