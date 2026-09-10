"""AJAS Azure Functions app entry point.

Registers health, Review, Auto-Apply, Settings, Resume Management, Job
Source Integration, Matching & Ranking, Email Ingestion, and Learning Loop
HTTP plus queue workers.
"""
import azure.functions as func

from app.features.auth_session import bp as auth_session_bp
from app.features.auto_apply import bp as auto_apply_bp
from app.features.email import bp as email_bp
from app.features.health import bp as health_bp
from app.features.learning_loop import bp as learning_bp
from app.features.matching import bp as matching_bp
from app.features.ops import bp as ops_bp
from app.features.resume_management import bp as resume_bp
from app.features.review_decision import bp as review_bp
from app.features.settings import bp as settings_bp
from app.features.source_ingestion import bp as job_source_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_blueprint(health_bp)
app.register_blueprint(review_bp)
app.register_blueprint(auto_apply_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(resume_bp)
app.register_blueprint(job_source_bp)
app.register_blueprint(matching_bp)
app.register_blueprint(email_bp)
app.register_blueprint(learning_bp)
app.register_blueprint(ops_bp)
app.register_blueprint(auth_session_bp)
