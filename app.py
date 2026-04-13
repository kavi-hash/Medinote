from dotenv import load_dotenv
from flask_mail import Mail
load_dotenv()

from flask import Flask, app
from flask_socketio import SocketIO
from config import Config
from models.database import db, login_manager

socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    from routes.patients import patients_bp
    app.register_blueprint(patients_bp)
    
    from datetime import datetime as _dt
    @app.context_processor
    def inject_now():
        return {"now": _dt.now}
    
    import hashlib
    @app.template_filter("md5_token")
    def md5_token_filter(patient_name, consultation_id):
        return hashlib.md5(
            f"{consultation_id}-{patient_name}".encode()
        ).hexdigest()[:8]

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    
    from flask_mail import Mail
    mail = Mail(app)
    app.extensions['mail'] = mail

    # Register blueprints (we'll add routes next)
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.consultation import consultation_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(consultation_bp)

    with app.app_context():
        db.create_all()
        print("✅ Database tables created")
        
    import json

    @app.template_filter("soap_section")
    def soap_section_filter(note_str, section):
        if not note_str:
            return "Not available"
        try:
            # Try proper JSON first
            if isinstance(note_str, str):
                data = json.loads(note_str)
                return data.get(section, "Not available")
        except Exception:
            pass
        try:
            # Try replacing single quotes (Python dict format fallback)
            if isinstance(note_str, str):
                data = json.loads(note_str.replace("'", '"'))
                return data.get(section, "Not available")
        except Exception:
            pass
        # Last resort — return raw string only for subjective
        if section == "subjective":
            return note_str
        return "Not available"
        
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("500.html"), 500
    return app

if __name__ == "__main__":
    app = create_app()
    socketio.run(app, debug=True)