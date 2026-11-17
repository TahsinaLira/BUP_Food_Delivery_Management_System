"""
auth_helpers.py
---------------
Small decorators that protect routes based on the logged-in user's role.

Usage:
    @login_required
    @role_required("admin")
    def some_admin_page(): ...

The logged-in user's info is kept in the Flask session:
    session["user_id"], session["role"], session["full_name"], session["canteen_id"]
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Allow access only to the listed roles (e.g. role_required('manager'))."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            if session.get("role") not in roles:
                flash("You are not authorised to view that page.", "danger")
                return redirect(url_for("auth.home_redirect"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_user():
    """Return a small dict describing the logged-in user (or None)."""
    if "user_id" not in session:
        return None
    return {
        "id": session.get("user_id"),
        "role": session.get("role"),
        "full_name": session.get("full_name"),
        "canteen_id": session.get("canteen_id"),
    }
