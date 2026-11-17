"""
routes/rider.py  (MongoDB version)
----------------------------------
Delivery Rider (mobile-friendly). A rider can only touch deliveries that are
available to pick up or already assigned to them.
Workflow owned by rider:
   accept (Ready for Pickup -> Rider Assigned) -> confirm pickup (Picked Up)
   -> start delivery (On the Way) -> enter OTP -> Delivered.
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session)
from db import find, find_one, count, update_doc, advance_order

rider_bp = Blueprint("rider", __name__, url_prefix="/rider")


@rider_bp.before_request
def only_rider():
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=request.path))
    if session.get("role") != "rider":
        flash("This area is for riders only.", "danger")
        return redirect(url_for("auth.home_redirect"))


def _me():
    return session["user_id"]


def _order(oid):
    order = find_one("orders", {"_id": oid})
    if order:
        c = find_one("canteens", {"_id": order["canteen_id"]})
        order["canteen_campus"] = c["campus"] if c else ""
    return order


@rider_bp.route("/")
def dashboard():
    me = find_one("users", {"_id": _me()})
    active_canteen_ids = [c["_id"] for c in find("canteens", {"is_active": True})]
    available = find("orders",
                     {"status_name": "Ready for Pickup", "rider_id": None,
                      "canteen_id": {"$in": active_canteen_ids}}, sort=[("_id", 1)])
    active = find("orders",
                  {"rider_id": _me(),
                   "status_name": {"$in": ["Rider Assigned", "Picked Up", "On the Way"]}},
                  sort=[("_id", -1)])
    done_today = count("orders", {"rider_id": _me(), "status_name": "Delivered"})
    return render_template("rider/dashboard.html", me=me, available=available,
                           active=active, done_today=done_today)


@rider_bp.route("/status", methods=["POST"])
def set_status():
    status = request.form.get("status", "Available")
    if status in ("Available", "Busy", "Offline"):
        update_doc("users", {"_id": _me()}, {"rider_status": status})
        flash("Status set to " + status + ".", "info")
    return redirect(url_for("rider.dashboard"))


@rider_bp.route("/delivery/<int:oid>/accept", methods=["POST"])
def accept(oid):
    order = _order(oid)
    if not order or order["status_name"] != "Ready for Pickup" or order["rider_id"]:
        flash("This delivery is no longer available.", "warning")
        return redirect(url_for("rider.dashboard"))
    me = find_one("users", {"_id": _me()})
    update_doc("orders", {"_id": oid}, {
        "rider_id": _me(), "rider_name": me["full_name"], "rider_phone": me.get("phone", ""),
    })
    advance_order(oid, "Rider Assigned", "Rider accepted delivery")
    update_doc("users", {"_id": _me()}, {"rider_status": "Busy"})
    flash("Delivery accepted.", "success")
    return redirect(url_for("rider.delivery", oid=oid))


@rider_bp.route("/delivery/<int:oid>")
def delivery(oid):
    order = _order(oid)
    if not order or order["rider_id"] != _me():
        flash("Delivery not found.", "danger")
        return redirect(url_for("rider.dashboard"))
    return render_template("rider/active_delivery.html", order=order, items=order["items"])


@rider_bp.route("/delivery/<int:oid>/pickup", methods=["POST"])
def confirm_pickup(oid):
    order = _order(oid)
    if not order or order["rider_id"] != _me():
        flash("Delivery not found.", "danger")
        return redirect(url_for("rider.dashboard"))
    if order["status_name"] != "Rider Assigned":
        flash("Cannot confirm pickup from the current status.", "warning")
        return redirect(url_for("rider.delivery", oid=oid))
    advance_order(oid, "Picked Up", "Picked up from canteen")
    flash("Pickup confirmed.", "success")
    return redirect(url_for("rider.delivery", oid=oid))


@rider_bp.route("/delivery/<int:oid>/start", methods=["POST"])
def start_delivery(oid):
    order = _order(oid)
    if not order or order["rider_id"] != _me():
        flash("Delivery not found.", "danger")
        return redirect(url_for("rider.dashboard"))
    if order["status_name"] != "Picked Up":
        flash("Cannot start delivery from the current status.", "warning")
        return redirect(url_for("rider.delivery", oid=oid))
    advance_order(oid, "On the Way", "Rider on the way")
    flash("Delivery started.", "success")
    return redirect(url_for("rider.delivery", oid=oid))


@rider_bp.route("/delivery/<int:oid>/otp", methods=["GET", "POST"])
def otp(oid):
    order = _order(oid)
    if not order or order["rider_id"] != _me():
        flash("Delivery not found.", "danger")
        return redirect(url_for("rider.dashboard"))
    if order["status_name"] != "On the Way":
        flash("You can enter the OTP once you are on the way.", "warning")
        return redirect(url_for("rider.delivery", oid=oid))

    if request.method == "POST":
        entered = request.form.get("otp", "").strip()
        if entered == order["otp"]:
            advance_order(oid, "Delivered", "Delivered - OTP verified")
            if order["payment"]["status"] == "Pending":
                update_doc("orders", {"_id": oid}, {"payment.status": "Paid"})
            update_doc("users", {"_id": _me()}, {"rider_status": "Available"})
            flash("Delivery completed successfully!", "success")
            return redirect(url_for("rider.completed", oid=oid))
        else:
            flash("Incorrect delivery OTP. Please try again.", "danger")
    return render_template("rider/otp.html", order=order)


@rider_bp.route("/delivery/<int:oid>/completed")
def completed(oid):
    order = _order(oid)
    if not order or order["rider_id"] != _me():
        flash("Delivery not found.", "danger")
        return redirect(url_for("rider.dashboard"))
    return render_template("rider/completed.html", order=order)


@rider_bp.route("/history")
def history():
    rows = find("orders", {"rider_id": _me(), "status_name": "Delivered"}, sort=[("_id", -1)])
    return render_template("rider/history.html", orders=rows)


@rider_bp.route("/profile")
def profile():
    me = find_one("users", {"_id": _me()})
    total = count("orders", {"rider_id": _me(), "status_name": "Delivered"})
    return render_template("rider/profile.html", me=me, total=total)
