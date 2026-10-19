from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import sqlite3, secrets, string, os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "savanna.db")
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.secret_key = os.environ.get("SAVANNA_SECRET", "CHANGE-ME-IN-PRODUCTION")

DEFAULT_PACKAGES = {
    "Daily": (700, 24),
    "Weekly": (4500, 24 * 7),
    "Monthly": (15000, 24 * 30),
}

PORTAL_TEXT = {
    "en": {
        "connected": "Get connected",
        "choose_access": "Choose how you want to access the internet.",
        "have_voucher": "I have a voucher",
        "voucher_caption": "Enter your code to connect",
        "buy_package": "Buy a package",
        "buy_caption": "Choose a plan for your device",
        "back": "Back",
        "voucher_heading": "Connect with a voucher",
        "voucher_details": "Enter your voucher and device details.",
        "voucher_code": "Voucher code",
        "device_id": "Device ID",
        "device_placeholder": "Your device identifier",
        "connect": "Connect to internet",
        "packages_heading": "Choose a package",
        "packages_details": "Select the plan that works for you.",
        "hours": "{hours} hours of access",
        "select_package": "Select package",
        "no_packages": "No packages are available right now.",
        "phone_heading": "Enter your number",
        "payment_prompt": "We’ll use this number for the payment prompt.",
        "phone_number": "Phone number",
        "phone_placeholder": "e.g. +255 7XX XXX XXX",
        "continue_payment": "Continue to payment",
        "all_packages": "All packages",
        "invalid_package": "That package is no longer available. Please choose another.",
        "phone_required": "Enter your phone number to continue.",
        "checkout_unavailable": "Mobile payment checkout is not configured yet. Your number was not submitted and you were not charged.",
        "choose_available": "Choose an available package to continue.",
        "voucher_required": "Voucher code and device ID are required.",
        "invalid_voucher": "Invalid voucher code.",
        "voucher_not_active": "Voucher exists but has not been activated yet.",
        "voucher_expired": "Voucher has expired.",
        "voucher_device_mismatch": "Access denied: voucher is already bound to another device.",
        "voucher_inactive": "This voucher cannot be used.",
        "voucher_success": "Access granted. Savanna authentication successful.",
    },
    "sw": {
        "connected": "Unganisha kwenye intaneti",
        "choose_access": "Chagua jinsi unavyotaka kupata huduma ya intaneti.",
        "have_voucher": "Nina vocha",
        "voucher_caption": "Ingiza msimbo wako ili uunganishe",
        "buy_package": "Nunua kifurushi",
        "buy_caption": "Chagua kifurushi cha kifaa chako",
        "back": "Rudi",
        "voucher_heading": "Unganisha kwa kutumia vocha",
        "voucher_details": "Ingiza vocha na taarifa za kifaa chako.",
        "voucher_code": "Msimbo wa vocha",
        "device_id": "Kitambulisho cha kifaa",
        "device_placeholder": "Kitambulisho cha kifaa chako",
        "connect": "Unganisha kwenye intaneti",
        "packages_heading": "Chagua kifurushi",
        "packages_details": "Chagua kifurushi kinachokufaa.",
        "hours": "Saa {hours} za intaneti",
        "select_package": "Chagua kifurushi",
        "no_packages": "Hakuna vifurushi vinavyopatikana kwa sasa.",
        "phone_heading": "Ingiza namba yako",
        "payment_prompt": "Tutatumia namba hii kuanzisha ombi la malipo.",
        "phone_number": "Namba ya simu",
        "phone_placeholder": "Mfano: +255 7XX XXX XXX",
        "continue_payment": "Endelea kulipa",
        "all_packages": "Vifurushi vyote",
        "invalid_package": "Kifurushi hicho hakipatikani tena. Tafadhali chagua kingine.",
        "phone_required": "Ingiza namba yako ya simu ili kuendelea.",
        "checkout_unavailable": "Malipo ya simu bado hayajawezeshwa. Namba yako haikutumwa na hujatozwa.",
        "choose_available": "Chagua kifurushi kinachopatikana ili kuendelea.",
        "voucher_required": "Msimbo wa vocha na kitambulisho cha kifaa vinahitajika.",
        "invalid_voucher": "Msimbo wa vocha si sahihi.",
        "voucher_not_active": "Vocha ipo lakini bado haijawezeshwa.",
        "voucher_expired": "Muda wa vocha umeisha.",
        "voucher_device_mismatch": "Ufikiaji umekataliwa: vocha hii tayari imeunganishwa na kifaa kingine.",
        "voucher_inactive": "Vocha hii haiwezi kutumika.",
        "voucher_success": "Umeunganishwa. Uthibitishaji wa Savanna umefanikiwa.",
    },
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def normalize_role(role):
    if role in (None, "admin", "manager"):
        return "admin"
    if role == "super_admin":
        return "super_admin"
    return role


def now():
    return datetime.now()

def ensure_admin_role_column(conn):
    columns = [row[1] for row in conn.execute("PRAGMA table_info(admins)").fetchall()]
    if "role" not in columns:
        conn.execute("ALTER TABLE admins ADD COLUMN role TEXT NOT NULL DEFAULT 'admin'")


def ensure_sales_payment_method_column(conn):
    columns = [row[1] for row in conn.execute("PRAGMA table_info(sales)").fetchall()]
    if "payment_method" not in columns:
        conn.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'cash'")


def ensure_voucher_customer_phone_column(conn):
    columns = [row[1] for row in conn.execute("PRAGMA table_info(vouchers)").fetchall()]
    if "customer_phone" not in columns:
        conn.execute("ALTER TABLE vouchers ADD COLUMN customer_phone TEXT")


def ensure_gateway_settings_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gateway_settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            router_type TEXT NOT NULL DEFAULT 'simulated',
            router_ip TEXT NOT NULL DEFAULT '192.168.1.1',
            username TEXT,
            password TEXT,
            enabled INTEGER NOT NULL DEFAULT 0,
            last_sync TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    settings = conn.execute("SELECT * FROM gateway_settings WHERE id = 1").fetchone()
    if not settings:
        conn.execute(
            "INSERT INTO gateway_settings(id, router_type, router_ip, username, password, enabled, last_sync, updated_at) VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
            (
                os.environ.get("SAVANNA_ROUTER_TYPE", "simulated"),
                os.environ.get("SAVANNA_ROUTER_IP", "192.168.1.1"),
                os.environ.get("SAVANNA_ROUTER_USER", ""),
                os.environ.get("SAVANNA_ROUTER_PASS", ""),
                0,
                None,
                now().isoformat(timespec="seconds")
            )
        )


def ensure_audit_logs_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(admin_id) REFERENCES admins(id)
        )
    """)


def ensure_network_inventory_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            location TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS network_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            parent_id INTEGER,
            name TEXT NOT NULL,
            device_type TEXT NOT NULL CHECK(device_type IN ('router', 'access_point')),
            vendor TEXT NOT NULL DEFAULT 'MikroTik',
            model TEXT,
            management_address TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY(site_id) REFERENCES sites(id),
            FOREIGN KEY(parent_id) REFERENCES network_devices(id) ON DELETE SET NULL
        );
    """)


