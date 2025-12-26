import os
import io
import calendar
import pandas as pd
from datetime import datetime, date, timedelta
from flask import Flask, request, redirect, url_for, render_template_string, flash, send_file
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
    nickname = db.Column(db.String(120), nullable=True)

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
    .sticky-th { position: sticky; top: 0; background: #f8f9fa; }
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
      <a class="btn btn-outline-dark btn-sm" href="{{ url_for('weekly_timetable') }}">Weekly Grid</a>
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
    sessions = current_month_sessions().all()
    rows = "".join(f"<tr><td>{s.session_date}</td><td>{s.teacher.name}</td><td>{s.student.name}</td><td>{s.subject.name}</td></tr>" for s in sessions)
    return render("<h5>Current Month Timetable</h5><table class='table'><tr><th>Date</th><th>Teacher</th><th>Student</th><th>Subject</th></tr>" + rows + "</table>")

@app.route("/weekly_timetable")
def weekly_timetable():
    sessions = ClassSession.query.order_by(ClassSession.session_date.asc()).all()
    rows = "".join(f"<tr><td>{s.session_date}</td><td>{s.start_time}-{s.end_time}</td><td>{s.teacher.name}</td><td>{s.student.name}</td><td>{s.subject.name}</td></tr>" for s in sessions)
    return render("<h5>Weekly Grid</h5><table class='table'><tr><th>Date</th><th>Time</th><th>Teacher</th><th>Student</th><th>Subject</th></tr>" + rows + "</table>")

@app.route("/teachers")
def manage_teachers():
    teachers = Teacher.query.all()
    rows = "".join(f"<li>{t.name} ({t.nickname or ''})</li>" for t in teachers)
    return render("<h5>Teachers</h5><ul>" + rows + "</ul>")

@app.route("/students")
def manage_students():
    students = Student.query.all()
    rows = "".join(f"<li>{s.name} (Rate: {s.rate_per_class})</li>" for s in students)
    return render("<h5>Students</h5><ul>" + rows + "</ul>")

@app.route("/subjects")
def manage_subjects():
    subjects = Subject.query.all()
    rows = "".join(f"<li>{sub.name}</li>" for sub in subjects)
    return render("<h5>Subjects</h5><ul>" + rows + "</ul>")

@app.route("/sessions/add")
def add_session():
    return render("<h5>Add Session form (to be implemented)</h5>")

@app.route("/payments")
def payments():
    students = Student.query.all()
    rows = "".join(f"<li>{s.name}: {len(s.sessions)} sessions × {s.rate_per_class} = {len(s.sessions)*s.rate_per_class}</li>" for s in students)
    return render("<h5>Payments</h5><ul>" + rows + "</ul>")

@app.route("/teacher_totals")
def teacher_totals():
    teachers = Teacher.query.all()
    rows = "".join(f"<li>{t.name}: {len(t.sessions)} sessions</li>" for t in teachers)
    return render("<h5>Teacher Totals</h5><ul>" + rows + "</ul>")

@app.route("/logs")
def logs():
    entries = LogEntry.query.order_by(LogEntry.timestamp.desc()).all()
    rows = "".join(f"<li>{e.timestamp}: {e.action} - {e.details}</li>" for e in entries)
    return render("<h5>Logs</h5><ul>" + rows + "</ul>")

# -------------------------
# Run the app (important for Render)
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
