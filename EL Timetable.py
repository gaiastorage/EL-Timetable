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
# Home / Timetable (daily grouped by teacher)
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
    page = """
    <h5>Timetable</h5>
    <form method="get" class="mb-3">
      <div class="row g-2">
        <div class="col-md-6">
          <select class="form-select" name="teacher_id">
            <option value="">-- choose teacher --</option>
            {% for t in teachers %}
              <option value="{{ t.id }}" {% if selected_teacher and selected_teacher.id == t.id %}selected{% endif %}>{{ t.name }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="col-md-2">
          <button class="btn btn-primary w-100">View</button>
        </div>
      </div>
    </form>
    {% if selected_teacher %}
      <h6>Timetable for {{ selected_teacher.name }} ({{ (date.today()).strftime('%B %Y') }})</h6>
      {% if grouped %}
        {% for day, items in grouped.items() %}
          <h6 class="mt-3">{{ day }}</h6>
          <table class="table table-sm table-bordered">
            <thead>
              <tr>
                <th class="timecell sticky-th">Start</th>
                <th class="timecell sticky-th">End</th>
                <th class="sticky-th">Student</th>
                <th class="sticky-th">Subject</th>
                <th class="sticky-th">Notes</th>
                <th class="sticky-th" style="width:140px">Actions</th>
              </tr>
            </thead>
            <tbody>
              {% for s in items %}
                <tr>
                  <td class="timecell">{{ s.start_time.strftime("%H:%M") }}</td>
                  <td class="timecell">{{ s.end_time.strftime("%H:%M") }}</td>
                  <td>{{ s.student.name }}</td>
                  <td>{{ s.subject.name }}</td>
                  <td>{{ s.notes or "" }}</td>
                  <td>
                    <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('edit_session', session_id=s.id) }}">Edit</a>
                    <a class="btn btn-sm btn-outline-danger" href="{{ url_for('delete_session', session_id=s.id) }}" onclick="return confirm('Delete this session?')">Delete</a>
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        {% endfor %}
      {% else %}
        <div class="alert alert-secondary">No sessions for this month. Use "Add Session" to create one.</div>
      {% endif %}
    {% endif %}
    """
    return render(page, teachers=teachers, selected_teacher=selected_teacher, grouped=grouped, date=date)

# -------------------------
# Weekly grid timetable (grouped by teacher)
# -------------------------
@app.route("/weekly_timetable")
def weekly_timetable():
    hours = [f"{h:02d}:00" for h in range(8, 21)]  # 08:00 to 20:00
    days = list(calendar.day_name)  # Monday ... Sunday
    today = date.today()
    start_week = today - timedelta(days=today.weekday())  # Monday
    end_week = start_week + timedelta(days=7)

    sessions = ClassSession.query.filter(
        ClassSession.session_date >= start_week,
        ClassSession.session_date < end_week
    ).order_by(ClassSession.session_date.asc(), ClassSession.start_time.asc()).all()

    # Build teacher -> student -> slots mapping
    teacher_groups = {}
    for s in sessions:
        t = s.teacher
        nick = t.nickname or t.name
        tg = teacher_groups.setdefault(t.id, {"teacher": t, "students": {}})
        st_map = tg["students"].setdefault(s.student_id, {"student": s.student, "slots": {}})
        day_name = calendar.day_name[s.session_date.weekday()]
        hour_str = s.start_time.strftime("%H:00")
        st_map["slots"][(day_name, hour_str)] = f"{s.student.name} - {s.subject.name} ({nick})"

    page = """
    <div class="d-flex gap-2 mb-2">
      <a class="btn btn-sm btn-outline-dark" href="{{ url_for('download_weekly', format='csv') }}">Download Weekly CSV</a>
      <a class="btn btn-sm btn-outline-dark" href="{{ url_for('download_weekly', format='excel') }}">Download Weekly Excel</a>
    </div>
    <h5>Weekly Timetable ({{ start_week.strftime('%d %b') }} - {{ (end_week - timedelta(days=1)).strftime('%d %b %Y') }})</h5>
    {% if not teacher_groups %}
      <div class="alert alert-secondary">No sessions scheduled this week.</div>
    {% endif %}
    {% for tg in teacher_groups.values() %}
      <h6 class="mt-4">Teacher: {{ tg.teacher.name }}{% if tg.teacher.nickname %} ({{ tg.teacher.nickname }}){% endif %}</h6>
      <table class="table table-sm table-bordered">
        <thead>
          <tr>
            <th class="sticky-th" style="width:90px">Hour</th>
            {% for d in days %}
              <th class="sticky-th">{{ d }}</th>
            {% endfor %}
          </tr>
        </thead>
        <tbody>
          {% for hour in hours %}
            <tr>
              <td class="timecell">{{ hour }}</td>
              {% for d in days %}
                <td style="min-width:200px">
                  {% set printed = False %}
                  {% for st in tg.students.values() %}
                    {% if (d, hour) in st.slots %}
                      {{ st.slots[(d, hour)] }}<br>
                      {% set printed = True %}
                    {% endif %}
                  {% endfor %}
                  {% if not printed %}-{% endif %}
                </td>
              {% endfor %}
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endfor %}
    """
    return render(page, teacher_groups=teacher_groups, days=days, hours=hours,
                  start_week=start_week, end_week=end_week, timedelta=timedelta)

