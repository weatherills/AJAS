"""AJAS Azure Functions app entry point.

Registers the health endpoint plus Job Source Integration HTTP, timer, and
queue workers.
"""
import azure.functions as func

from app.features.health import bp as health_bp
from app.features.source_ingestion import bp as source_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_blueprint(health_bp)
app.register_blueprint(source_bp)
