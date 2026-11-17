"""
seed_mongo.py  —  Builds the BUP Food Delivery database in MongoDB (NoSQL).

Run once to create the database and load the 5 canteens, their menus and the
staff accounts.  Every account's password is "password123".

    pip install pymongo
    python seed_mongo.py

MongoDB must be running locally (default mongodb://localhost:27017).
"""

from pymongo import MongoClient

# Same hash your SQL version used -> it decodes to the password "password123".
HASH = "pbkdf2:sha256:1000000$0TWCnYFfsRNt0ZMQ$c0ae3870f2dd039cd60bb4033f8bf96e94ee1c101f19fe677c392c06310ade48"

client = MongoClient("mongodb://localhost:27017")
db = client["bup_food_delivery"]          # <-- the database (like CREATE DATABASE)

# Start clean every time we run the seed.
for c in ["users", "canteens", "food_items", "delivery_locations", "order_statuses"]:
    db[c].drop()

# ---------------------------------------------------------------------
# 1) USERS collection
#    In SQL you had a roles table + a join. In MongoDB we just store the
#    role name directly on the user document (no join table needed).
#    Staff/managers also carry their canteen_id so we never need a JOIN.
# ---------------------------------------------------------------------
users = [
    {"_id": 1,  "role": "admin",          "full_name": "System Admin",        "email": "admin@bup.edu.bd",           "phone": "+8801700000000", "password_hash": HASH, "is_active": True},
    {"_id": 2,  "role": "canteen_manager","full_name": "Vista Manager",       "email": "vista@bup.edu.bd",           "phone": "+8801700000002", "password_hash": HASH, "is_active": True, "canteen_id": 1},
    {"_id": 3,  "role": "canteen_manager","full_name": "Amite Manager",       "email": "amite@bup.edu.bd",           "phone": "+8801700000003", "password_hash": HASH, "is_active": True, "canteen_id": 2},
    {"_id": 4,  "role": "canteen_manager","full_name": "Third Place Manager", "email": "thirdplace@bup.edu.bd",      "phone": "+8801700000004", "password_hash": HASH, "is_active": True, "canteen_id": 3},
    {"_id": 5,  "role": "canteen_manager","full_name": "Pitstop Manager",     "email": "pitstop@bup.edu.bd",         "phone": "+8801700000005", "password_hash": HASH, "is_active": True, "canteen_id": 4},
    {"_id": 6,  "role": "canteen_manager","full_name": "Alcave Manager",      "email": "alcave@bup.edu.bd",          "phone": "+8801700000006", "password_hash": HASH, "is_active": True, "canteen_id": 5},
    {"_id": 7,  "role": "canteen_staff",  "full_name": "Vista Staff",         "email": "vistastaff@bup.edu.bd",      "phone": "+8801700000007", "password_hash": HASH, "is_active": True, "canteen_id": 1},
    {"_id": 8,  "role": "canteen_staff",  "full_name": "Amite Staff",         "email": "amitestaff@bup.edu.bd",      "phone": "+8801700000008", "password_hash": HASH, "is_active": True, "canteen_id": 2},
    {"_id": 9,  "role": "canteen_staff",  "full_name": "Third Place Staff",   "email": "thirdplacestaff@bup.edu.bd", "phone": "+8801700000009", "password_hash": HASH, "is_active": True, "canteen_id": 3},
    {"_id": 10, "role": "canteen_staff",  "full_name": "Pitstop Staff",       "email": "pitstopstaff@bup.edu.bd",    "phone": "+8801700000010", "password_hash": HASH, "is_active": True, "canteen_id": 4},
    {"_id": 11, "role": "canteen_staff",  "full_name": "Alcave Staff",        "email": "alcavestaff@bup.edu.bd",     "phone": "+8801700000011", "password_hash": HASH, "is_active": True, "canteen_id": 5},
    {"_id": 12, "role": "rider",          "full_name": "Rider01",             "email": "rider01@bup.edu.bd",         "phone": "+8801700000012", "password_hash": HASH, "is_active": True, "rider_status": "Available"},
    {"_id": 13, "role": "rider",          "full_name": "Rider02",             "email": "rider02@bup.edu.bd",         "phone": "+8801700000013", "password_hash": HASH, "is_active": True, "rider_status": "Available"},
]
# Give every staff member a position + status (used on the manager's Staff page).
for u in users:
    if u["role"] == "canteen_staff":
        u["position"] = "Order Staff"
        u["staff_status"] = "Active"
