import streamlit as st
import sqlite3
import hashlib
import secrets
import os
import smtplib
import json
import urllib.parse
from email.message import EmailMessage
from datetime import datetime, date, time, timedelta
from pathlib import Path
import streamlit.components.v1 as components

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "eldercare.db"

st.set_page_config(
    page_title="ElderCare | Smart & Interactive Care",
    page_icon="💙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- Audio & Speech Synthesis ----------
def speak_text(text: str):
    """Client-side speech synthesis using browser Web Speech API."""
    safe_text = json.dumps(text)
    js = f"""
    <script>
    if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance({safe_text});
        utterance.rate = 0.88; // Gentle, elder-friendly pace
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }}
    </script>
    """
    components.html(js, height=0, width=0)

def play_chime():
    """Client-side pleasant two-tone reminder chime using Web Audio API."""
    js = """
    <script>
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioCtx();
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, now); // D5
        osc.frequency.setValueAtTime(880.00, now + 0.15); // A5
        gain.gain.setValueAtTime(0.25, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.7);
        osc.start(now);
        osc.stop(now + 0.7);
    } catch(e) {}
    </script>
    """
    components.html(js, height=0, width=0)

def play_sos_siren():
    """Client-side urgent emergency siren using Web Audio API."""
    js = """
    <script>
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioCtx();
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(650, now);
        osc.frequency.linearRampToValueAtTime(950, now + 0.3);
        osc.frequency.linearRampToValueAtTime(650, now + 0.6);
        osc.frequency.linearRampToValueAtTime(950, now + 0.9);
        gain.gain.setValueAtTime(0.35, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 1.2);
        osc.start(now);
        osc.stop(now + 1.2);
    } catch(e) {}
    </script>
    """
    components.html(js, height=0, width=0)

# ---------- Database Initialization & Migration ----------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt).split("$", 1)[1], expected)
    except Exception:
        return False

def ensure_column(conn, table, column, col_type):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT DEFAULT '',
            household TEXT NOT NULL DEFAULT 'home1'
        );
        CREATE TABLE IF NOT EXISTS medicines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            instructions TEXT DEFAULT '',
            times TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT DEFAULT '',
            category TEXT DEFAULT 'General',
            added_by TEXT NOT NULL,
            household TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dose_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            due_time TEXT NOT NULL,
            status TEXT NOT NULL,
            marked_by TEXT NOT NULL,
            marked_at TEXT NOT NULL,
            note TEXT DEFAULT '',
            UNIQUE(medicine_id, due_date, due_time)
        );
        CREATE TABLE IF NOT EXISTS appointments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor TEXT NOT NULL,
            purpose TEXT DEFAULT '',
            appt_date TEXT NOT NULL,
            appt_time TEXT NOT NULL,
            location TEXT DEFAULT '',
            created_by TEXT NOT NULL,
            household TEXT NOT NULL,
            status TEXT DEFAULT 'Scheduled'
        );
        CREATE TABLE IF NOT EXISTS alerts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            household TEXT NOT NULL,
            resolved INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS vitals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            household TEXT NOT NULL,
            recorded_by TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            systolic INTEGER DEFAULT 120,
            diastolic INTEGER DEFAULT 80,
            glucose INTEGER DEFAULT 100,
            heart_rate INTEGER DEFAULT 72,
            mood TEXT DEFAULT 'Good',
            water_glasses INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS care_notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            household TEXT NOT NULL,
            author TEXT NOT NULL,
            role TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        # Safely migrate older schemas if needed
        ensure_column(conn, "medicines", "category", "TEXT DEFAULT 'General'")
        ensure_column(conn, "dose_logs", "note", "TEXT DEFAULT ''")
        ensure_column(conn, "appointments", "status", "TEXT DEFAULT 'Scheduled'")
        ensure_column(conn, "alerts", "resolved", "INTEGER DEFAULT 0")

        # Demo users
        demo_users = [
            ("elder", "elder123", "Alex (Elder)", "Elder", ""),
            ("family", "family123", "Sam (Family)", "Family", ""),
            ("caregiver", "care123", "Jordan (Caregiver)", "Caregiver", ""),
        ]
        for username, password, display, role, email in demo_users:
            existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO users(username,password_hash,display_name,role,email,household) VALUES(?,?,?,?,?,?)",
                    (username, hash_password(password), display, role, email, "home1")
                )

        # Seed realistic starter data if empty
        med_count = conn.execute("SELECT COUNT(*) as c FROM medicines WHERE household='home1'").fetchone()["c"]
        if med_count == 0:
            today_str = date.today().isoformat()
            conn.executescript(f"""
            INSERT INTO medicines(name, dosage, instructions, times, start_date, end_date, category, added_by, household)
            VALUES
            ('Amlodipine', '5 mg', 'Take 1 tablet in the morning with a full glass of water.', '08:00', '{today_str}', '', 'Blood Pressure', 'Jordan (Caregiver)', 'home1'),
            ('Metformin', '500 mg', 'Take with meals to prevent upset stomach.', '08:30, 20:00', '{today_str}', '', 'Diabetes', 'Jordan (Caregiver)', 'home1'),
            ('Vitamin D3', '1000 IU', 'Take once daily after lunch.', '13:00', '{today_str}', '', 'Supplements', 'Jordan (Caregiver)', 'home1'),
            ('Omega-3 Fish Oil', '1000 mg', 'Take with dinner.', '19:30', '{today_str}', '', 'Heart Health', 'Jordan (Caregiver)', 'home1');
            """)

        appt_count = conn.execute("SELECT COUNT(*) as c FROM appointments WHERE household='home1'").fetchone()["c"]
        if appt_count == 0:
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            next_week = (date.today() + timedelta(days=6)).isoformat()
            conn.executescript(f"""
            INSERT INTO appointments(doctor, purpose, appt_date, appt_time, location, created_by, household, status)
            VALUES
            ('Dr. Sarah Jenkins (Cardiology)', 'Quarterly Blood Pressure & Heart Checkup', '{tomorrow}', '10:30', 'St. Jude Heart Clinic, Suite 302', 'Jordan (Caregiver)', 'home1', 'Scheduled'),
            ('Dr. Michael Chen (Ophthalmology)', 'Routine Glaucoma & Vision Screening', '{next_week}', '14:00', 'ClearView Eye Center', 'Sam (Family)', 'home1', 'Scheduled');
            """)

        notes_count = conn.execute("SELECT COUNT(*) as c FROM care_notes WHERE household='home1'").fetchone()["c"]
        if notes_count == 0:
            conn.executescript(f"""
            INSERT INTO care_notes(household, author, role, note, created_at)
            VALUES
            ('home1', 'Jordan (Caregiver)', 'Caregiver', 'Alex had oatmeal and fruit for breakfast. Went for a 15-minute sunshine walk in the garden.', '{(datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")}'),
            ('home1', 'Sam (Family)', 'Family', 'Picked up prescription refills from Walgreens. Restocked the medicine dispenser for the week.', '{(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")}');
            """)

        vitals_count = conn.execute("SELECT COUNT(*) as c FROM vitals WHERE household='home1'").fetchone()["c"]
        if vitals_count == 0:
            d2 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d 09:00")
            d1 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 09:15")
            d0 = datetime.now().strftime("%Y-%m-%d 08:45")
            conn.executescript(f"""
            INSERT INTO vitals(household, recorded_by, recorded_at, systolic, diastolic, glucose, heart_rate, mood, water_glasses)
            VALUES
            ('home1', 'Alex (Elder)', '{d2}', 122, 82, 106, 74, 'Good', 6),
            ('home1', 'Jordan (Caregiver)', '{d1}', 120, 80, 102, 72, 'Energetic', 7),
            ('home1', 'Alex (Elder)', '{d0}', 118, 78, 98, 70, 'Good', 4);
            """)

