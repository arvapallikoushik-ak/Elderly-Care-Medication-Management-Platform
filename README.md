# ElderCare — Smart & Interactive Elder Care Companion 💙

A modern, highly interactive **Streamlit + SQLite** application designed for elderly care, medication tracking, health vitals monitoring, appointment coordination, and emergency response.

---

## 🌟 Interactive Highlights

### 1. ⚡ One-Click Persona Quick Sign-In
- Instant 1-click sign-in cards on the login screen:
  - 👴 **Alex (Elder)** — Opens directly into Senior Accessibility Mode.
  - 👨‍👩‍👧 **Sam (Family)** — Full access to care notices, adherence, and SOS tracking.
  - 🩺 **Jordan (Caregiver)** — Full clinical access to add/manage medications and appointments.
- Traditional username/password login is also supported.
- Live in-app persona switcher in the sidebar for rapid multi-user testing.

### 2. 👓 Senior Accessibility Mode
- Large readable typography (1.2x scale), bold high-contrast buttons, and touch-friendly UI.
- Toggle anytime from the sidebar.

### 3. 🔊 Voice Readout & Sound Effects (Web Speech & Web Audio APIs)
- **"Read Schedule Aloud"**: Built-in browser text-to-speech reads the day's medication schedule at a calm, elderly-friendly pace.
- **Medication Reminder Chimes**: Pleasant two-tone chime when doses are taken or tested.
- **Celebration Confetti**: Triggers `st.balloons()` when all daily doses are completed!
- **Emergency Siren**: High-urgency audio siren when SOS is triggered.

### 4. 📅 Interactive Schedule & Date Navigator
- Navigate between days (`◀ Prev Day`, `📅 Jump to Today`, `Next Day ▶`) or pick any date.
- Real-time **Adherence Progress Bar** with percentage score and celebratory feedback.
- Interactive status filters (`All`, `🟡 Pending`, `🟢 Taken`, `🔴 Missed`) and live medication search.
- Per-dose action buttons:
  - `✅ Mark as Taken`
  - `⏰ Snooze (15m)`
  - `📝 Skip / Note` (record reasons such as doctor advice or fasting)
  - `↩ Undo` (revert accidental clicks)

### 5. 💧 Hydration & Mood Tracker
- Interactive **8-Glass Water Counter**: Click `➕ Drink 1 Glass` to fill water glasses visually.
- One-click daily mood check-in (`😄 Energetic`, `🙂 Good`, `🤕 In Pain`).

### 6. 🩺 Health & Vitals Monitoring
- Slider & number inputs for Blood Pressure (Systolic/Diastolic), Heart Rate, and Blood Glucose.
- Automatic Blood Pressure status categorization (Normal, Elevated, High).
- **Interactive Trend Line Charts**: Visualizes historical blood pressure and heart rate changes over time.

### 7. 🗓 Doctor Appointments & Google Calendar Export
- Relative countdown badges (`🚨 TODAY`, `⏰ Tomorrow`, `🗓 In X days`).
- **📅 Add to Google Calendar**: Direct one-click export button to add the appointment with date, time, notes, and clinic location pre-filled.

### 8. 💬 Ask CareBot (Interactive AI Companion)
- Chat with **CareBot** to ask questions about today's medicine schedule, next doctor appointments, recent vitals, or hydration levels.
- Includes quick-click question chips for effortless one-touch queries.

### 9. 🚨 Emergency SOS & Persistent Alert Banner
- Live Emergency vs. Practice Drill modes.
- Sounds the Web Audio siren and alerts all household members.
- Displays a persistent, top-of-page emergency banner across every view until marked resolved.

### 10. 📝 Shared Family Care Notice Board
- Real-time notice board for caregivers and family to post daily updates (meals, walks, pharmacy runs).

---

## 🚀 Running Locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Run:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The database (`eldercare.db`) is automatically initialized with realistic starter data for medicines, appointments, vitals, and care notes.

---

## 👥 Demo Accounts

| Role | Username | Password | Quick Login |
|---|---|---|---|
| **Elder** | `elder` | `elder123` | Click 👴 Alex card |
| **Family** | `family` | `family123` | Click 👨‍👩‍👧 Sam card |
| **Caregiver** | `caregiver` | `care123` | Click 🩺 Jordan card |

---

## ⚖️ Disclaimer

*ElderCare is a technology prototype for demonstration purposes. It is not a certified medical device and does not substitute for professional medical diagnosis, advice, or emergency services.*