db.users.insert_many(users)

# ---------------------------------------------------------------------
# 2) CANTEENS collection
#    Each canteen document EMBEDS its own category list (an array).
#    This is the NoSQL idea: related data that is always read together
#    lives inside the same document instead of in a separate table.
# ---------------------------------------------------------------------
canteens = [
    {"_id": 1, "name": "Vista Café",   "campus": "East Campus", "description": "Breakfast, rice meals, fast food, snacks & the in-house Juice Corner.",
     "is_active": True, "is_open": True, "status_label": "Active", "contact": "+8801711000001", "manager_id": 2, "image": None,
     "categories": [
        {"id": 1, "name": "Breakfast", "sort": 1},
        {"id": 2, "name": "Rice & Meals", "sort": 2},
        {"id": 3, "name": "Fast Food & Snacks", "sort": 3},
        {"id": 4, "name": "Juices", "sort": 4},
        {"id": 5, "name": "Shakes & Coffee", "sort": 5}]},
    {"_id": 2, "name": "Amite Café",   "campus": "East Campus", "description": "Breakfast, rice meals, snacks & fast food.",
     "is_active": True, "is_open": True, "status_label": "Active", "contact": "+8801711000002", "manager_id": 3, "image": None,
     "categories": [
        {"id": 6, "name": "Breakfast & Snacks", "sort": 1},
        {"id": 7, "name": "Rice & Meals", "sort": 2},
        {"id": 8, "name": "Fast Food", "sort": 3}]},
    {"_id": 3, "name": "Third Place",  "campus": "East Campus", "description": "Breakfast, lunch, tea-break snacks & ice cream.",
     "is_active": True, "is_open": True, "status_label": "Active", "contact": "+8801711000003", "manager_id": 4, "image": None,
     "categories": [
        {"id": 9,  "name": "Breakfast", "sort": 1},
        {"id": 10, "name": "Lunch", "sort": 2},
        {"id": 11, "name": "Tea Break", "sort": 3},
        {"id": 12, "name": "Ice Cream", "sort": 4}]},
    {"_id": 4, "name": "Pitstop",      "campus": "West Campus", "description": "Pizza, fried chicken, Chinese & fast food.",
     "is_active": True, "is_open": True, "status_label": "Active", "contact": "+8801711000004", "manager_id": 5, "image": None,
     "categories": [
        {"id": 13, "name": "Main Menu", "sort": 1}]},
    {"_id": 5, "name": "Alcave Café",  "campus": "West Campus", "description": "Coffee, flavoured drinks & fresh bakery items.",
     "is_active": True, "is_open": True, "status_label": "Active", "contact": "+8801711000005", "manager_id": 6, "image": None,
     "categories": [
        {"id": 14, "name": "Coffee", "sort": 1},
        {"id": 15, "name": "Flavoured Drinks", "sort": 2},
        {"id": 16, "name": "Bakery / New Items", "sort": 3}]},
]
for c in canteens:                    # opening/closing times shown on the menu page
    c["opening_time"] = "09:00"
    c["closing_time"] = "22:00"
db.canteens.insert_many(canteens)

