"""AJAS Azure Functions app entry point.

Registers the health endpoint plus Review & Decision HTTP and queue workers.
"""
import azure.functions as func

from app.features.health import bp as health_bp
from app.features.review_decision import bp as review_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_blueprint(health_bp)
app.register_blueprint(review_bp)
