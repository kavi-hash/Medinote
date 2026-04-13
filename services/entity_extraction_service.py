import os
import json
import re
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ENTITY_PROMPT = """You are a clinical NLP system. Extract medical entities from the consultation transcript below.

Return ONLY a valid JSON object with exactly these keys:
{{
  "symptoms":    ["list of symptoms mentioned"],
  "medications": ["list of medications mentioned"],
  "diagnoses":   ["list of diagnoses or impressions"],
  "allergies":   ["list of allergies mentioned"],
  "vitals":      ["list of vitals if mentioned e.g. temperature, BP"],
  "follow_up":   ["list of follow-up actions or advice"]
}}

Rules:
- Use short phrases, not full sentences
- If nothing found for a category, return empty list []
- Do NOT include any text outside the JSON object

Transcript:
{transcript}
"""

def extract_entities(text):
    """
    Extract clinical entities from transcript text using Groq LLM.
    Falls back to regex if API fails.
    """
    try:
        prompt = ENTITY_PROMPT.format(transcript=text)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800
        )

        raw = response.choices[0].message.content.strip()

        # Clean up any markdown code fences if present
        raw = re.sub(r"```json|```", "", raw).strip()

        entities = json.loads(raw)
        print(f"Entities extracted: {entities}")
        return entities

    except Exception as e:
        print(f"Groq entity extraction failed: {e}. Using regex fallback.")
        return _regex_fallback(text)


def _regex_fallback(text):
    """Simple regex fallback if Groq API is unavailable."""
    text_lower = text.lower()

    symptom_keywords = [
        "headache", "fever", "cough", "pain", "nausea", "vomiting",
        "fatigue", "dizziness", "rash", "shortness of breath",
        "chest pain", "diarrhea", "swelling", "weakness"
    ]
    med_keywords = [
        "paracetamol", "ibuprofen", "amoxicillin", "aspirin",
        "metformin", "lisinopril", "omeprazole", "cetirizine"
    ]

    found_symptoms = [s for s in symptom_keywords if s in text_lower]
    found_meds     = [m for m in med_keywords     if m in text_lower]

    return {
        "symptoms":    found_symptoms,
        "medications": found_meds,
        "diagnoses":   [],
        "allergies":   [],
        "vitals":      [],
        "follow_up":   []
    }