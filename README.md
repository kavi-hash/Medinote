# MediNote AI
### AI-Powered Clinical Documentation System

MediNote AI automates clinical documentation by recording doctor-patient conversations, transcribing them with AI, extracting medical entities, and generating SOAP notes — reducing documentation time so doctors can focus on patients.

## What it does
Records or uploads a doctor-patient consultation audio, automatically transcribes 
it, identifies speakers, extracts clinical entities, and generates a structured 
SOAP note — all reviewed and approved by the doctor before PDF export.

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | Flask, SQLAlchemy, Flask-Login |
| Database | SQLite |
| Speech-to-Text | WhisperX (faster-whisper) |
| Speaker Diarization | Pyannote Audio 3.1 |
| Entity Extraction | Groq LLM (llama-3.3-70b) |
| SOAP Generation | Groq LLM (llama-3.3-70b) |
| PDF Export | ReportLab |
| Frontend | Bootstrap 5, Jinja2 Templates |

## Pipeline
Audio → Transcription → Diarization → Entity Extraction → SOAP Note → Review → PDF

## Setup
1. Clone the repo
2. Create virtual environment: `python -m venv venv`
3. Activate: `venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Create `.env` file with your API keys
6. Run: `python app.py`
7. Open: http://127.0.0.1:5000

## Environment Variables
