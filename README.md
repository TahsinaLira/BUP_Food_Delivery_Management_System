# BUP Food Delivery Management System

A university **Web Technology** project for **Bangladesh University of Professionals (BUP)** —
a closed-campus food ordering & delivery platform.

**Stack:** HTML5 · CSS3 · **Bootstrap 5** (CSS framework) · **Vue.js** (JavaScript framework) ·
**Python Flask** (backend framework) · **MongoDB** (NoSQL database) · Jinja2 · Flask Sessions ·
Werkzeug password hashing · Chart.js.

Five roles share **one** login system: **Customer, Canteen Order Staff, Canteen Manager,
Rider, System Admin**.

---

## 1. Folder structure

```
bup_food_delivery/
├── app.py                  # entry point: creates the Flask app, registers blueprints
├── config.py               # all settings (MongoDB URI, delivery fee, etc.)
├── db.py                   # tiny PyMongo helper (find/insert/update + next_id)
├── helpers.py              # money(), status badges, OTP, cart-in-session helpers
├── auth_helpers.py         # login_required / role_required decorators
├── requirements.txt        # Python dependencies
├── seed_mongo.py           # creates the MongoDB database + loads all sample data
├── README.md               # this file
├── routes/                 # one file per role/area
│   ├── __init__.py
│   ├── auth.py             # login / register / logout
│   ├── customer.py         # browse, cart, checkout, orders, reviews, complaints, profile
│   ├── staff.py            # order processing workflow
│   ├── manager.py          # menu, categories, staff, reports, reviews, settings
│   ├── rider.py            # deliveries, pickup, OTP confirmation, history
│   └── admin.py            # users, canteens, riders, locations, complaints, reports
├── templates/              # Jinja2 templates (reusable base layouts + per-page)
│   ├── base.html           # public + customer layout (navbar)
│   ├── dashboard_base.html # sidebar layout (staff / manager / admin)
│   ├── rider_base.html     # mobile layout (rider)
│   ├── partials/           # flash messages, reusable order card
│   ├── auth/  customer/  staff/  manager/  rider/  admin/  errors/
└── static/
    ├── css/style.css       # custom theme on top of Bootstrap
    ├── js/main.js          # flash auto-dismiss + star rating picker
    ├── js/vue.global.prod.js  # Vue.js framework (bundled locally, works offline)
    └── images/             # put food/canteen images here (optional)
```

---

## 2. Requirements (`requirements.txt`)

```
Flask==3.0.3
pymongo==4.8.0
Werkzeug==3.0.3
python-dotenv==1.0.1
```

Bootstrap 5, Bootstrap Icons and Chart.js load from a CDN. **Vue.js is bundled locally**
in `static/js/`, so the menu page works even with no internet.

---

## 3. MongoDB setup (NoSQL database)

1. Install **MongoDB Community Server** (free): https://www.mongodb.com/try/download/community
   During install, also tick **MongoDB Compass** (a visual tool to see your data).
   Make sure the MongoDB service is running (it starts automatically on Windows).

2. Load all the sample data (5 canteens, menus, accounts) by running the seed once:

   ```bash
   python seed_mongo.py
   ```

   This creates a database called **`bup_food_delivery`** with these collections:
   `users`, `canteens` (categories embedded), `food_items`, `delivery_locations`,
   `order_statuses`, and `counters`. Re-running it resets everything to a clean state.
   Orders, reviews and complaints start empty — you create them live through the website.

3. `config.py` already points at a local MongoDB (`mongodb://localhost:27017`), so there is
   **no password to set**. (Using MongoDB Atlas instead? Put your connection string in `.env`
   as `MONGO_URI=...`.)

---

## 4. Windows setup & running the app

```powershell
# 1. Open the project folder in a terminal (PowerShell / CMD)
cd bup_food_delivery

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1
#   (if PowerShell blocks it: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)

# 3. Install the Python packages
pip install -r requirements.txt

# 4. Load the database (run once; needs MongoDB running)
python seed_mongo.py

# 5. Run the app
python app.py
```

Then open your browser at **http://127.0.0.1:5000/**

> **macOS / Linux** is the same, except activate the venv with `source venv/bin/activate`.

---

## 5. Sample login accounts

All accounts use the password: **`password123`**

| Role            | Email                   | Manages / Notes             |
|-----------------|-------------------------|-----------------------------|
| System Admin    | admin@bup.edu.bd        | full platform control       |
| Canteen Manager | vista@bup.edu.bd        | manages **Vista Café**      |
| Canteen Manager | amite@bup.edu.bd        | manages **Amite Café**      |
| Canteen Manager | thirdplace@bup.edu.bd   | manages **Third Place**     |
| Canteen Manager | pitstop@bup.edu.bd      | manages **Pitstop**         |
| Canteen Manager | alcave@bup.edu.bd       | manages **Alcave Café**     |
| Order Staff     | vistastaff@bup.edu.bd   | Vista Café counter          |
| Order Staff     | amitestaff@bup.edu.bd   | Amite Café counter          |
| Order Staff     | thirdplacestaff@bup.edu.bd | Third Place counter      |
| Order Staff     | pitstopstaff@bup.edu.bd | Pitstop counter             |
| Order Staff     | alcavestaff@bup.edu.bd  | Alcave Café counter         |
| Rider           | rider01@bup.edu.bd      | Available                   |
| Rider           | rider02@bup.edu.bd      | Available                   |