def get_gateway_settings(conn=None):
    should_close = conn is None
    conn = conn or get_db()
    settings = conn.execute("SELECT * FROM gateway_settings WHERE id = 1").fetchone()
    if should_close:
        conn.close()
    return dict(settings) if settings else {
        "id": 1,
        "router_type": os.environ.get("SAVANNA_ROUTER_TYPE", "simulated"),
        "router_ip": os.environ.get("SAVANNA_ROUTER_IP", "192.168.1.1"),
        "username": os.environ.get("SAVANNA_ROUTER_USER", ""),
        "password": os.environ.get("SAVANNA_ROUTER_PASS", ""),
        "enabled": 0,
        "last_sync": None,
        "updated_at": now().isoformat(timespec="seconds")
    }


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS packages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        price INTEGER NOT NULL,
        duration_hours INTEGER NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS vouchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        package_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'unused',
        customer_name TEXT,
        device_id TEXT,
        activated_at TEXT,
        expires_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(package_id) REFERENCES packages(id)
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voucher_id INTEGER NOT NULL,
        device_id TEXT NOT NULL,
        ip_address TEXT,
        login_at TEXT NOT NULL,
        logout_at TEXT,
        FOREIGN KEY(voucher_id) REFERENCES vouchers(id)
    );

    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voucher_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        payment_status TEXT NOT NULL DEFAULT 'paid',
        sold_at TEXT NOT NULL,
        FOREIGN KEY(voucher_id) REFERENCES vouchers(id)
    );
    """)

    ensure_admin_role_column(conn)
    ensure_sales_payment_method_column(conn)
    ensure_voucher_customer_phone_column(conn)
    ensure_gateway_settings_table(conn)
    ensure_audit_logs_table(conn)
    ensure_network_inventory_tables(conn)
    if not conn.execute("SELECT id FROM admins LIMIT 1").fetchone():
        conn.execute(
            "INSERT INTO admins(username,password_hash,role,created_at) VALUES (?,?,?,?)",
            ("admin", generate_password_hash("admin123"), "super_admin", now().isoformat(timespec="seconds"))
        )

    for name, (price, hours) in DEFAULT_PACKAGES.items():
        conn.execute(
            "INSERT OR IGNORE INTO packages(name,price,duration_hours) VALUES (?,?,?)",
            (name, price, hours)
        )
    conn.commit()
    conn.close()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "admin_id" not in session:
                return redirect(url_for("login"))
            session_role = normalize_role(session.get("role"))
            allowed = {normalize_role(role) for role in allowed_roles}
            if session_role not in allowed:
                flash("You do not have permission to perform that action.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def record_admin_action(action, details="", admin_id=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_logs(admin_id, action, details, created_at) VALUES (?, ?, ?, ?)",
        (admin_id or session.get("admin_id"), action, details, now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


def make_voucher_code():
    alphabet = string.ascii_uppercase + string.digits
    conn = get_db()
    try:
        while True:
            code = "SVN-" + "".join(secrets.choice(alphabet) for _ in range(4)) + "-" + "".join(secrets.choice(alphabet) for _ in range(4))
            if not conn.execute("SELECT 1 FROM vouchers WHERE code=?", (code,)).fetchone():
                return code
    finally:
        conn.close()

def expire_voucher_if_needed(conn, voucher):
    if voucher and voucher["status"] == "active" and voucher["expires_at"]:
        if datetime.fromisoformat(voucher["expires_at"]) <= now():
            conn.execute("UPDATE vouchers SET status='expired' WHERE id=?", (voucher["id"],))
            conn.commit()
            return True
    return False

@app.route("/")
@admin_required
def dashboard():
    conn = get_db()
    current_role = normalize_role(session.get("role"))
    stats = {
        "active_users": conn.execute(
            "SELECT COUNT(*) n FROM sessions WHERE logout_at IS NULL"
        ).fetchone()["n"],
        "active_vouchers": conn.execute(
            "SELECT COUNT(*) n FROM vouchers WHERE status='active'"
        ).fetchone()["n"],
        "unused_vouchers": conn.execute(
            "SELECT COUNT(*) n FROM vouchers WHERE status='unused'"
        ).fetchone()["n"],
        "revenue": conn.execute(
            "SELECT COALESCE(SUM(amount),0) n FROM sales WHERE payment_status='paid'"
        ).fetchone()["n"],
        "pending_payments": conn.execute(
            "SELECT COUNT(*) n FROM sales WHERE payment_status='partial'"
        ).fetchone()["n"],
        "customers": conn.execute(
            "SELECT COUNT(*) n FROM vouchers WHERE customer_name IS NOT NULL"
        ).fetchone()["n"],
        "expiring_soon": conn.execute(
            "SELECT COUNT(*) n FROM vouchers WHERE status='active' AND expires_at IS NOT NULL AND expires_at <= datetime('now', '+24 hours')"
        ).fetchone()["n"],
    }
    recent = conn.execute("""
        SELECT v.code, p.name package, v.status, v.customer_name, v.device_id, v.expires_at
        FROM vouchers v JOIN packages p ON p.id=v.package_id
        ORDER BY v.id DESC LIMIT 10
    """).fetchall()
    revenue_by_day = {
        row["sale_day"]: row["amount"]
        for row in conn.execute("""
            SELECT date(sold_at) sale_day, SUM(amount) amount
            FROM sales
            WHERE payment_status='paid' AND date(sold_at) >= date('now', '-6 days')
            GROUP BY date(sold_at)
        """).fetchall()
    }
    revenue_days = []
    for day_offset in range(6, -1, -1):
        sale_day = now().date() - timedelta(days=day_offset)
        revenue_days.append({
            "label": sale_day.strftime("%a"),
            "amount": revenue_by_day.get(sale_day.isoformat(), 0),
        })
    peak_revenue = max((day["amount"] for day in revenue_days), default=0)
    for day in revenue_days:
        day["height"] = round(day["amount"] / peak_revenue * 100) if peak_revenue else 0

    role_labels = {
        "super_admin": "Super Admin",
        "admin": "Admin",
        "support": "Support",
        "agent": "Agent",
        "customer_care": "Customer Care",
        "finance": "Finance",
    }
    role_cards = {
        "super_admin": [
            ("Active Sessions", stats["active_users"]),
            ("Active Vouchers", stats["active_vouchers"]),
            ("Revenue", f"{stats['revenue']:,} TSh"),
            ("Gateway Health", "Online"),
        ],
        "admin": [
            ("Active Vouchers", stats["active_vouchers"]),
            ("Unused Vouchers", stats["unused_vouchers"]),
            ("Customers", stats["customers"]),
            ("Revenue", f"{stats['revenue']:,} TSh"),
        ],
        "support": [
            ("Live Sessions", stats["active_users"]),
            ("Expiring Soon", stats["expiring_soon"]),
            ("Active Vouchers", stats["active_vouchers"]),
            ("Open Tickets", "0"),
        ],
        "agent": [
            ("New Activations", stats["customers"]),
            ("Active Vouchers", stats["active_vouchers"]),
            ("Unused Vouchers", stats["unused_vouchers"]),
            ("Sales Today", f"{stats['revenue']:,} TSh"),
        ],
        "customer_care": [
            ("Registered Customers", stats["customers"]),
            ("Active Sessions", stats["active_users"]),
            ("Expiring Soon", stats["expiring_soon"]),
            ("Support Queue", "0"),
        ],
        "finance": [
            ("Gross Revenue", f"{stats['revenue']:,} TSh"),
            ("Pending Payments", stats["pending_payments"]),
            ("Paid Sales", f"{stats['revenue']:,} TSh"),
            ("Collections", "Live"),
        ],
    }
    role_actions = {
        "super_admin": ["Monitor all operations", "Manage router controls", "Review audit trail"],
        "admin": ["Manage packages", "Generate vouchers", "Track coverage"],
        "support": ["Resolve live session issues", "Extend vouchers", "Check customer device binding"],
        "agent": ["Activate vouchers", "Support customers", "Promote packages"],
        "customer_care": ["Answer customer queries", "Check expiry alerts", "Follow up on activations"],
        "finance": ["Review payments", "Check revenue", "Verify collected amounts"],
    }
    role_summary = {
        "super_admin": "Unified visibility across the entire Wi‑Fi business",
        "admin": "Operational control for packages, users, and network health",
        "support": "Live service recovery and customer issue resolution",
        "agent": "Fast activation and customer onboarding workflow",
        "customer_care": "Customer satisfaction, renewals, and retention support",
        "finance": "Revenue tracking, collections, and payment monitoring",
    }
    role_highlights = {
        "super_admin": ["Router sync", "Risk alerts", "Audit trail", "Growth view"],
        "admin": ["Package control", "Voucher health", "Usage trends", "Coverage"],
        "support": ["Live sessions", "Device checks", "Voucher expiry", "Issue routing"],
        "agent": ["Activation speed", "Package upsell", "Customer onboarding", "Sales flow"],
        "customer_care": ["Retention", "Renewals", "Feedback loop", "Customer follow-up"],
        "finance": ["Revenue", "Collections", "Pending payouts", "Payment audit"],
    }
    role_panels = {
        "super_admin": [
            {"title": "Network oversight", "items": ["Monitor router health", "Track live sessions", "Review policy exceptions"]},
            {"title": "Business control", "items": ["Audit all actions", "Compare revenue movement", "Drive growth decisions"]},
        ],
        "admin": [
            {"title": "Operations", "items": ["Manage active packages", "Review voucher stock", "Track customer usage"]},
            {"title": "Coverage", "items": ["Monitor peak demand", "Check service gaps", "Prioritize network actions"]},
        ],
        "support": [
            {"title": "Live service", "items": ["Resolve session drops", "Check device bindings", "Extend expiry where needed"]},
            {"title": "Customer care", "items": ["Answer login complaints", "Review failed activations", "Escalate recurring issues"]},
        ],
        "agent": [
            {"title": "Sales workflow", "items": ["Activate vouchers quickly", "Recommend package tiers", "Handle first-time customers"]},
            {"title": "Conversion", "items": ["Promote popular plans", "Follow-up on purchases", "Increase daily activations"]},
        ],
        "customer_care": [
            {"title": "Retention", "items": ["Review customer renewals", "Check expiring accounts", "Resolve access complaints"]},
            {"title": "Experience", "items": ["Gather feedback", "Track satisfaction", "Follow up on service issues"]},
        ],
        "finance": [
            {"title": "Cashflow", "items": ["Track paid sales", "Monitor pending collections", "Review sales totals"]},
            {"title": "Reconciliation", "items": ["Verify payment records", "Check transaction status", "Prepare performance reports"]},
        ],
    }
    conn.close()
    return render_template(
        "dashboard.html",
        stats=stats,
        recent=recent,
        role=current_role,
        role_label=role_labels.get(current_role, "Admin"),
        role_cards=role_cards.get(current_role, role_cards["admin"]),
        role_actions=role_actions.get(current_role, role_actions["admin"]),
        role_summary=role_summary.get(current_role, role_summary["admin"]),
        role_highlights=role_highlights.get(current_role, role_highlights["admin"]),
        role_panels=role_panels.get(current_role, role_panels["admin"]),
        revenue_days=revenue_days,
        show_revenue_chart=current_role in {"super_admin", "admin", "finance"},
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["username"] = admin["username"]
            session["role"] = normalize_role(admin["role"] if "role" in admin.keys() else "admin")
            record_admin_action("login", f"User {admin['username']} logged in.", admin["id"])
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/account/password", methods=["GET", "POST"])
@admin_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        conn = get_db()
        admin = conn.execute(
            "SELECT password_hash FROM admins WHERE id=?", (session["admin_id"],)
        ).fetchone()

        if not admin or not check_password_hash(admin["password_hash"], current_password):
            conn.close()
            flash("Current password is incorrect.", "danger")
        elif len(new_password) < 8:
            conn.close()
            flash("New password must be at least 8 characters.", "danger")
        elif new_password != confirm_password:
            conn.close()
            flash("New password and confirmation do not match.", "danger")
        elif check_password_hash(admin["password_hash"], new_password):
            conn.close()
            flash("Choose a password different from your current password.", "danger")
        else:
            conn.execute(
                "UPDATE admins SET password_hash=? WHERE id=?",
                (generate_password_hash(new_password), session["admin_id"]),
            )
            conn.commit()
            conn.close()
            record_admin_action("password_changed", "User changed their password.", session["admin_id"])
            flash("Your password has been updated.", "success")
            return redirect(url_for("dashboard"))

    return render_template("change_password.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admins", methods=["GET", "POST"])
@role_required("super_admin")
def admins():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action", "update_role")
        if action == "create":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "").strip()
            valid_roles = {"super_admin", "admin", "support", "agent", "customer_care", "finance"}

            if len(username) < 3 or len(username) > 40:
                flash("Username must be between 3 and 40 characters.", "danger")
            elif len(password) < 8:
                flash("Temporary password must be at least 8 characters.", "danger")
            elif role not in valid_roles:
                flash("Select a valid role.", "danger")
            else:
                try:
                    conn.execute(
                        "INSERT INTO admins(username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                        (username, generate_password_hash(password), role, now().isoformat(timespec="seconds")),
                    )
                    conn.commit()
                    record_admin_action(
                        "admin_created", f"Created account {username} with role {role}.", session.get("admin_id")
                    )
                    flash("Account created. Share the temporary password securely and ask the user to change it after signing in.", "success")
                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash("That username is already in use.", "danger")
            conn.close()
            return redirect(url_for("admins"))

        admin_id = int(request.form.get("admin_id", "0") or 0)
        role = request.form.get("role", "").strip()
        if admin_id and role in {"super_admin", "admin", "support", "agent", "customer_care", "finance"}:
            conn.execute("UPDATE admins SET role=? WHERE id=?", (role, admin_id))
            conn.commit()
            record_admin_action("admin_role_updated", f"Updated admin id {admin_id} to {role}.", session.get("admin_id"))
            flash("Admin role updated.", "success")
        conn.close()
        return redirect(url_for("admins"))

    admin_rows = conn.execute("SELECT id, username, role, created_at FROM admins ORDER BY id").fetchall()
    logs = conn.execute("""
        SELECT a.username, l.action, l.details, l.created_at
        FROM audit_logs l
        LEFT JOIN admins a ON a.id = l.admin_id
        ORDER BY l.id DESC LIMIT 20
    """).fetchall()
    conn.close()
    return render_template("admins.html", admins=admin_rows, logs=logs)

@app.route("/network", methods=["GET", "POST"])
@role_required("super_admin", "admin")
def network_inventory():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create_site":
            name = request.form.get("name", "").strip()
            location = request.form.get("location", "").strip()
            if len(name) < 2 or len(name) > 80:
                flash("Site name must be between 2 and 80 characters.", "danger")
            else:
                try:
                    conn.execute(
                        "INSERT INTO sites(name, location, created_at) VALUES (?, ?, ?)",
                        (name, location, now().isoformat(timespec="seconds")),
                    )
                    conn.commit()
                    record_admin_action("site_created", f"Created site {name}.", session.get("admin_id"))
                    flash("Site added.", "success")
                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash("A site with that name already exists.", "danger")
        elif action == "create_device":
            try:
                site_id = int(request.form.get("site_id", "0"))
                parent_id = int(request.form.get("parent_id", "0") or 0)
            except ValueError:
                site_id, parent_id = 0, 0
            name = request.form.get("name", "").strip()
            device_type = request.form.get("device_type", "").strip()
            vendor = request.form.get("vendor", "MikroTik").strip() or "MikroTik"
            model = request.form.get("model", "").strip()
            management_address = request.form.get("management_address", "").strip()
            site_exists = conn.execute("SELECT 1 FROM sites WHERE id=? AND active=1", (site_id,)).fetchone()
            parent_router = None
            if parent_id:
                parent_router = conn.execute(
                    "SELECT id FROM network_devices WHERE id=? AND site_id=? AND device_type='router' AND active=1",
                    (parent_id, site_id),
                ).fetchone()

            if not site_exists:
                flash("Choose an active site.", "danger")
            elif len(name) < 2 or device_type not in {"router", "access_point"}:
                flash("Enter a device name and a valid device type.", "danger")
            elif parent_id and (device_type != "access_point" or not parent_router):
                flash("An access point can only be linked to an active router at the same site.", "danger")
            else:
                conn.execute("""
                    INSERT INTO network_devices(
                        site_id, parent_id, name, device_type, vendor, model, management_address, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    site_id, parent_id or None, name, device_type, vendor, model, management_address,
                    now().isoformat(timespec="seconds"),
                ))
                conn.commit()
                record_admin_action(
                    "network_device_created", f"Added {device_type} {name} at site id {site_id}.",
                    session.get("admin_id"),
                )
                flash("Network device added to inventory.", "success")
        elif action == "toggle_device":
            try:
                device_id = int(request.form.get("device_id", "0"))
            except ValueError:
                device_id = 0
            device = conn.execute("SELECT active, name FROM network_devices WHERE id=?", (device_id,)).fetchone()
            if device:
                active = 0 if device["active"] else 1
                conn.execute("UPDATE network_devices SET active=? WHERE id=?", (active, device_id))
                conn.commit()
                record_admin_action(
                    "network_device_updated", f"Set {device['name']} active={active}.", session.get("admin_id")
                )
                flash("Device status updated.", "success")
        conn.close()
        return redirect(url_for("network_inventory"))

    sites = conn.execute("SELECT * FROM sites ORDER BY name").fetchall()
    devices = conn.execute("""
        SELECT d.*, s.name site_name, parent.name parent_name
        FROM network_devices d
        JOIN sites s ON s.id=d.site_id
        LEFT JOIN network_devices parent ON parent.id=d.parent_id
        ORDER BY s.name, d.device_type, d.name
    """).fetchall()
    routers = conn.execute("""
        SELECT d.id, d.name, d.site_id, s.name site_name
        FROM network_devices d JOIN sites s ON s.id=d.site_id
        WHERE d.device_type='router' AND d.active=1
        ORDER BY s.name, d.name
    """).fetchall()
    conn.close()
    return render_template("network.html", sites=sites, devices=devices, routers=routers)

