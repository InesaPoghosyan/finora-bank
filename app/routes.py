from flask import Blueprint, render_template, request, redirect, flash, url_for, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

main_routes = Blueprint('main', __name__)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="2004",
    database="finora_bank"
)
cursor = db.cursor(dictionary=True)

@main_routes.route("/")
def welcome():
    return render_template("welcome.html")

@main_routes.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")

        if not (full_name and email and password and phone):
            flash("Please fill out all fields.", "warning")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        try:
            cursor.execute(
                "INSERT INTO users (full_name, email, password_hash, phone) VALUES (%s, %s, %s, %s)",
                (full_name, email, hashed_password, phone)
            )
            db.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("main.login"))
        except mysql.connector.IntegrityError:
            flash("Email already exists.", "danger")

    return render_template("register.html")

@main_routes.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not (email and password):
            flash("Please enter both email and password.", "warning")
            return render_template("login.html")

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            flash(f"Welcome, {user['full_name']}!", "success")
            return redirect(url_for("main.dashboard"))
        else:
            flash("Incorrect email or password.", "danger")

    return render_template("login.html")

@main_routes.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    # Get user's cards
    cursor.execute("SELECT * FROM cards WHERE user_id = %s", (user_id,))
    cards = cursor.fetchall()

    if not cards:
        return render_template("dashboard.html", cards=[], transactions=[])

    # If cards exist, get transactions
    card_ids = [card["id"] for card in cards]
    format_strings = ','.join(['%s'] * len(card_ids))
    cursor.execute(f"""
        SELECT t.*, c.card_number FROM transactions t
        JOIN cards c ON t.card_id = c.id
        WHERE t.card_id IN ({format_strings})
        ORDER BY t.date DESC
        LIMIT 5
    """, tuple(card_ids))
    transactions = cursor.fetchall()

    return render_template("dashboard.html", cards=cards, transactions=transactions)