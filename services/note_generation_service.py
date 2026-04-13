import os
import json
import re
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SOAP_PROMPT = """You are an experienced clinical documentation assistant.
Generate a professional SOAP note from the structured medical data below.

Medical data:
{medical_data}

Conversation transcript:
{transcript}

Return ONLY a valid JSON object with exactly these keys:
{{
  "subjective":  "Patient-reported symptoms, complaints, and history in 2-3 sentences",
  "objective":   "Observed findings, vitals, and measurable data in 1-2 sentences",
  "assessment":  "Clinical impression or likely diagnosis in 1-2 sentences",
  "plan":        "Treatment plan, medications, advice, and follow-up in 2-3 sentences"
}}

Rules:
- Write in professional clinical language
- Be concise and factual
- Do NOT include any text outside the JSON object
"""

def generate_soap_note(entities, segments):
    """
    Generate a SOAP note using Groq LLM from extracted entities and transcript.
    """
    try:
        # Build readable transcript
        transcript_text = "\n".join([
            f"[{s.get('speaker', 'UNKNOWN')}]: {s.get('text', '')}"
            for s in segments
        ])

        # Build medical summary
        medical_data = json.dumps(entities, indent=2)

        prompt = SOAP_PROMPT.format(
            medical_data=medical_data,
            transcript=transcript_text
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",   # use the bigger model for note quality
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1000
        )

        raw = response.choices[0].message.content.strip()

        # Clean markdown fences if present
        raw = re.sub(r"```json|```", "", raw).strip()

        soap = json.loads(raw)

        # Validate all keys exist
        for key in ["subjective", "objective", "assessment", "plan"]:
            if key not in soap:
                soap[key] = "Not available"

        print(f"SOAP note generated successfully ✅")
        return soap

    except Exception as e:
        print(f"Groq SOAP generation failed: {e}. Using fallback.")
        return _fallback_soap(entities)


def _fallback_soap(entities):
    """Fallback SOAP note built from entities if Groq fails."""
    symptoms  = ", ".join(entities.get("symptoms",    [])) or "not recorded"
    meds      = ", ".join(entities.get("medications", [])) or "none reported"
    diagnosis = ", ".join(entities.get("diagnoses",   [])) or "under evaluation"
    plan      = ", ".join(entities.get("follow_up",   [])) or "follow-up as needed"

    return {
        "subjective":  f"Patient reports the following symptoms: {symptoms}.",
        "objective":   "Vitals not recorded in this session.",
        "assessment":  f"Clinical impression: {diagnosis}.",
        "plan":        f"Medications discussed: {meds}. {plan}."
    }