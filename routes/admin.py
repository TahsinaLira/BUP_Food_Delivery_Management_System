"""
routes/admin.py  (MongoDB version)
----------------------------------
System Administrator: manages the whole platform — users, canteens,
managers, riders, orders, delivery locations, complaints, reports, settings.
Dashboard numbers are computed in Python from the collections.
"""
from datetime import date, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session)
from db import find, find_one, insert_doc, update_doc, count, next_id
from config import Config

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def only_admin():
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=request.path))
    if session.get("role") != "admin":
        flash("This area is for administrators only.", "danger")
        return redirect(url_for("auth.home_redirect"))


# --------------------------- Dashboard ---------------------------
@admin_bp.route("/")
def dashboard():
    orders = find("orders")
    valid = [o for o in orders if o["status_name"] not in ("Cancelled", "Rejected")]
    today = date.today()
    kpis = {
        "users": count("users"),
        "canteens": count("canteens", {"is_active": True}),
        "riders": count("users", {"role": "rider", "is_active": True}),
        "today_orders": sum(1 for o in orders if o["placed_at"].date() == today),
        "completed": sum(1 for o in orders if o["status_name"] == "Delivered"),
        "cancelled": sum(1 for o in orders if o["status_name"] in ("Cancelled", "Rejected")),
        "order_value": sum(o["total"] for o in valid),
        "open_complaints": count("complaints", {"status": "Open"}),
    }

    canteens = find("canteens", sort=[("name", 1)])
    oc = {}
    for o in orders:
        oc[o["canteen_id"]] = oc.get(o["canteen_id"], 0) + 1
    by_canteen = sorted(({"name": c["name"], "c": oc.get(c["_id"], 0)} for c in canteens),
                        key=lambda x: x["c"], reverse=True)

    bucket = {}
    for o in orders:
        key = o["placed_at"].strftime("%Y-%m-%d")
        bucket[key] = bucket.get(key, 0) + 1
    ot_labels, ot_values = [], []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        ot_labels.append(d.strftime("%a"))
        ot_values.append(bucket.get(d.strftime("%Y-%m-%d"), 0))

    recent = sorted(orders, key=lambda o: o["_id"], reverse=True)[:8]
    return render_template("admin/dashboard.html", kpis=kpis,
                           canteen_labels=[r["name"] for r in by_canteen],
                           canteen_values=[r["c"] for r in by_canteen],
                           ot_labels=ot_labels, ot_values=ot_values, recent=recent)


# --------------------------- Users ---------------------------
@admin_bp.route("/users")
def users():
    q = request.args.get("q", "").strip()
    filt = {}
    if q:
        filt = {"$or": [{"full_name": {"$regex": q, "$options": "i"}},
                        {"email": {"$regex": q, "$options": "i"}}]}
    rows = find("users", filt, sort=[("_id", 1)])
    for u in rows:
        u["role_name"] = u["role"]
    return render_template("admin/users.html", users=rows, q=q)


@admin_bp.route("/users/<int:uid>/toggle", methods=["POST"])
def toggle_user(uid):
    user = find_one("users", {"_id": uid})
    if user:
        new = not user.get("is_active", True)
        update_doc("users", {"_id": uid}, {"is_active": new})
        flash(("Activated " if new else "Suspended ") + user["full_name"] + ".", "info")
    return redirect(url_for("admin.users"))


# --------------------------- Canteens ---------------------------
@admin_bp.route("/canteens")
def canteens():
    rows = find("canteens", sort=[("campus", 1), ("name", 1)])
    for c in rows:
        mgr = find_one("users", {"_id": c.get("manager_id")}) if c.get("manager_id") else None
        c["manager_name"] = mgr["full_name"] if mgr else None
        c["order_count"] = count("orders", {"canteen_id": c["_id"]})
        revs = find("reviews", {"canteen_id": c["_id"]})
        c["rating"] = round(sum(r["canteen_rating"] for r in revs) / len(revs), 1) if revs else None
    return render_template("admin/canteens.html", canteens=rows)


@admin_bp.route("/canteens/<int:cid>/toggle", methods=["POST"])
def toggle_canteen(cid):
    c = find_one("canteens", {"_id": cid})
    if c:
        new_active = not c.get("is_active", True)
        label = "Active" if new_active else "Coming Soon"
        update_doc("canteens", {"_id": cid},
                   {"is_active": new_active, "is_open": new_active, "status_label": label})
        flash(c["name"] + (" activated." if new_active else " deactivated."), "info")
    return redirect(url_for("admin.canteens"))


# --------------------------- Managers ---------------------------
@admin_bp.route("/managers")
def managers():
    rows = find("users", {"role": "canteen_manager"}, sort=[("full_name", 1)])
    for m in rows:
        c = find_one("canteens", {"manager_id": m["_id"]})
        m["canteen_name"] = c["name"] if c else None
    return render_template("admin/managers.html", managers=rows)


