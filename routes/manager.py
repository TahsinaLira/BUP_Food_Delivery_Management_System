"""
routes/manager.py  (MongoDB version)
------------------------------------
Canteen Manager: manages ONLY their own canteen — menu, categories, staff,
orders (monitor), sales reports, reviews and settings.

Note on NoSQL: a canteen's categories are stored as an array INSIDE the
canteen document, and dashboard numbers are computed in Python from the
orders collection (orders embed their items), instead of SQL JOIN/GROUP BY.
"""
from collections import Counter
from datetime import date, datetime, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session)
from db import (get_db, find, find_one, insert_doc, update_doc, delete_doc,
                count, next_id)

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")


@manager_bp.before_request
def only_manager():
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=request.path))
    if session.get("role") != "canteen_manager":
        flash("This area is for canteen managers only.", "danger")
        return redirect(url_for("auth.home_redirect"))


def _cid():
    return session.get("canteen_id")


def _canteen_orders(cid):
    return find("orders", {"canteen_id": cid})


# --------------------------- Dashboard ---------------------------
@manager_bp.route("/")
def dashboard():
    cid = _cid()
    canteen = find_one("canteens", {"_id": cid})
    orders = _canteen_orders(cid)

    valid = [o for o in orders if o["status_name"] not in ("Cancelled", "Rejected")]
    today = date.today()
    today_orders = sum(1 for o in orders if o["placed_at"].date() == today)
    revenue = sum(o["total"] for o in valid)
    completed = sum(1 for o in orders if o["status_name"] == "Delivered")
    cancelled = sum(1 for o in orders if o["status_name"] in ("Cancelled", "Rejected"))

    reviews = find("reviews", {"canteen_id": cid})
    avg_rating = round(sum(r["canteen_rating"] for r in reviews) / len(reviews), 1) if reviews else 0

    sold = Counter()
    for o in orders:
        for it in o["items"]:
            sold[it["item_name"]] += it["quantity"]
    best_seller = sold.most_common(1)[0][0] if sold else "—"
    popular = [{"item_name": n, "q": q} for n, q in sold.most_common(5)]

    recent = sorted(orders, key=lambda o: o["_id"], reverse=True)[:6]
    unavailable = find("food_items", {"canteen_id": cid, "is_available": False})

    labels, values = _sales_series(orders, days=7)
    kpis = {"today_orders": today_orders, "revenue": revenue, "completed": completed,
            "cancelled": cancelled, "avg_rating": avg_rating, "best_seller": best_seller}
    return render_template("manager/dashboard.html", canteen=canteen, kpis=kpis,
                           recent=recent, popular=popular, unavailable=unavailable,
                           chart_labels=labels, chart_values=values)


def _sales_series(orders, days=7):
    """Revenue per day for the last `days` days (computed in Python)."""
    valid = [o for o in orders if o["status_name"] not in ("Cancelled", "Rejected")]
    bucket = {}
    for o in valid:
        key = o["placed_at"].strftime("%Y-%m-%d")
        bucket[key] = bucket.get(key, 0) + o["total"]
    labels, values = [], []
    for i in range(days - 1, -1, -1):
        d = date.today() - timedelta(days=i)
        labels.append(d.strftime("%a %d"))
        values.append(bucket.get(d.strftime("%Y-%m-%d"), 0))
    return labels, values


# --------------------------- Menu management ---------------------------
def _cat_name(canteen, category_id):
    for c in canteen.get("categories", []):
        if c["id"] == category_id:
            return c["name"]
    return ""


@manager_bp.route("/menu")
def menu():
    cid = _cid()
    canteen = find_one("canteens", {"_id": cid})
    order = {c["id"]: c["sort"] for c in canteen.get("categories", [])}
    foods = find("food_items", {"canteen_id": cid})
    foods.sort(key=lambda f: (order.get(f["category_id"], 99), f["name"]))
    return render_template("manager/menu.html", foods=foods)


@manager_bp.route("/food/add", methods=["GET", "POST"])
def add_food():
    cid = _cid()
    canteen = find_one("canteens", {"_id": cid})
    categories = sorted(canteen.get("categories", []), key=lambda c: c["sort"])
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float)
        available = bool(request.form.get("is_available"))
        image = request.form.get("image", "").strip()
        if not name or price is None or price < 0 or not category_id:
            flash("Please provide a name, category and a valid price.", "danger")
            return render_template("manager/food_form.html", categories=categories, food=None, action="add")
        insert_doc("food_items", {
            "_id": next_id("food_items"), "canteen_id": cid, "category_id": category_id,
            "category_name": _cat_name(canteen, category_id), "name": name,
            "description": description, "price": price, "is_available": available,
            "image": image or None, "rating": 0.0,
        })
        flash("Food item added.", "success")
        return redirect(url_for("manager.menu"))
    return render_template("manager/food_form.html", categories=categories, food=None, action="add")