@app.route("/integrations")
@role_required("super_admin")
def integrations():
    providers = [
        {
            "name": "Selcom payments",
            "description": "Checkout orders and mobile-money wallet prompts.",
            "configured": all(os.environ.get(key) for key in (
                "SELCOM_BASE_URL", "SELCOM_API_KEY", "SELCOM_API_SECRET", "SELCOM_VENDOR"
            )),
        },
        {
            "name": "Beem SMS",
            "description": "Customer purchase and package-expiry notifications.",
            "configured": all(os.environ.get(key) for key in (
                "BEEM_API_KEY", "BEEM_SECRET_KEY", "BEEM_SOURCE_ADDR"
            )),
        },
    ]
    return render_template("integrations.html", providers=providers)

@app.route("/audit")
@role_required("super_admin", "admin")
def audit():
    conn = get_db()
    logs = conn.execute("""
        SELECT a.username, l.action, l.details, l.created_at
        FROM audit_logs l
        LEFT JOIN admins a ON a.id = l.admin_id
        ORDER BY l.id DESC LIMIT 100
    """).fetchall()
    conn.close()
    return render_template("audit.html", logs=logs)

@app.route("/packages", methods=["GET", "POST"])
@role_required("super_admin", "admin")
def packages():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            price = int(request.form.get("price", "0") or 0)
            duration_hours = int(request.form.get("duration_hours", "0") or 0)
            if not name or price <= 0 or duration_hours <= 0:
                flash("Package name, price, and duration are required.", "danger")
            else:
                conn.execute(
                    "INSERT INTO packages(name, price, duration_hours, active) VALUES (?, ?, ?, 1)",
                    (name, price, duration_hours)
                )
                conn.commit()
                record_admin_action("package_created", f"Created package {name}.", session.get("admin_id"))
                flash("Package added successfully.", "success")
        elif action == "toggle":
            package_id = int(request.form.get("package_id", "0") or 0)
            package = conn.execute("SELECT active FROM packages WHERE id=?", (package_id,)).fetchone()
            if package:
                new_state = 0 if package["active"] else 1
                conn.execute("UPDATE packages SET active=? WHERE id=?", (new_state, package_id))
                conn.commit()
                record_admin_action("package_updated", f"Toggled package id {package_id} to {new_state}.", session.get("admin_id"))
                flash("Package status updated.", "success")
        elif action == "update":
            package_id = int(request.form.get("package_id", "0") or 0)
            name = request.form.get("name", "").strip()
            try:
                price = int(request.form.get("price", "0") or 0)
                duration_hours = int(request.form.get("duration_hours", "0") or 0)
            except ValueError:
                price = 0
                duration_hours = 0

            if not name or price <= 0 or duration_hours <= 0:
                flash("Package name, price, and duration must be valid.", "danger")
                conn.close()
                return redirect(url_for("packages", edit=package_id))

            package = conn.execute("SELECT id FROM packages WHERE id=?", (package_id,)).fetchone()
            duplicate = conn.execute(
                "SELECT id FROM packages WHERE name=? AND id<>?", (name, package_id)
            ).fetchone()
            if not package:
                flash("Package not found.", "danger")
            elif duplicate:
                flash("Another package already uses that name.", "danger")
                conn.close()
                return redirect(url_for("packages", edit=package_id))
            else:
                conn.execute(
                    "UPDATE packages SET name=?, price=?, duration_hours=? WHERE id=?",
                    (name, price, duration_hours, package_id)
                )
                conn.commit()
                record_admin_action("package_updated", f"Updated package {name} (id {package_id}).", session.get("admin_id"))
                flash("Package updated successfully.", "success")
        elif action == "delete":
            package_id = int(request.form.get("package_id", "0") or 0)
            if package_id:
                voucher_count = conn.execute(
                    "SELECT COUNT(*) FROM vouchers WHERE package_id=?", (package_id,)
                ).fetchone()[0]
                if voucher_count:
                    flash(
                        "This package is linked to existing vouchers and cannot be deleted. Disable it to prevent future sales.",
                        "warning",
                    )
                else:
                    conn.execute("DELETE FROM packages WHERE id=?", (package_id,))
                    conn.commit()
                    record_admin_action("package_deleted", f"Deleted package id {package_id}.", session.get("admin_id"))
                    flash("Package deleted.", "success")
        conn.close()
        return redirect(url_for("packages"))

    edit_package_id = request.args.get("edit", type=int)
    edit_package = conn.execute("SELECT * FROM packages WHERE id=?", (edit_package_id,)).fetchone() if edit_package_id else None
    rows = conn.execute("SELECT * FROM packages ORDER BY price").fetchall()
    conn.close()
    return render_template("packages.html", packages=rows, edit_package=edit_package)


