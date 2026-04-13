import os
import re
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SUMMARY_PROMPT = """You are a clinical documentation assistant.
Write a concise professional consultation summary (3-5 sentences) based on the SOAP note and entities below.

The summary should cover:
- Who the patient is and their chief complaint
- Key findings and clinical impression
- The treatment plan and follow-up

SOAP Note:
{soap}

Clinical Entities:
{entities}

Return ONLY the summary paragraph. No headings, no bullet points, no extra text.
"""

def generate_summary(soap, entities):
    """
    Generate a short narrative summary from SOAP note + entities.
    Falls back to a basic summary if Groq fails.
    """
    try:
        import json
        soap_text = json.dumps(soap) if isinstance(soap, dict) else str(soap)

        entity_lines = []
        if isinstance(entities, dict):
            for key, values in entities.items():
                if values:
                    entity_lines.append(f"{key}: {', '.join(values)}")
        entity_text = "\n".join(entity_lines) or "No entities extracted"

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": SUMMARY_PROMPT.format(
                soap=soap_text,
                entities=entity_text
            )}],
            temperature=0.3,
            max_tokens=300
        )
        summary = response.choices[0].message.content.strip()
        print(f"Summary generated ✅")
        return summary

    except Exception as e:
        print(f"Summary generation failed: {e}. Using fallback.")
        return _fallback_summary(soap, entities)


def _fallback_summary(soap, entities):
    """Build a basic summary from available data."""
    if isinstance(soap, dict):
        parts = []
        if soap.get("subjective"):
            parts.append(soap["subjective"])
        if soap.get("assessment"):
            parts.append(soap["assessment"])
        if soap.get("plan"):
            parts.append(soap["plan"])
        return " ".join(parts) if parts else "Clinical consultation completed."
    return str(soap) if soap else "Clinical consultation completed."