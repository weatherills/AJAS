"""AJAS Azure Functions app entry point.

Uses the Python v2 programming model. The app currently exposes only the
infrastructure health endpoint. Each runbook phase implements its feature module
under ``app/features/`` and registers that blueprint here.
"""
import azure.functions as func

from app.features.health import bp as health_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Infrastructure.
app.register_blueprint(health_bp)

# Feature blueprints are registered as each phase is implemented, e.g.:
#   from app.features.resume_management import bp as resume_bp
#   app.register_blueprint(resume_bp)