@app.route("/vouchers", methods=["GET", "POST"])
@role_required("super_admin", "admin", "support", "agent")
def vouchers():
    conn = get_db()
    if request.method == "POST":
        package_id = int(request.form["package_id"])
        quantity = max(1, min(int(request.form.get("quantity", 1)), 200))
        customer_phone = request.form.get("customer_phone", "").strip()
        if not customer_phone:
            flash("Customer phone number is required.", "danger")
            conn.close()
            return redirect(url_for("vouchers"))
        package = conn.execute("SELECT * FROM packages WHERE id=? AND active=1", (package_id,)).fetchone()
        if not package:
            flash("Invalid package.", "danger")
            conn.close()
            return redirect(url_for("vouchers"))

        for _ in range(quantity):
            code = make_voucher_code()
            conn.execute(
                "INSERT INTO vouchers(code,package_id,status,customer_phone,created_at) VALUES (?,?,?,?,?)",
                (code, package_id, "unused", customer_phone, now().isoformat(timespec="seconds"))
            )
        conn.commit()
        conn.close()
        flash(f"{quantity} voucher(s) generated.", "success")
        return redirect(url_for("vouchers"))

    packages = conn.execute("SELECT * FROM packages WHERE active=1 ORDER BY price").fetchall()
    rows = conn.execute("""
        SELECT v.*, p.name package, p.price
        FROM vouchers v JOIN packages p ON p.id=v.package_id
        ORDER BY v.id DESC
    """).fetchall()
    conn.close()
    return render_template("vouchers.html", vouchers=rows, packages=packages)