# --------------------------- Riders ---------------------------
@admin_bp.route("/riders")
def riders():
    rows = find("users", {"role": "rider"}, sort=[("full_name", 1)])
    for r in rows:
        r["delivered"] = count("orders", {"rider_id": r["_id"], "status_name": "Delivered"})
    return render_template("admin/riders.html", riders=rows)


# --------------------------- Orders monitoring ---------------------------
@admin_bp.route("/orders")
def orders():
    canteen_id = request.args.get("canteen", type=int)
    status = request.args.get("status", "").strip()
    filt = {}
    if canteen_id:
        filt["canteen_id"] = canteen_id
    if status:
        filt["status_name"] = status
    rows = find("orders", filt, sort=[("_id", -1)])
    for o in rows:
        o["pay_status"] = o.get("payment", {}).get("status", "")
    canteens = find("canteens", sort=[("name", 1)])
    statuses = find("order_statuses", sort=[("sort", 1)])
    return render_template("admin/orders.html", orders=rows, canteens=canteens,
                           statuses=statuses, sel_canteen=canteen_id, sel_status=status)


# --------------------------- Delivery locations ---------------------------
@admin_bp.route("/locations", methods=["GET", "POST"])
def locations():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        campus = request.form.get("campus", "").strip()
        if name and campus:
            if find_one("delivery_locations", {"name": name}):
                flash("A location with that name already exists.", "warning")
            else:
                insert_doc("delivery_locations", {
                    "_id": next_id("delivery_locations"), "name": name,
                    "campus": campus, "is_active": True})
                flash("Delivery location added.", "success")
        else:
            flash("Please provide a location name and campus.", "danger")
        return redirect(url_for("admin.locations"))
    rows = find("delivery_locations", sort=[("campus", 1), ("name", 1)])
    return render_template("admin/locations.html", locations=rows)


@admin_bp.route("/locations/<int:lid>/toggle", methods=["POST"])
def toggle_location(lid):
    loc = find_one("delivery_locations", {"_id": lid})
    if loc:
        update_doc("delivery_locations", {"_id": lid}, {"is_active": not loc.get("is_active", True)})
        flash("Delivery location updated.", "info")
    return redirect(url_for("admin.locations"))


# --------------------------- Complaints ---------------------------
@admin_bp.route("/complaints")
def complaints():
    tab = request.args.get("tab", "all")
    filt = {}
    if tab in ("Open", "Under Review", "Resolved"):
        filt["status"] = tab
    rows = find("complaints", filt, sort=[("_id", -1)])
    return render_template("admin/complaints.html", complaints=rows, tab=tab)


@admin_bp.route("/complaints/<int:cid>/status", methods=["POST"])
def complaint_status(cid):
    status = request.form.get("status")
    if status in ("Open", "Under Review", "Resolved"):
        update_doc("complaints", {"_id": cid}, {"status": status})
        flash("Complaint marked " + status + ".", "info")
    return redirect(url_for("admin.complaints"))


# --------------------------- Reports ---------------------------
@admin_bp.route("/reports")
def reports():
    orders = find("orders")
    canteens = find("canteens", sort=[("name", 1)])
    locations = find("delivery_locations")
    loc_campus = {l["_id"]: l["campus"] for l in locations}
    loc_name = {l["_id"]: l["name"] for l in locations}

    cstats = {c["_id"]: {"name": c["name"], "c": 0, "revenue": 0} for c in canteens}
    campus_count, location_count = {}, {}
    for o in orders:
        if o["canteen_id"] in cstats:
            cstats[o["canteen_id"]]["c"] += 1
            cstats[o["canteen_id"]]["revenue"] += o["total"]
        camp = loc_campus.get(o["delivery_location_id"], "—")
        nm = loc_name.get(o["delivery_location_id"], "—")
        campus_count[camp] = campus_count.get(camp, 0) + 1
        location_count[nm] = location_count.get(nm, 0) + 1

    by_canteen = sorted(cstats.values(), key=lambda x: x["revenue"], reverse=True)
    by_campus = sorted(({"campus": k, "c": v} for k, v in campus_count.items()),
                       key=lambda x: x["c"], reverse=True)
    by_location = sorted(({"name": k, "c": v} for k, v in location_count.items()),
                         key=lambda x: x["c"], reverse=True)
    valid = [o for o in orders if o["status_name"] not in ("Cancelled", "Rejected")]
    totals = {"revenue": sum(o["total"] for o in valid), "orders": len(orders)}
    return render_template("admin/reports.html", by_canteen=by_canteen, by_campus=by_campus,
                           by_location=by_location, totals=totals)


# --------------------------- System settings ---------------------------
@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        flash("System settings saved (prototype). Edit config.py for permanent changes.", "success")
        return redirect(url_for("admin.settings"))
    settings = {
        "delivery_fee": Config.DELIVERY_FEE,
        "payments": ["Cash on Delivery", "bKash", "Nagad"],
        "campuses": ["East Campus", "West Campus", "Boys' Hostel", "Girls' Hostel"],
    }
    return render_template("admin/settings.html", settings=settings)


@admin_bp.route("/profile")
def profile():
    user = find_one("users", {"_id": session["user_id"]})
    return render_template("admin/profile.html", user=user)
