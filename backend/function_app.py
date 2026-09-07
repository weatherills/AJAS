"""AJAS Azure Functions app entry point.

Uses the Python v2 programming model. Registers the health endpoint and the
Settings HTTP API.
"""
import azure.functions as func

from app.features.health import bp as health_bp
from app.features.settings import bp as settings_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_blueprint(health_bp)
app.register_blueprint(settings_bp)