@app.route("/vouchers/activate/<int:voucher_id>", methods=["GET", "POST"])
@role_required("super_admin", "admin", "support", "agent")
def activate_voucher(voucher_id):
    conn = get_db()
    voucher = conn.execute("""
        SELECT v.*, p.name package, p.price, p.duration_hours
        FROM vouchers v JOIN packages p ON p.id=v.package_id
        WHERE v.id=?
    """, (voucher_id,)).fetchone()

    if not voucher:
        conn.close()
        flash("Voucher not found.", "danger")
        return redirect(url_for("vouchers"))

    if request.method == "POST":
        if voucher["status"] != "unused":
            conn.close()
            flash("Only unused vouchers can be activated.", "danger")
            return redirect(url_for("vouchers"))

        customer = request.form.get("customer_name", "").strip() or "Walk-in Customer"
        device = request.form.get("device_id", "").strip()
        if not device:
            conn.close()
            flash("Device ID is required.", "danger")
            return redirect(url_for("activate_voucher", voucher_id=voucher_id))

        activated = now()
        expires = activated + timedelta(hours=voucher["duration_hours"])
        payment_method = (request.form.get("payment_method", "cash") or "cash").strip().lower()
        amount_paid = int(request.form.get("amount_paid", voucher["price"]) or voucher["price"])
        payment_status = "paid" if amount_paid >= voucher["price"] else "partial"

        conn.execute("""
            UPDATE vouchers
            SET status='active', customer_name=?, device_id=?, activated_at=?, expires_at=?
            WHERE id=?
        """, (
            customer, device,
            activated.isoformat(timespec="seconds"),
            expires.isoformat(timespec="seconds"),
            voucher_id
        ))
        conn.execute("""
            INSERT INTO sales(voucher_id,amount,payment_method,payment_status,sold_at)
            VALUES (?,?,?,?,?)
        """, (
            voucher_id,
            amount_paid,
            payment_method,
            payment_status,
            activated.isoformat(timespec="seconds")
        ))
        conn.commit()
        conn.close()
        flash("Voucher activated and bound to the device.", "success")
        return redirect(url_for("vouchers"))

    conn.close()
    return render_template("activate.html", voucher=voucher)

