"""
routes/customer.py  (MongoDB version)
-------------------------------------
Everything the customer can do: browse, cart, checkout, ordering,
tracking, history, reviews, complaints and profile.

Business rules enforced here:
  * Only order from active AND open canteens.
  * Unavailable food cannot be added.
  * A cart can hold food from ONE canteen only.
  * Cancel allowed only before "Preparing" (i.e. while Pending/Accepted).
  * Review only after "Delivered".
  * Delivery location must be one of the predefined locations.
  * All prices/totals are calculated on the backend.
"""
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session, jsonify)
from db import (find, find_one, insert_doc, update_doc, count, next_id,
                advance_order, aggregate)
from helpers import get_cart, save_cart, clear_cart, generate_otp
from config import Config

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")


@customer_bp.before_request
def only_customers():
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=request.path))
    if session.get("role") != "customer":
        flash("This area is for customers only.", "danger")
        return redirect(url_for("auth.home_redirect"))


# --------------------------- Browse ---------------------------
def popular_items(canteen_id, limit=6):
    """Most-ordered AVAILABLE items in one canteen, ranked by real order quantity.

    We look at every order for this canteen (skipping cancelled/rejected ones),
    unwind their embedded items, sum the quantity per food item, and keep the
    top few. Returns [] when the canteen has no orders yet, so the section
    simply doesn't appear until real demand exists (nothing is hardcoded)."""
    rows = aggregate("orders", [
        {"$match": {"canteen_id": canteen_id,
                    "status_name": {"$nin": ["Cancelled", "Rejected"]}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.food_item_id",
                    "qty": {"$sum": "$items.quantity"}}},
        {"$sort": {"qty": -1}},
        {"$limit": limit},
    ])
    items = []
    for row in rows:
        food = find_one("food_items", {"_id": row["_id"], "is_available": True})
        if food:
            food["order_count"] = row["qty"]
            items.append(food)
    return items


@customer_bp.route("/home")
def home():
    canteens = find("canteens", sort=[("is_active", -1), ("name", 1)])
    return render_template("customer/home.html", canteens=canteens)


@customer_bp.route("/canteens")
def canteens():
    q = request.args.get("q", "").strip()
    rows = find("canteens", sort=[("is_active", -1), ("campus", 1), ("name", 1)])
    if q:
        ql = q.lower()
        # canteens that sell a food item matching the search term
        food_matches = find("food_items", {"name": {"$regex": q, "$options": "i"}})
        ids_with_food = {f["canteen_id"] for f in food_matches}
        rows = [c for c in rows
                if ql in c["name"].lower()
                or ql in (c.get("description", "") or "").lower()
                or c["_id"] in ids_with_food]
    return render_template("customer/canteens.html", canteens=rows, q=q)


@customer_bp.route("/canteen/<int:cid>")
def canteen_menu(cid):
    canteen = find_one("canteens", {"_id": cid})
    if not canteen:
        flash("Canteen not found.", "danger")
        return redirect(url_for("customer.canteens"))

    q = request.args.get("q", "").strip()
    category_id = request.args.get("category", "").strip()

    filt = {"canteen_id": cid}
    if q:
        filt["name"] = {"$regex": q, "$options": "i"}   # case-insensitive "LIKE"
    if category_id.isdigit():
        filt["category_id"] = int(category_id)
    foods = find("food_items", filt)

    # Sort by the canteen's category order, then by food name.
    categories = sorted(canteen.get("categories", []), key=lambda c: c["sort"])
    order = {c["id"]: c["sort"] for c in categories}
    foods.sort(key=lambda f: (order.get(f["category_id"], 99), f["name"]))

    reviews = find("reviews", {"canteen_id": cid})
    avg = round(sum(r["canteen_rating"] for r in reviews) / len(reviews), 1) if reviews else 0
    popular = popular_items(cid, limit=6)
    return render_template("customer/canteen_menu.html", canteen=canteen, foods=foods,
                           categories=categories, q=q, category_id=category_id,
                           avg_rating=avg, popular=popular)


