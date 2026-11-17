"""
db.py  —  MongoDB (NoSQL) data layer using PyMongo.
Replaces the old MySQL / PyMySQL version.

Why these small helpers?
  In SQL we wrote query_db("SELECT ...") and execute_db("INSERT ...").
  With MongoDB there is no SQL — we work with collections of JSON-like
  documents. These helpers keep the route code short and readable:

    get_db()                        -> the MongoDB database object
    next_id(name)                   -> next auto-increment integer id (like AUTO_INCREMENT)
    find_one(coll, filt)            -> one document (or None)
    find(coll, filt, sort, limit)   -> list of documents
    insert_doc(coll, doc)           -> insert one document
    update_doc(coll, filt, changes) -> update fields ($set)
    delete_doc(coll, filt)          -> delete one document
    count(coll, filt)               -> number of matching documents
    advance_order(oid, status, note)-> move an order to a new status + log history

  Every document returned also gets an `id` field copied from `_id`, so the
  Jinja templates that use `.id` keep working unchanged.
"""
from datetime import datetime
from flask import current_app
from pymongo import MongoClient, ReturnDocument

_client = None


def _db():
    """Return the MongoDB database (one shared client for the whole app)."""
    global _client
    if _client is None:
        _client = MongoClient(current_app.config["MONGO_URI"])
    return _client[current_app.config["MONGO_DB"]]


def get_db():
    return _db()


def close_db(e=None):
    # PyMongo keeps its own connection pool, so there is nothing to close per request.
    pass


def _pub(doc):
    """Copy _id -> id so templates that use `.id` keep working."""
    if doc is not None and "id" not in doc and "_id" in doc:
        doc["id"] = doc["_id"]
    return doc


def next_id(name):
    """Return the next integer id for a collection (mimics SQL AUTO_INCREMENT)."""
    doc = _db().counters.find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}},
        upsert=True, return_document=ReturnDocument.AFTER)
    return doc["seq"]


def find_one(coll, filt=None):
    return _pub(_db()[coll].find_one(filt or {}))


def find(coll, filt=None, sort=None, limit=None):
    cur = _db()[coll].find(filt or {})
    if sort:
        cur = cur.sort(sort)
    if limit:
        cur = cur.limit(limit)
    return [_pub(d) for d in cur]


def insert_doc(coll, doc):
    _db()[coll].insert_one(doc)
    return doc.get("_id")


def update_doc(coll, filt, changes):
    _db()[coll].update_one(filt, {"$set": changes})


def delete_doc(coll, filt):
    _db()[coll].delete_one(filt)


def count(coll, filt=None):
    return _db()[coll].count_documents(filt or {})


def aggregate(coll, pipeline):
    """Run an aggregation pipeline (group / sum / sort) and return the rows.

    Used for things plain find() can't do — e.g. counting how many times each
    food item was ordered (group by food_item_id, sum the quantities)."""
    return list(_db()[coll].aggregate(pipeline))


def advance_order(oid, new_status, note):
    """Set an order's status and append an entry to its embedded history array."""
    _db()["orders"].update_one(
        {"_id": oid},
        {"$set": {"status_name": new_status},
         "$push": {"history": {"status_name": new_status, "note": note,
                               "created_at": datetime.now()}}},
    )