@manager_bp.route("/food/<int:fid>/edit", methods=["GET", "POST"])
def edit_food(fid):
    cid = _cid()
    food = find_one("food_items", {"_id": fid, "canteen_id": cid})
    if not food:
        flash("Food item not found for your canteen.", "danger")
        return redirect(url_for("manager.menu"))
    canteen = find_one("canteens", {"_id": cid})
    categories = sorted(canteen.get("categories", []), key=lambda c: c["sort"])
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float)
        available = bool(request.form.get("is_available"))
        image = request.form.get("image", "").strip()
        if not name or price is None or price < 0 or not category_id:
            flash("Please provide a name, category and a valid price.", "danger")
            return render_template("manager/food_form.html", categories=categories, food=food, action="edit")
        update_doc("food_items", {"_id": fid}, {
            "name": name, "description": description, "category_id": category_id,
            "category_name": _cat_name(canteen, category_id), "price": price,
            "is_available": available, "image": image or None,
        })
        flash("Food item updated.", "success")
        return redirect(url_for("manager.menu"))
    return render_template("manager/food_form.html", categories=categories, food=food, action="edit")


@manager_bp.route("/food/<int:fid>/toggle", methods=["POST"])
def toggle_food(fid):
    cid = _cid()
    food = find_one("food_items", {"_id": fid, "canteen_id": cid})
    if food:
        new = not food.get("is_available")
        update_doc("food_items", {"_id": fid}, {"is_available": new})
        flash(food["name"] + (" marked available." if new else " marked unavailable."), "info")
    return redirect(url_for("manager.menu"))


@manager_bp.route("/food/<int:fid>/delete", methods=["POST"])
def delete_food(fid):
    cid = _cid()
    food = find_one("food_items", {"_id": fid, "canteen_id": cid})
    if food:
        # Only delete if it was never ordered (keeps order history valid).
        used = get_db()["orders"].count_documents({"items.food_item_id": fid})
        if used:
            update_doc("food_items", {"_id": fid}, {"is_available": False})
            flash("This item has past orders, so it was marked unavailable instead of deleted.", "warning")
        else:
            delete_doc("food_items", {"_id": fid})
            flash("Food item deleted.", "info")
    return redirect(url_for("manager.menu"))


# --------------------------- Categories (embedded in the canteen doc) ---------------------------
@manager_bp.route("/categories", methods=["GET", "POST"])
def categories():
    cid = _cid()
    canteen = find_one("canteens", {"_id": cid})
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            if any(c["name"].lower() == name.lower() for c in canteen.get("categories", [])):
                flash("That category already exists.", "warning")
            else:
                new_cat = {"id": next_id("category"), "name": name, "sort": 99}
                get_db()["canteens"].update_one({"_id": cid}, {"$push": {"categories": new_cat}})
                flash("Category added.", "success")
        return redirect(url_for("manager.categories"))

    cats = sorted(canteen.get("categories", []), key=lambda c: c["sort"])
    for c in cats:
        c["item_count"] = count("food_items", {"category_id": c["id"]})
    return render_template("manager/categories.html", categories=cats)


@manager_bp.route("/categories/<int:catid>/delete", methods=["POST"])
def delete_category(catid):
    cid = _cid()
    if count("food_items", {"canteen_id": cid, "category_id": catid}):
        flash("Cannot delete a category that still has food items.", "warning")
    else:
        get_db()["canteens"].update_one({"_id": cid}, {"$pull": {"categories": {"id": catid}}})
        flash("Category removed.", "info")
    return redirect(url_for("manager.categories"))


# --------------------------- Staff ---------------------------
@manager_bp.route("/staff")
def staff():
    cid = _cid()
    rows = find("users", {"role": "canteen_staff", "canteen_id": cid}, sort=[("full_name", 1)])
    for r in rows:
        r["position"] = r.get("position", "Order Staff")
        r["status"] = r.get("staff_status", "Active")
    return render_template("manager/staff.html", staff=rows)


@manager_bp.route("/staff/<int:sid>/toggle", methods=["POST"])
def toggle_staff(sid):
    cid = _cid()
    member = find_one("users", {"_id": sid, "role": "canteen_staff", "canteen_id": cid})
    if member:
        new = "Inactive" if member.get("staff_status", "Active") == "Active" else "Active"
        update_doc("users", {"_id": sid}, {"staff_status": new})
        flash("Staff status updated.", "info")
    return redirect(url_for("manager.staff"))


