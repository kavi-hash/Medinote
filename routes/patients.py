from flask import Blueprint, flash, jsonify, render_template, request, redirect, url_for
from flask_login import login_required
from models.consultation import Consultation, Entity
from models.database import db
from sqlalchemy import func
from datetime import datetime, date, timedelta
from models.consultation import Appointment

patients_bp = Blueprint("patients", __name__)


@patients_bp.route("/patients")
@login_required
def patient_list():
    search = request.args.get("q", "").strip()
    query  = db.session.query(
        Consultation.patient_name,
        func.count(Consultation.id).label("visits"),
        func.max(Consultation.created_at).label("last_visit")
    ).group_by(Consultation.patient_name)

    if search:
        query = query.filter(
            Consultation.patient_name.ilike(f"%{search}%")
        )
    patients = query.order_by(
        func.max(Consultation.created_at).desc()
    ).all()
    return render_template("patient_list.html",
                           patients=patients, search=search)


@patients_bp.route("/patients/<path:patient_name>")
@login_required
def patient_detail(patient_name):
    consultations = Consultation.query.filter_by(
        patient_name=patient_name
    ).order_by(Consultation.created_at.desc()).all()
    return render_template("patient_detail.html",
                           patient_name=patient_name,
                           consultations=consultations)
    
from models.consultation import Prescription

@patients_bp.route("/prescriptions")
@login_required
def prescriptions():
    # Get all prescriptions joined with consultation info
    all_rxs = db.session.query(Prescription, Consultation).join(
        Consultation, Prescription.consultation_id == Consultation.id
    ).order_by(Prescription.created_at.desc()).all()

    # Group by consultation
    grouped = {}
    for rx, c in all_rxs:
        if c.id not in grouped:
            grouped[c.id] = {"consultation": c, "medicines": []}
        grouped[c.id]["medicines"].append(rx)

    return render_template("prescriptions.html",
                           grouped=grouped.values())
    
import qrcode
import io
import base64
import hashlib

@patients_bp.route("/qr-dispenser")
@login_required
def qr_dispenser():
    from models.consultation import Consultation
    consultations = Consultation.query.filter_by(
        status="approved"
    ).order_by(Consultation.approved_at.desc()).all()

    # Generate QR for each
    qr_data = []
    for c in consultations:
        token  = f"{c.id}-" + hashlib.md5(
            f"{c.id}-{c.patient_name}".encode()
        ).hexdigest()[:8]
        url    = f"http://127.0.0.1:5000/patient/{token}"

        img    = qrcode.QRCode(version=1, box_size=4, border=2,
                               error_correction=qrcode.constants.ERROR_CORRECT_M)
        img.add_data(url)
        img.make(fit=True)
        pil    = img.make_image(fill_color="black", back_color="white")
        buf    = io.BytesIO()
        pil.save(buf, format="PNG")
        b64    = base64.b64encode(buf.getvalue()).decode()

        qr_data.append({
            "consultation": c,
            "token":        token,
            "qr_b64":       b64,
            "url":          url
        })

    return render_template("qr_dispenser.html", qr_data=qr_data)

@patients_bp.route("/analytics")
@login_required
def analytics():
    from models.consultation import Consultation, Entity
    from sqlalchemy import func
    from datetime import datetime, timedelta

    # Total stats
    total         = Consultation.query.count()
    approved      = Consultation.query.filter_by(status="approved").count()
    this_month    = Consultation.query.filter(
        Consultation.created_at >= datetime.now().replace(day=1)
    ).count()

    # Status breakdown
    status_data = db.session.query(
        Consultation.status,
        func.count(Consultation.id)
    ).group_by(Consultation.status).all()

    # Department breakdown
    dept_data = db.session.query(
        Entity.entity_value,
        func.count(Entity.id)
    ).filter(Entity.entity_type == "department")\
     .group_by(Entity.entity_value).all()

    # Top symptoms
    symptom_data = db.session.query(
        Entity.entity_value,
        func.count(Entity.id).label("cnt")
    ).filter(Entity.entity_type == "symptoms")\
     .group_by(Entity.entity_value)\
     .order_by(func.count(Entity.id).desc()).limit(8).all()

    # Monthly volume (last 6 months)
    monthly = []
    for i in range(5, -1, -1):
        d     = datetime.now() - timedelta(days=30*i)
        count = Consultation.query.filter(
            func.strftime("%Y-%m", Consultation.created_at) ==
            d.strftime("%Y-%m")
        ).count()
        monthly.append({"month": d.strftime("%b %Y"), "count": count})

    # Top doctors
    doctor_data = db.session.query(
        Consultation.doctor_name,
        func.count(Consultation.id).label("cnt")
    ).group_by(Consultation.doctor_name)\
     .order_by(func.count(Consultation.id).desc()).limit(5).all()

    return render_template("analytics.html",
        total=total, approved=approved, this_month=this_month,
        status_data=status_data, dept_data=dept_data,
        symptom_data=symptom_data, monthly=monthly,
        doctor_data=doctor_data
    )

  
