"""AJAS Azure Functions app entry point.

Uses the Python v2 programming model. Registers the health endpoint and the
Resume Management HTTP API plus ``resume-parse`` queue worker.
"""
import azure.functions as func

from app.features.health import bp as health_bp
from app.features.resume_management import bp as resume_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Infrastructure.
app.register_blueprint(health_bp)
app.register_blueprint(resume_bp)