# --------------------------- Orders (monitor) ---------------------------
@manager_bp.route("/orders")
def orders():
    cid = _cid()
    tab = request.args.get("tab", "all")
    filters = {
        "all": None, "pending": ["Pending"], "preparing": ["Accepted", "Preparing"],
        "ready": ["Ready for Pickup", "Rider Assigned", "Picked Up", "On the Way"],
        "completed": ["Delivered"], "cancelled": ["Cancelled", "Rejected"],
    }
    filt = {"canteen_id": cid}
    if filters.get(tab):
        filt["status_name"] = {"$in": filters[tab]}
    rows = find("orders", filt, sort=[("_id", -1)])
    return render_template("manager/orders.html", orders=rows, tab=tab)


# --------------------------- Reports ---------------------------
@manager_bp.route("/reports")
def reports():
    cid = _cid()
    orders = _canteen_orders(cid)
    rng = request.args.get("range", "weekly")
    if rng == "monthly":
        labels, values = _monthly_series(orders)
    else:
        rng = "weekly"
        labels, values = _sales_series(orders, days=7)

    valid = [o for o in orders if o["status_name"] not in ("Cancelled", "Rejected")]
    orders_count = len(orders)
    total_sales = sum(o["total"] for o in valid)
    aov = (total_sales / orders_count) if orders_count else 0

    agg = {}
    for o in orders:
        for it in o["items"]:
            a = agg.setdefault(it["item_name"], {"item_name": it["item_name"], "q": 0, "revenue": 0})
            a["q"] += it["quantity"]
            a["revenue"] += it["line_total"]
    popular = sorted(agg.values(), key=lambda a: a["q"], reverse=True)[:6]
    return render_template("manager/reports.html", rng=rng, chart_labels=labels, chart_values=values,
                           orders_count=orders_count, total_sales=total_sales, aov=aov, popular=popular)


def _monthly_series(orders):
    valid = [o for o in orders if o["status_name"] not in ("Cancelled", "Rejected")]
    bucket = {}
    for o in valid:
        key = o["placed_at"].strftime("%Y-%m")
        bucket[key] = bucket.get(key, 0) + o["total"]
    labels, values = [], []
    today = date.today()
    for i in range(5, -1, -1):
        month = today.month - i
        yr = today.year
        while month <= 0:
            month += 12
            yr -= 1
        key = "%04d-%02d" % (yr, month)
        labels.append(date(yr, month, 1).strftime("%b"))
        values.append(bucket.get(key, 0))
    return labels, values


# --------------------------- Reviews ---------------------------
@manager_bp.route("/reviews")
def reviews():
    cid = _cid()
    rows = find("reviews", {"canteen_id": cid}, sort=[("_id", -1)])
    for r in rows:
        u = find_one("users", {"_id": r["customer_id"]})
        o = find_one("orders", {"_id": r["order_id"]})
        r["customer_name"] = u["full_name"] if u else "Customer"
        r["order_number"] = o["order_number"] if o else ""
    c = len(rows)
    avg_val = round(sum(r["canteen_rating"] for r in rows) / c, 1) if c else 0
    avg = {"r": avg_val, "c": c}
    dist = {i: sum(1 for r in rows if r["canteen_rating"] == i) for i in range(5, 0, -1)}
    return render_template("manager/reviews.html", reviews=rows, avg=avg, dist=dist)


# --------------------------- Settings ---------------------------
@manager_bp.route("/settings", methods=["GET", "POST"])
def settings():
    cid = _cid()
    canteen = find_one("canteens", {"_id": cid})
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        contact = request.form.get("contact", "").strip()
        opening = request.form.get("opening_time") or "09:00"
        closing = request.form.get("closing_time") or "22:00"
        is_open = bool(request.form.get("is_open"))
        if not name:
            flash("Canteen name is required.", "danger")
            return render_template("manager/settings.html", canteen=canteen)
        update_doc("canteens", {"_id": cid}, {
            "name": name, "description": description, "contact": contact,
            "opening_time": opening, "closing_time": closing, "is_open": is_open,
        })
        flash("Canteen settings saved.", "success")
        return redirect(url_for("manager.settings"))
    return render_template("manager/settings.html", canteen=canteen)


@manager_bp.route("/profile")
def profile():
    user = find_one("users", {"_id": session["user_id"]})
    canteen = find_one("canteens", {"_id": _cid()})
    return render_template("manager/profile.html", user=user, canteen=canteen)
