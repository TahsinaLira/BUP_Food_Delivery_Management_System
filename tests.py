"""
tests.py  —  automated test cases for the BUP Food Delivery app.
Run:   python tests.py

These tests use `mongomock`, an in-memory fake MongoDB, so they run WITHOUT
touching your real database. Install it once if needed:
    pip install mongomock

What is tested (11 cases):
  1. Password hashing (security)          5. Register rejects non-BUP email
  2. next_id auto-increment counter        6. Register accepts a BUP email
  3. insert + find round-trip (CRUD)       7. JSON API endpoint returns data (Fetch API)
  4. 'Popular' aggregation by order count   8. Login page loads

If every test prints OK, the core logic works.
"""
import unittest
import mongomock
from werkzeug.security import generate_password_hash, check_password_hash

import db as dbmod

# ---- Point the whole app at a fake in-memory MongoDB (not the real one) ----
_mock_client = mongomock.MongoClient()
dbmod._db = lambda: _mock_client["bup_food_delivery_test"]

from app import create_app
from db import next_id, insert_doc, find_one, find
from routes.customer import popular_items


def seed():
    """Put a little sample data into the fake database before each test."""
    db = dbmod._db()
    for name in db.list_collection_names():
        db[name].delete_many({})
    db.canteens.insert_one({
        "_id": 1, "name": "Vista", "description": "x", "campus": "East",
        "is_active": True, "is_open": True, "status_label": "Open",
        "opening_time": "8", "closing_time": "20", "image": "vista.jpg",
        "categories": [{"id": 10, "name": "Coffee", "sort": 1}],
    })
    db.food_items.insert_many([
        {"_id": 100, "canteen_id": 1, "category_id": 10, "category_name": "Coffee",
         "name": "Latte", "description": "hot", "price": 120, "is_available": True,
         "image": "latte.jpg", "rating": 0.0},
        {"_id": 101, "canteen_id": 1, "category_id": 10, "category_name": "Coffee",
         "name": "Espresso", "description": "strong", "price": 90, "is_available": True,
         "image": None, "rating": 0.0},
    ])
    db.counters.insert_one({"_id": "orders", "seq": 0})


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        seed()

    def test_password_hashing(self):
        """Passwords must be hashed, never stored as plain text."""
        h = generate_password_hash("password123", method="pbkdf2:sha256")
        self.assertNotEqual(h, "password123")           # not plain text
        self.assertTrue(check_password_hash(h, "password123"))   # correct password passes
        self.assertFalse(check_password_hash(h, "wrongpass"))    # wrong password fails

    def test_next_id_increments(self):
        """next_id() should give 1, 2, 3 ... like SQL AUTO_INCREMENT."""
        self.assertEqual(next_id("widgets"), 1)
        self.assertEqual(next_id("widgets"), 2)
        self.assertEqual(next_id("widgets"), 3)

    def test_insert_and_find(self):
        """CRUD: a document we insert can be read back."""
        insert_doc("food_items", {"_id": 200, "canteen_id": 1, "category_id": 10,
                                  "name": "Mocha", "price": 150, "is_available": True})
        doc = find_one("food_items", {"_id": 200})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["name"], "Mocha")

    def test_popular_items_by_orders(self):
        """'Popular' ranks items by real order quantity, not randomly."""
        db = dbmod._db()
        db.orders.insert_one({"_id": 1, "canteen_id": 1, "status_name": "Delivered",
                              "items": [{"food_item_id": 100, "quantity": 5},
                                        {"food_item_id": 101, "quantity": 2}]})
        pop = popular_items(1, limit=6)
        self.assertEqual(pop[0]["name"], "Latte")       # 5 ordered -> first
        self.assertEqual(pop[0]["order_count"], 5)


