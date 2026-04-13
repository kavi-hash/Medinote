import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.database import db
from models.consultation import Consultation, Transcript, Entity, Note, Prescription


consultation_bp = Blueprint("consultation", __name__)

ALLOWED = {"wav", "mp3", "m4a", "ogg", "webm"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED

@consultation_bp.route("/")
def index():
    return redirect(url_for("auth.login"))

@consultation_bp.route("/consent", methods=["GET"])
@login_required
def consent():
    return render_template("consent.html")

@consultation_bp.route("/consent", methods=["POST"])
@login_required
def consent_submit():
    from flask import session
    session["patient_name"]      = request.form.get("patient_name")
    session["doctor_name"]       = request.form.get("doctor_name", current_user.name)
    session["patient_age"]       = request.form.get("age", "")
    session["patient_gender"]    = request.form.get("gender", "")
    session["patient_phone"]     = request.form.get("phone", "")
    session["patient_allergies"] = request.form.get("allergies", "")
    session["chief_complaint"]   = request.form.get("chief_complaint", "")
    session["conditions"]        = request.form.get("conditions", "")
    session["current_meds"]      = request.form.get("current_meds", "")
    session["department"]        = request.form.get("department", "")
    session["blood_group"]       = request.form.get("blood_group", "")
    session["visit_type"]        = request.form.get("visit_type", "")
    session["pain_scale"]        = request.form.get("pain_scale", "0")
    session["symptom_duration"]  = request.form.get("symptom_duration", "")
    session["temperature"]       = request.form.get("temperature", "")
    session["blood_pressure"]    = request.form.get("blood_pressure", "")
    session["pulse"]             = request.form.get("pulse", "")
    session["spo2"]              = request.form.get("spo2", "")
    session["weight"]            = request.form.get("weight", "")
    session["height"]            = request.form.get("height", "")
    session["surgeries"]         = request.form.get("surgeries", "")
    session["family_history"]    = request.form.get("family_history", "")
    session["patient_email"] = request.form.get("patient_email", "")
    session["patient_email"] = request.form.get("patient_email", "")
    return redirect(url_for("consultation.upload"))


@consultation_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    from flask import session
    # Redirect to consent if no patient data in session
    if "patient_name" not in session:
        return redirect(url_for("consultation.consent"))

    if request.method == "POST":
        patient_name = session.pop("patient_name")
        doctor_name  = session.pop("doctor_name", current_user.name)
        audio_file   = request.files.get("audio_file")

        if not audio_file or audio_file.filename == "":
            flash("Please select an audio file", "warning")
            return redirect(url_for("consultation.upload"))

        if not allowed_file(audio_file.filename):
            flash("Unsupported file type. Use WAV, MP3, M4A, OGG or WEBM", "danger")
            return redirect(url_for("consultation.upload"))

        filename     = secure_filename(audio_file.filename)
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)
        save_path    = os.path.join(upload_folder, filename)
        audio_file.save(save_path)

        # Build extra context from consent form
        extra_context = {
        "age":             session.pop("patient_age",      ""),
        "gender":          session.pop("patient_gender",   ""),
        "phone":           session.pop("patient_phone",    ""),
        "allergies":       session.pop("patient_allergies",""),
        "chief_complaint": session.pop("chief_complaint",  ""),
        "conditions":      session.pop("conditions",       ""),
        "current_meds":    session.pop("current_meds",     ""),
        "department":      session.pop("department",       ""),
        "blood_group":     session.pop("blood_group",      ""),
        "visit_type":      session.pop("visit_type",       ""),
        "pain_scale":      session.pop("pain_scale",       ""),
        "symptom_duration":session.pop("symptom_duration", ""),
        "temperature":     session.pop("temperature",      ""),
        "blood_pressure":  session.pop("blood_pressure",   ""),
        "pulse":           session.pop("pulse",            ""),
        "spo2":            session.pop("spo2",             ""),
        "weight":          session.pop("weight",           ""),
        "height":          session.pop("height",           ""),
        "surgeries":       session.pop("surgeries",        ""),
        "family_history":  session.pop("family_history",   ""),
        "email":           session.pop("patient_email",    ""),
    }

        import json as _json
        consultation = Consultation(
            patient_name=patient_name,
            doctor_name=doctor_name,
            audio_file=filename,
            status="uploaded"
        )
        db.session.add(consultation)
        db.session.commit()

        # Store consent data as entities
        for key, val in extra_context.items():
            if val:
                e = Entity(
                    consultation_id=consultation.id,
                    entity_type=key,
                    entity_value=val
                )
                db.session.add(e)
        db.session.commit()

        flash(f"Consultation created for {patient_name}. Processing now.", "success")
        return redirect(url_for("consultation.process", id=consultation.id))

    # GET — show upload form with patient name pre-filled
    return render_template("upload.html",
                           patient_name=session.get("patient_name",""),
                           doctor_name=session.get("doctor_name", current_user.name))

