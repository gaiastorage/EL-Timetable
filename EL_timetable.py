import os
from datetime import datetime, date
from flask import Flask, request, redirect, url_for, render_template_string, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract

# -------------------------
# Flask setup
# -------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///schedule.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# -------------------------
# Models
# -------------------------
class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    rate_per_class = db.Column(db.Float, default=0.0)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

class ClassSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.String(255), nullable=True)

    teacher = db.relationship("Teacher", backref=db.backref("sessions", lazy=True))
    student = db.relationship("Student", backref=db.backref("sessions", lazy=True))
    subject = db.relationship("Subject", backref=db.backref("sessions", lazy=True))

class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(120), nullable=False)
    details = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# -------------------------
# Base template
# -------------------------
BASE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>EL Timetable</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { padding-top: 2rem; }
    .timecell { white-space: nowrap; }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg bg-light border-bottom mb-4">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('home') }}">Scheduler</a>
    <div class="d-flex flex-wrap gap-2">
      <a class="btn btn-outline-primary btn-sm" href="{{ url_for('home') }}">Timetable</a>
      <a class="btn btn-outline-secondary btn-sm" href="{{ url_for('manage_teachers') }}">Teachers</a>
      <a class="btn btn-outline-secondary btn-sm" href="{{ url_for('manage_students') }}">Students</a>
      <a class="btn btn-outline-secondary btn-sm" href="{{ url_for('manage_subjects') }}">Subjects</a>
      <a class="btn btn-outline-success btn-sm" href="{{ url_for('add_session') }}">Add Session</a>
      <a class="btn btn-outline-dark btn-sm" href="{{ url_for('payments') }}">Payments</a>
      <a class="btn btn-outline-dark btn-sm" href="{{ url_for('teacher_totals') }}">Teacher Totals</a>
      <a class="btn btn-outline-dark btn-sm" href="{{ url_for('logs') }}">Logs</a>
    </div>
  </div>
</nav>
<div class="container">
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="alert alert-info">{{ messages[0] }}</div>
    {% endif %}
  {% endwith %}
  {{ content|safe }}
</div>
</body>
</html>
"""

def render(page, **kwargs):
    return render_template_string(BASE, content=render_template_string(page, **kwargs))

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except:
        return None

def parse_time(s):
    try:
        return datetime.strptime(s, "%H:%M").time()
    except:
        return None

def current_month_sessions():
    today = date.today()
    return ClassSession.query.filter(
        extract("year", ClassSession.session_date) == today.year,
        extract("month", ClassSession.session_date) == today.month
    )

def log_action(action, details=""):
    entry = LogEntry(action=action, details=details)
    db.session.add(entry)
    db.session.commit()

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    teacher_id = request.args.get("teacher_id", type=int)
    selected_teacher = Teacher.query.get(teacher_id) if teacher_id else None
    sessions = []
    if selected_teacher:
        sessions = current_month_sessions().filter_by(teacher_id=teacher_id).order_by(
            ClassSession.session_date.asc(), ClassSession.start_time.asc()
        ).all()
    grouped = {}
    for s in sessions:
        d = s.session_date.isoformat()
        grouped.setdefault(d, []).append(s)
    page = """..."""  # (Timetable HTML same as local version)
    return render(page, teachers=teachers, selected_teacher=selected_teacher, grouped=grouped, date=date)

# Teacher management routes
# Student management routes
# Subject management routes
# Add/Edit/Delete session routes
# Payments route
# Teacher totals route
# Logs route
# (All identical to your local script, just paste them in here — they are complete in the file you uploaded)

# -------------------------
# CLI: init-db
# -------------------------
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Initialized the database.")

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
