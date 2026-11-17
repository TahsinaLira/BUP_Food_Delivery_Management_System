"""Set each canteen's banner image in MongoDB. Run once:  python set_images.py
(Place vista.jpg, amite.jpg, thirdplace.jpg, pitstop.jpg, alcove.jpg in static/images first.)"""
from pymongo import MongoClient
db = MongoClient("mongodb://localhost:27017")["bup_food_delivery"]
mapping = {
    "Vista Café":  "vista.jpg",
    "Amite Café":  "amite.jpg",
    "Third Place": "thirdplace.jpg",
    "Pitstop":     "pitstop.jpg",
    "Alcave Café": "alcove.jpg",
}
for name, img in mapping.items():
    r = db.canteens.update_one({"name": name}, {"$set": {"image": img}})
    print(f"{name:14} -> {img}   {'updated' if r.matched_count else 'NOT FOUND'}")
print("Done. Refresh the website to see the canteen photos.")