@consultation_bp.route("/process/<int:id>")
@login_required
def process(id):
    consultation = Consultation.query.get_or_404(id)
    consultation.status = "processing"
    db.session.commit()
    return render_template("process.html", consultation=consultation)


@consultation_bp.route("/api/run-pipeline/<int:id>", methods=["POST"])
@login_required
def run_pipeline(id):
    consultation = Consultation.query.get_or_404(id)
    from utils.file_utils import convert_to_wav
    raw_path   = os.path.join(current_app.config["UPLOAD_FOLDER"], consultation.audio_file)
    audio_path = convert_to_wav(raw_path)

    try:
        # Step 1 — Transcription
        from services.transcription_service import transcribe_audio
        segments = transcribe_audio(audio_path)

        if not segments:
            raise ValueError("Transcription returned no segments. Check your audio file.")

        # Step 2 — Save transcripts to DB
        # Clear old transcripts for this consultation first
        Transcript.query.filter_by(consultation_id=consultation.id).delete()
        db.session.commit()

        for seg in segments:
            t = Transcript(
                consultation_id=consultation.id,
                speaker=seg.get("speaker", "UNKNOWN"),
                start_time=seg.get("start", 0),
                end_time=seg.get("end", 0),
                text=seg.get("text", ""),
                confidence=seg.get("confidence", 1.0)
            )
            db.session.add(t)

        consultation.status = "transcribed"
        db.session.commit()

        # Step 3 — Entity extraction
        from services.entity_extraction_service import extract_entities
        full_text = " ".join([s.get("text", "").strip() for s in segments if s.get("text","").strip()])
        print(f"Full transcript text: {full_text[:200]}")
        
        from utils.file_utils import convert_to_wav, ensure_proper_wav
        raw_path   = os.path.join(current_app.config["UPLOAD_FOLDER"], consultation.audio_file)
        audio_path = convert_to_wav(raw_path)
        audio_path = ensure_proper_wav(audio_path)

        if not full_text.strip():
            print("Warning: transcript text is empty, using placeholder for entity extraction")
            full_text = "Patient consultation recorded."

        entities = extract_entities(full_text)

        for etype, values in entities.items():
            for val in values:
                e = Entity(
                    consultation_id=consultation.id,
                    entity_type=etype,
                    entity_value=val if isinstance(val, str) else str(val)
                )
                db.session.add(e)

        db.session.commit()

        # Step 4 — SOAP note generation
        # Step 4 — SOAP note generation
        from services.note_generation_service import generate_soap_note
        soap = generate_soap_note(entities, segments)

        import json as _json
        soap_json = _json.dumps(soap) if isinstance(soap, dict) else soap
        # Generate summary
        from services.summary_service import generate_summary
        summary = generate_summary(soap, entities)

        note = Note(
            consultation_id=consultation.id,
            generated_note=soap_json,
            edited_note=soap_json,
            approved=False,
            fhir_json=summary   # reusing fhir_json column to store summary
        )
        db.session.add(note)
        consultation.status = "ready"
        db.session.commit()

        return jsonify({"status": "success", "redirect": url_for("consultation.review", id=id)})

    except Exception as e:
        consultation.status = "error"
        db.session.commit()
        return jsonify({"status": "error", "message": str(e)}), 500


@consultation_bp.route("/review/<int:id>")
@login_required
def review(id):
    consultation = Consultation.query.get_or_404(id)
    transcripts  = Transcript.query.filter_by(consultation_id=id).all()
    entities     = Entity.query.filter_by(consultation_id=id).all()
    note         = Note.query.filter_by(consultation_id=id).first()
    return render_template("review.html",
        consultation=consultation,
        transcripts=transcripts,
        entities=entities,
        note=note
    )


@consultation_bp.route("/api/update-note/<int:id>", methods=["POST"])
@login_required
def update_note(id):
    note = Note.query.filter_by(consultation_id=id).first_or_404()
    data = request.get_json()
    new_note = data.get("note", note.edited_note)
    # Store as JSON string if dict passed
    if isinstance(new_note, dict):
        import json as _json
        note.edited_note = _json.dumps(new_note)
    else:
        note.edited_note = new_note
    db.session.commit()
    return jsonify({"status": "saved"})