# -------------------------
# Teachers management (with nickname)
# -------------------------
@app.route("/teachers", methods=["GET", "POST"])
def manage_teachers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        nickname = request.form.get("nickname", "").strip()
        if not name:
            flash("Teacher name cannot be empty.")
        elif Teacher.query.filter_by(name=name).first():
            flash("Teacher already exists.")
        else:
            db.session.add(Teacher(name=name, nickname=nickname or None))
            db.session.commit()
            log_action("add_teacher", f"Added teacher {name} (nickname={nickname})")
            flash("Teacher added.")
        return redirect(url_for("manage_teachers"))

    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    page = """
    <h5>Teachers</h5>
    <form method="post" class="row g-2 mb-3">
      <div class="col-md-4"><input class="form-control" name="name" placeholder="Full name"></div>
      <div class="col-md-4"><input class="form-control" name="nickname" placeholder="Nickname (optional)"></div>
      <div class="col-md-2"><button class="btn btn-primary w-100">Add</button></div>
    </form>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Name</th><th>Nickname</th><th style="width:120px">Actions</th></tr></thead>
      <tbody>
        {% for t in teachers %}
          <tr>
            <td>{{ t.name }}</td>
            <td>{{ t.nickname or "" }}</td>
            <td>
              <a class="btn btn-sm btn-outline-danger" href="{{ url_for('delete_teacher', teacher_id=t.id) }}" onclick="return confirm('Delete teacher and their sessions?')">Delete</a>
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, teachers=teachers)

@app.route("/teachers/<int:teacher_id>/delete")
def delete_teacher(teacher_id):
    t = Teacher.query.get_or_404(teacher_id)
    ClassSession.query.filter_by(teacher_id=teacher_id).delete()
    db.session.delete(t)
    db.session.commit()
    log_action("delete_teacher", f"Deleted teacher id={teacher_id}")
    flash("Teacher deleted.")
    return redirect(url_for("manage_teachers"))

# -------------------------
# Students management
# -------------------------
@app.route("/students", methods=["GET","POST"])
def manage_students():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        rate = request.form.get("rate", type=float)
        if not name:
            flash("Student name cannot be empty.")
        elif Student.query.filter_by(name=name).first():
            flash("Student already exists.")
        else:
            db.session.add(Student(name=name, rate_per_class=rate or 0))
            db.session.commit()
            log_action("add_student", f"Added student {name} with rate {rate or 0}")
            flash("Student added.")
        return redirect(url_for("manage_students"))

    students = Student.query.order_by(Student.name.asc()).all()
    page = """
    <h5>Students</h5>
    <form method="post" class="row g-2 mb-3">
      <div class="col-md-4"><input class="form-control" name="name" placeholder="Name"></div>
      <div class="col-md-3"><input class="form-control" name="rate" type="number" step="0.01" placeholder="Rate per class"></div>
      <div class="col-md-2"><button class="btn btn-primary w-100">Add</button></div>
    </form>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Name</th><th>Rate/Class</th><th style="width:120px">Actions</th></tr></thead>
      <tbody>
        {% for s in students %}
          <tr>
            <td>{{ s.name }}</td>
            <td>${{ "%.2f"|format(s.rate_per_class) }}</td>
            <td>
              <a class="btn btn-sm btn-outline-danger" href="{{ url_for('delete_student', student_id=s.id) }}" onclick="return confirm('Delete student and their sessions?')">Delete</a>
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, students=students)