@app.route("/customers")
@role_required("super_admin", "admin", "support", "agent", "customer_care")
def customers():
    conn = get_db()
    rows = conn.execute("""
        SELECT v.customer_name, v.device_id, v.code, p.name package,
               v.status, v.activated_at, v.expires_at
        FROM vouchers v JOIN packages p ON p.id=v.package_id
        WHERE v.customer_name IS NOT NULL
        ORDER BY v.id DESC
    """).fetchall()
    conn.close()
    return render_template("customers.html", customers=rows)

@app.route("/sessions")
@role_required("super_admin", "admin", "support", "customer_care")
def session_list():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.id, s.voucher_id, s.device_id, s.ip_address, s.login_at, s.logout_at,
               v.code, v.expires_at
        FROM sessions s JOIN vouchers v ON v.id=s.voucher_id
        ORDER BY s.id DESC LIMIT 200
    """).fetchall()
    conn.close()
    return render_template("sessions.html", sessions=rows)

@app.post("/sessions/<int:session_id>/end")
@role_required("super_admin", "admin", "support")
def end_session(session_id):
    conn = get_db()
    session_row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not session_row:
        conn.close()
        flash("Session not found.", "danger")
        return redirect(url_for("session_list"))

    conn.execute(
        "UPDATE sessions SET logout_at=? WHERE id=? AND logout_at IS NULL",
        (now().isoformat(timespec="seconds"), session_id)
    )
    conn.commit()
    record_admin_action("session_ended", f"Ended session id {session_id}.", session.get("admin_id"))
    conn.close()
    flash("Session ended successfully.", "success")
    return redirect(url_for("session_list"))

@app.post("/sessions/<int:session_id>/extend")
@role_required("super_admin", "admin", "support")
def extend_session(session_id):
    conn = get_db()
    session_row = conn.execute("""
        SELECT s.*, v.expires_at, v.status
        FROM sessions s
        JOIN vouchers v ON v.id=s.voucher_id
        WHERE s.id=?
    """, (session_id,)).fetchone()

    if not session_row:
        conn.close()
        flash("Session not found.", "danger")
        return redirect(url_for("session_list"))

    if session_row["status"] != "active":
        conn.close()
        flash("Only active vouchers can be extended.", "danger")
        return redirect(url_for("session_list"))

    current_expiry = datetime.fromisoformat(session_row["expires_at"]) if session_row["expires_at"] else now()
    new_expiry = current_expiry + timedelta(hours=1)
    conn.execute(
        "UPDATE vouchers SET expires_at=? WHERE id=?",
        (new_expiry.isoformat(timespec="seconds"), session_row["voucher_id"])
    )
    conn.commit()
    record_admin_action("voucher_extended", f"Extended voucher id {session_row['voucher_id']} by 1 hour.", session.get("admin_id"))
    conn.close()
    flash("Voucher extended by 1 hour.", "success")
    return redirect(url_for("session_list"))

@app.route("/sales")
@role_required("super_admin", "admin", "finance")
def sales():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, v.code, p.name package
        FROM sales s
        JOIN vouchers v ON v.id=s.voucher_id
        JOIN packages p ON p.id=v.package_id
        ORDER BY s.id DESC
    """).fetchall()
    total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) n FROM sales WHERE payment_status='paid'"
    ).fetchone()["n"]
    conn.close()
    return render_template("sales.html", sales=rows, total=total)

