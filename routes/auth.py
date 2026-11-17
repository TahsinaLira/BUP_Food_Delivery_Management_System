"""
routes/auth.py  (MongoDB version)
---------------------------------
Login, registration and logout for every role (single `users` collection).
Passwords are checked with Werkzeug (never stored in plain text).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash, check_password_hash
from db import find_one, insert_doc, next_id, update_doc
from helpers import clear_cart
from mailer import send_email

auth_bp = Blueprint("auth", __name__)

# Where each role goes after logging in.
ROLE_HOME = {
    "customer": "customer.home",
    "canteen_staff": "staff.dashboard",
    "canteen_manager": "manager.dashboard",
    "rider": "rider.dashboard",
    "admin": "admin.dashboard",
}


@auth_bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("auth.home_redirect"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/home")
def home_redirect():
    """Send a logged-in user to the correct dashboard for their role."""
    role = session.get("role")
    if role in ROLE_HOME:
        return redirect(url_for(ROLE_HOME[role]))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("auth/login.html")

        # In MongoDB the role is stored right on the user document, so there
        # is no "roles" table to join — we just read user["role"].
        user = find_one("users", {"email": email})

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        if not user.get("is_active", True):
            flash("Your account is suspended. Please contact the administrator.", "warning")
            return render_template("auth/login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]
        session["canteen_id"] = user.get("canteen_id")   # staff/managers carry this
        clear_cart()

        flash("Welcome back, " + user["full_name"] + "!", "success")
        next_url = request.args.get("next")
        if next_url:
            return redirect(next_url)
        return redirect(url_for(ROLE_HOME.get(user["role"], "auth.login")))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    from db import find
    locations = find("delivery_locations", {"is_active": True}, sort=[("_id", 1)])
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        bup_id = request.form.get("bup_id", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        user_type = request.form.get("user_type", "Student")
        campus = request.form.get("campus", "East Campus")
        hostel = bool(request.form.get("hostel_resident"))

        # ---- Backend validation ----
        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not bup_id:
            errors.append("BUP ID is required.")
        if "@" not in email:
            errors.append("A valid email is required.")
        elif not email.endswith("@bup.edu.bd"):
            errors.append("Please register with your BUP email.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if user_type not in ("Student", "Faculty", "Staff"):
            errors.append("Invalid user type.")
        if find_one("users", {"email": email}):
            errors.append("That email is already registered.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", locations=locations, form=request.form)

        # One document holds the account AND the customer profile (no join table).
        uid = next_id("users")
        insert_doc("users", {
            "_id": uid,
            "role": "customer",
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "password_hash": generate_password_hash(password, method="pbkdf2:sha256"),
            "is_active": True,
            # embedded customer profile
            "bup_id": bup_id,
            "user_type": user_type,
            "campus": campus,
            "hostel_resident": hostel,
            "default_location_id": None,
        })
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", locations=locations, form={})
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Step 1: the user enters their email; we email a 6-digit OTP code."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = find_one("users", {"email": email})
        if user:
            otp = "{:06d}".format(random.randint(0, 999999))
            minutes = current_app.config["OTP_VALIDITY_MINUTES"]
            update_doc("users", {"_id": user["_id"]}, {
                "reset_otp": otp,
                "reset_otp_expires": datetime.now() + timedelta(minutes=minutes),
            })
            send_email(email, "Your BUP Food password reset code",
                       f"Hi {user.get('full_name', '')},\n\n"
                       f"Your password reset code is: {otp}\n"
                       f"It will expire in {minutes} minutes.\n\n"
                       f"If you did not request this, you can safely ignore this email.")
        # Same message whether or not the email exists (don't reveal accounts).
        session["reset_email"] = email
        flash("If that email is registered, a 6-digit code has been sent to it.", "info")
        return redirect(url_for("auth.verify_otp"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """Step 2 & 3: the user enters the OTP, then sets a new password."""
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm", "")

        user = find_one("users", {"email": email})
        if not user or not user.get("reset_otp"):
            flash("Please request a new code.", "danger")
            return redirect(url_for("auth.forgot_password"))

        expires = user.get("reset_otp_expires")
        if expires and datetime.now() > expires:
            flash("That code has expired. Please request a new one.", "warning")
            return redirect(url_for("auth.forgot_password"))
        if otp != user.get("reset_otp"):
            flash("Incorrect code. Please check your email and try again.", "danger")
            return render_template("auth/verify_otp.html", email=email)
        if len(new_password) < 6:
            flash("New password must be at least 6 characters.", "danger")
            return render_template("auth/verify_otp.html", email=email)
        if new_password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("auth/verify_otp.html", email=email)

        update_doc("users", {"_id": user["_id"]}, {
            "password_hash": generate_password_hash(new_password, method="pbkdf2:sha256"),
            "reset_otp": None, "reset_otp_expires": None,
        })
        session.pop("reset_email", None)
        flash("Password reset successfully. Please log in with your new password.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/verify_otp.html", email=email)


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
