"""
routes/staff.py  (MongoDB version)
----------------------------------
Canteen Order Staff: process incoming orders for THEIR canteen only.
Workflow owned by staff:  Pending -> Accepted -> Preparing -> Ready for Pickup
                          (and confirm handover -> Picked Up once a rider is assigned)
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session)
from db import find, find_one, advance_order, update_doc

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


@staff_bp.before_request
def only_staff():
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=request.path))
    if session.get("role") != "canteen_staff":
        flash("This area is for canteen staff only.", "danger")
        return redirect(url_for("auth.home_redirect"))


def _my_canteen():
    return session.get("canteen_id")


def _orders_by_status(status_names):
    return find("orders",
                {"canteen_id": _my_canteen(), "status_name": {"$in": list(status_names)}},
                sort=[("_id", -1)])


@staff_bp.route("/")
def dashboard():
    new_orders = _orders_by_status(["Pending"])
    counts = {
        "new": len(new_orders),
        "preparing": len(_orders_by_status(["Accepted", "Preparing"])),
        "ready": len(_orders_by_status(["Ready for Pickup", "Rider Assigned"])),
        "completed": len(_orders_by_status(["Delivered"])),
    }
    canteen = find_one("canteens", {"_id": _my_canteen()})
    return render_template("staff/dashboard.html", new_orders=new_orders, counts=counts, canteen=canteen)


@staff_bp.route("/orders")
def live_orders():
    return render_template("staff/live_orders.html", orders=_orders_by_status(["Pending", "Accepted"]))


@staff_bp.route("/preparing")
def preparing():
    return render_template("staff/preparing.html", orders=_orders_by_status(["Preparing"]))


@staff_bp.route("/ready")
def ready():
    return render_template("staff/ready.html", orders=_orders_by_status(["Ready for Pickup", "Rider Assigned"]))


@staff_bp.route("/completed")
def completed():
    return render_template("staff/completed.html",
                           orders=_orders_by_status(["Picked Up", "On the Way", "Delivered", "Rejected", "Cancelled"]))


def _get_my_order(oid):
    return find_one("orders", {"_id": oid, "canteen_id": _my_canteen()})


@staff_bp.route("/order/<int:oid>")
def order_details(oid):
    order = _get_my_order(oid)
    if not order:
        flash("Order not found for your canteen.", "danger")
        return redirect(url_for("staff.dashboard"))
    return render_template("staff/order_details.html", order=order,
                           items=order["items"], history=order["history"])


@staff_bp.route("/order/<int:oid>/action", methods=["POST"])
def order_action(oid):
    order = _get_my_order(oid)
    if not order:
        flash("Order not found for your canteen.", "danger")
        return redirect(url_for("staff.dashboard"))
    action = request.form.get("action")
    current = order["status_name"]

    if action == "accept" and current == "Pending":
        advance_order(oid, "Accepted", "Accepted by staff")
        flash("Order accepted.", "success")
    elif action == "reject" and current == "Pending":
        advance_order(oid, "Rejected", "Rejected by staff")
        if order["payment"]["status"] == "Pending":
            update_doc("orders", {"_id": oid}, {"payment.status": "Failed"})
        flash("Order rejected.", "info")
    elif action == "prepare" and current == "Accepted":
        advance_order(oid, "Preparing", "Sent to kitchen / preparing")
        flash("Order is now being prepared.", "success")
    elif action == "ready" and current == "Preparing":
        advance_order(oid, "Ready for Pickup", "Packaged and ready for pickup")
        flash("Marked ready for pickup.", "success")
    elif action == "handover" and current == "Rider Assigned":
        advance_order(oid, "Picked Up", "Handover confirmed to rider")
        flash("Handover confirmed.", "success")
    else:
        flash("That action is not allowed from the current status.", "warning")

    return redirect(url_for("staff.order_details", oid=oid))


@staff_bp.route("/profile")
def profile():
    user = find_one("users", {"_id": session["user_id"]})
    canteen = find_one("canteens", {"_id": _my_canteen()})
    staff = {"position": user.get("position", "Order Staff"),
             "status": user.get("staff_status", "Active")}
    return render_template("staff/profile.html", user=user, canteen=canteen, staff=staff)
