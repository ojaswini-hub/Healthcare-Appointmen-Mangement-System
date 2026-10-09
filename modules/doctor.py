from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from database.db import get_db_connection


doctor = Blueprint("doctor", __name__, url_prefix="/doctor")


# ------------------------------------------
# CHECK DOCTOR LOGIN
# ------------------------------------------

def doctor_required():
    if "user_id" not in session:
        flash("Please log in first.", "error")
        return False

    if session.get("role") != "doctor":
        flash("Access denied. Doctors only.", "error")
        return False

    return True


# ------------------------------------------
# DOCTOR DASHBOARD
# ------------------------------------------

@doctor.route("/dashboard")
def dashboard():

    if not doctor_required():
        return redirect(url_for("auth.login"))

    return render_template("doctor_dashboard.html")


# ------------------------------------------
# VIEW DOCTOR'S APPOINTMENTS
# ------------------------------------------

@doctor.route("/appointments")
def appointments():

    if not doctor_required():
        return redirect(url_for("auth.login"))

    doctor_email = session.get("user_email")

    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        # Find the doctor's name
        cursor.execute(
            "SELECT full_name FROM doctors WHERE id = ?",
            (session["user_id"],)
        )

        doctor_record = cursor.fetchone()

        if doctor_record is None:
            flash("Doctor account not found.", "error")
            return redirect(url_for("auth.logout"))

        doctor_name = doctor_record["full_name"]

        # Find appointments assigned to this doctor
        cursor.execute("""
            SELECT *
            FROM appointments
            WHERE LOWER(doctor) = LOWER(?)
            ORDER BY date, time
        """, (doctor_name,))

        appointment_records = cursor.fetchall()

    finally:
        connection.close()

    return render_template(
        "doctor_appointments.html",
        appointments=appointment_records
    )

@doctor.route("/appointments/<int:appointment_id>/status", methods=["POST"])
def update_appointment_status(appointment_id):

    if not doctor_required():
        return redirect(url_for("auth.login"))

    new_status = request.form.get("status", "").strip()

    allowed_statuses = ["Confirmed", "Completed"]

    if new_status not in allowed_statuses:
        flash("Invalid appointment status.", "error")
        return redirect(url_for("doctor.appointments"))

    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        # Find the logged-in doctor's name
        cursor.execute(
            "SELECT full_name FROM doctors WHERE id = ?",
            (session["user_id"],)
        )

        doctor_record = cursor.fetchone()

        if doctor_record is None:
            flash("Doctor account not found.", "error")
            return redirect(url_for("auth.logout"))

        doctor_name = doctor_record["full_name"]

        # Update only appointments assigned to this doctor
        cursor.execute("""
            UPDATE appointments
            SET status = ?
            WHERE id = ?
              AND LOWER(doctor) = LOWER(?)
        """, (new_status, appointment_id, doctor_name))

        if cursor.rowcount == 0:
            flash("Appointment not found.", "error")
        else:
            connection.commit()
            flash("Appointment status updated successfully!", "success")

    except Exception:
        connection.rollback()
        flash("Unable to update appointment status.", "error")

    finally:
        connection.close()

    return redirect(url_for("doctor.appointments"))