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
# Helpers
# -------------------------
def render(page, **kwargs):
    BASE = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>EL Timetable</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="p-4">
    <nav class="mb-3">
      <a href="{{ url_for('home') }}" class="btn btn-sm btn-outline-primary">Timetable</a>
      <a href="{{ url_for('manage_teachers') }}" class="btn btn-sm btn-outline-secondary">Teachers</a>
      <a href="{{ url_for('manage_students') }}" class="btn btn-sm btn-outline-secondary">Students</a>
      <a href="{{ url_for('manage_subjects') }}" class="btn btn-sm btn-outline-secondary">Subjects</a>
      <a href="{{ url_for('add_session') }}" class="btn btn-sm btn-outline-success">Add Session</a>
      <a href="{{ url_for('payments') }}" class="btn btn-sm btn-outline-dark">Payments</a>
      <a href="{{ url_for('teacher_totals') }}" class="btn btn-sm btn-outline-dark">Teacher Totals</a>
      <a href="{{ url_for('weekly_timetable') }}" class="btn btn-sm btn-outline-dark">Weekly Grid</a>
      <a href="{{ url_for('logs') }}" class="btn btn-sm btn-outline-dark">Logs</a>
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

def log_action(action, details=""):
    entry = LogEntry(action=action, details=details)
    db.session.add(entry)
    db.session.commit()

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    sessions = ClassSession.query.order_by(ClassSession.session_date.asc()).all()
    rows = "".join(
        f"<tr><td>{s.session_date}</td><td>{s.start_time}-{s.end_time}</td>"
        f"<td>{s.teacher.name}</td><td>{s.student.name}</td><td>{s.subject.name}</td>"
        f"<td><a href='{url_for('delete_session', session_id=s.id)}' class='btn btn-sm btn-danger'>Delete</a></td></tr>"
        for s in sessions
    )
    return render("<h5>All Sessions</h5><table class='table'><tr><th>Date</th><th>Time</th><th>Teacher</th><th>Student</th><th>Subject</th><th>Action</th></tr>" + rows + "</table>")

@app.route("/sessions/delete/<int:session_id>")
def delete_session(session_id):
    s = ClassSession.query.get_or_404(session_id)
    db.session.delete(s)
    db.session.commit()
    log_action("Delete Session", f"Session {session_id}")
    flash("Session deleted.")
    return redirect(url_for("home"))

@app.route("/teachers", methods=["GET", "POST"])
def manage_teachers():
    if request.method == "POST":
        name = request.form.get("name")
        nickname = request.form.get("nickname")
        if name:
            t = Teacher(name=name, nickname=nickname)
            db.session.add(t)
            db.session.commit()
            log_action("Add Teacher", name)
            flash("Teacher added.")
        return redirect(url_for("manage_teachers"))
    teachers = Teacher.query.all()
    rows = "".join(f"<li>{t.name} ({t.nickname or ''})</li>" for t in teachers)
    form = """
    <form method="post" class="mb-3">
      <input name="name" class="form-control mb-2" placeholder="Teacher name">
      <input name="nickname" class="form-control mb-2" placeholder="Nickname">
      <button class="btn btn-primary">Add Teacher</button>
    </form>
    """
    return render("<h5>Teachers</h5>" + form + "<ul>" + rows + "</ul>")

@app.route("/students", methods=["GET", "POST"])
def manage_students():
    if request.method == "POST":
        name = request.form.get("name")
        rate = float(request.form.get("rate") or 0)
        if name:
            s = Student(name=name, rate_per_class=rate)
            db.session.add(s)
            db.session.commit()
            log_action("Add Student", name)
            flash("Student added.")
        return redirect(url_for("manage_students"))
    students = Student.query.all()
    rows = "".join(f"<li>{s.name} (Rate: {s.rate_per_class})</li>" for s in students)
    form = """
    <form method="post" class="mb-3">
      <input name="name" class="form-control mb-2" placeholder="Student name">
      <input name="rate" class="form-control mb-2" placeholder="Rate per class">
      <button class="btn btn-primary">Add Student</button>
    </form>
    """
    return render("<h5>Students</h5>" + form + "<ul>" + rows + "</ul>")

@app.route("/subjects", methods=["GET", "POST"])
def manage_subjects():
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            sub = Subject(name=name)
            db.session.add(sub)
            db.session.commit()
            log_action("Add Subject", name)
            flash("Subject added.")
        return redirect(url_for("manage_subjects"))
    subjects = Subject.query.all()
    rows = "".join(f"<li>{sub.name}</li>" for sub in subjects)
    form = """
    <form method="post" class="mb-3">
      <input name="name" class="form-control mb-2" placeholder="Subject name">
      <button class="btn btn-primary">Add Subject</button>
    </form>
    """
    return render("<h5>Subjects</h5>" + form + "<ul>" + rows + "</ul>")

@app.route("/sessions/add", methods=["GET", "POST"])
def add_session():
    teachers = Teacher.query.all()
    students = Student.query.all()
    subjects = Subject.query.all()
    if request.method == "POST":
        teacher_id = int(request.form.get("teacher_id"))
        student_id = int(request.form
