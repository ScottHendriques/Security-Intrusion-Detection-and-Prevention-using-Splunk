# WorkPortal — Employee Self-Service Portal

A Python Flask web application for employees to manage their duty sheets, leave requests, and off days.

## Features
- **Login / Sign Up** — Secure authentication with hashed passwords
- **Dashboard** — Today's shift, leave balance overview, upcoming duties, notifications
- **Duty Sheet** — Monthly view of all scheduled shifts with status tracking
- **Leave Requests** — Apply for annual/sick/emergency leave, view history and balance
- **Off Days** — View approved off days and automatic weekend schedule
- **Profile** — Update contact details and change password
- **Notifications** — In-app notifications for leave approvals and schedule updates

## Setup & Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```

### 3. Open in Browser
```
http://localhost:5000
```

### 4. Create an Account
- Click **Sign Up** on the login page
- Fill in your details (name, email, department, role, password)
- Demo duty sheets, leave history and notifications are automatically generated
- Log in and explore your dashboard

## Project Structure
```
employee_portal/
├── app.py                  # Main Flask application (routes, DB, auth)
├── requirements.txt        # Python dependencies
├── employee_portal.db      # SQLite database (auto-created on first run)
└── templates/
    ├── base.html           # Base layout with sidebar & topbar
    ├── login.html          # Login page
    ├── signup.html         # Registration page
    ├── dashboard.html      # Main dashboard
    ├── duty_sheet.html     # Monthly duty schedule
    ├── leaves.html         # Leave request management
    ├── off_days.html       # Off day calendar
    ├── profile.html        # User profile & password change
    └── notifications.html  # Notification centre
```

## Tech Stack
- **Backend**: Python 3, Flask, Flask-Login
- **Database**: SQLite (via Python's built-in sqlite3)
- **Auth**: Werkzeug password hashing (PBKDF2)
- **Frontend**: Pure HTML/CSS (no external frameworks required)
- **Fonts**: Google Fonts (DM Sans + Syne)