# ---------------------------------------------------------------------
# 3) FOOD_ITEMS collection
#    Kept as its own collection (managers add/edit items a lot, and the
#    cart refers to an item by its id). Each item REFERENCES its canteen
#    and category by id — this is the "referencing" style (vs embedding).
# ---------------------------------------------------------------------
# (canteen_id, category_id, name, price)
raw_items = [
    (1,1,"Paratha",10),(1,1,"Daal",15),(1,1,"Shobji",15),(1,1,"Vorta Item",15),
    (1,2,"Rice",10),(1,2,"Khichuri",30),(1,2,"Dim Khichuri",40),(1,2,"Fried Rice",80),
    (1,2,"Chicken Fry",50),(1,2,"Biriyani",70),(1,2,"Chicken Curry",50),(1,2,"Dim Bhuna",25),
    (1,3,"Sandwich",40),(1,3,"Chowmin",40),(1,3,"Pasta",40),(1,3,"Hot Dog",30),
    (1,3,"Chicken Shawarma",40),(1,3,"Alur Chop",10),(1,3,"Dim Chop",20),(1,3,"Burger",50),
    (1,3,"Chola Bhuna",20),(1,3,"Butter Bun",15),(1,3,"Chicken Wings",30),(1,3,"Wedges",30),
    (1,3,"Chinese Vegetable",30),(1,3,"Jhalmuri",30),(1,3,"Doi Chira",90),(1,3,"Chicken Kabab",50),
    (1,3,"Fuchka",40),
    (1,4,"Lemon Mint",40),(1,4,"Papaya Juice",70),(1,4,"Watermelon Juice",70),
    (1,4,"Mango Smoothie",100),(1,4,"Strawberry Smoothie",100),(1,4,"Lacchi",70),
    (1,5,"Cold Coffee",80),(1,5,"Oreo Shake",120),(1,5,"Mango Milkshake",100),
    (1,5,"Chocolate Milkshake",100),(1,5,"Banana Milkshake",90),(1,5,"Kitkat Milkshake",120),
    (1,5,"Strawberry Milkshake",100),
    (2,6,"Porota",10),(2,6,"Dal / Bhaji",15),(2,6,"Fried Egg",20),(2,6,"Singara",10),
    (2,6,"Samosa",10),(2,6,"Puri",5),(2,6,"Vorta Item",15),(2,6,"Potato Chop",10),(2,6,"Slice Cake",10),
    (2,7,"Rice",10),(2,7,"Rui Fish",80),(2,7,"Egg Bhuna",25),(2,7,"Broiler Chicken",50),
    (2,7,"Small Fish",30),(2,7,"Khichuri",30),(2,7,"Chicken Tehari",70),(2,7,"Morog Polao",130),
    (2,7,"Egg Polao",60),
    (2,8,"Sandwich",40),(2,8,"Chicken Shawarma",50),(2,8,"Meat Box",100),(2,8,"Chicken Ball",25),
    (2,8,"Vegetable Roll",20),(2,8,"Jhal Patties",30),(2,8,"Tikka Burger",50),(2,8,"Chola",15),
    (2,8,"Pizza",30),(2,8,"Wedges",30),(2,8,"Butter Bun",10),
    (3,9,"Porota",10),(3,9,"Dal-Bhaji",15),(3,9,"Egg Omelette",18),
    (3,9,"Bou-Rani Rice (Trivuja Vorta)",50),(3,9,"Egg Khichuri",50),(3,9,"Chicken Khichuri",70),(3,9,"Chola",15),
    (3,10,"Plain Rice",10),(3,10,"Rice + Beef + Dal",150),(3,10,"Chicken Curry",50),(3,10,"Egg Bhuna",25),
    (3,10,"Morog Polao",150),(3,10,"Fried Rice + Chili Chicken + Chicken Fry",150),
    (3,10,"Spicy Tehari (Broiler)",70),(3,10,"Beef Tehari",140),(3,10,"Koi Fish",60),(3,10,"Trivuja Vorta",25),
    (3,11,"Chotpoti",35),(3,11,"Vel Puri",25),(3,11,"Mini Singara",3),(3,11,"Bombai Chili Singara",10),
    (3,11,"Junior Burger",50),(3,11,"Burger Clash",80),(3,11,"Dal Puri",10),(3,11,"Alu Puri",5),
    (3,11,"French Fry",30),(3,11,"Wedges",35),(3,11,"Chicken Lollipop",30),(3,11,"Chicken Wing",30),
    (3,11,"Chicken Shawarma",100),(3,11,"Jhal Muri",30),
    (3,12,"Carnival Hazelnut Cone",70),(3,12,"Carnival Butterscotch Cone",60),(3,12,"Choco Delight Cone",60),
    (3,12,"Robusto",100),(3,12,"Rocks / Crunchy",70),(3,12,"Choco Bar",40),(3,12,"Polar Tornado",30),
    (3,12,"Savoy Discone",100),(3,12,"Savoy Chocolate Fudge",85),(3,12,"Savoy Kheer Malai",75),
    (3,12,"Savoy Shahi Kheer",80),(3,12,"Savoy Caramel",75),(3,12,"Polar Ice Lollie",30),
    (4,13,"Hot Dog",90),(4,13,"Chicken Pizza",110),(4,13,"Margharita Pizza",90),
    (4,13,"Crispy Fried Chicken",90),(4,13,"Naga Fried Chicken",100),(4,13,"Chicken Shawarma",100),
    (4,13,"Fried Rice",60),(4,13,"Chicken Manchurian",110),(4,13,"Chicken Chilli",110),
    (4,13,"Beef Chilli Dry",130),(4,13,"Sauteed Vegetables",30),(4,13,"Chicken Bun",70),
    (4,13,"French Fries",60),(4,13,"Hakka Noodles",80),(4,13,"Pineapple / Papaya Juice",70),
    (5,14,"Espresso",70),(5,14,"Americano",90),(5,14,"Cappuccino",110),(5,14,"Latte",130),
    (5,15,"Hazelnut Latte",150),(5,15,"Caramel Latte",150),(5,15,"Dark Chocolate Mocha",170),
    (5,15,"Hazelnut Cappuccino",150),(5,15,"Caramel Cappuccino",150),
    (5,16,"Brownie",70),(5,16,"Choco Chip Cookie",80),(5,16,"Biscoff Cookie",80),
]
# category id -> name, so each item also stores a readable category label
cat_name = {c["id"]: c["name"] for ca in canteens for c in ca["categories"]}
food_items = []
for i, (cid, catid, name, price) in enumerate(raw_items, start=1):
    food_items.append({
        "_id": i,
        "canteen_id": cid,
        "category_id": catid,
        "category_name": cat_name[catid],
        "name": name,
        "description": "",
        "price": price,
        "is_available": True,
        "image": None,
        "rating": 0.0,
    })
