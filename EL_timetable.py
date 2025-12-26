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
    try: return datetime.strptime(s, "%Y-%m-%d").date()
    except: return None

def parse_time(s):
    try: return datetime.strptime(s, "%H:%M").time()
    except: return None

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
                <th class="timecell">Start</th>
                <th class="timecell">End</th>
                <th>Student</th>
                <th>Subject</th>
                <th>Notes</th>
                <th style="width:140px">Actions</th>
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

@app.route("/teachers", methods=["GET","POST"])
def manage_teachers():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if name and not Teacher.query.filter_by(name=name).first():
            db.session.add(Teacher(name=name))
            db.session.commit()
            log_action("add_teacher", f"Added teacher {name}")
            flash("Teacher added.")
        else:
            flash("Invalid or duplicate teacher.")
        return redirect(url_for("manage_teachers"))
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    page = """
   <h5>Teachers</h5>
<form method="post" class="row g-2 mb-3">
  <div class="col-auto"><input class="form-control" name="name" placeholder="New teacher name"></div>
  <div class="col-auto"><button class="btn btn-primary">Add</button></div>
</form>
<table class="table table-sm table-bordered">
  <thead><tr><th>Name</th><th style="width:120px">Actions</th></tr></thead>
  <tbody>
    {% for t in teachers %}
      <tr>
        <td>{{ t.name }}</td>
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

@app.route("/students", methods=["GET","POST"])
def manage_students():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        rate = request.form.get("rate", type=float) or 0
        if name and not Student.query.filter_by(name=name).first():
            db.session.add(Student(name=name, rate_per_class=rate))
            db.session.commit()
            log_action("add_student", f"Added student {name} with rate {rate}")
            flash("Student added.")
        else:
            flash("Invalid or duplicate student.")
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
          <a class="btn btn-sm btn-outline-danger"
             href="{{ url_for('delete_student', student_id=s.id) }}"
             onclick="return confirm('Delete student and their sessions?')">Delete</a>
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
    """
    return render(page, students=students)