# --------- JSON API: the Vue.js menu fetches this asynchronously (Fetch API) ---------
@customer_bp.route("/api/canteen/<int:cid>/foods")
def api_canteen_foods(cid):
    """Return a canteen's food items as JSON. The Vue.js menu page calls this
    with the browser Fetch API (async/await) instead of embedding data in HTML."""
    canteen = find_one("canteens", {"_id": cid})
    if not canteen:
        return jsonify({"error": "Canteen not found"}), 404
    foods = find("food_items", {"canteen_id": cid})
    categories = sorted(canteen.get("categories", []), key=lambda c: c["sort"])
    order = {c["id"]: c["sort"] for c in categories}
    foods.sort(key=lambda f: (order.get(f["category_id"], 99), f["name"]))
    return jsonify({
        "foods": [{"id": f["_id"], "name": f["name"], "price": f["price"],
                   "description": f.get("description", ""), "image": f.get("image"),
                   "rating": f.get("rating", 0), "category_id": f["category_id"],
                   "is_available": f.get("is_available", True)} for f in foods],
        "categories": [{"id": c["id"], "name": c["name"]} for c in categories],
    })



@customer_bp.route("/food/<int:fid>")
def food_details(fid):
    food = find_one("food_items", {"_id": fid})
    if not food:
        flash("Food item not found.", "danger")
        return redirect(url_for("customer.canteens"))
    canteen = find_one("canteens", {"_id": food["canteen_id"]})
    food["canteen_name"] = canteen["name"] if canteen else ""
    food["is_active"] = canteen.get("is_active") if canteen else False
    food["is_open"] = canteen.get("is_open") if canteen else False
    return render_template("customer/food_details.html", food=food)


# --------------------------- Cart ---------------------------
def _cart_details():
    """Return (items_with_food, subtotal). Each item = food doc + qty + line_total."""
    cart = get_cart()
    detailed, subtotal = [], 0
    for it in cart["items"]:
        food = find_one("food_items", {"_id": it["food_id"]})
        if not food:
            continue
        line = float(food["price"]) * it["qty"]
        subtotal += line
        detailed.append({"food": food, "qty": it["qty"], "line_total": line})
    return detailed, subtotal


@customer_bp.route("/cart")
def cart():
    items, subtotal = _cart_details()
    cart = get_cart()
    canteen = find_one("canteens", {"_id": cart["canteen_id"]}) if cart["canteen_id"] else None
    fee = Config.DELIVERY_FEE if items else 0
    return render_template("customer/cart.html", items=items, subtotal=subtotal,
                           fee=fee, total=subtotal + fee, canteen=canteen)


@customer_bp.route("/cart/add", methods=["POST"])
def cart_add():
    fid = request.form.get("food_id", type=int)
    qty = request.form.get("qty", default=1, type=int)
    qty = max(1, qty or 1)

    food = find_one("food_items", {"_id": fid})
    if not food:
        flash("Food item not found.", "danger")
        return redirect(url_for("customer.canteens"))
    canteen = find_one("canteens", {"_id": food["canteen_id"]})
    if not canteen or not canteen.get("is_active") or not canteen.get("is_open"):
        flash((canteen["name"] if canteen else "This canteen") + " is not accepting orders right now.", "warning")
        return redirect(url_for("customer.canteen_menu", cid=food["canteen_id"]))
    if not food.get("is_available"):
        flash("That item is currently unavailable.", "warning")
        return redirect(url_for("customer.canteen_menu", cid=food["canteen_id"]))

    cart = get_cart()
    if cart["canteen_id"] and cart["canteen_id"] != food["canteen_id"]:
        flash("Your cart already has items from another canteen. Clear it first.", "warning")
        return redirect(url_for("customer.cart"))

    cart["canteen_id"] = food["canteen_id"]
    for it in cart["items"]:
        if it["food_id"] == fid:
            it["qty"] += qty
            break
    else:
        cart["items"].append({"food_id": fid, "qty": qty})
    save_cart(cart)
    flash(food["name"] + " added to cart.", "success")
    return redirect(request.form.get("next") or url_for("customer.canteen_menu", cid=food["canteen_id"]))


