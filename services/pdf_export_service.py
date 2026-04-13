import os
import json
import io
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm as rl_cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable
)
from reportlab.platypus import Image as RLImage
# Brand colors
PRIMARY   = colors.HexColor("#2e3d52")
SUCCESS   = colors.HexColor("#198754")
WARNING   = colors.HexColor("#ffc107")
INFO      = colors.HexColor("#0dcaf0")
LIGHT_BG  = colors.HexColor("#f8f9fa")
DARK_TEXT = colors.HexColor("#212529")
MUTED     = colors.HexColor("#6c757d")
WHITE     = colors.white

def _parse_note(note_str):
    """Parse SOAP note from JSON string or plain string."""
    if not note_str:
        return {}
    try:
        cleaned = note_str.replace("'", '"')
        return json.loads(cleaned)
    except Exception:
        return {
            "subjective":  note_str,
            "objective":   "",
            "assessment":  "",
            "plan":        ""
        }

def _parse_entities(entities):
    """Group Entity objects by type."""
    grouped = {}
    for e in entities:
        grouped.setdefault(e.entity_type, []).append(e.entity_value)
    return grouped


def generate_pdf(consultation, note, transcripts, entities, output_folder):
    """
    Generate a clinical PDF report for a consultation.
    Returns the path to the generated PDF file.
    """
    os.makedirs(output_folder, exist_ok=True)

    filename  = f"medinote_{consultation.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath  = os.path.join(output_folder, filename)

    doc    = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=2*rl_cm, leftMargin=2*rl_cm,
        topMargin=2*rl_cm,   bottomMargin=2*rl_cm
    )
    styles = getSampleStyleSheet()
    story  = []

    # ── Custom styles ──────────────────────────────────────────
    title_style = ParagraphStyle(
        "MediTitle",
        parent=styles["Normal"],
        fontSize=20, fontName="Helvetica-Bold",
        textColor=PRIMARY, spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "MediSubtitle",
        parent=styles["Normal"],
        fontSize=10, textColor=MUTED, spaceAfter=2
    )
    section_header = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontSize=11, fontName="Helvetica-Bold",
        textColor=WHITE, spaceAfter=6
    )
    body_style = ParagraphStyle(
        "MediBody",
        parent=styles["Normal"],
        fontSize=10, leading=16,
        textColor=DARK_TEXT, spaceAfter=4
    )
    label_style = ParagraphStyle(
        "MediLabel",
        parent=styles["Normal"],
        fontSize=9, fontName="Helvetica-Bold",
        textColor=MUTED, spaceAfter=2
    )
    transcript_doctor = ParagraphStyle(
        "TransDoctor",
        parent=styles["Normal"],
        fontSize=9, leading=14,
        textColor=colors.HexColor("#084298"),
        leftIndent=8
    )
    transcript_patient = ParagraphStyle(
        "TransPatient",
        parent=styles["Normal"],
        fontSize=9, leading=14,
        textColor=colors.HexColor("#0a3622"),
        leftIndent=8
    )

    # ── Header ─────────────────────────────────────────────────
    story.append(Paragraph("MediNote AI", title_style))
    story.append(Paragraph("AI-Powered Clinical Documentation System", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=12))

    # ── Patient info table ─────────────────────────────────────
    approved_at = consultation.approved_at.strftime("%d %b %Y, %H:%M") \
                  if consultation.approved_at else "Pending"
    created_at  = consultation.created_at.strftime("%d %b %Y, %H:%M")

    info_data = [
        ["Patient name",  consultation.patient_name,
         "Consultation date", created_at],
        ["Doctor",        consultation.doctor_name,
         "Approved on",       approved_at],
        ["Status",        consultation.status.upper(),
         "Report ID",         f"MN-{consultation.id:04d}"],
    ]
    info_table = Table(info_data, colWidths=[3.5*rl_cm, 6*rl_cm, 3.5*rl_cm, 4*rl_cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), LIGHT_BG),
        ("BACKGROUND",  (0,0), (0,-1), colors.HexColor("#e7f1ff")),
        ("BACKGROUND",  (2,0), (2,-1), colors.HexColor("#e7f1ff")),
        ("FONTNAME",    (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",    (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("TEXTCOLOR",   (0,0), (0,-1), PRIMARY),
        ("TEXTCOLOR",   (2,0), (2,-1), PRIMARY),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [LIGHT_BG, WHITE]),
        ("PADDING",     (0,0), (-1,-1), 6),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 16))

    # ── SOAP Note ──────────────────────────────────────────────
    soap = _parse_note(note.edited_note if note else None)

    soap_sections = [
        ("S — Subjective",  "subjective", PRIMARY,              "Patient-reported symptoms and history"),
        ("O — Objective",   "objective",  INFO,                 "Observations and measurable findings"),
        ("A — Assessment",  "assessment", WARNING,              "Clinical impression and diagnosis"),
        ("P — Plan",        "plan",       SUCCESS,              "Treatment, medications and follow-up"),
    ]

    story.append(Paragraph("SOAP Note", ParagraphStyle(
        "SoapTitle", parent=styles["Normal"],
        fontSize=13, fontName="Helvetica-Bold",
        textColor=DARK_TEXT, spaceAfter=8
    )))

    for label, key, color, hint in soap_sections:
        content = soap.get(key, "") or hint

        # Colored section header row
        header_table = Table([[Paragraph(label, section_header)]], colWidths=[17*rl_cm])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), color),
            ("PADDING",    (0,0), (-1,-1), 6),
            ("ROUNDEDCORNERS", [4]),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 4))
        story.append(Paragraph(content, body_style))
        story.append(Spacer(1, 10))

    # ── Clinical Entities ──────────────────────────────────────
    grouped = _parse_entities(entities)
    if grouped:
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#dee2e6"), spaceAfter=10))
        story.append(Paragraph("Extracted Clinical Entities", ParagraphStyle(
            "EntTitle", parent=styles["Normal"],
            fontSize=13, fontName="Helvetica-Bold",
            textColor=DARK_TEXT, spaceAfter=8
        )))

        entity_labels = {
            "symptoms":    "Symptoms",
            "medications": "Medications",
            "diagnoses":   "Diagnoses",
            "allergies":   "Allergies",
            "vitals":      "Vitals",
            "follow_up":   "Follow-up"
        }
        ent_rows = []
        for key, label in entity_labels.items():
            if key in grouped and grouped[key]:
                values = ", ".join(grouped[key])
                ent_rows.append([
                    Paragraph(label, label_style),
                    Paragraph(values, body_style)
                ])

        if ent_rows:
            ent_table = Table(ent_rows, colWidths=[4*rl_cm, 13*rl_cm])
            ent_table.setStyle(TableStyle([
                ("VALIGN",      (0,0), (-1,-1), "TOP"),
                ("ROWBACKGROUNDS", (0,0), (-1,-1), [LIGHT_BG, WHITE]),
                ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
                ("PADDING",     (0,0), (-1,-1), 7),
            ]))
            story.append(ent_table)
            story.append(Spacer(1, 16))

    # ── Transcript ─────────────────────────────────────────────
    # ── Consultation Summary ────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.HexColor("#dee2e6"), spaceAfter=10))
    story.append(Paragraph("Consultation Summary", ParagraphStyle(
        "SumTitle", parent=styles["Normal"],
        fontSize=13, fontName="Helvetica-Bold",
        textColor=DARK_TEXT, spaceAfter=8
    )))

    # Get summary from note.fhir_json (we store summary there)
    summary_text = ""
    if note and note.fhir_json:
        summary_text = note.fhir_json
    else:
        # Build fallback summary from SOAP
        soap_data = _parse_note(note.edited_note if note else None)
        parts = []
        if soap_data.get("subjective"): parts.append(soap_data["subjective"])
        if soap_data.get("assessment"): parts.append(soap_data["assessment"])
        if soap_data.get("plan"):       parts.append(soap_data["plan"])
        summary_text = " ".join(parts) or "Clinical consultation completed."

    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 16))

    # ── Doctor signature line ───────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.HexColor("#dee2e6"), spaceAfter=10))
    sig_data = [["Approved by:", consultation.doctor_name,
                 "Designation:", "Medical Officer"]]
    sig_table = Table(sig_data, colWidths=[3*rl_cm, 6*rl_cm, 3*rl_cm, 5*rl_cm])
    sig_table.setStyle(TableStyle([
        ("FONTNAME",    (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",    (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("TEXTCOLOR",   (0,0), (0,-1), PRIMARY),
        ("TEXTCOLOR",   (2,0), (2,-1), PRIMARY),
        ("BACKGROUND",  (0,0), (-1,-1), LIGHT_BG),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
        ("PADDING",     (0,0), (-1,-1), 7),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 12))
    # ── Footer ─────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.HexColor("#dee2e6"), spaceAfter=6))
    story.append(Paragraph(
        f"Generated by MediNote AI &nbsp;·&nbsp; {datetime.now().strftime('%d %b %Y %H:%M')} "
        f"&nbsp;·&nbsp; Report ID: MN-{consultation.id:04d}",
        ParagraphStyle("Footer", parent=styles["Normal"],
                       fontSize=8, textColor=MUTED, alignment=1)
    ))
    # ── QR Code prescription ───────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.HexColor("#dee2e6"), spaceAfter=10))
    story.append(Paragraph("Prescription QR Code", ParagraphStyle(
        "QRTitle", parent=styles["Normal"],
        fontSize=13, fontName="Helvetica-Bold",
        textColor=DARK_TEXT, spaceAfter=6
    )))

    # Build QR data string
    soap      = _parse_note(note.edited_note if note else None)
    # Get prescriptions from DB
    from models.consultation import Prescription as PrescriptionModel
    db_rxs = PrescriptionModel.query.filter_by(
        consultation_id=consultation.id
    ).all()

    if db_rxs:
        rx_lines = []
        for rx in db_rxs:
            line = rx.medicine_name
            if rx.dosage:    line += f" {rx.dosage}"
            if rx.frequency: line += f" — {rx.frequency}"
            if rx.duration:  line += f" for {rx.duration}"
            rx_lines.append(line)
        rx_text = "\n".join(rx_lines)
    else:
        extracted = _parse_entities(entities).get("medications", [])
        rx_text   = ", ".join(extracted) if extracted else "No medicines prescribed"

    follow_up = ", ".join(_parse_entities(entities).get("follow_up", ["As advised"]))

    # Get prescriptions from DB
    from models.consultation import Prescription as PrescriptionModel
    db_rxs = PrescriptionModel.query.filter_by(
        consultation_id=consultation.id
    ).all()

    if db_rxs:
        rx_lines = []
        for rx in db_rxs:
            line = rx.medicine_name
            if rx.dosage:    line += f" {rx.dosage}"
            if rx.frequency: line += f" — {rx.frequency}"
            if rx.duration:  line += f" for {rx.duration}"
            rx_lines.append(line)
        rx_text = "\n".join(rx_lines)
    else:
        extracted = _parse_entities(entities).get("medications", [])
        rx_text   = ", ".join(extracted) if extracted else "No medicines prescribed"

    follow_up = ", ".join(_parse_entities(entities).get("follow_up", ["As advised"]))

    # Get prescriptions from DB
    from models.consultation import Prescription as PrescriptionModel
    db_rxs = PrescriptionModel.query.filter_by(
        consultation_id=consultation.id
    ).all()

    if db_rxs:
        rx_lines = []
        for rx in db_rxs:
            line = rx.medicine_name
            if rx.dosage:    line += f" {rx.dosage}"
            if rx.frequency: line += f" — {rx.frequency}"
            if rx.duration:  line += f" for {rx.duration}"
            rx_lines.append(line)
        rx_text = "\n".join(rx_lines)
    else:
        extracted = _parse_entities(entities).get("medications", [])
        rx_text   = ", ".join(extracted) if extracted else "No medicines prescribed"

    follow_up = ", ".join(_parse_entities(entities).get("follow_up", ["As advised"]))

    qr_data = (
        f"MEDINOTE AI — PRESCRIPTION\n"
        f"Report ID: MN-{consultation.id:04d}\n"
        f"Patient: {consultation.patient_name}\n"
        f"Doctor: {consultation.doctor_name}\n"
        f"Date: {consultation.created_at.strftime('%d %b %Y')}\n"
        f"--- MEDICINES ---\n"
        f"{rx_text}\n"
        f"--- FOLLOW-UP ---\n"
        f"{follow_up}"
    )
    

    # Generate QR image
    qr_img    = qrcode.QRCode(version=1, box_size=4, border=2,
                               error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr_img.add_data(qr_data)
    qr_img.make(fit=True)
    qr_pil    = qr_img.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_pil.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    from reportlab.platypus import Image as RLImage
    from reportlab.lib.units import cm

    qr_table = Table([[RLImage(qr_buffer, width=3.5*rl_cm, height=3.5*rl_cm),
         Paragraph(
             f"<b>Scan to view prescription</b><br/><br/>"
             f"Patient: {consultation.patient_name}<br/>"
             f"Doctor: {consultation.doctor_name}<br/>"
             f"Date: {consultation.created_at.strftime('%d %b %Y')}<br/>"
             f"<b>Medicines:</b><br/>{rx_text.replace(chr(10), '<br/>')}<br/>"
             f"<b>Follow-up:</b> {follow_up}",
             body_style
         )]
    ], colWidths=[4*cm, 13*cm])
    qr_table.setStyle(TableStyle([
        ("VALIGN",    (0,0), (-1,-1), "MIDDLE"),
        ("BACKGROUND",(0,0), (-1,-1), LIGHT_BG),
        ("BOX",       (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
        ("PADDING",   (0,0), (-1,-1), 10),
    ]))
    story.append(qr_table)
    story.append(Spacer(1, 12))
    doc.build(story)
    print(f"PDF generated: {filepath}")
    return filename