@app.route("/subjects", methods=["GET","POST"])
def manage_subjects():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if name and not Subject.query.filter_by(name=name).first():
            db.session.add(Subject(name=name))
            db.session.commit()
            log_action("add_subject", f"Added subject {name}")
            flash("Subject added.")
        else:
            flash("Invalid or duplicate subject.")
        return redirect(url_for("manage_subjects"))

    subjects = Subject.query.order_by(Subject.name.asc()).all()
    page = """
    <h5>Subjects</h5>
<form method="post" class="row g-2 mb-3">
  <div class="col-md-6"><input class="form-control" name="name" placeholder="Subject name"></div>
  <div class="col-md-2"><button class="btn btn-primary w-100">Add</button></div>
</form>
<table class="table table-sm table-bordered">
  <thead><tr><th>Name</th><th style="width:120px">Actions</th></tr></thead>
  <tbody>
    {% for sub in subjects %}
      <tr>
        <td>{{ sub.name }}</td>
        <td>
          <a class="btn btn-sm btn-outline-danger"
             href="{{ url_for('delete_subject', subject_id=sub.id) }}"
             onclick="return confirm('Delete subject and its sessions?')">Delete</a>
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
    """
    return render(page, subjects=subjects)

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
        log_action("add_session", f"Teacher={teacher_id}, Student={student_id}, Subject={subject_id}, Date={session_date}")
        flash("Session added.")
        return redirect(url_for("home", teacher_id=teacher_id))

    page = """
    <h5>Add Session</h5>
    <form method="post">
      <label>Teacher</label>
      <select class="form-select mb-2" name="teacher_id">
        {% for t in teachers %}<option value="{{t.id}}">{{t.name}}</option>{% endfor %}
      </select>
      <label>Student</label>
      <select class="form-select mb-2" name="student_id">
        {% for s in students %}<option value="{{s.id}}">{{s.name}}</option>{% endfor %}
      </select>
      <label>Subject</label>
      <select class="form-select mb-2" name="subject_id">
        {% for sub in subjects %}<option value="{{sub.id}}">{{sub.name}}</option>{% endfor %}
      </select>
      <input class="form-control mb-2" type="date" name="session_date">
      <input class="form-control mb-2" type="time" name="start_time">
      <input class="form-control mb-2" type="time" name="end_time">
      <input class="form-control mb-2" name="notes" placeholder="Notes">
      <button class="btn btn-success">Add</button>
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
        log_action("edit_session", f"Session id={session_id} updated")
        flash("Session updated.")
        return redirect(url_for("home", teacher_id=teacher_id))

    page = """
    <h5>Edit Session</h5>
    <form method="post">
      <label>Teacher</label>
      <select class="form-select mb-2" name="teacher_id">
        {% for t in teachers %}<option value="{{t.id}}" {% if s.teacher_id==t.id %}selected{% endif %}>{{t.name}}</option>{% endfor %}
      </select>
      <label>Student</label>
      <select class="form-select mb-2" name="student_id">
        {% for st in students %}<option value="{{st.id}}" {% if s.student_id==st.id %}selected{% endif %}>{{st.name}}</option>{% endfor %}
      </select>
      <label>Subject</label>
      <select class="form-select mb-2" name="subject_id">
        {% for sub in subjects %}<option value="{{sub.id}}" {% if s.subject_id==sub.id %}selected{% endif %}>{{sub.name}}</option>{% endfor %}
      </select>
      <input class="form-control mb-2" type="date" name="session_date" value="{{s.session_date}}">
      <input class="form-control mb-2" type="time" name="start_time" value="{{s.start_time}}">
      <input class="form-control mb-2" type="time" name="end_time" value="{{s.end_time}}">
      <input class="form-control mb-2" name="notes" value="{{s.notes or ''}}">
      <button class="btn btn-success">Update</button>
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
    <h5>Payments ({{today.strftime('%B %Y')}})</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Student</th><th>Sessions</th><th>Total Payment</th></tr></thead>
      <tbody>
        {% for p in payments_data %}
          <tr><td>{{p.student.name}}</td><td>{{p.sessions}}</td><td>${{"%.2f"|format(p.total)}}</td></tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, payments_data=payments_data, today=today)

@app.route("/teacher_totals")
def teacher_totals():
    today = date.today()
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    totals_data = []
    for t in teachers:
        sessions = current_month_sessions().filter_by(teacher_id=t.id).all()
        subject_counts = {}
        student_counts_by_subject = {}
        for s in sessions:
            subj = s.subject.name
            subject_counts[subj] = subject_counts.get(subj, 0) + 1
            student_counts_by_subject.setdefault(subj, set()).add(s.student_id)
        # convert sets to counts
        student_counts_by_subject = {k: len(v) for k, v in student_counts_by_subject.items()}
        totals_data.append({
            "teacher": t,
            "total_sessions": len(sessions),
            "subject_counts": subject_counts,
            "student_counts_by_subject": student_counts_by_subject
        })
    page = """
    <h5>Teacher Totals ({{today.strftime('%B %Y')}})</h5>
    {% for td in totals_data %}
      <h6 class="mt-3">{{td.teacher.name}}</h6>
      <p>Total sessions: {{td.total_sessions}}</p>
      <table class="table table-sm table-bordered">
        <thead><tr><th>Subject</th><th>Sessions</th><th>Unique Students</th></tr></thead>
        <tbody>
          {% for subj, count in td.subject_counts.items() %}
            <tr>
              <td>{{subj}}</td>
              <td>{{count}}</td>
              <td>{{td.student_counts_by_subject[subj]}}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endfor %}
    """
    return render(page, totals_data=totals_data, today=today)

@app.route("/logs")
def logs():
    entries = LogEntry.query.order_by(LogEntry.timestamp.desc()).limit(200).all()
    page = """
    <h5>Logs</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Time</th><th>Action</th><th>Details</th></tr></thead>
      <tbody>
        {% for e in entries %}
          <tr><td>{{e.timestamp}}</td><td>{{e.action}}</td><td>{{e.details}}</td></tr>
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