@app.route("/students/<int:student_id>/delete")
def delete_student(student_id):
    s = Student.query.get_or_404(student_id)
    ClassSession.query.filter_by(student_id=student_id).delete()
    db.session.delete(s)
    db.session.commit()
    log_action("delete_student", f"Deleted student id={student_id}")
    flash("Student deleted.")
    return redirect(url_for("manage_students"))

# -------------------------
# Subjects management
# -------------------------
@app.route("/subjects", methods=["GET","POST"])
def manage_subjects():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name:
            flash("Subject name cannot be empty.")
        elif Subject.query.filter_by(name=name).first():
            flash("Subject already exists.")
        else:
            db.session.add(Subject(name=name))
            db.session.commit()
            log_action("add_subject", f"Added subject {name}")
            flash("Subject added.")
        return redirect(url_for("manage_subjects"))

    subjects = Subject.query.order_by(Subject.name.asc()).all()
    page = """
    <h5>Subjects</h5>
    <form method="post" class="row g-2 mb-3">
      <div class="col-md-6"><input class="form-control" name="name" placeholder="New subject name"></div>
      <div class="col-md-2"><button class="btn btn-primary w-100">Add</button></div>
    </form>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Name</th><th style="width:120px">Actions</th></tr></thead>
      <tbody>
        {% for subj in subjects %}
          <tr>
            <td>{{ subj.name }}</td>
            <td>
              <a class="btn btn-sm btn-outline-danger" href="{{ url_for('delete_subject', subject_id=subj.id) }}" onclick="return confirm('Delete subject and their sessions?')">Delete</a>
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, subjects=subjects)

@app.route("/subjects/<int:subject_id>/delete")
def delete_subject(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    ClassSession.query.filter_by(subject_id=subject_id).delete()
    db.session.delete(subj)
    db.session.commit()
    log_action("delete_subject", f"Deleted subject id={subject_id}")
    flash("Subject deleted.")
    return redirect(url_for("manage_subjects"))

# -------------------------
# Sessions (add/edit/delete)
# -------------------------
@app.route("/sessions/add", methods=["GET","POST"])
def add_session():
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    students = Student.query.order_by(Student.name.asc()).all()
    subjects = Subject.query.order_by(Subject.name.asc()).all()

    if request.method == "POST":
        teacher_id = request.form.get("teacher_id", type=int)
        student_id = request.form.get("student_id", type=int)
        subject_id = request.form.get("subject_id", type=int)
        session_date = parse_date(request.form.get("session_date",""))
        start_time = parse_time(request.form.get("start_time",""))
        end_time = parse_time(request.form.get("end_time",""))
        notes = request.form.get("notes","").strip()

        if not all([teacher_id, student_id, subject_id, session_date, start_time, end_time]):
            flash("All fields are required and must be valid.")
            return redirect(url_for("add_session"))
        if end_time <= start_time:
            flash("End time must be after start time.")
            return redirect(url_for("add_session"))

        new_s = ClassSession(
            teacher_id=teacher_id,
            student_id=student_id,
            subject_id=subject_id,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            notes=notes or None
        )
        db.session.add(new_s)
        db.session.commit()
        log_action("add_session", f"Teacher={teacher_id}, Student={student_id}, Subject={subject_id}, Date={session_date}, {start_time}-{end_time}")
        flash("Session added.")
        return redirect(url_for("home", teacher_id=teacher_id))

    page = """
    <h5>Add session</h5>
    <form method="post" class="row g-3">
      <div class="col-md-4">
        <label class="form-label">Teacher</label>
        <select class="form-select" name="teacher_id" required>
          <option value="">-- choose --</option>
          {% for t in teachers %}<option value="{{ t.id }}">{{ t.name }}</option>{% endfor %}
        </select>
      </div>
      <div class="col-md-4">
        <label class="form-label">Student</label>
        <select class="form-select" name="student_id" required>
          <option value="">-- choose --</option>
          {% for s in students %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}
        </select>
      </div>
      <div class="col-md-4">
        <label class="form-label">Subject</label>
        <select class="form-select" name="subject_id" required>
          <option value="">-- choose --</option>
          {% for subj in subjects %}<option value="{{ subj.id }}">{{ subj.name }}</option>{% endfor %}
        </select>
      </div>
      <div class="col-md-4">
        <label class="form-label">Date</label>
        <input class="form-control" type="date" name="session_date" required>
      </div>
      <div class="col-md-4">
        <label class="form-label">Start time</label>
        <input class="form-control" type="time" name="start_time" required>
      </div>
      <div class="col-md-4">
        <label class="form-label">End time</label>
        <input class="form-control" type="time" name="end_time" required>
      </div>
      <div class="col-12">
        <label class="form-label">Notes (optional)</label>
        <input class="form-control" name="notes" placeholder="Room, materials, etc.">
      </div>
      <div class="col-12">
        <button class="btn btn-success">Save</button>
        <a class="btn btn-outline-secondary" href="{{ url_for('home') }}">Cancel</a>
      </div>
    </form>
    """
    return render(page, teachers=teachers, students=students, subjects=subjects)

@app.route("/sessions/<int:session_id>/edit", methods=["GET","POST"])
def edit_session(session_id):
    s = ClassSession.query.get_or_404(session_id)
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    students = Student.query.order_by(Student.name.asc()).all()
    subjects = Subject.query.order_by(Subject.name.asc()).all()

    if request.method == "POST":
        teacher_id = request.form.get("teacher_id", type=int)
        student_id = request.form.get("student_id", type=int)
        subject_id = request.form.get("subject_id", type=int)
        session_date = parse_date(request.form.get("session_date",""))
        start_time = parse_time(request.form.get("start_time",""))
        end_time = parse_time(request.form.get("end_time",""))
        notes = request.form.get("notes","").strip()

        if not all([teacher_id, student_id, subject_id, session_date, start_time, end_time]):
            flash("All fields are required and must be valid.")
            return redirect(url_for("edit_session", session_id=session_id))
        if end_time <= start_time:
            flash("End time must be after start time.")
            return redirect(url_for("edit_session", session_id=session_id))

        s.teacher_id = teacher_id
        s.student_id = student_id
        s.subject_id = subject_id
        s.session_date = session_date
        s.start_time = start_time
        s.end_time = end_time
        s.notes = notes or None
        db.session.commit()
        log_action("edit_session", f"Session id={session_id} updated by teacher={teacher_id}, student={student_id}, subject={subject_id}")
        flash("Session updated.")
        return redirect(url_for("home", teacher_id=teacher_id))

    page = """
    <h5>Edit session</h5>
    <form method="post" class="row g-3">
      <div class="col-md-4">
        <label class="form-label">Teacher</label>
        <select class="form-select" name="teacher_id" required>
          {% for t in teachers %}<option value="{{ t.id }}" {% if t.id == s.teacher_id %}selected{% endif %}>{{ t.name }}</option>{% endfor %}
        </select>
      </div>
      <div class="col-md-4">
        <label class="form-label">Student</label>
        <select class="form-select" name="student_id" required>
          {% for st in students %}<option value="{{ st.id }}" {% if st.id == s.student_id %}selected{% endif %}>{{ st.name }}</option>{% endfor %}
        </select>
      </div>
      <div class="col-md-4">
        <label class="form-label">Subject</label>
        <select class="form-select" name="subject_id" required>
          {% for subj in subjects %}<option value="{{ subj.id }}" {% if subj.id == s.subject_id %}selected{% endif %}>{{ subj.name }}</option>{% endfor %}
        </select>
      </div>
      <div class="col-md-4">
        <label class="form-label">Date</label>
        <input class="form-control" type="date" name="session_date" value="{{ s.session_date.isoformat() }}" required>
      </div>
      <div class="col-md-4">
        <label class="form-label">Start time</label>
        <input class="form-control" type="time" name="start_time" value="{{ s.start_time.strftime('%H:%M') }}" required>
      </div>
      <div class="col-md-4">
        <label class="form-label">End time</label>
        <input class="form-control" type="time" name="end_time" value="{{ s.end_time.strftime('%H:%M') }}" required>
      </div>
      <div class="col-12">
        <label class="form-label">Notes (optional)</label>
        <input class="form-control" name="notes" value="{{ s.notes or '' }}">
      </div>
      <div class="col-12">
        <button class="btn btn-success">Update</button>
        <a class="btn btn-outline-secondary" href="{{ url_for('home', teacher_id=s.teacher_id) }}">Cancel</a>
      </div>
    </form>
    """
    return render(page, s=s, teachers=teachers, students=students, subjects=subjects)

@app.route("/sessions/<int:session_id>/delete")
def delete_session(session_id):
    s = ClassSession.query.get_or_404(session_id)
    teacher_id = s.teacher_id
    db.session.delete(s)
    db.session.commit()
    log_action("delete_session", f"Deleted session id={session_id}")
    flash("Session deleted.")
    return redirect(url_for("home", teacher_id=teacher_id))

# -------------------------
# Payments (current month)
# -------------------------
@app.route("/payments")
def payments():
    today = date.today()
    students = Student.query.order_by(Student.name.asc()).all()
    payments_data = []
    for st in students:
        sessions_count = current_month_sessions().filter_by(student_id=st.id).count()
        total_payment = sessions_count * (st.rate_per_class or 0)
        payments_data.append({"student": st, "sessions": sessions_count, "total": total_payment})

    page = """
    <div class="d-flex gap-2 mb-2">
      <a class="btn btn-sm btn-outline-dark" href="{{ url_for('download_payments', format='csv') }}">Download CSV</a>
      <a class="btn btn-sm btn-outline-dark" href="{{ url_for('download_payments', format='excel') }}">Download Excel</a>
    </div>
    <h5>Student Payments ({{ today.strftime('%B %Y') }})</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Student</th><th>Rate/Class</th><th>Classes</th><th>Total Payment</th></tr></thead>
      <tbody>
        {% for p in payments_data %}
          <tr>
            <td>{{ p.student.name }}</td>
            <td>${{ "%.2f"|format(p.student.rate_per_class) }}</td>
            <td>{{ p.sessions }}</td>
            <td>${{ "%.2f"|format(p.total) }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, payments_data=payments_data, today=today)

