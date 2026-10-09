from werkzeug.security import generate_password_hash
from flask import session
from database.db import create_tables
from flask import Flask, render_template, request, redirect, url_for, session
from translations import TRANSLATIONS
import os
import sqlite3

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from database.db import create_tables
from modules.auth import auth
from modules.doctor import doctor


# ------------------------------------------
# APPLICATION CONFIGURATION
# ------------------------------------------

app = Flask(__name__)
@app.route("/set-language/<language>")
def set_language(language):
    if language in TRANSLATIONS:
        session["language"] = language

    return redirect(request.referrer or url_for("index"))

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "local-development-key-change-before-deployment"
)
@app.context_processor
def inject_translations():
    language = session.get("language", "en")
    translations = TRANSLATIONS.get(language, TRANSLATIONS["en"])

    return {
        "translations": translations,
        "current_language": language
    }

app.register_blueprint(auth)
app.register_blueprint(doctor)


# ------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------

DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "appointments.db"
)


def get_appointments_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# ------------------------------------------
# CREATE APPOINTMENTS TABLE
# ------------------------------------------

def create_database():
    connection = get_appointments_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                email TEXT NOT NULL,
                doctor TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL
            )
        """)
                # Add status to existing appointments without deleting records
        columns = connection.execute(
            "PRAGMA table_info(appointments)"
        ).fetchall()

        column_names = [column["name"] for column in columns]

        if "status" not in column_names:
            connection.execute("""
                ALTER TABLE appointments
                ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'
            """)

        connection.commit()

    finally:
        connection.close()


# ------------------------------------------
# PATIENT ACCESS CHECK
# ------------------------------------------

def patient_required():
    if "user_id" not in session:
        flash("Please log in to continue.", "error")
        return False

    if session.get("role") != "patient":
        flash("You do not have permission to access this page.", "error")
        return False

    return True


# ------------------------------------------
# HOME PAGE
# ------------------------------------------


@app.route("/")
def home():
    language = session.get("language", "en")
    translations = TRANSLATIONS.get(language, TRANSLATIONS["en"])

    return render_template(
        "index.html",
        translations=translations
    )

# ------------------------------------------
# TEMPORARY LOCAL DOCTOR ACCOUNT SETUP
# Remove this route after creating the account.
# ------------------------------------------

@app.route("/setup-doctor", methods=["GET", "POST"])
def setup_doctor():

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not all([full_name, email, phone, password]):
            return "Please fill in every field.", 400

        if len(password) < 8:
            return "Password must contain at least 8 characters.", 400

        connection = get_appointments_connection()

        try:
            connection.execute("""
                INSERT INTO doctors
                (full_name, email, phone, specialization, password)
                VALUES (?, ?, ?, ?, ?)
            """, (
                full_name,
                email,
                phone,
                request.form.get("specialization", "").strip(),
                generate_password_hash(password)
            ))

            connection.commit()

            return """
                <h2>Doctor account created successfully!</h2>
                <p>Now log in using the doctor email and password.</p>
                <a href="/login">Go to Login</a>
            """

        except sqlite3.IntegrityError:
            return "An account with this email may already exist.", 409

        finally:
            connection.close()

    return """
        <h1>Create Your First Doctor Account</h1>
        <form method="POST">
            <label>Full Name:</label><br>
            <input name="full_name" required><br><br>

            <label>Email:</label><br>
            <input type="email" name="email" required><br><br>

            <label>Phone:</label><br>
            <input name="phone" required><br><br>

            <label>Specialization:</label><br>
            <input name="specialization" required><br><br>

            <label>Password (minimum 8 characters):</label><br>
            <input type="password" name="password" minlength="8" required><br><br>

            <button type="submit">Create Doctor Account</button>
        </form>
    """

# ------------------------------------------
# BOOK APPOINTMENT
# ------------------------------------------
@app.route("/book", methods=["GET", "POST"])
def book():

    if not patient_required():
        return redirect(url_for("auth.login"))

    # Fetch registered and available doctors from the database
    connection = get_appointments_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT full_name, specialization, available
            FROM doctors
            WHERE available = 1
            ORDER BY full_name
        """)

        doctors = cursor.fetchall()

    except sqlite3.Error:
        doctors = []

    finally:
        connection.close()

    if request.method == "POST":

        patient_name = session.get("user_name")
        email = session.get("user_email")

        selected_doctor = request.form.get("doctor", "").strip()
        appointment_date = request.form.get("date", "").strip()
        appointment_time = request.form.get("time", "").strip()

        if not all([
            patient_name,
            email,
            selected_doctor,
            appointment_date,
            appointment_time
        ]):
            return render_template(
                "book.html",
                doctors=doctors,
                error="Please fill in all appointment details."
            )

        # Verify that the selected doctor is registered and available
        valid_doctor_names = [
            doctor["full_name"] for doctor in doctors
        ]

        if selected_doctor not in valid_doctor_names:
            return render_template(
                "book.html",
                doctors=doctors,
                error="Please select a valid, available doctor."
            )

        connection = get_appointments_connection()

        try:
            cursor = connection.cursor()

            # Prevent duplicate bookings for the same doctor,
            # date, and time
            cursor.execute("""
                SELECT id
                FROM appointments
                WHERE LOWER(doctor) = LOWER(?)
                  AND date = ?
                  AND time = ?
            """, (
                selected_doctor,
                appointment_date,
                appointment_time
            ))

            if cursor.fetchone():
                return render_template(
                    "book.html",
                    doctors=doctors,
                    error=(
                        "This doctor is already booked "
                        "for this date and time."
                    )
                )

            # Save the appointment
            cursor.execute("""
                INSERT INTO appointments (
                    patient_name,
                    email,
                    doctor,
                    date,
                    time
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                patient_name,
                email,
                selected_doctor,
                appointment_date,
                appointment_time
            ))

            connection.commit()

            return render_template(
                "book.html",
                doctors=doctors,
                success="Appointment booked successfully!"
            )

        except sqlite3.Error:
            connection.rollback()

            return render_template(
                "book.html",
                doctors=doctors,
                error="Unable to book the appointment. Please try again."
            )

        finally:
            connection.close()

    return render_template(
        "book.html",
        doctors=doctors
    )
# ------------------------------------------
# VIEW PATIENT APPOINTMENTS
# ------------------------------------------

@app.route("/appointments")
def appointments():

    if not patient_required():
        return redirect(url_for("auth.login"))

    email = session.get("user_email")
    connection = get_appointments_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM appointments
            WHERE email = ?
            ORDER BY date, time
        """, (email,))

        appointment_records = cursor.fetchall()

    finally:
        connection.close()

    return render_template(
        "appointments.html",
        appointments=appointment_records
    )


# ------------------------------------------
# CANCEL PATIENT APPOINTMENT
# ------------------------------------------

@app.route("/cancel/<int:appointment_id>", methods=["GET", "POST"])
def cancel_appointment(appointment_id):

    if not patient_required():
        return redirect(url_for("auth.login"))

    email = session.get("user_email")
    connection = get_appointments_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM appointments
            WHERE id = ?
              AND email = ?
        """, (appointment_id, email))

        connection.commit()

        if cursor.rowcount == 0:
            flash(
                "Appointment not found or you cannot cancel it.",
                "error"
            )
        else:
            flash("Appointment cancelled successfully.", "success")

    except sqlite3.Error:
        connection.rollback()
        flash("Unable to cancel the appointment.", "error")

    finally:
        connection.close()

    return redirect(url_for("appointments"))


# ------------------------------------------
# ERROR HANDLER
# ------------------------------------------

@app.errorhandler(404)
def page_not_found(error):
    return "Page not found. Please check the URL.", 404

# ------------------------------------------
# INITIALIZE DATABASE
# ------------------------------------------

create_database()
create_tables()


# ------------------------------------------
# START APPLICATION
# ------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)