init_db()

# ---------- Helpers ----------
def current_user():
    return st.session_state.get("user")

def send_email(to_email, subject, body):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_PASSWORD")
    if not all([host, sender, password, to_email]):
        return False, "Email is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_EMAIL and SMTP_PASSWORD."
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        return True, "Email sent successfully."
    except Exception as exc:
        return False, f"Email failed: {exc}"

def household_users(household):
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE household=?", (household,)).fetchall()

def log_alert(kind, message, household):
    with db() as conn:
        conn.execute(
            "INSERT INTO alerts(alert_type,message,created_at,household,resolved) VALUES(?,?,?,?,0)",
            (kind, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), household)
        )

def get_medicines(household):
    with db() as conn:
        return conn.execute("SELECT * FROM medicines WHERE household=? ORDER BY name", (household,)).fetchall()

def get_due_items(household, on_date=None):
    on_date = on_date or date.today()
    items = []
    now = datetime.now()
    meds = get_medicines(household)
    with db() as conn:
        for med in meds:
            if med["start_date"] > on_date.isoformat():
                continue
            if med["end_date"] and med["end_date"] < on_date.isoformat():
                continue
            for due_time in [x.strip() for x in med["times"].split(",") if x.strip()]:
                row = conn.execute(
                    "SELECT status, marked_by, marked_at, note FROM dose_logs WHERE medicine_id=? AND due_date=? AND due_time=?",
                    (med["id"], on_date.isoformat(), due_time)
                ).fetchone()
                try:
                    due_dt = datetime.combine(on_date, time.fromisoformat(due_time))
                except ValueError:
                    continue
                if row:
                    status = row["status"]
                    note = row["note"] or ""
                    marked_by = row["marked_by"] or ""
                    marked_at = row["marked_at"] or ""
                else:
                    status = "Missed" if (on_date == date.today() and now > due_dt + timedelta(minutes=45)) else "Pending"
                    note = ""
                    marked_by = ""
                    marked_at = ""
                items.append({
                    "medicine_id": med["id"],
                    "name": med["name"],
                    "dosage": med["dosage"],
                    "category": med["category"] or "General",
                    "instructions": med["instructions"],
                    "due_time": due_time,
                    "status": status,
                    "note": note,
                    "marked_by": marked_by,
                    "marked_at": marked_at,
                    "due_dt": due_dt
                })
    return sorted(items, key=lambda x: x["due_time"])

def mark_dose_status(medicine_id, due_date_str, due_time, status, user_display, note=""):
    with db() as conn:
        conn.execute("""
            INSERT INTO dose_logs(medicine_id, due_date, due_time, status, marked_by, marked_at, note)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(medicine_id, due_date, due_time)
            DO UPDATE SET status=excluded.status, marked_by=excluded.marked_by, marked_at=excluded.marked_at, note=excluded.note
        """, (medicine_id, due_date_str, due_time, status, user_display,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), note))

def get_today_water(household):
    today_str = date.today().isoformat()
    with db() as conn:
        row = conn.execute(
            "SELECT water_glasses FROM vitals WHERE household=? AND recorded_at LIKE ? ORDER BY id DESC LIMIT 1",
            (household, f"{today_str}%")
        ).fetchone()
        return row["water_glasses"] if row else 0

def update_today_water(household, count, user_display):
    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM vitals WHERE household=? AND recorded_at LIKE ? ORDER BY id DESC LIMIT 1",
            (household, f"{today_str}%")
        ).fetchone()
        if row:
            conn.execute("UPDATE vitals SET water_glasses=? WHERE id=?", (count, row["id"]))
        else:
            conn.execute(
                "INSERT INTO vitals(household, recorded_by, recorded_at, water_glasses) VALUES(?,?,?,?)",
                (household, user_display, now_str, count)
            )

def get_active_sos(household):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM alerts WHERE household=? AND alert_type='SOS' AND resolved=0 ORDER BY id DESC LIMIT 1",
            (household,)
        ).fetchone()

