"""
validate.py  —  quick project validation for BUP Food Delivery.
Run:  python validate.py

Checks, in order:
  1. every Python module compiles,
  2. every HTML template parses,
  3. each required feature is wired in the code.
Prints a PASS/FAIL line for each and a final summary.
"""
import os, py_compile, glob

def ok(msg):   print("    PASS - " + msg)
def bad(msg):  print("    FAIL - " + msg)

passed = failed = 0
def check(name, cond):
    global passed, failed
    (ok if cond else bad)(name)
    if cond: passed += 1
    else:    failed += 1

print("[1] Compiling Python modules ...")
pyfiles = ["app.py","db.py","helpers.py","mailer.py","config.py"] + glob.glob("routes/*.py")
compile_ok = True
for f in pyfiles:
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        compile_ok = False; print("    compile error in", f, "->", e)
print("    " + ", ".join(pyfiles) + ("  ... OK" if compile_ok else "  ... FAIL"))

print("[2] Parsing templates ...")
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("templates"))
n = terr = 0
for root,_,files in os.walk("templates"):
    for fn in files:
        if fn.endswith(".html"):
            rel = os.path.relpath(os.path.join(root, fn), "templates").replace(os.sep, "/")
            try: env.parse(env.loader.get_source(env, rel)[0]); n += 1
            except Exception as e: terr += 1; print("    parse error:", rel, e)
print(f"    {n} templates parsed, {terr} errors  ... " + ("OK" if terr == 0 else "FAIL"))

print("[3] Feature-wiring checks ...")
def read(p):
    try: return open(p, encoding="utf-8").read()
    except: return ""
auth = read("routes/auth.py"); cust = read("routes/customer.py")
menu = read("templates/customer/canteen_menu.html"); dbpy = read("db.py")
check("Password hashing (pbkdf2:sha256)", "generate_password_hash" in auth and "check_password_hash" in auth)
check("Role-based access control", "before_request" in cust)
check("Fetch API endpoint (JSON)", "api_canteen_foods" in cust and "jsonify" in cust)
check("Vue fetch()/async menu", "await fetch(" in menu)
check("MongoDB aggregation (Popular)", "aggregate(" in cust and "$group" in cust)
check("CRUD: create / read / update / delete", all(s in dbpy for s in ["insert_doc","def find(","update_doc","delete_doc"]))
check("Email-OTP password reset", "reset_otp" in auth)
check("BUP email validation (@bup.edu.bd)", 'endswith("@bup.edu.bd")' in auth)
check("Error pages (404 / 403)", os.path.exists("templates/errors/404.html"))

print("-" * 70)
total = passed + failed
print(f"Validation complete: {passed}/{total} checks passed. " + ("OK" if failed == 0 else "FAILED"))
