import os
from datetime import datetime
from flask import Flask, request, redirect, url_for, render_template_string, flash
from flask_sqlalchemy import SQLAlchemy

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
    except Exception:
        return None

def parse_time(s):
    try:
        return datetime.strptime(s, "%H:%M").time()
    except Exception:
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
    sessions = ClassSession.query.order_by(ClassSession.session_date.asc(), ClassSession.start_time.asc()).all()
    rows = "".join(
        f"<tr><td>{s.session_date}</td><td>{s.start_time}-{s.end_time}</td>"
        f"<td>{s.teacher.name}</td><td>{s.student.name}</td><td>{s.subject.name}</td>"
        f"<td><a href='{url_for('delete_session', session_id=s.id)}' class='btn btn-sm btn-danger'>Delete</a></td></tr>"
        for s in sessions
    )
    return render(
        "<h5>All Sessions</h5>"
        "<table class='table'><tr><th>Date</th><th>Time</th><th>Teacher</th><th>Student</th><th>Subject</th><th>Action</th></tr>"
        + rows + "</table>"
    )

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
        student_id = int(request.form.get("student_id"))
        subject_id = int(request.form.get("subject_id"))
        session_date = parse_date(request.form.get("session_date"))
        start_time = parse_time(request.form.get("start_time"))
        end_time = parse_time(request.form.get("end_time"))
        notes = request.form.get("notes")

        if not (teacher_id and student_id and subject_id and session_date and start_time and end_time):
            flash("Please fill all required fields (teacher, student, subject, date, start, end).")
            return redirect(url_for("add_session"))

        s = ClassSession(
            teacher_id=teacher_id,
            student_id=student_id,
            subject_id=subject_id,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            notes=notes
        )
        db.session.add(s)
        db.session.commit()
        log_action("Add Session", f"{session_date} teacher={teacher_id} student={student_id}")
        flash("Session added!")
        return redirect(url_for("home"))

    form = """
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
      <input class="form-control mb-2" name="session_date" placeholder="YYYY-MM-DD">
      <input class="form-control mb-2" name="start_time" placeholder="HH:MM">
      <input class="form-control mb-2" name="end_time" placeholder="HH:MM">
      <input class="form-control mb-2" name="notes" placeholder="Notes">
      <button class="btn btn-success" type="submit">Add Session</button>
    </form>
    """
    return render("<h5>Add Session</h5>" + form, teachers=teachers, students=students, subjects=subjects)

@app.route("/payments")
def payments():
    students = Student.query.all()
    rows = "".join(
        f"<li>{s.name}: {len(s.sessions)} sessions × {s.rate_per_class} = {len(s.sessions) * s.rate_per_class:.2f}</li>"
        for s in students
    )
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
# Run
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