class RouteTests(unittest.TestCase):
    def setUp(self):
        seed()
        self.app = create_app()
        # Force DEV MODE for tests (no real SMTP) so they run offline & deterministically.
        self.app.config["SMTP_HOST"] = ""
        self.app.config["SMTP_USER"] = ""
        self.app.config["SMTP_PASS"] = ""
        self.client = self.app.test_client()

    def _login_customer(self):
        with self.client.session_transaction() as s:
            s["user_id"] = 999
            s["role"] = "customer"
            s["full_name"] = "Tester"

    def test_login_page_loads(self):
        """The login page should load (HTTP 200)."""
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)

    def test_register_rejects_non_bup_email(self):
        """A non-BUP email must be refused."""
        r = self.client.post("/register", data={
            "full_name": "Test", "bup_id": "123", "email": "test@gmail.com",
            "password": "password123", "confirm": "password123",
            "user_type": "Student", "campus": "East Campus",
        }, follow_redirects=True)
        self.assertIn("BUP email", r.get_data(as_text=True))

    def test_register_accepts_bup_email(self):
        """A valid @bup.edu.bd email should create an account."""
        r = self.client.post("/register", data={
            "full_name": "Test", "bup_id": "123", "email": "newuser@bup.edu.bd",
            "password": "password123", "confirm": "password123",
            "user_type": "Student", "campus": "East Campus",
        }, follow_redirects=True)
        self.assertIsNotNone(find_one("users", {"email": "newuser@bup.edu.bd"}))

    def test_json_api_returns_foods(self):
        """The Fetch API endpoint must return the canteen's foods as JSON."""
        self._login_customer()
        r = self.client.get("/customer/api/canteen/1/foods")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, "application/json")
        data = r.get_json()
        self.assertEqual(len(data["foods"]), 2)
        self.assertEqual(data["foods"][0]["name"], "Espresso")  # sorted by name

    def _make_reset_user(self):
        from werkzeug.security import generate_password_hash
        dbmod._db().users.insert_one({
            "_id": 500, "role": "customer", "full_name": "Lira",
            "email": "lira@bup.edu.bd", "phone": "+8801711111111",
            "password_hash": generate_password_hash("password123", method="pbkdf2:sha256"),
            "is_active": True})

    def test_forgot_password_page_loads(self):
        """The forgot-password page should load (HTTP 200)."""
        self.assertEqual(self.client.get("/forgot-password").status_code, 200)

    def test_forgot_password_sends_otp(self):
        """Requesting a reset must generate and store a 6-digit OTP."""
        self._make_reset_user()
        self.client.post("/forgot-password", data={"email": "lira@bup.edu.bd"})
        u = find_one("users", {"_id": 500})
        self.assertIsNotNone(u.get("reset_otp"))
        self.assertEqual(len(u["reset_otp"]), 6)

    def test_wrong_otp_refused(self):
        """A wrong OTP must NOT reset the password (security)."""
        from werkzeug.security import check_password_hash
        self._make_reset_user()
        self.client.post("/forgot-password", data={"email": "lira@bup.edu.bd"})
        self.client.post("/verify-otp", data={
            "otp": "000000", "new_password": "hacked123", "confirm": "hacked123"})
        u = find_one("users", {"_id": 500})
        self.assertTrue(check_password_hash(u["password_hash"], "password123"))   # unchanged
        self.assertFalse(check_password_hash(u["password_hash"], "hacked123"))    # attacker failed

    def test_correct_otp_resets_password(self):
        """The real OTP from the email must reset the password and then be cleared."""
        from werkzeug.security import check_password_hash
        self._make_reset_user()
        self.client.post("/forgot-password", data={"email": "lira@bup.edu.bd"})
        otp = find_one("users", {"_id": 500})["reset_otp"]   # read the generated code
        self.client.post("/verify-otp", data={
            "otp": otp, "new_password": "brandnew1", "confirm": "brandnew1"})
        u = find_one("users", {"_id": 500})
        self.assertTrue(check_password_hash(u["password_hash"], "brandnew1"))
        self.assertIsNone(u.get("reset_otp"))   # OTP cleared after use



if __name__ == "__main__":
    unittest.main(verbosity=2)