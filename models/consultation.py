from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from models.database import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    role          = db.Column(db.String(20), default="doctor")
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Consultation(db.Model):
    __tablename__ = "consultations"
    id           = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100))
    doctor_name  = db.Column(db.String(100))
    audio_file   = db.Column(db.String(200))
    status       = db.Column(db.String(30), default="uploaded")
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at  = db.Column(db.DateTime, nullable=True)
    transcripts  = db.relationship("Transcript", backref="consultation", lazy=True)
    entities     = db.relationship("Entity", backref="consultation", lazy=True)
    notes        = db.relationship("Note", backref="consultation", lazy=True)
    prescriptions = db.relationship("Prescription", backref="consultation", lazy=True)


class Transcript(db.Model):
    __tablename__ = "transcripts"
    id              = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey("consultations.id"))
    speaker         = db.Column(db.String(20))
    start_time      = db.Column(db.Float)
    end_time        = db.Column(db.Float)
    text            = db.Column(db.Text)
    confidence      = db.Column(db.Float, default=1.0)


class Entity(db.Model):
    __tablename__ = "entities"
    id              = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey("consultations.id"))
    entity_type     = db.Column(db.String(50))
    entity_value    = db.Column(db.String(200))
    metadata_json   = db.Column(db.Text)


class Note(db.Model):
    __tablename__ = "notes"
    id               = db.Column(db.Integer, primary_key=True)
    consultation_id  = db.Column(db.Integer, db.ForeignKey("consultations.id"))
    generated_note   = db.Column(db.Text)
    edited_note      = db.Column(db.Text)
    approved         = db.Column(db.Boolean, default=False)
    exported_pdf     = db.Column(db.String(200))
    fhir_json        = db.Column(db.Text)
    
class Prescription(db.Model):
    __tablename__ = "prescriptions"
    id              = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey("consultations.id"))
    medicine_name   = db.Column(db.String(200))
    dosage          = db.Column(db.String(100))
    frequency       = db.Column(db.String(100))
    duration        = db.Column(db.String(100))
    instructions    = db.Column(db.String(300))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    
class Appointment(db.Model):
    __tablename__ = "appointments"
    id            = db.Column(db.Integer, primary_key=True)
    patient_name  = db.Column(db.String(100), nullable=False)
    doctor_name   = db.Column(db.String(100))
    department    = db.Column(db.String(100))
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.String(10))
    visit_type    = db.Column(db.String(50), default="First visit")
    status        = db.Column(db.String(30), default="scheduled")
    phone         = db.Column(db.String(20))
    notes         = db.Column(db.String(300))
    consultation_id = db.Column(db.Integer,
                        db.ForeignKey("consultations.id"), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)