@app.route("/gateway", methods=["GET", "POST"])
@role_required("super_admin")
def gateway():
    conn = get_db()
    settings = get_gateway_settings(conn)

    if request.method == "POST":
        router_type = (request.form.get("router_type") or settings.get("router_type") or "simulated").strip()
        router_ip = (request.form.get("router_ip") or settings.get("router_ip") or "192.168.1.1").strip()
        username = (request.form.get("username") or settings.get("username") or "").strip()
        password = (request.form.get("password") or settings.get("password") or "").strip()
        enabled = 1 if request.form.get("enabled") == "on" else 0

        conn.execute("""
            UPDATE gateway_settings
            SET router_type=?, router_ip=?, username=?, password=?, enabled=?, updated_at=?
            WHERE id=1
        """, (router_type, router_ip, username, password, enabled, now().isoformat(timespec="seconds")))
        conn.commit()
        record_admin_action("gateway_updated", f"Updated gateway config for {router_type} on {router_ip}.", session.get("admin_id"))
        settings = get_gateway_settings(conn)
        flash("Gateway settings saved successfully.", "success")
        conn.close()
        return redirect(url_for("gateway"))

    conn.close()
    return render_template("gateway.html", settings=settings)

@app.get("/api/v1/gateway/status")
@role_required("super_admin", "admin", "support")
def gateway_status():
    conn = get_db()
    settings = get_gateway_settings(conn)
    conn.close()
    return jsonify({"enabled": bool(settings.get("enabled")), "router_type": settings.get("router_type"), "router_ip": settings.get("router_ip")})

# ---------- Captive portal prototype ----------

