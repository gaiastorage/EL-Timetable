import os
import io
import calendar
import pandas as pd
from datetime import datetime, date, timedelta
from flask import Flask, request, redirect, url_for, render_template_string, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract, func

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


# Many-to-many link table between students and subjects
student_subjects = db.Table("student_subjects",
    db.Column("student_id", db.Integer, db.ForeignKey("student.id")),
    db.Column("subject_id", db.Integer, db.ForeignKey("subject.id"))
)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=True)   # internal ID
    name = db.Column(db.String(120), unique=True, nullable=False)
    id_number = db.Column(db.String(50), nullable=True)
    telephone = db.Column(db.String(50), nullable=True)
    mobile = db.Column(db.String(50), nullable=True)
    contact1_name = db.Column(db.String(120), nullable=True)
    contact1_phone = db.Column(db.String(50), nullable=True)
    contact2_name = db.Column(db.String(120), nullable=True)
    contact2_phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(255), nullable=True)

    # Subjects enrolled
    subjects = db.relationship("Subject", secondary=student_subjects, backref="students")




class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    number_of_classes = db.Column(db.Integer, nullable=False)
    discount = db.Column(db.Float, default=0.0)  # percentage discount

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

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today)
    method = db.Column(db.String(50), nullable=True)  # cash, card, transfer

    student = db.relationship("Student", backref=db.backref("payments", lazy=True))
    subject = db.relationship("Subject", backref=db.backref("payments", lazy=True))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("class_session.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # Arrived, Late, Absent, Vacation
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("ClassSession", backref=db.backref("attendance", lazy=True))
    student = db.relationship("Student", backref=db.backref("attendance", lazy=True))

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

# -------------------------
# Helpers
# -------------------------
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
# Search routes (autocomplete)
# -------------------------
@app.route("/search_students")
def search_students():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        matches = Student.query.filter(func.lower(Student.name).like(f"%{q.lower()}%")).order_by(Student.name.asc()).all()
        results = [{"id": s.id, "name": s.name} for s in matches]
    return {"results": results}

@app.route("/search_teachers")
def search_teachers():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        matches = Teacher.query.filter(func.lower(Teacher.name).like(f"%{q.lower()}%")).order_by(Teacher.name.asc()).all()
        results = [{"id": t.id, "name": t.name} for t in matches]
    return {"results": results}

@app.route("/search_subjects")
def search_subjects():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        matches = Subject.query.filter(func.lower(Subject.name).like(f"%{q.lower()}%")).order_by(Subject.name.asc()).all()
        results = [{"id": subj.id, "name": subj.name} for subj in matches]
    return {"results": results}


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
      <h6>Timetable for {{ selected_teacher.name }}{% if selected_teacher.nickname %} ({{ selected_teacher.nickname }}){% endif %} ({{ (date.today()).strftime('%B %Y') }})</h6>
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
# Teacher management
# -------------------------
@app.route("/teachers", methods=["GET","POST"])
def manage_teachers():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        nickname = request.form.get("nickname","").strip()
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
              <a class="btn btn-sm btn-outline-danger"
                 href="{{ url_for('delete_teacher', teacher_id=t.id) }}"
                 onclick="return confirm('Delete teacher and their sessions?')">Delete</a>
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
# Teacher totals
# -------------------------
@app.route("/teacher_totals")
def teacher_totals():
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    totals = []
    for t in teachers:
        totals.append({
            "name": t.name,
            "nickname": t.nickname or "",
            "sessions": len(t.sessions)
        })
    page = """
    <h5>Teacher Totals</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Name</th><th>Nickname</th><th>Sessions</th></tr></thead>
      <tbody>
        {% for row in totals %}
          <tr>
            <td>{{ row.name }}</td>
            <td>{{ row.nickname }}</td>
            <td>{{ row.sessions }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, totals=totals)

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

    # Build combined slots for all teachers
    combined_slots = {}
    for s in sessions:
        day_name = calendar.day_name[s.session_date.weekday()]
        hour_str = s.start_time.strftime("%H:00")
        nick = s.teacher.nickname or s.teacher.name
        entry = f"{s.student.name} - {s.subject.name} ({nick})"
        combined_slots.setdefault((day_name, hour_str), []).append(entry)

    # Sort entries by teacher nickname
    for key in combined_slots:
        combined_slots[key].sort(key=lambda e: e.split("(")[-1].strip(")"))

    page = """
    <h5>Weekly Timetable ({{ start_week.strftime('%d %b') }} - {{ (end_week - timedelta(days=1)).strftime('%d %b %Y') }})</h5>

    <!-- Combined table -->
    <h6 class="mt-3">All Teachers Combined</h6>
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
                {% set entries = combined_slots.get((d, hour), []) %}
                {% if entries %}
                  {% for e in entries %}
                    {{ e }}<br>
                  {% endfor %}
                {% else %}
                  -
                {% endif %}
              </td>
            {% endfor %}
          </tr>
        {% endfor %}
      </tbody>
    </table>

    {% if not teacher_groups %}
      <div class="alert alert-secondary">No sessions scheduled this week.</div>
    {% endif %}

    <!-- Individual teacher tables -->
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
    return render(page,
                  teacher_groups=teacher_groups,
                  days=days,
                  hours=hours,
                  start_week=start_week,
                  end_week=end_week,
                  timedelta=timedelta,
                  combined_slots=combined_slots)

# -------------------------
# Logs page
# -------------------------
@app.route("/logs")
def logs():
    entries = LogEntry.query.order_by(LogEntry.timestamp.desc()).all()
    page = """
    <h5>System Logs</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Time</th><th>Action</th><th>Details</th></tr></thead>
      <tbody>
        {% for e in entries %}
          <tr>
            <td>{{ e.timestamp.strftime("%Y-%m-%d %H:%M") }}</td>
            <td>{{ e.action }}</td>
            <td>{{ e.details or "" }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    {% if not entries %}
      <div class="alert alert-secondary">No log entries yet.</div>
    {% endif %}
    """
    return render(page, entries=entries)

# -------------------------
# Student management (profile + subjects)
# -------------------------
@app.route("/students/<int:student_id>/edit", methods=["GET","POST"])
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    subjects = Subject.query.order_by(Subject.name.asc()).all()

    if request.method == "POST":
        student.name = request.form.get("name","").strip()
        student.student_id = request.form.get("student_id","").strip() or None
        student.id_number = request.form.get("id_number","").strip() or None
        student.telephone = request.form.get("telephone","").strip() or None
        student.mobile = request.form.get("mobile","").strip() or None
        student.contact1_name = request.form.get("contact1_name","").strip() or None
        student.contact1_phone = request.form.get("contact1_phone","").strip() or None
        student.contact2_name = request.form.get("contact2_name","").strip() or None
        student.contact2_phone = request.form.get("contact2_phone","").strip() or None
        student.address = request.form.get("address","").strip() or None

        # reset subjects
        student.subjects = []
        for sid in request.form.getlist("subjects"):
            subj = Subject.query.get(int(sid))
            if subj:
                student.subjects.append(subj)

        db.session.commit()
        flash("Student updated.")
        return redirect(url_for("manage_students"))

    page = """
    <h5>Edit Student</h5>
    <form method="post" class="row g-2 mb-3">
      <div class="col-md-4"><input class="form-control" name="name" value="{{ student.name }}"></div>
      <div class="col-md-3"><input class="form-control" name="student_id" value="{{ student.student_id or '' }}"></div>
      <div class="col-md-3"><input class="form-control" name="id_number" value="{{ student.id_number or '' }}"></div>
      <div class="col-md-3"><input class="form-control" name="telephone" value="{{ student.telephone or '' }}"></div>
      <div class="col-md-3"><input class="form-control" name="mobile" value="{{ student.mobile or '' }}"></div>
      <div class="col-md-3"><input class="form-control" name="contact1_name" value="{{ student.contact1_name or '' }}"></div>
      <div class="col-md-3"><input class="form-control" name="contact1_phone" value="{{ student.contact1_phone or '' }}"></div>
      <div class="col-md-3"><input class="form-control" name="contact2_name" value="{{ student.contact2_name or '' }}"></div>
      <div class="col-md-3"><input class="form-control" name="contact2_phone" value="{{ student.contact2_phone or '' }}"></div>
      <div class="col-md-6"><input class="form-control" name="address" value="{{ student.address or '' }}"></div>
      <div class="col-md-6">
        <label class="form-label">Subjects</label>
        <select class="form-select" name="subjects" multiple>
          {% for subj in subjects %}
            <option value="{{ subj.id }}" {% if subj in student.subjects %}selected{% endif %}>
              {{ subj.name }} ({{ "%.2f"|format(subj.price) }} / {{ subj.number_of_classes }} classes{% if subj.discount %}, {{ subj.discount }}% off{% endif %})
            </option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-2"><button class="btn btn-success w-100">Save</button></div>
      <div class="col-md-2"><a class="btn btn-outline-secondary w-100" href="{{ url_for('manage_students') }}">Cancel</a></div>
    </form>
    """
    return render(page, student=student, subjects=subjects)

@app.route("/students", methods=["GET","POST"])
def manage_students():
    subjects = Subject.query.order_by(Subject.name.asc()).all()

    if request.method == "POST":
        # ... your existing add student logic ...
        return redirect(url_for("manage_students"))

    # Build list of (student, subject) pairs
    students = Student.query.order_by(Student.name.asc()).all()

# Build list of (student, subject) pairs and subject counts
student_subject_rows = []
subject_counts = {}
for s in students:
    if s.subjects:
        for subj in s.subjects:
            student_subject_rows.append((s, subj))
            subject_counts[subj.name] = subject_counts.get(subj.name, 0) + 1
    else:
        student_subject_rows.append((s, None))

page = """
<h5>Total Student-Subject Enrollments: {{ student_subject_rows|length }}</h5>

<h6>Subject Breakdown</h6>
<ul>
  {% for subj, count in subject_counts.items() %}
    <li>{{ subj }}: {{ count }} students</li>
  {% endfor %}
</ul>

<form method="post" class="row g-2 mb-3">
  <div class="col-md-4"><label class="form-label">Name</label><input class="form-control" name="name" placeholder="Name"></div>
  <div class="col-md-3"><label class="form-label">Student ID</label><input class="form-control" name="student_id" placeholder="Student ID"></div>
  <div class="col-md-3"><label class="form-label">ID Number</label><input class="form-control" name="id_number" placeholder="ID Number"></div>
  <div class="col-md-3"><label class="form-label">Telephone</label><input class="form-control" name="telephone" placeholder="Telephone"></div>
  <div class="col-md-3"><label class="form-label">Mobile</label><input class="form-control" name="mobile" placeholder="Mobile"></div>
  <div class="col-md-3"><label class="form-label">Contact 1 Name</label><input class="form-control" name="contact1_name" placeholder="Contact 1 Name"></div>
  <div class="col-md-3"><label class="form-label">Contact 1 Phone</label><input class="form-control" name="contact1_phone" placeholder="Contact 1 Phone"></div>
  <div class="col-md-3"><label class="form-label">Contact 2 Name</label><input class="form-control" name="contact2_name" placeholder="Contact 2 Name"></div>
  <div class="col-md-3"><label class="form-label">Contact 2 Phone</label><input class="form-control" name="contact2_phone" placeholder="Contact 2 Phone"></div>
  <div class="col-md-6"><label class="form-label">Address</label><input class="form-control" name="address" placeholder="Address"></div>
  <div class="col-md-6">
    <label class="form-label">Subjects</label>
    <select class="form-select" name="subjects" multiple>
      {% for subj in subjects %}
        <option value="{{ subj.id }}">{{ subj.name }} ({{ "%.2f"|format(subj.price) }} / {{ subj.number_of_classes }} classes{% if subj.discount %}, {{ subj.discount }}% off{% endif %})</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-md-2"><button class="btn btn-primary w-100">Add</button></div>
</form>

<table class="table table-sm table-bordered">
  <thead>
    <tr>
      <th>Name</th>
      <th>Student ID</th>
      <th>ID Number</th>
      <th>Telephone</th>
      <th>Mobile</th>
      <th>Contact1</th>
      <th>Contact2</th>
      <th>Address</th>
      <th>Subject</th>
      <th style="width:160px">Actions</th>
    </tr>
  </thead>
  <tbody>
    {% for s, subj in student_subject_rows %}
      <tr>
        <td><a href="{{ url_for('edit_student', student_id=s.id) }}">{{ s.name }}</a></td>
        <td>{{ s.student_id or "" }}</td>
        <td>{{ s.id_number or "" }}</td>
        <td>{{ s.telephone or "" }}</td>
        <td>{{ s.mobile or "" }}</td>
        <td>{{ s.contact1_name or "" }} {{ s.contact1_phone or "" }}</td>
        <td>{{ s.contact2_name or "" }} {{ s.contact2_phone or "" }}</td>
        <td>{{ s.address or "" }}</td>
        <td>{{ subj.name if subj else "" }}</td>
        <td>
          <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('edit_student', student_id=s.id) }}">Edit</a>
          <a class="btn btn-sm btn-outline-danger"
             href="{{ url_for('delete_student', student_id=s.id) }}"
             onclick="return confirm('Delete student and their sessions?')">Delete</a>
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
    """
    return render(page,
              student_subject_rows=student_subject_rows,
              subject_counts=subject_counts,
              subjects=subjects)

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
# Subject management
# -------------------------
@app.route("/subjects", methods=["GET","POST"])
def manage_subjects():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        price = request.form.get("price", type=float)
        num_classes = request.form.get("number_of_classes", type=int)
        discount = request.form.get("discount", type=float)
        if not name or price is None or num_classes is None:
            flash("Subject name, price, and number of classes are required.")
        elif Subject.query.filter_by(name=name).first():
            flash("Subject already exists.")
        else:
            db.session.add(Subject(name=name, price=price, number_of_classes=num_classes, discount=discount or 0.0))
            db.session.commit()
            log_action("add_subject", f"Added subject {name} price={price}, classes={num_classes}, discount={discount or 0}")
            flash("Subject added.")
        return redirect(url_for("manage_subjects"))

    subjects = Subject.query.order_by(Subject.name.asc()).all()
    page = """
    <h5>Subjects</h5>
    <form method="post" class="row g-2 mb-3">
      <div class="col-md-3"><input class="form-control" name="name" placeholder="Subject name"></div>
      <div class="col-md-2"><input class="form-control" name="price" type="number" step="0.01" placeholder="Price"></div>
      <div class="col-md-2"><input class="form-control" name="number_of_classes" type="number" placeholder="Classes"></div>
      <div class="col-md-2"><input class="form-control" name="discount" type="number" step="0.01" placeholder="Discount %"></div>
      <div class="col-md-2"><button class="btn btn-primary w-100">Add</button></div>
    </form>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Name</th><th>Price</th><th>Classes</th><th>Discount</th><th style="width:120px">Actions</th></tr></thead>
      <tbody>
        {% for subj in subjects %}
          <tr>
            <td>{{ subj.name }}</td>
            <td>${{ "%.2f"|format(subj.price) }}</td>
            <td>{{ subj.number_of_classes }}</td>
            <td>{{ subj.discount }}%</td>
            <td>
              <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('edit_subject', subject_id=subj.id) }}">Edit</a>
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
# Edit subject
# -------------------------
@app.route("/subjects/<int:subject_id>/edit", methods=["GET","POST"])
def edit_subject(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    if request.method == "POST":
        name = request.form.get("name","").strip()
        price = request.form.get("price", type=float)
        num_classes = request.form.get("number_of_classes", type=int)
        discount = request.form.get("discount", type=float)

        if not name or price is None or num_classes is None:
            flash("Subject name, price, and number of classes are required.")
        else:
            subj.name = name
            subj.price = price
            subj.number_of_classes = num_classes
            subj.discount = discount or 0.0
            db.session.commit()
            log_action("edit_subject", f"Edited subject {name}")
            flash("Subject updated.")
            return redirect(url_for("manage_subjects"))

    page = """
    <h5>Edit Subject</h5>
    <form method="post" class="row g-2 mb-3">
      <div class="col-md-3"><input class="form-control" name="name" value="{{ subj.name }}"></div>
      <div class="col-md-2"><input class="form-control" name="price" type="number" step="0.01" value="{{ subj.price }}"></div>
      <div class="col-md-2"><input class="form-control" name="number_of_classes" type="number" value="{{ subj.number_of_classes }}"></div>
      <div class="col-md-2"><input class="form-control" name="discount" type="number" step="0.01" value="{{ subj.discount }}"></div>
      <div class="col-md-2"><button class="btn btn-success w-100">Save</button></div>
      <div class="col-md-2"><a class="btn btn-outline-secondary w-100" href="{{ url_for('manage_subjects') }}">Cancel</a></div>
    </form>
    """
    return render(page, subj=subj)

    page = """
    <h5>Edit Subject</h5>
    <form method="post" class="row g-2 mb-3">
      <div class="col-md-3"><input class="form-control" name="name" value="{{ subj.name }}"></div>
      <div class="col-md-2"><input class="form-control" name="price" type="number" step="0.01" value="{{ subj.price }}"></div>
      <div class="col-md-2"><input class="form-control" name="number_of_classes" type="number" value="{{ subj.number_of_classes }}"></div>
      <div class="col-md-2"><input class="form-control" name="discount" type="number" step="0.01" value="{{ subj.discount }}"></div>
      <div class="col-md-2"><button class="btn btn-success w-100">Save</button></div>
      <div class="col-md-2"><a class="btn btn-outline-secondary w-100" href="{{ url_for('manage_subjects') }}">Cancel</a></div>
    </form>
    """
    return render(page, subj=subj)# -------------------------
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
          {% for t in teachers %}
            <option value="{{ t.id }}">{{ t.name }}</option>
          {% endfor %}
        </select>
      </div>

      <div class="col-md-4">
        <label class="form-label">Student</label>
        <input class="form-control" id="studentSearch" name="student_name" placeholder="Type student name">
        <input type="hidden" id="studentId" name="student_id">
        <div id="studentSuggestions" class="list-group"></div>
      </div>

      <div class="col-md-4">
        <label class="form-label">Subject</label>
        <select class="form-select" name="subject_id" required>
          <option value="">-- choose --</option>
          {% for subj in subjects %}
            <option value="{{ subj.id }}">{{ subj.name }}</option>
          {% endfor %}
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

    <script>
      document.getElementById("studentSearch").addEventListener("input", async function() {
        const q = this.value;
        if (q.length > 0) {
          const res = await fetch(`/search_students?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          const suggestions = document.getElementById("studentSuggestions");
          suggestions.innerHTML = "";
          data.results.forEach(st => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "list-group-item list-group-item-action";
            item.textContent = st.name;
            item.onclick = () => {
              document.getElementById("studentSearch").value = st.name;
              document.getElementById("studentId").value = st.id;
              suggestions.innerHTML = "";
            };
            suggestions.appendChild(item);
          });
        } else {
          document.getElementById("studentSuggestions").innerHTML = "";
        }
      });
    </script>
    """
    return render(page, teachers=teachers, students=students, subjects=subjects)

@app.route("/sessions/<int:session_id>/edit", methods=["GET","POST"])
def edit_session(session_id):
    s = ClassSession.query.get_or_404(session_id)
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
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
        log_action("edit_session", f"Edited session id={session_id}")
        flash("Session updated.")
        return redirect(url_for("home", teacher_id=teacher_id))

    page = """
    <h5>Edit session</h5>
    <form method="post" class="row g-3">
      <div class="col-md-4">
        <label class="form-label">Teacher</label>
        <select class="form-select" name="teacher_id" required>
          {% for t in teachers %}
            <option value="{{ t.id }}" {% if t.id == s.teacher_id %}selected{% endif %}>{{ t.name }}</option>
          {% endfor %}
        </select>
      </div>

      <div class="col-md-4">
        <label class="form-label">Student</label>
        <input class="form-control" id="studentSearch" name="student_name" value="{{ s.student.name }}" placeholder="Type student name">
        <input type="hidden" id="studentId" name="student_id" value="{{ s.student_id }}">
        <div id="studentSuggestions" class="list-group"></div>
      </div>

      <div class="col-md-4">
        <label class="form-label">Subject</label>
        <select class="form-select" name="subject_id" required>
          {% for subj in subjects %}
            <option value="{{ subj.id }}" {% if subj.id == s.subject_id %}selected{% endif %}>{{ subj.name }}</option>
          {% endfor %}
        </select>
      </div>

      <div class="col-md-4">
        <label class="form-label">Date</label>
        <input class="form-control" type="date" name="session_date" value="{{ s.session_date }}" required>
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
        <input class="form-control" name="notes" value="{{ s.notes or '' }}" placeholder="Room, materials, etc.">
      </div>

      <div class="col-12">
        <button class="btn btn-success">Save</button>
                <a class="btn btn-outline-secondary" href="{{ url_for('home') }}">Cancel</a>
      </div>
    </form>

    <script>
      document.getElementById("studentSearch").addEventListener("input", async function() {
        const q = this.value;
        if (q.length > 0) {
          const res = await fetch(`/search_students?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          const suggestions = document.getElementById("studentSuggestions");
          suggestions.innerHTML = "";
          data.results.forEach(st => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "list-group-item list-group-item-action";
            item.textContent = st.name;
            item.onclick = () => {
              document.getElementById("studentSearch").value = st.name;
              document.getElementById("studentId").value = st.id;
              suggestions.innerHTML = "";
            };
            suggestions.appendChild(item);
          });
        } else {
          document.getElementById("studentSuggestions").innerHTML = "";
        }
      });
    </script>
    """
    return render(page, s=s, teachers=teachers, subjects=subjects)

@app.route("/sessions/<int:session_id>/delete")
def delete_session(session_id):
    s = ClassSession.query.get_or_404(session_id)
    db.session.delete(s)
    db.session.commit()
    log_action("delete_session", f"Deleted session id={session_id}")
    flash("Session deleted.")
    return redirect(url_for("home"))

# -------------------------
# Attendance tracking
# -------------------------
@app.route("/attendance/<int:session_id>/<int:student_id>/<status>")
def mark_attendance(session_id, student_id, status):
    s = ClassSession.query.get_or_404(session_id)
    st = Student.query.get_or_404(student_id)
    valid_status = ["Arrived", "Late", "Absent", "Vacation"]
    if status not in valid_status:
        flash("Invalid attendance status.")
        return redirect(url_for("home"))

    record = Attendance(session_id=session_id, student_id=student_id, status=status)
    db.session.add(record)
    db.session.commit()
    log_action("attendance", f"Marked {status} for student {st.name} in session {session_id}")
    flash(f"Attendance marked: {st.name} - {status}")
    return redirect(url_for("home", teacher_id=s.teacher_id))

@app.route("/attendance")
def attendance_overview():
    records = Attendance.query.order_by(Attendance.timestamp.desc()).all()
    page = """
    <h5>Attendance Records</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Timestamp</th><th>Student</th><th>Session</th><th>Status</th></tr></thead>
      <tbody>
        {% for r in records %}
          <tr>
            <td>{{ r.timestamp.strftime("%Y-%m-%d %H:%M") }}</td>
            <td>{{ r.student.name }}</td>
            <td>{{ r.session.session_date }} {{ r.session.start_time.strftime("%H:%M") }}</td>
            <td>{{ r.status }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, records=records)

# -------------------------
# Payments management
# -------------------------
@app.route("/payments", methods=["GET","POST"])
def payments():
    students = Student.query.order_by(Student.name.asc()).all()
    subjects = Subject.query.order_by(Subject.name.asc()).all()

    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        subject_id = request.form.get("subject_id", type=int)
        amount = request.form.get("amount", type=float)
        method = request.form.get("method","").strip()
        if not all([student_id, subject_id, amount]):
            flash("Student, subject, and amount are required.")
        else:
            payment = Payment(student_id=student_id, subject_id=subject_id, amount=amount, method=method or None)
            db.session.add(payment)
            db.session.commit()
            log_action("add_payment", f"Payment student={student_id}, subject={subject_id}, amount={amount}")
            flash("Payment recorded.")
        return redirect(url_for("payments"))

    # Build payment overview per student+subject
    overview = []
    for s in students:
        for subj in s.subjects:
            paid = sum(p.amount for p in s.payments if p.subject_id == subj.id)
            overview.append({
                "student": s.name,
                "subject": subj.name,
                "price": subj.price,
                "classes": subj.number_of_classes,
                "discount": subj.discount,
                "paid": paid,
                "outstanding": max(subj.price - paid, 0)
            })

    page = """
    <h5>Payments</h5>
    <form method="post" class="row g-2 mb-3">
      <div class="col-md-3">
        <select class="form-select" name="student_id" required>
          <option value="">-- student --</option>
          {% for s in students %}
            <option value="{{ s.id }}">{{ s.name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-3">
        <select class="form-select" name="subject_id" required>
          <option value="">-- subject --</option>
          {% for subj in subjects %}
            <option value="{{ subj.id }}">{{ subj.name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-2"><input class="form-control" name="amount" type="number" step="0.01" placeholder="Amount"></div>
      <div class="col-md-2"><input class="form-control" name="method" placeholder="Method (cash, card, etc.)"></div>
      <div class="col-md-2"><button class="btn btn-primary w-100">Add</button></div>
    </form>

    <table class="table table-sm table-bordered">
      <thead><tr><th>Student</th><th>Subject</th><th>Price</th><th>Classes</th><th>Discount</th><th>Paid</th><th>Outstanding</th></tr></thead>
      <tbody>
        {% for row in overview %}
          <tr>
            <td>{{ row.student }}</td>
            <td>{{ row.subject }}</td>
            <td>${{ "%.2f"|format(row.price) }}</td>
            <td>{{ row.classes }}</td>
            <td>{{ row.discount }}%</td>
            <td>${{ "%.2f"|format(row.paid) }}</td>
            <td>${{ "%.2f"|format(row.outstanding) }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, students=students, subjects=subjects, overview=overview)

# -------------------------
# Export routes
# -------------------------
@app.route("/export/students/<format>")
def export_students(format):
    students = Student.query.order_by(Student.name.asc()).all()
    data = []
    for s in students:
        data.append({
            "Name": s.name,
            "Student ID": s.student_id or "",
            "ID Number": s.id_number or "",
            "Telephone": s.telephone or "",
            "Mobile": s.mobile or "",
            "Contact1": s.contact1_name or "",
            "Contact1 Phone": s.contact1_phone or "",
            "Contact2": s.contact2_name or "",
            "Contact2 Phone": s.contact2_phone or "",
            "Address": s.address or "",
            "Subjects": ", ".join(subj.name for subj in s.subjects)
        })
    df = pd.DataFrame(data)
    if format == "csv":
        return send_file(io.BytesIO(df.to_csv(index=False).encode()), mimetype="text/csv",
                         download_name="students.csv", as_attachment=True)
    elif format == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         download_name="students.xlsx", as_attachment=True)

@app.route("/export/payments/<format>")
def export_payments(format):
    payments = Payment.query.order_by(Payment.date.desc()).all()
    data = []
    for p in payments:
        data.append({
            "Date": p.date.isoformat(),
            "Student": p.student.name,
            "Subject": p.subject.name,
            "Amount": p.amount,
            "Method": p.method or ""
        })
    df = pd.DataFrame(data)
    if format == "csv":
        return send_file(io.BytesIO(df.to_csv(index=False).encode()), mimetype="text/csv",
                         download_name="payments.csv", as_attachment=True)
    elif format == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         download_name="payments.xlsx", as_attachment=True)




@app.route("/export/attendance/<format>")
def export_attendance(format):
    records = Attendance.query.order_by(Attendance.timestamp.desc()).all()
    data = []
    for r in records:
        data.append({
            "Timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M"),
            "Student": r.student.name,
            "Session Date": r.session.session_date.isoformat(),
            "Start": r.session.start_time.strftime("%H:%M"),
            "Status": r.status
        })
    df = pd.DataFrame(data)
    if format == "csv":
        return send_file(io.BytesIO(df.to_csv(index=False).encode()), mimetype="text/csv",
                         download_name="attendance.csv", as_attachment=True)
    elif format == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         download_name="attendance.xlsx", as_attachment=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    with app.app_context():
        db.create_all()   # <-- creates tables if they don't exist
        print("Database tables created/verified.")
    app.run(host="0.0.0.0", port=port)