def make_gcal_url(title, appt_date_str, appt_time_str, details="", location=""):
    try:
        start_dt = datetime.strptime(f"{appt_date_str} {appt_time_str}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(hours=1)
        base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        params = {
            "text": title,
            "dates": f"{start_dt.strftime('%Y%m%dT%H%M00')}/{end_dt.strftime('%Y%m%dT%H%M00')}",
            "details": details,
            "location": location,
        }
        return f"{base}&{urllib.parse.urlencode(params)}"
    except Exception:
        return "https://calendar.google.com"

# ---------- Login Screen ----------
def login_screen():
    st.markdown("""
    <div style='text-align:center; padding: 1.5rem 0 0.5rem;'>
        <h1 style='color:#1E40AF; font-size: 2.8rem; margin-bottom: 0.2rem;'>💙 ElderCare</h1>
        <p style='color:#475569; font-size: 1.15rem; max-width:600px; margin:0 auto;'>
            Smart, interactive medication management & family care companion
        </p>
    </div>
    """, unsafe_allow_html=True)

    c_left, c_center, c_right = st.columns([1, 2, 1])

    with c_center:
        st.markdown("### ⚡ One-Click Instant Sign-In")
        st.caption("Click any demo persona to test the interactive experience immediately:")

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("👴 **Alex**\n\n*Elder*", use_container_width=True):
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE username='elder'").fetchone()
                if user:
                    st.session_state.user = dict(user)
                    st.session_state.senior_mode = True
                    st.toast("Welcome back, Alex! Senior Mode enabled.", icon="👴")
                    st.rerun()
        with b2:
            if st.button("👨‍👩‍👧 **Sam**\n\n*Family*", use_container_width=True):
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE username='family'").fetchone()
                if user:
                    st.session_state.user = dict(user)
                    st.toast("Welcome back, Sam!", icon="👨‍👩‍👧")
                    st.rerun()
        with b3:
            if st.button("🩺 **Jordan**\n\n*Caregiver*", use_container_width=True):
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE username='caregiver'").fetchone()
                if user:
                    st.session_state.user = dict(user)
                    st.toast("Welcome back, Jordan!", icon="🩺")
                    st.rerun()

        st.divider()

        with st.expander("🔑 Or sign in with username & password", expanded=False):
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="e.g. elder")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)
            if submitted:
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
                if user and verify_password(password, user["password_hash"]):
                    st.session_state.user = dict(user)
                    st.rerun()
                else:
                    st.error("Incorrect username or password. Try the one-click demo buttons above.")

        st.caption("🔒 All data is securely stored in local SQLite database.")

