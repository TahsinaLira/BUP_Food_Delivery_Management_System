"""
config.py
---------
All configuration values live here so you can edit them in one place.

Secrets (like your database URI) are read from a `.env` file that is NOT
uploaded to GitHub. Copy `.env.example` to `.env` and adjust if needed.
"""
import os

# Load variables from a local .env file if python-dotenv is installed.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    # Secret key signs the Flask session cookie.
    SECRET_KEY = os.environ.get("SECRET_KEY", "bup-food-delivery-secret-key-change-me")

    # ---- MongoDB (NoSQL) connection settings ----
    # Local MongoDB runs on this address by default. No username/password needed
    # for a default local install. Put a different URI in your .env if you use Atlas.
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB = os.environ.get("MONGO_DB", "bup_food_delivery")

    # ---- App business settings (editable) ----
    DELIVERY_FEE = 20          # flat delivery fee in BDT
    CURRENCY = "৳"
    PASSWORD_HASH_METHOD = "pbkdf2:sha256"

    # ---- Email (SMTP) settings for the password-reset OTP ----
    # Leave blank to run in DEV MODE (the OTP is printed in the terminal).
    # To send real email (e.g. Mailtrap), fill these in your .env (see .env.example).
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    OTP_VALIDITY_MINUTES = 10