db.food_items.insert_many(food_items)

# ---------------------------------------------------------------------
# 4) DELIVERY_LOCATIONS collection
# ---------------------------------------------------------------------
db.delivery_locations.insert_many([
    {"_id": 1, "name": "East Campus",  "campus": "East Campus", "is_active": True},
    {"_id": 2, "name": "West Campus",  "campus": "West Campus", "is_active": True},
    {"_id": 3, "name": "Boys' Hostel", "campus": "Hostel",      "is_active": True},
    {"_id": 4, "name": "Girls' Hostel","campus": "Hostel",      "is_active": True},
])

# ---------------------------------------------------------------------
# 5) ORDER_STATUSES — the fixed workflow steps
# ---------------------------------------------------------------------
db.order_statuses.insert_many([
    {"_id": i+1, "name": n, "sort": i+1} for i, n in enumerate(
        ["Pending","Accepted","Preparing","Ready for Pickup","Rider Assigned",
         "Picked Up","On the Way","Delivered","Rejected","Cancelled"])
])

# ---------------------------------------------------------------------
# 6) COUNTERS — give new records (register, orders, etc.) the next integer id.
#    next_id() in db.py increments these, mimicking SQL AUTO_INCREMENT.
# ---------------------------------------------------------------------
db.counters.drop()
db.counters.insert_many([
    {"_id": "users", "seq": len(users)},               # next new user id = 14
    {"_id": "food_items", "seq": len(food_items)},      # next new food id = 143
    {"_id": "category", "seq": 16},                     # 16 categories already used
    {"_id": "delivery_locations", "seq": 4},
    {"_id": "orders", "seq": 0},
    {"_id": "reviews", "seq": 0},
    {"_id": "complaints", "seq": 0},
])

# Orders / reviews / complaints are created live through the website, so we
# seed none — same "clean start" as your SQL version.

print("Seed complete.")
print("  users:            ", db.users.count_documents({}))
print("  canteens:         ", db.canteens.count_documents({}))
print("  food_items:       ", db.food_items.count_documents({}))
print("  delivery_locations:", db.delivery_locations.count_documents({}))
print("  order_statuses:   ", db.order_statuses.count_documents({}))
