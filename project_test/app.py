from flask import Flask, render_template, request, redirect, send_from_directory, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime, date, timedelta
import random

app = Flask(__name__)
app.secret_key = 'employee_portal_secret_key_2024'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your portal.'
login_manager.login_message_category = 'info'

# ─── LOGGING CONFIGURATION ──────────────────────────────────────────────────

import logging
from logging.handlers import RotatingFileHandler

# Create a 'logs' directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure the Security Logger
security_log_handler = RotatingFileHandler(
    'logs/security_events.log', 
    maxBytes=1000000, 
    backupCount=5
)

# format = Splunk (Timestamp | Level | IP | Event | Message)
log_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(remote_addr)s | %(event_type)s | %(message)s')
security_log_handler.setFormatter(log_formatter)

# Create a custom logger
security_logger = logging.getLogger('security')
security_logger.setLevel(logging.INFO)
security_logger.addHandler(security_log_handler)

DATABASE = 'employee_portal.db'

def log_security_event(level, event_type, message):
    extra_data={
        'remote_addr': request.remote_addr,
        'event_type': event_type
    }
    if level.lower() == 'info':
        security_logger.info(message, extra = extra_data)
    elif level.lower() == 'warning':
        security_logger.warning(message, extra = extra_data)
    elif level.lower() == 'error':
        security_logger.error(message, extra = extra_data)

