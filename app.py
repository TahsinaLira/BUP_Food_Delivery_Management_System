"""
app.py
------
The application entry point. Run it with:  python app.py
It creates the Flask app, wires up the database, registers all route
blueprints, and exposes a few helper functions to the templates.
"""
from flask import Flask, render_template, session
from config import Config
from db import close_db
import helpers

# Route blueprints (each file groups the routes for one role/area)
from routes.auth import auth_bp
from routes.customer import customer_bp
from routes.staff import staff_bp
from routes.manager import manager_bp
from routes.rider import rider_bp
from routes.admin import admin_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Close the DB connection automatically after every request.
    app.teardown_appcontext(close_db)

    # Register all blueprints.
    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(rider_bp)
    app.register_blueprint(admin_bp)

    # Make helpers available inside every Jinja2 template.
    @app.context_processor
    def inject_helpers():
        role_titles = {
            "customer": "Customer", "canteen_staff": "Order Staff",
            "canteen_manager": "Canteen Manager", "rider": "Delivery Rider",
            "admin": "System Administrator",
        }
        return {
            "money": helpers.money,
            "status_badge": helpers.status_badge,
            "cart_count": helpers.cart_count(),
            "session": session,
            "STATUS_FLOW": helpers.STATUS_FLOW,
            "role_title": role_titles.get(session.get("role"), ""),
        }

    # Friendly error pages.
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    return app


app = create_app()

if __name__ == "__main__":
    # debug=True shows helpful error pages while you develop.
    app.run(host="127.0.0.1", port=5000, debug=True)
