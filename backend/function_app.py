"""AJAS Azure Functions app entry point.

Registers the health endpoint plus Matching & Ranking HTTP and queue workers.
"""
import azure.functions as func

from app.features.health import bp as health_bp
from app.features.matching import bp as matching_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_blueprint(health_bp)
app.register_blueprint(matching_bp)