# ─── DB HELPERS ─────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        department TEXT NOT NULL,
        role TEXT NOT NULL,
        phone TEXT,
        iban TEXT,
        join_date TEXT NOT NULL,
        total_leave_days INTEGER DEFAULT 20,
        used_leave_days INTEGER DEFAULT 0,
        profile_color TEXT DEFAULT '#3B82F6'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS duty_sheets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        work_date TEXT NOT NULL,
        shift TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        location TEXT NOT NULL,
        status TEXT DEFAULT 'Scheduled',
        notes TEXT,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        leave_type TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        days INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        applied_on TEXT NOT NULL,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS off_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        off_date TEXT NOT NULL,
        reason TEXT NOT NULL,
        approved INTEGER DEFAULT 1,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        notif_type TEXT DEFAULT 'info',
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )''')

    conn.commit()
    conn.close()

# ─── USER MODEL ─────────────────────────────────────────────────────────────

class User(UserMixin):
    def __init__(self, id, emp_id, name, email, department, role, phone,
        iban, join_date, total_leave_days, used_leave_days, profile_color):
        self.id = id
        self.emp_id = emp_id
        self.name = name
        self.email = email
        self.department = department
        self.role = role
        self.phone = phone
        self.iban = iban
        self.join_date = join_date
        self.total_leave_days = total_leave_days
        self.used_leave_days = used_leave_days
        self.profile_color = profile_color

    @property
    def remaining_leave(self):
        return self.total_leave_days - self.used_leave_days

    @property
    def initials(self):
        parts = self.name.split()
        return ''.join(p[0].upper() for p in parts[:2])

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM employees WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row['id'], row['emp_id'], row['name'], row['email'],
                    row['department'], row['role'], row['phone'], row['iban'], row['join_date'],
                    row['total_leave_days'], row['used_leave_days'], row['profile_color'])
    return None

# ─── SEED DEMO DATA ──────────────────────────────────────────────────────────

def seed_demo_data(employee_id, emp_db_id):
    conn = get_db()
    c = conn.cursor()

    today = date.today()
    shifts = [('Morning', '08:00', '16:00'), ('Afternoon', '14:00', '22:00'), ('Evening', '16:00', '00:00')]
    locations = ['Main Office', 'Branch A', 'Remote', 'Warehouse', 'HQ Floor 2']

    # Generate duty sheets for current month
    for i in range(-10, 15):
        d = today + timedelta(days=i)
        if d.weekday() < 5:  # weekdays only
            shift = random.choice(shifts)
            status = 'Completed' if i < 0 else ('In Progress' if i == 0 else 'Scheduled')
            c.execute('''INSERT OR IGNORE INTO duty_sheets
                (employee_id, work_date, shift, start_time, end_time, location, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (emp_db_id, d.isoformat(), shift[0], shift[1], shift[2],
                 random.choice(locations), status))

    # Generate some leave requests
    leave_types = ['Annual Leave', 'Sick Leave', 'Emergency Leave']
    statuses = ['Approved', 'Pending', 'Rejected']
    for i in range(3):
        start = today + timedelta(days=random.randint(5, 30))
        days = random.randint(1, 3)
        end = start + timedelta(days=days - 1)
        c.execute('''INSERT OR IGNORE INTO leave_requests
            (employee_id, leave_type, start_date, end_date, days, reason, status, applied_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (emp_db_id, random.choice(leave_types), start.isoformat(), end.isoformat(),
             days, 'Personal reasons', statuses[i], today.isoformat()))

    # Off days (weekends already off, add some extras)
    for i in range(3):
        off = today + timedelta(days=random.randint(15, 40))
        c.execute('''INSERT OR IGNORE INTO off_days
            (employee_id, off_date, reason, approved)
            VALUES (?, ?, ?, ?)''',
            (emp_db_id, off.isoformat(), 'Public Holiday', 1))

    # Notifications
    messages = [
        ('Your duty schedule for next week has been published.', 'info'),
        ('Leave request approved for 2 days.', 'success'),
        ('Reminder: Submit your weekly report.', 'warning'),
    ]
    for msg, ntype in messages:
        c.execute('''INSERT INTO notifications (employee_id, message, created_at, notif_type)
            VALUES (?, ?, ?, ?)''', (emp_db_id, msg, datetime.now().isoformat(), ntype))

    conn.commit()
    conn.close()

# ─── ROUTES ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        query = f"SELECT * FROM employees WHERE email = '{email}'"
        row = conn.execute(query).fetchone()
        conn.close()
        if row :
            user = User(row['id'], row['emp_id'], row['name'], row['email'],
                        row['department'], row['role'], row['phone'], row['iban'], row['join_date'],
                        row['total_leave_days'], row['used_leave_days'], row['profile_color'])
            login_user(user, remember=request.form.get('remember'))
            #Log successful Login
            log_security_event('INFO', 'AUTH_SUCCESS', f"User login: {email}")
            return redirect(url_for('dashboard'))
        #Log failed Login
        log_security_event('WARNING', 'AUTH_FAILURE', f"Failed login Attempt: {email} ")
        flash('Invalid email or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        department = request.form.get('department', '')
        role = request.form.get('role', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()

        if not all([name, email, password, department, role]):
            flash('Please fill in all required fields.', 'error')
            return render_template('signup.html')
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('signup.html')

        conn = get_db()
        existing = conn.execute('SELECT id FROM employees WHERE email = ?', (email,)).fetchone()
        if existing:
            conn.close()
            #Log attempt to re-register existing email
            log_security_event('WARNING', 'SIGNUP_CONFLICT', f"Signup attempt with existing email: {email}")
            flash('Email already registered.', 'error')
            return render_template('signup.html')

        colors = ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#06B6D4', '#EC4899']
        emp_id = f"EMP{random.randint(1000,9999)}"
        join_date = date.today().isoformat()
        hashed = generate_password_hash(password)
        color = random.choice(colors)

        c = conn.cursor()
        c.execute('''INSERT INTO employees
            (emp_id, name, email, password, department, role, phone, iban, join_date, profile_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (emp_id, name, email, hashed, department, role, phone, '', join_date, color))
        emp_db_id = c.lastrowid
        conn.commit()
        conn.close()

        #Log successful account creation
        log_security_event('INFO', 'ACCOUNT_CREATED', f"New account created for email : {email} (EMP ID: {emp_id})")

        seed_demo_data(emp_id, emp_db_id)
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    today = date.today().isoformat()

    today_duty = conn.execute(
        'SELECT * FROM duty_sheets WHERE employee_id=? AND work_date=?',
        (current_user.id, today)).fetchone()

    upcoming = conn.execute(
        '''SELECT * FROM duty_sheets WHERE employee_id=? AND work_date > ?
           ORDER BY work_date ASC LIMIT 5''',
        (current_user.id, today)).fetchall()

    recent_leaves = conn.execute(
        '''SELECT * FROM leave_requests WHERE employee_id=?
           ORDER BY applied_on DESC LIMIT 3''',
        (current_user.id,)).fetchall()

    notifs = conn.execute(
        '''SELECT * FROM notifications WHERE employee_id=? AND is_read=0
           ORDER BY created_at DESC''',
        (current_user.id,)).fetchall()

    # Monthly duty count
    month_start = date.today().replace(day=1).isoformat()
    month_duties = conn.execute(
        '''SELECT COUNT(*) as cnt FROM duty_sheets
           WHERE employee_id=? AND work_date >= ? AND status != "Off"''',
        (current_user.id, month_start)).fetchone()['cnt']

    upcoming_off = conn.execute(
        '''SELECT * FROM off_days WHERE employee_id=? AND off_date >= ?
           ORDER BY off_date ASC LIMIT 3''',
        (current_user.id, today)).fetchall()

    conn.close()
    return render_template('dashboard.html',
        today_duty=today_duty, upcoming=upcoming,
        recent_leaves=recent_leaves, notifs=notifs,
        month_duties=month_duties, upcoming_off=upcoming_off,
        today=today)

@app.route('/duty-sheet')
@login_required
def duty_sheet():
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        year, mon = map(int, month.split('-'))
    except:
        year, mon = date.today().year, date.today().month

    conn = get_db()
    duties = conn.execute(
        '''SELECT * FROM duty_sheets
           WHERE employee_id=? AND strftime('%Y-%m', work_date)=?
           ORDER BY work_date ASC''',
        (current_user.id, month)).fetchall()
    conn.close()

    prev_month = (date(year, mon, 1) - timedelta(days=1)).strftime('%Y-%m')
    if mon == 12:
        next_month = f"{year+1}-01"
    else:
        next_month = f"{year}-{mon+1:02d}"

    return render_template('duty_sheet.html',
        duties=duties, month=month, year=year, mon=mon,
        prev_month=prev_month, next_month=next_month,
        month_name=date(year, mon, 1).strftime('%B %Y'))

@app.route('/leaves', methods=['GET', 'POST'])
@login_required
def leaves():
    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason', '').strip()

        if not all([leave_type, start_date, end_date, reason]):
            flash('Please fill all fields.', 'error')
        else:
            try:
                s = date.fromisoformat(start_date)
                e = date.fromisoformat(end_date)
                days = (e - s).days + 1
                if days < 1:
                    flash('End date must be after start date.', 'error')
                elif days > current_user.remaining_leave:
                    flash(f'Not enough leave days. You have {current_user.remaining_leave} days remaining.', 'error')
                else:
                    conn = get_db()
                    conn.execute('''INSERT INTO leave_requests
                        (employee_id, leave_type, start_date, end_date, days, reason, applied_on)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (current_user.id, leave_type, start_date, end_date, days, reason,
                         date.today().isoformat()))
                    conn.execute('''INSERT INTO notifications
                        (employee_id, message, created_at, notif_type)
                        VALUES (?, ?, ?, ?)''',
                        (current_user.id, f'Leave request submitted for {days} day(s) — {leave_type}.',
                         datetime.now().isoformat(), 'info'))
                    conn.commit()
                    conn.close()
                    #log dynamic data entry
                    log_security_event('INFO', 'LEAVE_SUBMITTED', f"User {current_user.email} applied for {days} days of {leave_type}")
                    flash('Leave request submitted successfully!', 'success')
                    return redirect(url_for('leaves'))
            except ValueError:
                flash('Invalid date format.', 'error')

    conn = get_db()
    all_leaves = conn.execute(
        'SELECT * FROM leave_requests WHERE employee_id=? ORDER BY applied_on DESC',
        (current_user.id,)).fetchall()
    conn.close()
    
    # Calculate leave progress percentage
    leave_progress = int((current_user.used_leave_days / current_user.total_leave_days * 100)) if current_user.total_leave_days > 0 else 0
    
    return render_template('leaves.html', leaves=all_leaves, leave_progress=leave_progress)

@app.route('/off-days')
@login_required
def off_days():
    conn = get_db()
    off = conn.execute(
        '''SELECT * FROM off_days WHERE employee_id=?
           ORDER BY off_date ASC''',
        (current_user.id,)).fetchall()

    # Also include weekends for current + next month as auto off-days
    today = date.today()
    weekends = []
    for i in range(60):
        d = today + timedelta(days=i)
        if d.weekday() >= 5:
            weekends.append(d.isoformat())

    conn.close()
    return render_template('off_days.html', off_days=off, weekends=weekends)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        iban = request.form.get('iban', '').strip()
        role = request.form.get('role', '').strip()
        conn = get_db()
        conn.execute('UPDATE employees SET phone=?, iban=?, role=? WHERE id=?',
                     (phone, iban, role, current_user.id))
        conn.commit()
        conn.close()
        #Log data modification
        log_security_event('INFO', 'PROFILE_UPDATED', f"Profile updated by: {current_user.email} (Fields: Phone/IBAN/Role)")
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    old = request.form.get('old_password', '')
    new = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    conn = get_db()
    row = conn.execute('SELECT password FROM employees WHERE id=?', (current_user.id,)).fetchone()
    if not check_password_hash(row['password'], old):
        #Log failed password change 
        log_security_event('WARNING', 'PASSWORD_CHANGE_FAILURE', f"Incorrect password attempt for: {current_user.email}")
        flash('Current password is incorrect.', 'error')
    elif new != confirm:
        flash('New passwords do not match.', 'error')
    elif len(new) < 6:
        flash('Password must be at least 6 characters.', 'error')
    else:
        conn.execute('UPDATE employees SET password=? WHERE id=?',
                     (generate_password_hash(new), current_user.id))
        conn.commit()
        #Log successful security setting change
        log_security_event('INFO', 'PASSWORD_CHANGED_SUCCESS', f"Password updated for: {current_user.email}")
        flash('Password changed successfully!', 'success')
    conn.close()
    return redirect(url_for('profile'))

@app.route('/mark-read/<int:notif_id>')
@login_required
def mark_read(notif_id):
    conn = get_db()
    conn.execute('UPDATE notifications SET is_read=1 WHERE id=? AND employee_id=?',
                 (notif_id, current_user.id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/notifications')
@login_required
def notifications():
    conn = get_db()
    notifs = conn.execute(
        'SELECT * FROM notifications WHERE employee_id=? ORDER BY created_at DESC',
        (current_user.id,)).fetchall()
    conn.execute('UPDATE notifications SET is_read=1 WHERE employee_id=?', (current_user.id,))
    conn.commit()
    conn.close()
    return render_template('notifications.html', notifs=notifs)

@app.route('/payslips')
@login_required
def payslips():
    emp_id = current_user.emp_id
    available_payslips = [
        {'month': 'March 2026', 'filename': f"payslip_{emp_id}_2026.pdf.pdf"},
        {'month': 'February 2026', 'filename': f"payslip_EMP4242_2026.pdf.pdf"},
        {'month': 'January 2026', 'filename': f"payslip_EMP5698_2026.pdf.pdf"}
    ]
    return render_template('payslips.html', payslips = available_payslips)

@app.route('/download-payslip/<filename>')
@login_required
def download_payslip(filename):
    #Security check: PAth traversal Detection
    if ".." in filename or filename.startswith("/"):
        log_security_event('ERROR', 'MALICIOUS_PATH_TRAVERSAL', f"User {current_user.email} attempted path traversal: {filename}")
        return "Access Denied: MAlicious Activity detected", 403
    #Security Check: Unauthorised Access
    
    #Check if admin or if file belongs to the user
    is_admin = (current_user.role.lower() == 'administrator')
    is_own_file = (current_user.emp_id in filename)
    
    if not (is_admin or is_own_file):
        log_security_event('WARNING', 'UNAUTHORISED_FILE_ACCESS', f"User {current_user.email} tried to access a restricted payslip: {filename}")
        return "Access Denied: You do not have permission to view this file", 403
    
    #Log successful access
    log_security_event('INFO', 'FILE_DOWNLOAD_SUCCESS', f"User {current_user.email} dwonloaded: {filename}")

    #point to the folder where payslips are stored
    directory = os.path.join(app.root_path, 'uploads', 'payslips')

    #To ensure the directory exists
    if not os.path.exists(directory):
        os.makedirs(directory)

    return send_from_directory(directory, filename)

# ─── RUN ─────────────────────────────────────────────────────────────────────
init_db()

if __name__ == '__main__':
    app.run(debug=True, host = "0.0.0.0", port=5000)