@consultation_bp.route("/approve/<int:id>", methods=["POST"])
@login_required
def approve(id):
    import hashlib
    from datetime import datetime
    consultation          = Consultation.query.get_or_404(id)
    note                  = Note.query.filter_by(consultation_id=id).first_or_404()
    note.approved         = True
    consultation.status   = "approved"
    consultation.approved_at = datetime.utcnow()
    db.session.commit()

    # Generate token for patient view
    token = f"{consultation.id}-" + hashlib.md5(
        f"{consultation.id}-{consultation.patient_name}".encode()
    ).hexdigest()[:8]

    # Auto-generate PDF
    try:
        from services.pdf_export_service import generate_pdf
        from models.consultation import Transcript, Entity
        transcripts = Transcript.query.filter_by(consultation_id=id).all()
        entities    = Entity.query.filter_by(consultation_id=id).all()
        output_folder = current_app.config["OUTPUT_FOLDER"]
        pdf_filename  = generate_pdf(consultation, note,
                                     transcripts, entities, output_folder)
        note.exported_pdf = pdf_filename
        db.session.commit()

        # Send email if patient email exists
        # Find patient email — stored as entity_type "email"
        patient_email = None
        email_entity  = Entity.query.filter_by(
            consultation_id=id, entity_type="email"
        ).first()
        if email_entity and email_entity.entity_value:
            patient_email = email_entity.entity_value
        print(f"Patient email: {patient_email}")

        if patient_email:
            from services.email_service import send_report_email
            send_report_email(
                patient_email, consultation.patient_name,
                consultation.doctor_name, consultation.id,
                pdf_filename, token
            )
            flash(f"Consultation approved! Report emailed to {patient_email}", "success")
        else:
            flash("Consultation approved! No email on file — share QR code with patient.", "success")

    except Exception as e:
        flash(f"Approved but PDF/email failed: {str(e)}", "warning")

    return redirect(url_for("consultation.review", id=id))

import json as _json

@consultation_bp.route("/audio/<path:filename>")
@login_required
def serve_audio(filename):
    from flask import send_from_directory
    return send_from_directory(
        os.path.join(os.getcwd(), current_app.config["UPLOAD_FOLDER"]),
        filename
    )


@consultation_bp.route("/export/pdf/<int:id>")
@login_required
def export_pdf(id):
    from flask import send_from_directory
    from services.pdf_export_service import generate_pdf

    consultation = Consultation.query.get_or_404(id)
    note         = Note.query.filter_by(consultation_id=id).first()
    transcripts  = Transcript.query.filter_by(consultation_id=id).all()
    entities     = Entity.query.filter_by(consultation_id=id).all()

    if not note:
        flash("No note available to export", "warning")
        return redirect(url_for("consultation.review", id=id))

    try:
        output_folder = current_app.config["OUTPUT_FOLDER"]
        filename = generate_pdf(
            consultation, note,
            transcripts, entities,
            output_folder
        )
        # Save PDF path to DB
        note.exported_pdf = filename
        db.session.commit()

        return send_from_directory(
            os.path.join(os.getcwd(), output_folder),
            filename,
            as_attachment=True,
            download_name=f"MediNote_{consultation.patient_name.replace(' ','_')}_{consultation.id}.pdf"
        )
    except Exception as e:
        flash(f"PDF export failed: {str(e)}", "danger")
        return redirect(url_for("consultation.review", id=id))
    
    
@consultation_bp.route("/api/update-speaker/<int:transcript_id>", methods=["POST"])
@login_required
def update_speaker(transcript_id):
    t    = Transcript.query.get_or_404(transcript_id)
    data = request.get_json()
    t.speaker = data.get("speaker", t.speaker)
    db.session.commit()
    return jsonify({"status": "updated", "speaker": t.speaker})

@consultation_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_consultation(id):
    consultation = Consultation.query.get_or_404(id)
    # Delete related records
    Transcript.query.filter_by(consultation_id=id).delete()
    Entity.query.filter_by(consultation_id=id).delete()
    Note.query.filter_by(consultation_id=id).delete()
    db.session.delete(consultation)
    db.session.commit()
    flash("Consultation deleted.", "info")
    return redirect(url_for("dashboard.dashboard"))

@consultation_bp.route("/record", methods=["GET"])
@login_required
def record():
    from flask import session
    if "patient_name" not in session:
        return redirect(url_for("consultation.consent"))
    return render_template("record.html",
                           patient_name=session.get("patient_name",""),
                           doctor_name=session.get("doctor_name", current_user.name))


