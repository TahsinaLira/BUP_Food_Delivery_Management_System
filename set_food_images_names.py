"""
set_food_images_names.py  —  link each food item to its photo file.
Run it whenever you add more photos (you can run it many times):
    python set_food_images_names.py

It names a file after the item (e.g. "Chicken Tehari" -> chicken-tehari.jpg) and
ONLY sets the photo if that file actually exists in static/images. Items whose
photo you haven't made yet keep showing the plain icon (no broken images).
"""
import os, re
from pymongo import MongoClient

db = MongoClient("mongodb://localhost:27017")["bup_food_delivery"]
IMG_DIR = os.path.join("static", "images")


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


have, missing = 0, 0
for f in db.food_items.find():
    fn = slug(f["name"]) + ".jpg"
    if os.path.exists(os.path.join(IMG_DIR, fn)):
        db.food_items.update_one({"_id": f["_id"]}, {"$set": {"image": fn}})
        have += 1
    else:
        db.food_items.update_one({"_id": f["_id"]}, {"$set": {"image": None}})
        missing += 1

print(f"Linked photos for {have} items. {missing} items have no photo yet (they show the icon).")
print("Add more photos to static/images and run this again anytime.")