from flask_login import current_user
from werkzeug.security import check_password_hash

@patients_bp.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    from models.consultation import Consultation
    from datetime import datetime

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_name":
            new_name = request.form.get("name","").strip()
            if new_name:
                current_user.name = new_name
                db.session.commit()
                flash("Name updated successfully!", "success")
            else:
                flash("Name cannot be empty", "warning")

        elif action == "change_password":
            current_pw  = request.form.get("current_password","")
            new_pw      = request.form.get("new_password","")
            confirm_pw  = request.form.get("confirm_password","")

            if not current_user.check_password(current_pw):
                flash("Current password is incorrect", "danger")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters", "warning")
            elif new_pw != confirm_pw:
                flash("Passwords do not match", "warning")
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash("Password changed successfully!", "success")

        return redirect(url_for("patients.profile"))

    total     = Consultation.query.filter_by(
        doctor_name=current_user.name).count()
    approved  = Consultation.query.filter_by(
        doctor_name=current_user.name, status="approved").count()
    this_month = Consultation.query.filter(
        Consultation.doctor_name == current_user.name,
        Consultation.created_at >= datetime.now().replace(day=1)
    ).count()

    return render_template("profile.html",
        total=total, approved=approved, this_month=this_month)
    
    
@patients_bp.route("/appointments", methods=["GET","POST"])
@login_required
def appointments():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            appt = Appointment(
                patient_name     = request.form.get("patient_name"),
                doctor_name      = request.form.get("doctor_name",
                                    current_user.name),
                department       = request.form.get("department",""),
                appointment_date = datetime.strptime(
                    request.form.get("appointment_date"), "%Y-%m-%d").date(),
                appointment_time = request.form.get("appointment_time",""),
                visit_type       = request.form.get("visit_type","First visit"),
                phone            = request.form.get("phone",""),
                notes            = request.form.get("notes",""),
                status           = "scheduled"
            )
            db.session.add(appt)
            db.session.commit()
            flash(f"Appointment booked for {appt.patient_name}", "success")

        elif action == "update_status":
            appt = Appointment.query.get_or_404(
                int(request.form.get("appt_id")))
            appt.status = request.form.get("status")
            db.session.commit()

        elif action == "delete":
            appt = Appointment.query.get_or_404(
                int(request.form.get("appt_id")))
            db.session.delete(appt)
            db.session.commit()
            flash("Appointment removed", "info")

        return redirect(url_for("patients.appointments"))

    today  = date.today()
    upcoming = Appointment.query.filter(
        Appointment.appointment_date >= today
    ).order_by(
        Appointment.appointment_date,
        Appointment.appointment_time
    ).all()
    past = Appointment.query.filter(
        Appointment.appointment_date < today
    ).order_by(Appointment.appointment_date.desc()).limit(10).all()

    return render_template("appointments.html",
        upcoming=upcoming, past=past, today=today)


@patients_bp.route("/api/appointments/today")
@login_required
def today_appointments():
    today = date.today()
    appts = Appointment.query.filter_by(
        appointment_date=today
    ).order_by(Appointment.appointment_time).all()
    return jsonify([{
        "id":           a.id,
        "patient_name": a.patient_name,
        "time":         a.appointment_time,
        "department":   a.department,
        "status":       a.status,
        "visit_type":   a.visit_type
    } for a in appts])
    
@patients_bp.route("/start-from-appointment/<int:appt_id>")
@login_required
def start_from_appointment(appt_id):
    """Pre-fill consent session with appointment data and redirect to consent."""
    from flask import session
    appt = Appointment.query.get_or_404(appt_id)

    # Pre-fill session with appointment data
    session["patient_name"]      = appt.patient_name
    session["doctor_name"]       = appt.doctor_name or current_user.name
    session["patient_age"]       = ""
    session["patient_gender"]    = ""
    session["patient_phone"]     = appt.phone or ""
    session["patient_allergies"] = ""
    session["chief_complaint"]   = appt.notes or ""
    session["conditions"]        = ""
    session["current_meds"]      = ""
    session["department"]        = appt.department or ""
    session["blood_group"]       = ""
    session["visit_type"]        = appt.visit_type or "First visit"
    session["pain_scale"]        = "0"
    session["symptom_duration"]  = ""
    session["temperature"]       = ""
    session["blood_pressure"]    = ""
    session["pulse"]             = ""
    session["spo2"]              = ""
    session["weight"]            = ""
    session["height"]            = ""
    session["surgeries"]         = ""
    session["family_history"]    = ""
    session["patient_email"]     = ""
    session["from_appointment"]  = appt_id

    # Update appointment status to in_consultation
    appt.status = "in_consultation"
    db.session.commit()

    flash(f"Starting consultation for {appt.patient_name} — some fields pre-filled from appointment.", "info")
    return redirect(url_for("consultation.consent"))