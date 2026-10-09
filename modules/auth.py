from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database.db import get_db_connection


auth = Blueprint("auth", __name__)


# Login for all four roles
@auth.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()

        role_tables = {
            "patient": "patients",
            "doctor": "doctors",
            "receptionist": "receptionists",
            "admin": "admins"
        }

        if role not in role_tables:
            flash("Please select a valid role.", "error")
            return redirect(url_for("auth.login"))

        connection = get_db_connection()

        try:
            cursor = connection.cursor()

            # Find the account using its email
            query = (
                f"SELECT * FROM {role_tables[role]} WHERE email = ?"
            )

            cursor.execute(query, (email,))
            user = cursor.fetchone()

        finally:
            connection.close()

        # Check whether the account exists and the password is correct
        if user and check_password_hash(user["password"], password):

            # Check whether the account is active
            if role == "doctor" and not user["available"]:
                flash("This doctor account is inactive.", "error")
                return redirect(url_for("auth.login"))

            if role == "receptionist" and not user["active"]:
                flash("This receptionist account is inactive.", "error")
                return redirect(url_for("auth.login"))

            # Clear any previous login session
            session.clear()

            # Save login information in the session
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            session["user_email"] = user["email"]
            session["role"] = role

            flash("Login successful!", "success")

            if role == "doctor":
                return redirect(url_for("doctor.dashboard"))

            return redirect(url_for("auth.dashboard"))

        flash("Invalid email, password, or role.", "error")

    return render_template("login.html")


# Patient registration
@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate the submitted information
        if not all([full_name, email, phone, password, confirm_password]):
            flash("Please fill in all fields.", "error")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("auth.register"))

        # Hash the password before storing it
        hashed_password = generate_password_hash(password)

        connection = get_db_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO patients
                (full_name, email, phone, password)
                VALUES (?, ?, ?, ?)
                """,
                (full_name, email, phone, hashed_password)
            )

            connection.commit()

        except Exception as error:
            connection.rollback()

            # Handle duplicate email addresses
            if "UNIQUE constraint failed" in str(error):
                flash("An account with this email already exists.", "error")
            else:
                flash("Registration failed. Please try again.", "error")

            return redirect(url_for("auth.register"))

        finally:
            connection.close()

        flash("Registration successful! You can now log in.", "success")

        return redirect(url_for("auth.login"))

    return render_template("register.html")


# Dashboard after login
@auth.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("auth.login"))

    return render_template("dashboard.html")


# Logout
@auth.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))