@app.route("/portal", methods=["GET", "POST"])
def portal():
    message = None
    language = request.values.get("lang", session.get("portal_language", "en"))
    if language not in PORTAL_TEXT:
        language = "en"
    session["portal_language"] = language
    text = PORTAL_TEXT[language]
    mode = request.args.get("mode", "start")
    if mode not in {"start", "voucher", "packages", "buy"}:
        mode = "start"
    selected_package = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "voucher":
            code = request.form.get("code", "").strip().upper()
            device_id = request.form.get("device_id", "").strip()
            message = authenticate_voucher(code, device_id, request.remote_addr)
            mode = "voucher"
        elif action == "purchase":
            mode = "buy"
            try:
                package_id = int(request.form.get("package_id", "0"))
            except ValueError:
                package_id = 0
            conn = get_db()
            selected_package = conn.execute(
                "SELECT * FROM packages WHERE id=? AND active=1", (package_id,)
            ).fetchone()
            conn.close()
            phone = request.form.get("phone", "").strip()
            if not selected_package:
                mode = "packages"
                message = ("danger", text["invalid_package"])
            elif not phone:
                message = ("danger", text["phone_required"])
            else:
                message = ("warning", text["checkout_unavailable"])

    conn = get_db()
    packages = conn.execute(
        "SELECT * FROM packages WHERE active=1 ORDER BY price"
    ).fetchall()
    if mode == "buy" and selected_package is None and request.method == "GET":
        try:
            package_id = int(request.args.get("package_id", "0"))
        except ValueError:
            package_id = 0
        selected_package = conn.execute(
            "SELECT * FROM packages WHERE id=? AND active=1", (package_id,)
        ).fetchone()
        if not selected_package:
            mode = "packages"
            message = ("danger", text["choose_available"])
    if message and language == "sw":
        localized_messages = {
            "Voucher code and device ID are required.": text["voucher_required"],
            "Invalid voucher code.": text["invalid_voucher"],
            "Voucher exists but has not been activated yet.": text["voucher_not_active"],
            "Voucher has expired.": text["voucher_expired"],
            "Access denied: voucher is already bound to another device.": text["voucher_device_mismatch"],
            "Access granted. Savanna authentication successful.": text["voucher_success"],
        }
        status_prefix = "Voucher status is "
        if message[1].startswith(status_prefix):
            message = (message[0], text["voucher_inactive"])
        else:
            message = (message[0], localized_messages.get(message[1], message[1]))
    conn.close()
    return render_template(
        "portal.html",
        message=message,
        mode=mode,
        packages=packages,
        selected_package=selected_package,
        language=language,
        text=text,
    )

def authenticate_voucher(code, device_id, ip_address=None):
    if not code or not device_id:
        return ("danger", "Voucher code and device ID are required.")

    conn = get_db()
    voucher = conn.execute("SELECT * FROM vouchers WHERE code=?", (code,)).fetchone()

    if not voucher:
        conn.close()
        return ("danger", "Invalid voucher code.")

    if voucher["status"] == "unused":
        conn.close()
        return ("warning", "Voucher exists but has not been activated yet.")

    if voucher["status"] != "active":
        conn.close()
        return ("danger", f"Voucher status is {voucher['status']}.")

    if expire_voucher_if_needed(conn, voucher):
        conn.close()
        return ("danger", "Voucher has expired.")

    if voucher["device_id"] != device_id:
        conn.close()
        return ("danger", "Access denied: voucher is already bound to another device.")

    # Prevent duplicate simultaneous sessions for the same voucher/device.
    active = conn.execute("""
        SELECT id FROM sessions
        WHERE voucher_id=? AND device_id=? AND logout_at IS NULL
        ORDER BY id DESC LIMIT 1
    """, (voucher["id"], device_id)).fetchone()

    if not active:
        conn.execute("""
            INSERT INTO sessions(voucher_id,device_id,ip_address,login_at)
            VALUES (?,?,?,?)
        """, (voucher["id"], device_id, ip_address, now().isoformat(timespec="seconds")))
        conn.commit()

    conn.close()
    return ("success", "Access granted. Savanna authentication successful.")

# ---------- API ----------

@app.post("/api/v1/auth")
def api_auth():
    data = request.get_json(silent=True) or request.form
    result = authenticate_voucher(
        str(data.get("code", "")).strip().upper(),
        str(data.get("device_id", "")).strip(),
        request.remote_addr
    )
    ok = result[0] == "success"
    return jsonify({"success": ok, "message": result[1]}), (200 if ok else 403)

@app.get("/api/v1/voucher/<code>")
@role_required("super_admin", "admin", "support", "agent", "customer_care")
def api_voucher(code):
    conn = get_db()
    voucher = conn.execute("""
        SELECT v.id, v.code, v.status, v.customer_name, v.device_id,
               v.activated_at, v.expires_at, p.name package, p.price
        FROM vouchers v JOIN packages p ON p.id=v.package_id
        WHERE v.code=?
    """, (code.upper(),)).fetchone()
    conn.close()
    if not voucher:
        return jsonify({"success": False, "message": "Voucher not found"}), 404
    return jsonify({"success": True, "voucher": dict(voucher)})

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "savanna-v2"})

# ---------- Gateway integration placeholder ----------

@app.post("/api/v1/gateway/authorize")
def gateway_authorize():
    """
    Gateway integration contract.
    The configured router type determines how the gateway should enforce the returned decision.
    This version supports a simulated or router-driven workflow while still exposing a clean API contract.
    """
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().upper()
    device_id = str(data.get("device_id", "")).strip()

    if not code or not device_id:
        return jsonify({"allow": False, "reason": "missing_credentials"}), 400

    conn = get_db()
    settings = get_gateway_settings(conn)
    voucher = conn.execute("SELECT * FROM vouchers WHERE code=?", (code,)).fetchone()

    if not voucher:
        conn.close()
        return jsonify({"allow": False, "reason": "invalid_voucher", "router_type": settings.get("router_type")}), 403

    if expire_voucher_if_needed(conn, voucher):
        conn.close()
        return jsonify({"allow": False, "reason": "expired", "router_type": settings.get("router_type")}), 403

    if voucher["status"] != "active":
        conn.close()
        return jsonify({"allow": False, "reason": voucher["status"], "router_type": settings.get("router_type")}), 403

    if voucher["device_id"] != device_id:
        conn.close()
        return jsonify({"allow": False, "reason": "device_mismatch", "router_type": settings.get("router_type")}), 403

    conn.execute(
        "UPDATE gateway_settings SET last_sync=?, updated_at=? WHERE id=1",
        (now().isoformat(timespec="seconds"), now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

    return jsonify({
        "allow": True,
        "voucher": code,
        "expires_at": voucher["expires_at"],
        "router_type": settings.get("router_type"),
        "router_ip": settings.get("router_ip"),
        "enabled": bool(settings.get("enabled"))
    })

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
