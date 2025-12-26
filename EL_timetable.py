# -------------------------
# Payments (current month) + downloads
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
            "Rate/Class": st.rate_per_class,
            "Classes": sessions_count,
            "Total": total_payment
        })
    df = pd.DataFrame(data)
    if format == "csv":
        return send_file(io.BytesIO(df.to_csv(index=False).encode()), mimetype="text/csv",
                         download_name=f"payments_{today.strftime('%Y_%m')}.csv", as_attachment=True)
    elif format == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         download_name=f"payments_{today.strftime('%Y_%m')}.xlsx", as_attachment=True)

# -------------------------
# Teacher totals (hourly sessions + student/subject counts)
# -------------------------
@app.route("/teacher_totals")
def teacher_totals():
    today = date.today()
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    totals_data = []
    for t in teachers:
        sessions = current_month_sessions().filter_by(teacher_id=t.id).all()
        hourly_sessions = len(sessions)
        student_subject_counts = {}
        for s in sessions:
            key = f"{s.student.name} - {s.subject.name}"
            student_subject_counts[key] = student_subject_counts.get(key, 0) + 1
        totals_data.append({
            "teacher": t,
            "hourly_sessions": hourly_sessions,
            "student_subject_counts": student_subject_counts
        })
    page = """
    <div class="d-flex gap-2 mb-2">
      <a class="btn btn-sm btn-outline-dark" href="{{ url_for('download_totals', format='csv') }}">Download CSV</a>
      <a class="btn btn-sm btn-outline-dark" href="{{ url_for('download_totals', format='excel') }}">Download Excel</a>
    </div>
    <h5>Teacher Totals ({{ today.strftime('%B %Y') }})</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Teacher</th><th>Hourly Sessions</th><th>Students & Subjects</th></tr></thead>
      <tbody>
        {% for row in totals_data %}
          <tr>
            <td>{{ row.teacher.name }}{% if row.teacher.nickname %} ({{ row.teacher.nickname }}){% endif %}</td>
            <td>{{ row.hourly_sessions }}</td>
            <td>
              {% for key, count in row.student_subject_counts.items() %}
                {{ key }}: {{ count }}<br>
              {% endfor %}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    """
    return render(page, totals_data=totals_data, today=today)

@app.route("/download_totals/<format>")
def download_totals(format):
    today = date.today()
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    data = []
    for t in teachers:
        sessions = current_month_sessions().filter_by(teacher_id=t.id).all()
        for s in sessions:
            data.append({
                "Teacher": t.name,
                "Nickname": t.nickname or "",
                "Date": s.session_date.isoformat(),
                "Start": s.start_time.strftime("%H:%M"),
                "End": s.end_time.strftime("%H:%M"),
                "Student": s.student.name,
                "Subject": s.subject.name
            })
    df = pd.DataFrame(data)
    if format == "csv":
        return send_file(io.BytesIO(df.to_csv(index=False).encode()), mimetype="text/csv",
                         download_name=f"totals_{today.strftime('%Y_%m')}.csv", as_attachment=True)
    elif format == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         download_name=f"totals_{today.strftime('%Y_%m')}.xlsx", as_attachment=True)

# -------------------------
# Logs
# -------------------------
@app.route("/logs")
def logs():
    entries = LogEntry.query.order_by(LogEntry.timestamp.desc()).limit(200).all()
    page = """
    <h5>Logs</h5>
    <table class="table table-sm table-bordered">
      <thead><tr><th>Time</th><th>Action</th><th>Details</th></tr></thead>
      <tbody>
        {% for e in entries %}
          <tr><td>{{ e.timestamp }}</td><td>{{ e.action }}</td><td>{{ e.details }}</td></tr>
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
