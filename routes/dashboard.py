from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models.consultation import Consultation, Entity
from models.database import db
from sqlalchemy import func
from datetime import datetime, timedelta

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    from models.consultation import Consultation, Entity, Prescription, Appointment
    from datetime import datetime, date, timedelta

    today       = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    # Stats
    total      = Consultation.query.count()
    approved   = Consultation.query.filter_by(status="approved").count()
    pending    = Consultation.query.filter(
        Consultation.status.in_(["ready","uploaded","transcribed"])
    ).count()
    processing = Consultation.query.filter_by(status="processing").count()

    # Needs prescription — approved but no prescriptions written
    approved_ids = [c.id for c in Consultation.query.filter_by(
        status="approved").all()]
    has_rx_ids   = [p.consultation_id for p in
                    Prescription.query.distinct(
                        Prescription.consultation_id).all()]
    no_rx_count  = len(set(approved_ids) - set(has_rx_ids))

    # Notes waiting for review
    needs_review = Consultation.query.filter_by(status="ready").count()

    # PDFs ready (approved + has pdf)
    from models.consultation import Note
    pdfs_ready = Note.query.filter(
        Note.approved == True,
        Note.exported_pdf != None
    ).count()

    # Today's appointments
    today_appts = Appointment.query.filter_by(
        appointment_date=today
    ).order_by(Appointment.appointment_time).all()

    # This week stats
    week_ago    = datetime.now() - timedelta(days=7)
    week_consults = Consultation.query.filter(
        Consultation.created_at >= week_ago).count()
    week_approved = Consultation.query.filter(
        Consultation.created_at >= week_ago,
        Consultation.status == "approved").count()
    week_rxs = Prescription.query.filter(
        Prescription.created_at >= week_ago).count()
    week_pdfs = Note.query.filter(
        Note.approved == True,
        Note.exported_pdf != None,
        Note.consultation_id.in_(
            db.session.query(Consultation.id).filter(
                Consultation.created_at >= week_ago)
        )
    ).count()

    # Top symptoms this week
    top_symptoms = db.session.query(
        Entity.entity_value,
        func.count(Entity.id).label("cnt")
    ).filter(
        Entity.entity_type == "symptoms",
        Entity.consultation_id.in_(
            db.session.query(Consultation.id).filter(
                Consultation.created_at >= week_ago))
    ).group_by(Entity.entity_value)\
     .order_by(func.count(Entity.id).desc()).limit(5).all()

    return render_template("dashboard.html",
        total=total, approved=approved,
        pending=pending, processing=processing,
        no_rx_count=no_rx_count,
        needs_review=needs_review,
        pdfs_ready=pdfs_ready,
        today_appts=today_appts,
        week_consults=week_consults,
        week_approved=week_approved,
        week_rxs=week_rxs,
        week_pdfs=week_pdfs,
        top_symptoms=top_symptoms,
        today=today
    )

@dashboard_bp.route("/consultations")
@login_required
def all_consultations():
    consultations = Consultation.query.order_by(
        Consultation.created_at.desc()
    ).all()
    return render_template("all_consultations.html",
                           consultations=consultations)