# -------------------------
# Teacher totals (current month)
# -------------------------
@app.route("/teacher_totals")
def teacher_totals():
    today = date.today()
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    totals_data = []
    for t in teachers:
        sessions = current_month_sessions().filter_by(teacher_id=t.id).all()
        student_counts_by_subject = {}
        for s in sessions:
            subj = s.subject.name
            student_counts_by_subject.setdefault(subj, set()).add(s.student_id)
        student_counts_by_subject = {k: len(v) for k, v in student_counts_by_subject.items()}
        totals_data.append({
            "teacher": t,
            "total_sessions": len(sessions),
            "student_counts_by_subject": student_counts_by_subject
        })

    page = """
    <div class="d-flex gap-2 mb-2">
      <a class="btn btn-sm btn-outline-dark" href="{{ url_for('download_totals', format='csv') }}">Download CSV</a>
      <a class="btn btn-sm btn-outline-dark" href="{{ url_for('download_totals', format='excel') }}">Download Excel</a>
    </div>
    <h5>Teacher totals ({{ today.strftime('%B %Y') }})</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Teacher</th><th>Total sessions</th><th>Students per subject</th></tr></thead>
      <tbody>
        {% for row in totals_data %}
          <tr>
            <td>{{ row.teacher.name }}{% if row.teacher.nickname %} ({{ row.teacher.nickname }}){% endif %}</td>
            <td>{{ row.total_sessions }}</td>
            <td>
              {% for subj, scnt in row.student_counts_by_subject.items() %}
                {{ subj }}: {{ scnt }}<br>
              {% endfor %}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, totals_data=totals_data, today=today)

# -------------------------
# Download routes
# -------------------------
@app.route("/download_weekly/<format>")
def download_weekly(format):
    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=7)
    sessions = ClassSession.query.filter(
        ClassSession.session_date >= start_week,
        ClassSession.session_date < end_week
    ).order_by(ClassSession.session_date.asc(), ClassSession.start_time.asc()).all()

    data = []
    for s in sessions:
        data.append({
            "Date": s.session_date.isoformat(),
            "Day": calendar.day_name[s.session_date.weekday()],
            "Start": s.start_time.strftime("%H:%M"),
            "End": s.end_time.strftime("%H:%M"),
            "Teacher": s.teacher.name,
            "Nickname": s.teacher.nickname or "",
            "Student": s.student.name,
            "Subject": s.subject.name,
            "Notes": s.notes or ""
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    if format == "csv":
        df.to_csv(output, index=False)
        mimetype = "text/csv"
        fname = f"weekly_{start_week.strftime('%Y_%m_%d')}.csv"
    elif format == "excel":
        df.to_excel(output, index=False, engine="openpyxl")
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        fname = f"weekly_{start_week.strftime('%Y_%m_%d')}.xlsx"
    else:
        flash("Invalid format requested.")
        return redirect(url_for("weekly_timetable"))
    output.seek(0)
    return send_file(output, mimetype=mimetype, download_name=fname, as_attachment=True)

@app.route("/download_payments/<format>")
def download_payments(format):
    today = date.today()
    students = Student.query.order_by(Student.name.asc()).all()
    data = []
    for st in students:
        sessions_count = current_month_sessions().filter_by(student_id=st.id).count()
        total_payment = sessions_count * (st.rate_per_class or 0)
        data.append({
            "Student": st.name,
            "Rate per Class": st.rate_per_class,
            "Classes": sessions_count,
            "Total Payment": total_payment
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    if format == "csv":
        df.to_csv(output, index=False)
        mimetype = "text/csv"
        fname = f"payments_{today.strftime('%Y_%m')}.csv"
    elif format == "excel":
        df.to_excel(output, index=False, engine="openpyxl")
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        fname = f"payments_{today.strftime('%Y_%m')}.xlsx"
    else:
        flash("Invalid format requested.")
        return redirect(url_for("payments"))
    output.seek(0)
    return send_file(output, mimetype=mimetype, download_name=fname, as_attachment=True)

@app.route("/download_totals/<format>")
def download_totals(format):
    today = date.today()
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    data = []
    for t in teachers:
        sessions = current_month_sessions().filter_by(teacher_id=t.id).all()
        student_counts_by_subject = {}
        for s in sessions:
            subj = s.subject.name
            student_counts_by_subject.setdefault(subj, set()).add(s.student_id)
        student_counts_by_subject = {k: len(v) for k, v in student_counts_by_subject.items()}
        data.append({
            "Teacher": t.name,
            "Nickname": t.nickname or "",
            "Total Sessions": len(sessions),
            "Students per Subject": "; ".join([f"{subj}: {cnt}" for subj, cnt in student_counts_by_subject.items()])
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    if format == "csv":
        df.to_csv(output, index=False)
        mimetype = "text/csv"
        fname = f"totals_{today.strftime('%Y_%m')}.csv"
    elif format == "excel":
        df.to_excel(output, index=False, engine="openpyxl")
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        fname = f"totals_{today.strftime('%Y_%m')}.xlsx"
    else:
        flash("Invalid format requested.")
        return redirect(url_for("teacher_totals"))
    output.seek(0)
    return send_file(output, mimetype=mimetype, download_name=fname, as_attachment=True)

# -------------------------
# Logs
# -------------------------
@app.route("/logs")
def logs():
    entries = LogEntry.query.order_by(LogEntry.timestamp.desc()).limit(200).all()
    page = """
    <h5>Logs (latest 200)</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Time (UTC)</th><th>Action</th><th>Details</th></tr></thead>
      <tbody>
        {% for e in entries %}
          <tr>
            <td>{{ e.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</td>
            <td>{{ e.action }}</td>
            <td>{{ e.details or '' }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, entries=entries)

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
    app.run(debug=True)