No customers are seeded — register a brand-new customer from the **Register** page
and create all orders live through the website.

---

## 6. Canteens (seeded)

All five canteens are **active** and have a full menu loaded.
**Juice Corner is a section inside Vista Café** (its own *Juices* and *Shakes & Coffee*
categories on Vista's menu), not a separate canteen.

| Canteen        | Campus       | Manager login          |
|----------------|--------------|------------------------|
| Vista Café     | East Campus  | vista@bup.edu.bd       |
| Amite Café     | East Campus  | amite@bup.edu.bd       |
| Third Place    | East Campus  | thirdplace@bup.edu.bd  |
| Pitstop        | West Campus  | pitstop@bup.edu.bd     |
| Alcave Café    | West Campus  | alcave@bup.edu.bd      |

Each manager can edit their own canteen's menu and prices from *Manager → Menu*.

---

## 7. Order workflow

```
Pending → Accepted → Preparing → Ready for Pickup → Rider Assigned
        → Picked Up → On the Way → Delivered
also: Rejected, Cancelled
```

Every status change is saved in `order_status_history` **with a timestamp**.
Delivery is only completed after the rider enters the customer's **4-digit OTP**.

---

## 8. Key business rules (all enforced in the backend)

- Orders only from **active + open** canteens (West Campus canteen is blocked).
- **Unavailable** food cannot be added to the cart.
- A cart holds food from **one canteen** only.
- A customer can **cancel** only before *Preparing*.
- A **review** is possible only after *Delivered*.
- Delivery location must be a **predefined** location (no room numbers).
- **Prices/totals** are always recalculated on the server.
- All SQL uses **parameterized queries** (safe from SQL injection).
- Passwords are stored **hashed** (Werkzeug `pbkdf2:sha256`), never in plain text.

---

## 9. Testing checklist (for your viva)

**Auth**
- [ ] Register a new customer, then log in.
- [ ] Wrong password is rejected; suspended user cannot log in.
- [ ] Each role lands on its own dashboard.
- [ ] Visiting another role's URL redirects you away (role protection).

**Customer**
- [ ] Browse all five canteens; open any one and see its menu by category.
- [ ] Search + filter food by category.
- [ ] Add to cart; try adding from a 2nd canteen → blocked.
- [ ] Try adding an **unavailable** item → blocked.
- [ ] Checkout: pick a delivery location + payment method → order placed.
- [ ] Track order shows the status stepper; OTP appears after a rider is assigned.
- [ ] Cancel a Pending order (allowed); try cancelling a Preparing order (blocked).
- [ ] Reorder a past order; submit a review on a Delivered order; file a complaint.

**Staff** (log in as vistastaff@ … for Vista Café, or pitstopstaff@ … for Pitstop)
- [ ] See new orders for **your** canteen only.
- [ ] Accept → Start Preparing → Mark Ready.
- [ ] After a rider accepts, Confirm Handover.

**Rider** (rider01@bup.edu.bd)
- [ ] Set status Available/Busy/Offline.
- [ ] Accept a *Ready for Pickup* delivery → Confirm Pickup → Start Delivery.
- [ ] Enter a wrong OTP → rejected; enter the correct OTP → Delivered.
      (The OTP is shown to the customer on their order-tracking page.)
- [ ] Delivery history updates.

**Manager** (vista@bup.edu.bd)
- [ ] Dashboard KPIs + sales chart render.
- [ ] Add / edit / delete a food item; toggle availability.
- [ ] Add / remove a category.
- [ ] Reports page (weekly / monthly) with Chart.js.
- [ ] Reviews and canteen settings (open/close) work.

**Admin** (admin@bup.edu.bd)
- [ ] Dashboard KPIs + charts.
- [ ] Suspend / activate a user.
- [ ] Toggle a canteen active/inactive and see it appear/disappear for customers.
- [ ] Add / deactivate a delivery location.
- [ ] Filter all orders; update a complaint status.

---

## 10. Everything is editable

The seed data (users, canteens, menus, locations) lives in **`seed_mongo.py`** (edit + re-run),
and everything can also be changed live from the Manager/Admin dashboards or viewed/edited in
**MongoDB Compass**. App-wide values (delivery fee, currency symbol) are in **`config.py`**.

---

*Web Technology Course Project — prototype for demonstration. No real payment gateway is used;
bKash/Nagad payments are simulated (`Pending / Paid / Failed / Refunded`).*
