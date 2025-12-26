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
# Ensure database tables exist
# -------------------------
with app.app_context():
    db.create_all()

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