@customer_bp.route("/cart/update", methods=["POST"])
def cart_update():
    fid = request.form.get("food_id", type=int)
    qty = request.form.get("qty", type=int)
    cart = get_cart()
    for it in list(cart["items"]):
        if it["food_id"] == fid:
            if qty and qty > 0:
                it["qty"] = qty
            else:
                cart["items"].remove(it)
    if not cart["items"]:
        cart["canteen_id"] = None
    save_cart(cart)
    return redirect(url_for("customer.cart"))


@customer_bp.route("/cart/remove", methods=["POST"])
def cart_remove():
    fid = request.form.get("food_id", type=int)
    cart = get_cart()
    cart["items"] = [it for it in cart["items"] if it["food_id"] != fid]
    if not cart["items"]:
        cart["canteen_id"] = None
    save_cart(cart)
    flash("Item removed from cart.", "info")
    return redirect(url_for("customer.cart"))


@customer_bp.route("/cart/clear", methods=["POST"])
def cart_clear():
    clear_cart()
    flash("Cart cleared.", "info")
    return redirect(url_for("customer.cart"))


# --------------------------- Checkout ---------------------------
@customer_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, subtotal = _cart_details()
    cart = get_cart()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("customer.canteens"))

    canteen = find_one("canteens", {"_id": cart["canteen_id"]})
    if not canteen or not canteen.get("is_active") or not canteen.get("is_open"):
        flash("This canteen is not accepting orders right now.", "danger")
        return redirect(url_for("customer.cart"))

    locations = find("delivery_locations", {"is_active": True}, sort=[("_id", 1)])
    fee = Config.DELIVERY_FEE
    payment_methods = ["Cash on Delivery", "bKash", "Nagad"]

    if request.method == "POST":
        location_id = request.form.get("location_id", type=int)
        payment_method = request.form.get("payment_method", "Cash on Delivery")
        instructions = request.form.get("instructions", "").strip()

        loc = find_one("delivery_locations", {"_id": location_id, "is_active": True})
        if not loc:
            flash("Please choose a valid delivery location.", "danger")
            return render_template("customer/checkout.html", items=items, subtotal=subtotal,
                                   fee=fee, total=subtotal + fee, canteen=canteen,
                                   locations=locations, payment_methods=payment_methods)
        if payment_method not in payment_methods:
            flash("Please choose a valid payment method.", "danger")
            return render_template("customer/checkout.html", items=items, subtotal=subtotal,
                                   fee=fee, total=subtotal + fee, canteen=canteen,
                                   locations=locations, payment_methods=payment_methods)

        total = subtotal + fee
        otp = generate_otp()
        me = find_one("users", {"_id": session["user_id"]})
        oid = next_id("orders")
        order_number = "BUP" + str(1042 + oid)
        pay_status = "Pending" if payment_method == "Cash on Delivery" else "Paid"
        ref = None if payment_method == "Cash on Delivery" else payment_method.upper() + "-SIM-" + str(oid)

        # ONE order document holds items + status history + payment (all embedded).
        insert_doc("orders", {
            "_id": oid,
            "order_number": order_number,
            "customer_id": session["user_id"],
            "customer_name": me["full_name"],
            "customer_phone": me.get("phone", ""),
            "canteen_id": canteen["_id"],
            "canteen_name": canteen["name"],
            "delivery_location_id": loc["_id"],
            "location_name": loc["name"],
            "status_name": "Pending",
            "rider_id": None,
            "rider_name": None,
            "rider_phone": None,
            "payment_method": payment_method,
            "special_instructions": instructions,
            "subtotal": subtotal,
            "delivery_fee": fee,
            "total": total,
            "otp": otp,
            "placed_at": datetime.now(),
            "items": [{"food_item_id": d["food"]["_id"], "item_name": d["food"]["name"],
                       "unit_price": d["food"]["price"], "quantity": d["qty"],
                       "line_total": d["line_total"]} for d in items],
            "history": [{"status_name": "Pending", "note": "Order placed",
                         "created_at": datetime.now()}],
            "payment": {"method": payment_method, "amount": total,
                        "status": pay_status, "transaction_ref": ref},
        })
        clear_cart()
        return redirect(url_for("customer.order_confirmation", oid=oid))

    return render_template("customer/checkout.html", items=items, subtotal=subtotal,
                           fee=fee, total=subtotal + fee, canteen=canteen,
                           locations=locations, payment_methods=payment_methods)