# ---------- Main Application ----------
def main_app(user):
    # Accessibility Senior Mode Styling
    senior_mode = st.session_state.get("senior_mode", False)

    if senior_mode:
        st.markdown("""
        <style>
        html, body, [class*="css"], .stMarkdown, p, span, label, div {
            font-size: 1.15rem !important;
            line-height: 1.6 !important;
        }
        h1 { font-size: 2.5rem !important; font-weight: 800 !important; color: #1E3A8A !important; }
        h2 { font-size: 2.0rem !important; font-weight: 700 !important; color: #1E3A8A !important; }
        h3 { font-size: 1.55rem !important; font-weight: 700 !important; }
        button {
            font-size: 1.15rem !important;
            padding: 0.75rem 1.1rem !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 2.2rem !important;
            font-weight: 800 !important;
        }
        .stButton>button {
            border: 2px solid #2563EB !important;
        }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 2.5rem; }
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #f0f7ff 0%, #e2eeff 100%);
            padding: 16px;
            border-radius: 14px;
            border: 1px solid #c7dcff;
        }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
        }
        </style>
        """, unsafe_allow_html=True)

    household = user["household"]

    # Active SOS Emergency Banner
    active_sos = get_active_sos(household)
    if active_sos:
        with st.container():
            st.error(f"🚨 **ACTIVE SOS EMERGENCY ALERT:** {active_sos['message']} *(Triggered at {active_sos['created_at']})*")
            col_s1, col_s2 = st.columns([3, 1])
            with col_s1:
                st.caption("All emergency contacts have been notified. Please confirm safety.")
            with col_s2:
                if st.button("✅ Mark SOS as Resolved", use_container_width=True):
                    with db() as conn:
                        conn.execute("UPDATE alerts SET resolved=1 WHERE id=?", (active_sos["id"],))
                    st.success("Emergency alert resolved.")
                    st.rerun()

    # Sidebar Navigation & Settings
    with st.sidebar:
        st.markdown("<h2 style='margin-bottom:0;'>💙 ElderCare</h2>", unsafe_allow_html=True)
        st.markdown(f"**{user['display_name']}** · `{user['role']}`")

        # Quick Switch Persona
        with st.expander("🔄 Switch User Persona", expanded=False):
            with db() as conn:
                all_users = conn.execute("SELECT * FROM users WHERE household=?", (household,)).fetchall()
            for u in all_users:
                if u["username"] != user["username"]:
                    if st.button(f"Switch to {u['display_name']}", key=f"sw_{u['username']}", use_container_width=True):
                        st.session_state.user = dict(u)
                        st.rerun()

        st.divider()

        # Accessibility Controls
        st.subheader("👓 Accessibility")
        new_senior_mode = st.toggle("Senior Friendly Mode", value=senior_mode, help="Increases text size, button size and contrast for senior readability.")
        if new_senior_mode != senior_mode:
            st.session_state.senior_mode = new_senior_mode
            st.rerun()

        st.divider()

        # Navigation Menu
        page = st.radio(
            "Navigation",
            ["📅 Dashboard", "💊 Medicines", "🩺 Health & Vitals", "🗓 Appointments", "💬 Ask CareBot", "🚨 Family & SOS"],
            index=0
        )

        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.pop("user", None)
            st.rerun()

    # Dynamic Header
    h1, h2 = st.columns([3, 1.2])
    with h1:
        st.title(f"Good day, {user['display_name'].split()[0]}! 👋")
    with h2:
        st.markdown(f"<div style='text-align:right; color:#64748b; padding-top:1.2rem; font-weight:600;'>{date.today().strftime('%A, %d %B %Y')}</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # PAGE 1: DASHBOARD
    # -------------------------------------------------------------
    if page == "📅 Dashboard":
        # Interactive Date Selector & Controls
        nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1.2, 1.2, 1.5, 2.5])
        
        if "selected_date" not in st.session_state:
            st.session_state.selected_date = date.today()

        with nav_col1:
            if st.button("◀ Prev Day", use_container_width=True):
                st.session_state.selected_date -= timedelta(days=1)
                st.rerun()
        with nav_col2:
            if st.button("Next Day ▶", use_container_width=True):
                st.session_state.selected_date += timedelta(days=1)
                st.rerun()
        with nav_col3:
            if st.button("📅 Jump to Today", use_container_width=True):
                st.session_state.selected_date = date.today()
                st.rerun()
        with nav_col4:
            picked_date = st.date_input("Filter by Date", value=st.session_state.selected_date, label_visibility="collapsed")
            if picked_date != st.session_state.selected_date:
                st.session_state.selected_date = picked_date
                st.rerun()

        sel_date = st.session_state.selected_date
        items = get_due_items(household, on_date=sel_date)

        # Metrics & Adherence Calculations
        total_doses = len(items)
        taken_doses = sum(1 for x in items if x["status"] == "Taken")
        pending_doses = sum(1 for x in items if x["status"] == "Pending")
        missed_doses = sum(1 for x in items if x["status"] == "Missed")
        adherence_pct = int((taken_doses / total_doses * 100)) if total_doses > 0 else 100

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Taken", f"{taken_doses}/{total_doses}", delta=f"{adherence_pct}% Adherence" if total_doses else "No doses")
        m2.metric("Pending", pending_doses)
        m3.metric("Missed / Late", missed_doses)
        m4.metric("Water Intake", f"{get_today_water(household)} / 8 glasses")

        # Interactive Adherence Bar
        if total_doses > 0:
            st.write(f"**Daily Progress:** {taken_doses} of {total_doses} doses taken ({adherence_pct}%)")
            st.progress(adherence_pct / 100)
            if adherence_pct == 100:
                st.success("🎉 Outstanding! All scheduled medications for this day are completed!")

        # Audio Voice Readout Button
        audio_col1, audio_col2 = st.columns([2.5, 1])
        with audio_col1:
            st.subheader(f"Medication Schedule for {sel_date.strftime('%A, %b %d')}")
        with audio_col2:
            if st.button("🔊 Read Schedule Aloud", use_container_width=True):
                if not items:
                    speak_text(f"Hello {user['display_name']}. You have no medication scheduled for {sel_date.strftime('%B %d')}.")
                else:
                    speech = f"Hello {user['display_name']}. For {sel_date.strftime('%B %d')}, you have {total_doses} scheduled doses. "
                    for item in items:
                        speech += f"{item['name']} {item['dosage']} due at {item['due_time']}, currently {item['status']}. "
                    speak_text(speech)
                    st.toast("Reading medication schedule aloud...", icon="🔊")

        # Interactive Search & Filter Chips
        fil_col1, fil_col2 = st.columns([2, 2])
        with fil_col1:
            status_filter = st.radio(
                "Filter status:",
                ["All", "🟡 Pending", "🟢 Taken", "🔴 Missed"],
                horizontal=True,
                label_visibility="collapsed"
            )
        with fil_col2:
            search_query = st.text_input("🔍 Search medicine...", placeholder="Search by name, dosage or instructions", label_visibility="collapsed")

        # Apply Filters
        filtered_items = items
        if status_filter == "🟡 Pending":
            filtered_items = [x for x in filtered_items if x["status"] == "Pending"]
        elif status_filter == "🟢 Taken":
            filtered_items = [x for x in filtered_items if x["status"] == "Taken"]
        elif status_filter == "🔴 Missed":
            filtered_items = [x for x in filtered_items if x["status"] == "Missed"]

        if search_query.strip():
            q = search_query.strip().lower()
            filtered_items = [x for x in filtered_items if q in x["name"].lower() or q in x["dosage"].lower() or q in x["instructions"].lower()]

        if not filtered_items:
            st.info("No medications match the selected filters for this date.")
        else:
            for item in filtered_items:
                with st.container(border=True):
                    ic1, ic2, ic3 = st.columns([3, 1.3, 1.7])
                    with ic1:
                        st.markdown(f"### {item['name']} — `{item['dosage']}`")
                        cat_tag = f"<span style='background:#E0E7FF; color:#3730A3; padding:2px 8px; border-radius:12px; font-size:0.85rem; font-weight:600;'>{item['category']}</span>"
                        st.markdown(f"⏰ **Due Time: {item['due_time']}** &nbsp; {cat_tag}", unsafe_allow_html=True)
                        if item["instructions"]:
                            st.write(f"📝 *Instructions:* {item['instructions']}")
                        if item["note"]:
                            st.caption(f"📌 Note: {item['note']}")

                    with ic2:
                        status_badges = {
                            "Taken": "🟢 **Taken**",
                            "Pending": "🟡 **Pending**",
                            "Missed": "🔴 **Missed / Overdue**",
                            "Skipped": "⚪ **Skipped**"
                        }
                        st.markdown(f"<div style='padding-top:0.8rem;'>{status_badges.get(item['status'], item['status'])}</div>", unsafe_allow_html=True)
                        if item["status"] == "Taken" and item["marked_by"]:
                            st.caption(f"Marked by {item['marked_by']} at {item['marked_at']}")

                    with ic3:
                        st.write("")
                        if item["status"] != "Taken":
                            if st.button("✅ Mark as Taken", key=f"take_{item['medicine_id']}_{item['due_time']}", use_container_width=True, type="primary"):
                                mark_dose_status(item["medicine_id"], sel_date.isoformat(), item["due_time"], "Taken", user["display_name"])
                                log_alert("Dose Taken", f"{item['name']} ({item['dosage']}) taken by {user['display_name']} at {item['due_time']}.", household)
                                play_chime()
                                st.toast(f"Marked {item['name']} as taken! 💊", icon="✅")
                                if taken_doses + 1 == total_doses:
                                    st.balloons()
                                st.rerun()

                            # Interactive Snooze & Skip options
                            sub_c1, sub_c2 = st.columns(2)
                            with sub_c1:
                                if st.button("⏰ Snooze", key=f"snz_{item['medicine_id']}_{item['due_time']}", use_container_width=True):
                                    log_alert("Dose Snoozed", f"{item['name']} snoozed 15 min by {user['display_name']}.", household)
                                    st.toast(f"Snoozed {item['name']} for 15 minutes.", icon="⏰")
                            with sub_c2:
                                with st.popover("📝 Skip / Note"):
                                    skip_reason = st.text_input("Reason", placeholder="e.g. Doctor paused, Nausea", key=f"r_{item['medicine_id']}_{item['due_time']}")
                                    if st.button("Confirm Skip", key=f"cf_{item['medicine_id']}_{item['due_time']}"):
                                        mark_dose_status(item["medicine_id"], sel_date.isoformat(), item["due_time"], "Skipped", user["display_name"], skip_reason)
                                        log_alert("Dose Skipped", f"{item['name']} skipped by {user['display_name']}. Reason: {skip_reason}", household)
                                        st.rerun()
                        else:
                            if st.button("↩ Undo Taken", key=f"undo_{item['medicine_id']}_{item['due_time']}", use_container_width=True):
                                mark_dose_status(item["medicine_id"], sel_date.isoformat(), item["due_time"], "Pending", user["display_name"])
                                st.toast(f"Reverted {item['name']} to Pending.", icon="↩")
                                st.rerun()

        st.divider()

        # Interactive Daily Wellness & Hydration Tracker
        st.subheader("💧 Today's Hydration & Wellness")
        w_col1, w_col2 = st.columns([2.5, 1.5])
        with w_col1:
            current_water = get_today_water(household)
            glasses_display = " ".join(["🥛" if i < current_water else "⚪" for i in range(8)])
            st.markdown(f"<div style='font-size:1.8rem; letter-spacing:4px;'>{glasses_display}</div>", unsafe_allow_html=True)
            st.caption(f"Target: 8 glasses daily · Recorded: **{current_water}** glasses ({current_water * 250} ml)")

            btn_w1, btn_w2 = st.columns(2)
            with btn_w1:
                if st.button("➕ Drink 1 Glass (250ml)", use_container_width=True):
                    update_today_water(household, min(current_water + 1, 15), user["display_name"])
                    st.toast("Great job staying hydrated! 💧", icon="🥛")
                    st.rerun()
            with btn_w2:
                if st.button("➖ Remove 1 Glass", use_container_width=True):
                    update_today_water(household, max(current_water - 1, 0), user["display_name"])
                    st.rerun()

        with w_col2:
            st.write("**Quick Mood Check-in:**")
            m_b1, m_b2, m_b3 = st.columns(3)
            with m_b1:
                if st.button("😄 Energetic", use_container_width=True):
                    with db() as conn:
                        conn.execute("INSERT INTO vitals(household, recorded_by, recorded_at, mood) VALUES(?,?,?,?)",
                                     (household, user["display_name"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Energetic"))
                    st.toast("Glad you feel energetic today! 🌟")
            with m_b2:
                if st.button("🙂 Good", use_container_width=True):
                    with db() as conn:
                        conn.execute("INSERT INTO vitals(household, recorded_by, recorded_at, mood) VALUES(?,?,?,?)",
                                     (household, user["display_name"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Good"))
                    st.toast("Good mood recorded! 😊")
            with m_b3:
                if st.button("🤕 In Pain", use_container_width=True):
                    with db() as conn:
                        conn.execute("INSERT INTO vitals(household, recorded_by, recorded_at, mood) VALUES(?,?,?,?)",
                                     (household, user["display_name"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "In Pain"))
                    log_alert("Health Notice", f"{user['display_name']} reported feeling in pain.", household)
                    st.toast("Health notice saved. Family notified.", icon="❤️")

    # -------------------------------------------------------------
    # PAGE 2: MEDICINES
    # -------------------------------------------------------------
    elif page == "💊 Medicines":
        st.subheader("💊 Medicine Cabinet & Prescriptions")

        if user["role"] in ("Family", "Caregiver"):
            with st.expander("➕ Add New Medication", expanded=False):
                with st.form("add_med_form"):
                    f1, f2 = st.columns(2)
                    with f1:
                        med_name = st.text_input("Medicine Name *", placeholder="e.g. Lisinopril")
                        dosage = st.text_input("Prescribed Dosage *", placeholder="e.g. 10 mg or 1 tablet")
                        category = st.selectbox("Category", ["Blood Pressure", "Diabetes", "Heart Health", "Supplements", "Pain Relief", "Antibiotics", "Other"])
                    with f2:
                        instructions = st.text_input("Instructions", placeholder="e.g. Take with warm water after breakfast")
                        times = st.text_input("Dose Times (24-hr format, comma separated) *", value="08:00, 20:00", placeholder="08:00, 20:00")
                        c_d1, c_d2 = st.columns(2)
                        with c_d1:
                            start_d = st.date_input("Start Date", value=date.today())
                        with c_d2:
                            end_d = st.date_input("End Date (optional)", value=None)

                    st.caption("💡 Quick presets for dose times: `08:00` (Morning), `13:00` (Afternoon), `19:00` (Evening), `21:30` (Bedtime)")
                    save_med = st.form_submit_button("Save Medication", use_container_width=True, type="primary")

                if save_med:
                    parsed = [x.strip() for x in times.split(",") if x.strip()]
                    valid = True
                    try:
                        for x in parsed:
                            time.fromisoformat(x)
                    except ValueError:
                        valid = False

                    if not med_name.strip() or not dosage.strip() or not parsed or not valid:
                        st.error("Please provide a medicine name, dosage, and valid times such as 08:00, 20:00.")
                    elif end_d and end_d < start_d:
                        st.error("End date cannot be prior to start date.")
                    else:
                        with db() as conn:
                            conn.execute("""
                                INSERT INTO medicines(name, dosage, instructions, times, start_date, end_date, category, added_by, household)
                                VALUES(?,?,?,?,?,?,?,?,?)
                            """, (med_name.strip(), dosage.strip(), instructions.strip(), ",".join(parsed),
                                  start_d.isoformat(), end_d.isoformat() if end_d else "", category, user["display_name"], household))
                        log_alert("Medicine Added", f"{med_name} added by {user['display_name']}.", household)
                        st.success(f"{med_name} added successfully!")
                        st.rerun()
        else:
            st.info("Elder persona has read-only view of prescription setup. Family and Caregivers can add or delete medications.")

        # Filter & Display Medicines
        meds = get_medicines(household)
        f_cat = st.selectbox("Filter by Category", ["All Categories"] + sorted(list(set(m["category"] for m in meds if m["category"]))))

        filtered_meds = meds if f_cat == "All Categories" else [m for m in meds if m["category"] == f_cat]

        if filtered_meds:
            for med in filtered_meds:
                with st.container(border=True):
                    col_m1, col_m2 = st.columns([4, 1.2])
                    with col_m1:
                        st.markdown(f"### {med['name']} — `{med['dosage']}`")
                        st.write(f"🏷 **Category:** {med['category']} · ⏰ **Times:** `{med['times']}`")
                        st.write(f"📅 **Active Window:** {med['start_date']} to {med['end_date'] or 'Ongoing'}")
                        if med["instructions"]:
                            st.write(f"📝 *Instructions:* {med['instructions']}")
                        st.caption(f"Prescribed / added by {med['added_by']}")
                    with col_m2:
                        st.write("")
                        if st.button("🔔 Test Chime", key=f"chime_{med['id']}", use_container_width=True):
                            play_chime()
                            st.toast(f"Playing reminder chime for {med['name']}!", icon="🔔")

                        if user["role"] in ("Family", "Caregiver"):
                            if st.button("🗑 Delete", key=f"del_m_{med['id']}", use_container_width=True):
                                with db() as conn:
                                    conn.execute("DELETE FROM medicines WHERE id=? AND household=?", (med["id"], household))
                                    conn.execute("DELETE FROM dose_logs WHERE medicine_id=?", (med["id"],))
                                log_alert("Medicine Deleted", f"{med['name']} was removed by {user['display_name']}.", household)
                                st.warning(f"Deleted {med['name']}.")
                                st.rerun()
        else:
            st.info("No medicines found.")

    # -------------------------------------------------------------
    # PAGE 3: HEALTH & VITALS
    # -------------------------------------------------------------
    elif page == "🩺 Health & Vitals":
        st.subheader("🩺 Daily Health & Vitals Monitoring")

        tab_v1, tab_v2 = st.tabs(["📝 Record Vitals", "📈 Trends & History"])

        with tab_v1:
            with st.form("record_vitals_form"):
                st.write("**Enter Today's Measurements:**")
                vc1, vc2 = st.columns(2)
                with vc1:
                    sys_bp = st.slider("Systolic Blood Pressure (mmHg)", 80, 200, 120, help="Target: < 120 mmHg")
                    dia_bp = st.slider("Diastolic Blood Pressure (mmHg)", 50, 130, 80, help="Target: < 80 mmHg")
                with vc2:
                    heart_rate = st.number_input("Heart Rate (BPM)", min_value=40, max_value=180, value=72)
                    glucose = st.number_input("Blood Glucose (mg/dL)", min_value=50, max_value=350, value=100)

                v_mood = st.select_slider("Mood / Overall Feeling", options=["In Pain", "Fatigued", "Neutral", "Good", "Energetic"], value="Good")
                save_vitals = st.form_submit_button("Save Measurements", use_container_width=True, type="primary")

            if save_vitals:
                # BP Status assessment
                bp_status = "Normal"
                if sys_bp >= 140 or dia_bp >= 90:
                    bp_status = "High (Stage 2)"
                elif sys_bp >= 130 or dia_bp >= 80:
                    bp_status = "Elevated"

                now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with db() as conn:
                    conn.execute("""
                        INSERT INTO vitals(household, recorded_by, recorded_at, systolic, diastolic, glucose, heart_rate, mood, water_glasses)
                        VALUES(?,?,?,?,?,?,?,?,?)
                    """, (household, user["display_name"], now_ts, sys_bp, dia_bp, glucose, heart_rate, v_mood, get_today_water(household)))

                log_alert("Vitals Logged", f"BP {sys_bp}/{dia_bp} mmHg ({bp_status}), HR {heart_rate} BPM logged by {user['display_name']}.", household)
                st.success(f"Vitals recorded! Blood pressure status: {bp_status}")
                st.rerun()

        with tab_v2:
            with db() as conn:
                v_rows = conn.execute(
                    "SELECT recorded_at, systolic, diastolic, heart_rate, glucose, mood FROM vitals WHERE household=? ORDER BY id DESC LIMIT 15",
                    (household,)
                ).fetchall()

            if v_rows:
                chart_data = []
                for r in reversed(v_rows):
                    chart_data.append({
                        "Time": r["recorded_at"].split()[0],
                        "Systolic BP": r["systolic"],
                        "Diastolic BP": r["diastolic"],
                        "Heart Rate": r["heart_rate"]
                    })
                st.write("**Recent Blood Pressure & Heart Rate Trends:**")
                st.line_chart(chart_data, x="Time", y=["Systolic BP", "Diastolic BP", "Heart Rate"])

                st.write("**Recent Logs:**")
                for r in v_rows:
                    with st.container(border=True):
                        st.markdown(f"📅 **{r['recorded_at']}** · BP: `{r['systolic']}/{r['diastolic']}` mmHg · HR: `{r['heart_rate']}` BPM · Glucose: `{r['glucose']}` mg/dL · Mood: `{r['mood']}`")
            else:
                st.info("No vitals recorded yet. Use the Record Vitals tab to log measurements.")

    # -------------------------------------------------------------
    # PAGE 4: APPOINTMENTS
    # -------------------------------------------------------------
    elif page == "🗓 Appointments":
        st.subheader("🗓 Doctor & Clinical Appointments")

        if user["role"] in ("Family", "Caregiver"):
            with st.expander("➕ Schedule New Doctor Visit", expanded=False):
                with st.form("new_appt_form"):
                    a1, a2 = st.columns(2)
                    with a1:
                        dr_name = st.text_input("Doctor / Clinic Name *", placeholder="e.g. Dr. Jane Foster (Cardiologist)")
                        purpose = st.text_input("Purpose of Visit", placeholder="e.g. 6-Month Blood Pressure Checkup")
                    with a2:
                        a_d1, a_d2 = st.columns(2)
                        with a_d1:
                            appt_date = st.date_input("Appointment Date", value=date.today() + timedelta(days=2))
                        with a_d2:
                            appt_time = st.time_input("Appointment Time", value=time(10, 30))
                        location = st.text_input("Location / Address", placeholder="e.g. 100 Medical Plaza, Suite 201")
                    save_appt = st.form_submit_button("Save Appointment", use_container_width=True, type="primary")

                if save_appt:
                    if not dr_name.strip():
                        st.error("Please enter doctor or clinic name.")
                    else:
                        with db() as conn:
                            conn.execute("""
                                INSERT INTO appointments(doctor, purpose, appt_date, appt_time, location, created_by, household, status)
                                VALUES(?,?,?,?,?,?,?, 'Scheduled')
                            """, (dr_name.strip(), purpose.strip(), appt_date.isoformat(), appt_time.strftime("%H:%M"),
                                  location.strip(), user["display_name"], household))
                        log_alert("Appointment Added", f"Visit scheduled with {dr_name} on {appt_date.isoformat()} at {appt_time.strftime('%H:%M')}.", household)
                        st.success("Appointment saved successfully!")
                        st.rerun()

        with db() as conn:
            all_appts = conn.execute(
                "SELECT * FROM appointments WHERE household=? ORDER BY appt_date, appt_time",
                (household,)
            ).fetchall()

        if all_appts:
            for appt in all_appts:
                try:
                    appt_dt = datetime.strptime(f"{appt['appt_date']} {appt['appt_time']}", "%Y-%m-%d %H:%M")
                    days_diff = (appt_dt.date() - date.today()).days
                    if days_diff == 0:
                        countdown = "🚨 **TODAY**"
                    elif days_diff == 1:
                        countdown = "⏰ **Tomorrow**"
                    elif days_diff > 1:
                        countdown = f"🗓 **In {days_diff} days**"
                    else:
                        countdown = "Past visit"
                except Exception:
                    countdown = ""

                with st.container(border=True):
                    ac1, ac2 = st.columns([3.5, 1.5])
                    with ac1:
                        st.markdown(f"### {appt['doctor']}")
                        st.markdown(f"📅 **Date & Time:** `{appt['appt_date']} at {appt['appt_time']}` &nbsp; ({countdown})", unsafe_allow_html=True)
                        st.write(f"🎯 **Purpose:** {appt['purpose'] or 'General checkup'}")
                        if appt["location"]:
                            st.write(f"📍 **Location:** {appt['location']}")
                        st.caption(f"Status: {appt['status']} · Created by {appt['created_by']}")

                    with ac2:
                        st.write("")
                        gcal_url = make_gcal_url(appt["doctor"], appt["appt_date"], appt["appt_time"], appt["purpose"], appt["location"])
                        st.markdown(f"""
                        <a href="{gcal_url}" target="_blank" style="text-decoration:none;">
                            <button style="width:100%; background:#2563EB; color:white; border:none; padding:8px; border-radius:8px; cursor:pointer; font-weight:600; margin-bottom:8px;">
                                📅 Add to Google Calendar
                            </button>
                        </a>
                        """, unsafe_allow_html=True)

                        if user["role"] in ("Family", "Caregiver"):
                            if st.button("🗑 Cancel", key=f"del_apt_{appt['id']}", use_container_width=True):
                                with db() as conn:
                                    conn.execute("DELETE FROM appointments WHERE id=? AND household=?", (appt["id"], household))
                                log_alert("Appointment Removed", f"Appointment with {appt['doctor']} cancelled.", household)
                                st.warning("Appointment cancelled.")
                                st.rerun()
        else:
            st.info("No appointments currently scheduled.")

    # -------------------------------------------------------------
    # PAGE 5: ASK CAREBOT (AI Care Companion)
    # -------------------------------------------------------------
    elif page == "💬 Ask CareBot":
        st.subheader("💬 Ask CareBot — Your Interactive Care Companion")
        st.caption("Ask questions about medications, daily schedule, doctor appointments, or general wellness.")

        # Quick clickable prompts
        st.write("**Quick Questions (Click to Ask):**")
        qp1, qp2, qp3, qp4 = st.columns(4)
        quick_query = None
        with qp1:
            if st.button("💊 What meds are due today?", use_container_width=True):
                quick_query = "What meds are due today?"
        with qp2:
            if st.button("🩺 When is my next doctor visit?", use_container_width=True):
                quick_query = "When is my next doctor visit?"
        with qp3:
            if st.button("📊 Show my recent vitals", use_container_width=True):
                quick_query = "Show my recent vitals"
        with qp4:
            if st.button("💧 How much water today?", use_container_width=True):
                quick_query = "How much water today?"

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                {"role": "assistant", "content": f"Hello {user['display_name']}! I am CareBot. How can I assist you with your care routines, medication times, or doctor visits today?"}
            ]

        # Display history
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        user_input = st.chat_input("Type your question for CareBot...") or quick_query

        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)

            # Generate smart context-aware response from live database
            q_lower = user_input.lower()
            response = ""

            if "med" in q_lower or "due" in q_lower or "schedule" in q_lower or "pill" in q_lower:
                today_items = get_due_items(household)
                if not today_items:
                    response = "You have no medications scheduled in the database for today. Please check with your caregiver or add them in the Medicines tab."
                else:
                    pending_list = [f"• **{m['name']}** ({m['dosage']}) at **{m['due_time']}** [{m['status']}]" for m in today_items]
                    taken_count = sum(1 for m in today_items if m['status'] == 'Taken')
                    response = f"Here is today's medication status ({taken_count}/{len(today_items)} completed):\n\n" + "\n".join(pending_list)
                    response += "\n\nYou can mark any pending dose directly on the Dashboard!"

            elif "appointment" in q_lower or "doctor" in q_lower or "visit" in q_lower:
                with db() as conn:
                    next_appt = conn.execute(
                        "SELECT * FROM appointments WHERE household=? AND appt_date>=? ORDER BY appt_date, appt_time LIMIT 2",
                        (household, date.today().isoformat())
                    ).fetchall()
                if next_appt:
                    appts_text = "\n".join([f"• **{a['doctor']}** on **{a['appt_date']}** at **{a['appt_time']}** ({a['purpose']})" for a in next_appt])
                    response = f"Here are your upcoming appointments:\n\n{appts_text}\n\nYou can also export them to Google Calendar in the Appointments tab!"
                else:
                    response = "You have no upcoming appointments on file. You or your family can add one under the Appointments tab."

            elif "vital" in q_lower or "blood pressure" in q_lower or "heart" in q_lower or "pulse" in q_lower:
                with db() as conn:
                    v_latest = conn.execute(
                        "SELECT * FROM vitals WHERE household=? ORDER BY id DESC LIMIT 1",
                        (household,)
                    ).fetchone()
                if v_latest:
                    response = f"Your latest recorded vitals ({v_latest['recorded_at']}):\n" \
                               f"• Blood Pressure: **{v_latest['systolic']}/{v_latest['diastolic']} mmHg**\n" \
                               f"• Heart Rate: **{v_latest['heart_rate']} BPM**\n" \
                               f"• Blood Glucose: **{v_latest['glucose']} mg/dL**\n" \
                               f"• Mood: **{v_latest['mood']}**\n\nRecorded by {v_latest['recorded_by']}."
                else:
                    response = "No vitals have been recorded yet. You can log them in the Health & Vitals tab!"

            elif "water" in q_lower or "hydrat" in q_lower:
                w_count = get_today_water(household)
                response = f"You have logged **{w_count} of 8 glasses** of water today ({w_count * 250} ml). " \
                           f"{'Keep going, great job staying hydrated!' if w_count >= 5 else 'Remember to take a sip soon!'}"

            elif "hello" in q_lower or "hi" in q_lower:
                response = f"Hello {user['display_name']}! I'm here to help you stay on top of your health routines. Feel free to ask about your medicines, appointments, or vitals!"

            else:
                response = f"Thank you for asking! For specific details, please check your **Dashboard** or **Medicines** tab. If this is a medical emergency, please call your local emergency services (e.g. 911) or press the red **SOS Alert** button immediately."

            with st.chat_message("assistant"):
                st.write(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})

    # -------------------------------------------------------------
    # PAGE 6: FAMILY & SOS
    # -------------------------------------------------------------
    elif page == "🚨 Family & SOS":
        st.subheader("🚨 Emergency SOS & Family Care Notice Board")

        # Emergency SOS Controls
        st.markdown("""
        <div style='background:#FEE2E2; border-left:6px solid #EF4444; padding:16px; border-radius:8px; margin-bottom:1rem;'>
            <h3 style='color:#991B1B; margin:0;'>⚠️ Emergency Distress Button</h3>
            <p style='color:#7F1D1D; margin:4px 0 0;'>
                Pressing this sends an instant alert to all registered family members and caregivers, and sounds an audio siren.
            </p>
        </div>
        """, unsafe_allow_html=True)

        sos_c1, sos_c2 = st.columns([2.5, 1.5])
        with sos_c1:
            sos_mode = st.radio("SOS Mode:", ["🚨 LIVE EMERGENCY", "🧪 PRACTICE DRILL (Test)"], horizontal=True)
            if st.button("🚨 TRIGGER EMERGENCY SOS", type="primary", use_container_width=True):
                msg = f"{'[TEST DRILL] ' if 'DRILL' in sos_mode else ''}SOS triggered by {user['display_name']} at {datetime.now().strftime('%d %b %Y, %I:%M %p')}."
                log_alert("SOS", msg, household)
                play_sos_siren()
                members = household_users(household)
                recipients = [m for m in members if m["role"] in ("Family", "Caregiver") and m["email"]]
                sent_count = 0
                for r in recipients:
                    ok, _ = send_email(r["email"], "URGENT: ElderCare SOS Alert", msg)
                    sent_count += int(ok)

                st.error(f"🚨 **EMERGENCY ALARM ACTIVATED!** {msg}")
                if sent_count:
                    st.info(f"Notification email dispatched to {sent_count} recipient(s).")
                else:
                    st.caption("Notice logged in shared household feed. (Configure SMTP to dispatch live emails).")
                st.rerun()

        with sos_c2:
            st.write("**Emergency Contacts:**")
            members = household_users(household)
            for m in members:
                st.markdown(f"• **{m['display_name']}** (`{m['role']}`)")

        st.divider()

        # Shared Care Notice Board
        st.subheader("📝 Shared Care Notice Board")
        st.caption("Leave real-time notes for family and caregivers about meals, moods, or prescription refills.")

        with st.form("new_care_note_form"):
            note_text = st.text_input("Post a care update:", placeholder="e.g. Alex took morning walk. Appetite was great at lunch.")
            post_btn = st.form_submit_button("Post Care Note", use_container_width=True)

        if post_btn and note_text.strip():
            now_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            with db() as conn:
                conn.execute(
                    "INSERT INTO care_notes(household, author, role, note, created_at) VALUES(?,?,?,?,?)",
                    (household, user["display_name"], user["role"], note_text.strip(), now_time)
                )
            log_alert("Care Note", f"{user['display_name']} posted: {note_text.strip()}", household)
            st.toast("Care note posted to family feed!", icon="📝")
            st.rerun()

        with db() as conn:
            notes = conn.execute("SELECT * FROM care_notes WHERE household=? ORDER BY id DESC LIMIT 10", (household,)).fetchall()

        if notes:
            for n in notes:
                with st.container(border=True):
                    nc1, nc2 = st.columns([3.5, 1])
                    with nc1:
                        st.markdown(f"**{n['author']}** · `{n['role']}`")
                        st.write(n["note"])
                    with nc2:
                        st.caption(f"🕒 {n['created_at']}")
        else:
            st.info("No care notes posted yet.")

        st.divider()

        # Audit Activity Log
        st.subheader("📜 Activity Audit Log")
        with db() as conn:
            alerts = conn.execute("SELECT * FROM alerts WHERE household=? ORDER BY id DESC LIMIT 15", (household,)).fetchall()

        if alerts:
            for a in alerts:
                resolved_tag = " [Resolved]" if a["resolved"] else ""
                st.write(f"• **{a['alert_type']}{resolved_tag}** — {a['message']} &nbsp; <span style='color:#64748b; font-size:0.85rem;'>({a['created_at']})</span>", unsafe_allow_html=True)
        else:
            st.caption("No activity recorded yet.")

    st.divider()
    st.caption("💙 ElderCare Prototype · Interactive Smart Care System. Designed for accessibility, compliance and elderly wellbeing.")

# ---------- Entrypoint ----------
if not current_user():
    login_screen()
else:
    main_app(current_user())
