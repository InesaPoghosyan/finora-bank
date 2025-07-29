from flask import Blueprint, render_template, request, redirect, flash, url_for, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal

main_routes = Blueprint('main', __name__)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="2004",
    database="finora_bank"
)
db.autocommit = False  # IMPORTANT: Disable autocommit to control transactions manually
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

    cursor.execute("""
        SELECT c.* FROM cards c
        JOIN user_cards uc ON c.id = uc.card_id
        WHERE uc.user_id = %s
    """, (user_id,))
    cards = cursor.fetchall()

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
        return redirect(url_for("main.login"))

    if request.method == "POST":
        card_holder = request.form.get("card_holder_name")
        card_number = request.form.get("card_number")
        expiry_date = request.form.get("expiry_date")
        cvv = request.form.get("cvv")

        if not (card_holder and card_number and expiry_date and cvv):
            flash("Please fill out all card fields.", "warning")
            return redirect(url_for("main.add_card"))

        cursor.execute("""
            SELECT * FROM cards 
            WHERE card_number = %s AND expiry_date = %s AND cvv = %s AND card_holder_name = %s
        """, (card_number, expiry_date, cvv, card_holder))
        existing_card = cursor.fetchone()

        if not existing_card:
            flash("Card does not exist in our system. Please contact support.", "danger")
            return redirect(url_for("main.add_card"))

        cursor.execute("""
            SELECT * FROM user_cards WHERE card_id = %s AND user_id = %s
        """, (existing_card["id"], session["user_id"]))
        already_linked = cursor.fetchone()

        if already_linked:
            flash("This card is already linked to your account.", "info")
            return redirect(url_for("main.dashboard"))

        cursor.execute("""
            INSERT INTO user_cards (user_id, card_id) VALUES (%s, %s)
        """, (session["user_id"], existing_card["id"]))
        db.commit()

        flash("Card linked successfully!")
        return redirect(url_for("main.dashboard"))

    return render_template('add_card.html')

@main_routes.route('/submit-card', methods=['POST'])
def submit_card():
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("main.login"))
    
    card_holder = request.form.get('card_holder_name')
    card_number = request.form.get('card_number')
    cvv = request.form.get('cvv')
    expiry = request.form.get('expiry_date')

    if not (card_holder and card_number and cvv and expiry):
        flash("Please fill all the card fields.", "warning")
        return redirect(url_for("main.add_card"))

    cursor.execute("""
        SELECT id FROM cards
        WHERE card_holder_name = %s AND card_number = %s AND cvv = %s AND expiry_date = %s
    """, (card_holder, card_number, cvv, expiry))
    card = cursor.fetchone()

    if not card:
        flash("Card does not exist in our system. Please contact support.", "danger")
        return redirect(url_for("main.add_card"))

    card_id = card['id']

    cursor.execute("""
        SELECT * FROM user_cards WHERE card_id = %s AND user_id = %s
    """, (card_id, session["user_id"]))
    linked = cursor.fetchone()

    if linked:
        flash("This card is already linked to your account.", "info")
        return redirect(url_for("main.dashboard"))

    cursor.execute("""
        INSERT INTO user_cards (user_id, card_id) VALUES (%s, %s)
    """, (session["user_id"], card_id))
    db.commit()

    flash("Card linked successfully!")
    return redirect(url_for("main.dashboard"))

@main_routes.route('/transfer', methods=['GET', 'POST'])

def transfer():
    if "user_id" not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']

    if request.method == 'POST':
        from_card_id = request.form['from_card']
        to_card_number = request.form['to_card_number'].replace(" ", "")  # normalize spaces

        print(f"[DEBUG] Transfer Request:")
        print(f"User ID: {user_id}")
        print(f"From Card ID: {from_card_id}")
        print(f"To Card Number: {to_card_number}")

        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Invalid transfer amount.", "danger")
            print("[ERROR] Invalid amount entered.")
            return redirect(url_for("main.transfer"))

        try:
           
            # Get from_card and its balance
            cursor.execute("SELECT balance FROM cards WHERE id = %s", (from_card_id,))
            from_card = cursor.fetchone()
            print(f"[DEBUG] From Card Record: {from_card}")

            if not from_card:
                flash("Source card not found.", "danger")
                db.rollback()
                print("[ERROR] From card not found.")
                return redirect(url_for("main.transfer"))

            # Get recipient card ID and balance, normalize card_number lookup
            cursor.execute(
                "SELECT id, balance FROM cards WHERE REPLACE(card_number, ' ', '') = %s",
                (to_card_number,)
            )
            to_card = cursor.fetchone()
            print(f"[DEBUG] To Card Record: {to_card}")

            if not to_card:
                flash("Recipient card number not found.", "danger")
                db.rollback()
                print("[ERROR] To card not found.")
                return redirect(url_for("main.transfer"))

            to_card_id = to_card['id']

            # Prevent transferring to the same card
            if int(from_card_id) == int(to_card_id):
                flash("You cannot transfer to the same card.", "warning")
                db.rollback()
                print("[ERROR] Same card transfer blocked.")
                return redirect(url_for("main.transfer"))

            if from_card['balance'] < amount:
                flash("Insufficient funds in the source card.", "danger")
                db.rollback()
                print(f"[ERROR] Insufficient balance: {from_card['balance']} < {amount}")
                return redirect(url_for("main.transfer"))

            # Find the user_id who owns the recipient card
            cursor.execute("SELECT user_id FROM user_cards WHERE card_id = %s", (to_card_id,))
            receiver_user = cursor.fetchone()

            if not receiver_user:
                flash("Recipient card is not linked to any user.", "danger")
                db.rollback()
                print("[ERROR] Recipient card user not found.")
                return redirect(url_for("main.transfer"))

            receiver_user_id = receiver_user['user_id']

            # Perform balance updates
            cursor.execute("UPDATE cards SET balance = balance - %s WHERE id = %s", (amount, from_card_id))
            cursor.execute("UPDATE cards SET balance = balance + %s WHERE id = %s", (amount, to_card_id))

            # Insert transactions
            cursor.execute("""
                INSERT INTO transactions (user_id, card_id, description, amount, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (user_id, from_card_id, f'Transfer to card ending {to_card_number[-4:]}', -amount))

            cursor.execute("""
                INSERT INTO transactions (user_id, card_id, description, amount, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (receiver_user_id, to_card_id, f'Received from card ending {to_card_number[-4:]}', amount))

            db.commit()
            flash("Transfer successful!", "success")
            print("[SUCCESS] Transfer completed.")

        except Exception as e:
            db.rollback()
            flash(f"Transfer failed: {str(e)}", "danger")
            print(f"[EXCEPTION] Transfer failed: {str(e)}")

        return redirect(url_for("main.transfer"))

    # GET request: show user's own cards
    cursor.execute("""
        SELECT c.id, c.card_holder_name, c.card_number, c.balance
        FROM cards c
        JOIN user_cards uc ON c.id = uc.card_id
        WHERE uc.user_id = %s
    """, (user_id,))
    cards = cursor.fetchall()
    print(f"[DEBUG] Cards fetched for user {user_id}: {cards}")

    return render_template('transfer.html', cards=cards)

@main_routes.route('/transaction')
def transaction():
    if "user_id" not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']

    cursor.execute("""
        SELECT t.description, t.amount, t.created_at, c.card_number
        FROM transactions t
        JOIN cards c ON t.card_id = c.id
        WHERE t.user_id = %s
        ORDER BY t.created_at DESC
    """, (user_id,))
    user_transactions = cursor.fetchall()

    return render_template('transaction.html', transactions=user_transactions)


@main_routes.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('main.login'))