# --------------------------- Orders ---------------------------
def _get_order(oid, own=True):
    order = find_one("orders", {"_id": oid})
    if not order:
        return None
    if own and order["customer_id"] != session["user_id"]:
        return None
    return order


@customer_bp.route("/order/<int:oid>/confirmation")
def order_confirmation(oid):
    order = _get_order(oid)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("customer.my_orders"))
    return render_template("customer/order_confirmation.html", order=order, items=order["items"])


@customer_bp.route("/order/<int:oid>/track")
def order_tracking(oid):
    order = _get_order(oid)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("customer.my_orders"))
    return render_template("customer/order_tracking.html", order=order,
                           items=order["items"], history=order["history"])


@customer_bp.route("/order/<int:oid>")
def order_details(oid):
    order = _get_order(oid)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("customer.my_orders"))
    review = find_one("reviews", {"order_id": oid})
    return render_template("customer/order_details.html", order=order, items=order["items"],
                           history=order["history"], payment=order["payment"], review=review)


@customer_bp.route("/my-orders")
def my_orders():
    tab = request.args.get("tab", "active")
    active_states = ("Pending", "Accepted", "Preparing", "Ready for Pickup",
                     "Rider Assigned", "Picked Up", "On the Way")
    orders = find("orders", {"customer_id": session["user_id"]}, sort=[("_id", -1)])
    if tab == "completed":
        orders = [o for o in orders if o["status_name"] == "Delivered"]
    elif tab == "cancelled":
        orders = [o for o in orders if o["status_name"] in ("Cancelled", "Rejected")]
    else:
        tab = "active"
        orders = [o for o in orders if o["status_name"] in active_states]
    return render_template("customer/my_orders.html", orders=orders, tab=tab)


@customer_bp.route("/order/<int:oid>/cancel", methods=["POST"])
def cancel_order(oid):
    order = _get_order(oid)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("customer.my_orders"))
    if order["status_name"] not in ("Pending", "Accepted"):
        flash("This order can no longer be cancelled.", "warning")
        return redirect(url_for("customer.order_tracking", oid=oid))
    advance_order(oid, "Cancelled", "Cancelled by customer")
    if order["payment"]["status"] == "Pending":
        update_doc("orders", {"_id": oid}, {"payment.status": "Failed"})
    flash("Order cancelled.", "info")
    return redirect(url_for("customer.my_orders"))


@customer_bp.route("/order/<int:oid>/reorder", methods=["POST"])
def reorder(oid):
    order = _get_order(oid)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("customer.my_orders"))
    cart = {"canteen_id": order["canteen_id"], "items": []}
    for it in order["items"]:
        cart["items"].append({"food_id": it["food_item_id"], "qty": it["quantity"]})
    save_cart(cart)
    flash("Items added to your cart.", "success")
    return redirect(url_for("customer.cart"))