@consultation_bp.route("/api/save-recording", methods=["POST"])
@login_required
def save_recording():
    from flask import session
    import uuid

    patient_name = session.pop("patient_name", "Unknown")
    doctor_name  = session.pop("doctor_name",  current_user.name)

    # Pop all consent data
    extra_context = {
        "age":             session.pop("patient_age",      ""),
        "gender":          session.pop("patient_gender",   ""),
        "phone":           session.pop("patient_phone",    ""),
        "allergies":       session.pop("patient_allergies",""),
        "chief_complaint": session.pop("chief_complaint",  ""),
        "conditions":      session.pop("conditions",       ""),
        "current_meds":    session.pop("current_meds",     ""),
        "department":      session.pop("department",       ""),
        "email":           session.pop("patient_email",    ""),
    }

    audio_data = request.files.get("audio")
    if not audio_data:
        return jsonify({"status": "error", "message": "No audio received"}), 400

    # Save with unique filename
    filename     = f"recording_{uuid.uuid4().hex[:8]}.wav"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    save_path    = os.path.join(upload_folder, filename)
    audio_data.save(save_path)

    # Create consultation record
    consultation = Consultation(
        patient_name=patient_name,
        doctor_name=doctor_name,
        audio_file=filename,
        status="uploaded"
    )
    db.session.add(consultation)
    db.session.commit()

    # Save consent entities
    for key, val in extra_context.items():
        if val:
            e = Entity(
                consultation_id=consultation.id,
                entity_type=key,
                entity_value=val
            )
            db.session.add(e)
    db.session.commit()

    return jsonify({
        "status":  "success",
        "id":      consultation.id,
        "redirect": url_for("consultation.process", id=consultation.id)
    })

@consultation_bp.route("/export/excel")
@login_required
def export_excel():
    from flask import send_from_directory
    from services.excel_export_service import generate_excel
    from models.consultation import Consultation

    consultations = Consultation.query.order_by(
        Consultation.created_at.desc()
    ).all()

    try:
        output_folder = current_app.config["OUTPUT_FOLDER"]
        filename = generate_excel(consultations, output_folder)
        return send_from_directory(
            os.path.join(os.getcwd(), output_folder),
            filename,
            as_attachment=True,
            download_name=f"MediNote_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
    except Exception as e:
        flash(f"Excel export failed: {str(e)}", "danger")
        return redirect(url_for("dashboard.dashboard"))
    
    
@consultation_bp.route("/api/prescriptions/<int:id>", methods=["GET"])
@login_required
def get_prescriptions(id):
    from models.consultation import Prescription
    rxs = Prescription.query.filter_by(consultation_id=id).all()
    return jsonify([{
        "id":           r.id,
        "medicine_name":r.medicine_name,
        "dosage":       r.dosage,
        "frequency":    r.frequency,
        "duration":     r.duration,
        "instructions": r.instructions
    } for r in rxs])


@consultation_bp.route("/api/prescriptions/<int:id>", methods=["POST"])
@login_required
def save_prescriptions(id):
    from models.consultation import Prescription
    data = request.get_json()
    medicines = data.get("medicines", [])

    # Clear old and save fresh
    Prescription.query.filter_by(consultation_id=id).delete()
    for m in medicines:
        if m.get("medicine_name","").strip():
            rx = Prescription(
                consultation_id=id,
                medicine_name  =m.get("medicine_name",""),
                dosage         =m.get("dosage",""),
                frequency      =m.get("frequency",""),
                duration       =m.get("duration",""),
                instructions   =m.get("instructions","")
            )
            db.session.add(rx)
    db.session.commit()
    return jsonify({"status":"saved","count":len(medicines)})


@consultation_bp.route("/patient/<token>")
def patient_view(token):
    """Public page — no login needed. Patient sees their report via QR."""
    import hashlib
    consultation = Consultation.query.filter_by(id=int(token.split("-")[0])).first_or_404()
    # Simple token check
    expected = hashlib.md5(
        f"{consultation.id}-{consultation.patient_name}".encode()
    ).hexdigest()[:8]
    if token.split("-")[1] != expected:
        return "Invalid link", 403
    from models.consultation import Prescription, Note, Entity
    note          = Note.query.filter_by(consultation_id=consultation.id).first()
    prescriptions = Prescription.query.filter_by(consultation_id=consultation.id).all()
    entities      = Entity.query.filter_by(consultation_id=consultation.id).all()
    return render_template("patient_view.html",
        consultation=consultation,
        note=note,
        prescriptions=prescriptions,
        entities=entities
    )
@consultation_bp.route("/api/entities/<int:id>")
@login_required
def get_entities(id):
    entities = Entity.query.filter_by(consultation_id=id).all()
    return jsonify([{
        "entity_type":  e.entity_type,
        "entity_value": e.entity_value
    } for e in entities])
    
@consultation_bp.route("/api/prefill-data")
@login_required
def prefill_data():
    from flask import session
    return jsonify({
        "patient_name":  session.get("patient_name", ""),
        "phone":         session.get("patient_phone", ""),
        "chief_complaint": session.get("chief_complaint", ""),
        "department":    session.get("department", ""),
        "visit_type":    session.get("visit_type", ""),
        "from_appointment": session.get("from_appointment", None)
    })