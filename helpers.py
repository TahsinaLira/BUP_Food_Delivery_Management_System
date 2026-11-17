"""
helpers.py
----------
Small shared helper functions used across the app and templates.
"""
import random
from flask import session, current_app

# The full order lifecycle, in order. "Rejected" and "Cancelled" are end states.
STATUS_FLOW = [
    "Pending", "Accepted", "Preparing", "Ready for Pickup",
    "Rider Assigned", "Picked Up", "On the Way", "Delivered",
]
END_STATES = ["Delivered", "Rejected", "Cancelled"]

# Maps each status to a Bootstrap badge colour class (used in templates).
STATUS_BADGE = {
    "Pending": "secondary",
    "Accepted": "info",
    "Preparing": "warning",
    "Ready for Pickup": "primary",
    "Rider Assigned": "info",
    "Picked Up": "primary",
    "On the Way": "warning",
    "Delivered": "success",
    "Rejected": "danger",
    "Cancelled": "danger",
    # payment statuses
    "Paid": "success", "Failed": "danger", "Refunded": "dark",
    # complaint statuses
    "Open": "danger", "Under Review": "warning", "Resolved": "success",
    # rider / generic
    "Available": "success", "Busy": "warning", "Offline": "secondary",
    "Active": "success", "Inactive": "secondary", "Coming Soon": "warning",
    "Suspended": "danger",
}


def status_badge(name):
    return STATUS_BADGE.get(name, "secondary")


def money(amount):
    """Format a number as Bangladeshi Taka, e.g. 470 -> '৳470'."""
    try:
        return current_app.config["CURRENCY"] + "{:,.0f}".format(float(amount))
    except (TypeError, ValueError):
        return current_app.config["CURRENCY"] + "0"


def generate_otp():
    """Return a random 4-digit delivery code as a string, e.g. '4821'."""
    return "{:04d}".format(random.randint(0, 9999))


# ---------------- Cart helpers (cart is stored in the Flask session) ----------------
def get_cart():
    """Cart = {'canteen_id': int|None, 'items': [{'food_id', 'qty'}]}"""
    return session.get("cart", {"canteen_id": None, "items": []})


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_count():
    cart = get_cart()
    return sum(i["qty"] for i in cart["items"])


def clear_cart():
    session["cart"] = {"canteen_id": None, "items": []}
    session.modified = True