@customer_bp.route("/order/<int:oid>/review", methods=["GET", "POST"])
def review(oid):
    order = _get_order(oid)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("customer.my_orders"))
    if order["status_name"] != "Delivered":
        flash("You can only review delivered orders.", "warning")
        return redirect(url_for("customer.order_details", oid=oid))
    if find_one("reviews", {"order_id": oid}):
        flash("You have already reviewed this order.", "info")
        return redirect(url_for("customer.order_details", oid=oid))

    if request.method == "POST":
        food_r = request.form.get("food_rating", type=int) or 5
        canteen_r = request.form.get("canteen_rating", type=int) or 5
        delivery_r = request.form.get("delivery_rating", type=int) or 5
        comment = request.form.get("comment", "").strip()
        for r in (food_r, canteen_r, delivery_r):
            if r < 1 or r > 5:
                flash("Ratings must be between 1 and 5.", "danger")
                return render_template("customer/review.html", order=order)
        insert_doc("reviews", {
            "_id": next_id("reviews"),
            "order_id": oid,
            "customer_id": session["user_id"],
            "canteen_id": order["canteen_id"],
            "food_rating": food_r, "canteen_rating": canteen_r, "delivery_rating": delivery_r,
            "comment": comment, "created_at": datetime.now(),
        })
        flash("Thank you for your review!", "success")
        return redirect(url_for("customer.order_details", oid=oid))

    return render_template("customer/review.html", order=order)


@customer_bp.route("/complaint", methods=["GET", "POST"])
def complaint():
    my_orders_list = find("orders", {"customer_id": session["user_id"]}, sort=[("_id", -1)])
    categories = ["Missing item", "Wrong item", "Food quality", "Late delivery",
                  "Rider issue", "Payment issue", "Other"]
    if request.method == "POST":
        category = request.form.get("category", "Other")
        description = request.form.get("description", "").strip()
        order_id = request.form.get("order_id", type=int)
        if not description:
            flash("Please describe the problem.", "danger")
            return render_template("customer/complaint.html", orders=my_orders_list, categories=categories)
        cid = next_id("complaints")
        ticket = "CMP-" + str(100 + cid)
        order_doc = find_one("orders", {"_id": order_id}) if order_id else None
        me = find_one("users", {"_id": session["user_id"]})
        insert_doc("complaints", {
            "_id": cid, "ticket_no": ticket,
            "customer_id": session["user_id"], "customer_name": me["full_name"],
            "order_id": order_id if order_id else None,
            "order_number": order_doc["order_number"] if order_doc else None,
            "category": category, "description": description,
            "status": "Open", "created_at": datetime.now(),
        })
        flash("Complaint submitted. Ticket " + ticket + ".", "success")
        return redirect(url_for("customer.my_orders"))
    return render_template("customer/complaint.html", orders=my_orders_list, categories=categories)


# --------------------------- Profile ---------------------------
def _profile_view(user):
    """Build the 'profile' dict the template expects from the user document."""
    loc = find_one("delivery_locations", {"_id": user.get("default_location_id")}) \
        if user.get("default_location_id") else None
    return {
        "bup_id": user.get("bup_id", ""),
        "user_type": user.get("user_type", "Student"),
        "campus": user.get("campus", ""),
        "hostel_resident": user.get("hostel_resident", False),
        "default_location_id": user.get("default_location_id"),
        "location_name": loc["name"] if loc else None,
    }


@customer_bp.route("/profile")
def profile():
    user = find_one("users", {"_id": session["user_id"]})
    return render_template("customer/profile.html", user=user, profile=_profile_view(user))


@customer_bp.route("/profile/edit", methods=["GET", "POST"])
def edit_profile():
    user = find_one("users", {"_id": session["user_id"]})
    locations = find("delivery_locations", {"is_active": True}, sort=[("_id", 1)])
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        user_type = request.form.get("user_type", "Student")
        campus = request.form.get("campus", "East Campus")
        default_location_id = request.form.get("default_location_id", type=int)
        hostel = bool(request.form.get("hostel_resident"))
        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("customer/edit_profile.html", user=user,
                                   profile=_profile_view(user), locations=locations)
        update_doc("users", {"_id": session["user_id"]}, {
            "full_name": full_name, "phone": phone, "user_type": user_type,
            "campus": campus, "hostel_resident": hostel,
            "default_location_id": default_location_id or None,
        })
        session["full_name"] = full_name
        flash("Profile updated.", "success")
        return redirect(url_for("customer.profile"))
    return render_template("customer/edit_profile.html", user=user,
                           profile=_profile_view(user), locations=locations)