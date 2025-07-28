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

    # Get user's linked cards
    cursor.execute("""
        SELECT c.* FROM cards c
        JOIN user_cards uc ON c.id = uc.card_id
        WHERE uc.user_id = %s
    """, (user_id,))
    cards = cursor.fetchall()

    # Get recent transactions for this user ordered by created_at
    cursor.execute("""
        SELECT description, amount, created_at FROM transactions
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 5
    """, (user_id,))
    transactions = cursor.fetchall()

    return render_template("dashboard.html", cards=cards, transactions=transactions)


@main_routes.route('/add-card', methods=["GET", "POST"])
def add_card():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        card_holder = request.form.get("card_holder_name")
        card_number = request.form.get("card_number")
        expiry_date = request.form.get("expiry_date")
        cvv = request.form.get("cvv")

        if not (card_holder and card_number and expiry_date and cvv):
            flash("Please fill out all card fields.", "warning")
            return redirect(url_for("main.add_card"))

        # Check if card exists in cards table
        cursor.execute("""
            SELECT * FROM cards 
            WHERE card_number = %s AND expiry_date = %s AND cvv = %s AND card_holder_name = %s
        """, (card_number, expiry_date, cvv, card_holder))
        existing_card = cursor.fetchone()

        if not existing_card:
            flash("Card does not exist in our system. Please contact support to register your card.", "danger")
            return redirect(url_for("main.add_card"))

        # Check if this card already linked to user
        cursor.execute("""
            SELECT * FROM user_cards WHERE card_id = %s AND user_id = %s
        """, (existing_card["id"], session["user_id"]))
        already_added = cursor.fetchone()

        if already_added:
            flash("This card is already linked to your account.", "info")
            return redirect(url_for("main.dashboard"))

        # Link card to user
        cursor.execute("""
            INSERT INTO user_cards (user_id, card_id) VALUES (%s, %s)
        """, (session["user_id"], existing_card["id"]))
        db.commit()

        flash("Card added successfully!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template('add_card.html')


@main_routes.route('/submit_card', methods=['POST'])
def submit_card():
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('main.login'))

    card_number = request.form.get('card_number')
    card_holder_name = request.form.get('card_holder_name')
    expiry_date = request.form.get('expiry_date')
    cvv = request.form.get('cvv')

    if not all([card_number, card_holder_name, expiry_date, cvv]):
        flash("Please fill out all card fields.", "warning")
        return redirect(url_for('main.add_card'))

    try:
        # Insert new card (id is auto-increment, no need to specify)
        cursor.execute("""
            INSERT INTO cards (card_number, card_holder_name, expiry_date, cvv, balance)
            VALUES (%s, %s, %s, %s, %s)
        """, (card_number, card_holder_name, expiry_date, cvv, 0))  # New card balance default to 0
        db.commit()

        # Get the inserted card's id
        card_id = cursor.lastrowid

        # Link the new card to the user
        cursor.execute("""
            INSERT INTO user_cards (user_id, card_id)
            VALUES (%s, %s)
        """, (session['user_id'], card_id))
        db.commit()

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        return redirect(url_for('main.add_card'))

    flash("Card added successfully!")
    return redirect(url_for('main.dashboard'))