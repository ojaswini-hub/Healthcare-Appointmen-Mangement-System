from multiprocessing.dummy import connection
from time import time

from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)


# Create database and table
def create_database():
    connection = sqlite3.connect("appointments.db")
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            email TEXT NOT NULL,
            doctor TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


# Home page
@app.route("/")
def home():
    return render_template("index.html")


# Book appointment
@app.route("/book", methods=["GET", "POST"])
def book():

    if request.method == "POST":

        patient_name = request.form["patient_name"]
        email = request.form["email"]
        doctor = request.form["doctor"]
        date = request.form["date"]
        time = request.form["time"]

        connection = sqlite3.connect("appointments.db")
        cursor = connection.cursor()

        # Check if doctor is already booked
        cursor.execute("""
            SELECT * FROM appointments
            WHERE doctor = ? AND date = ? AND time = ?
        """, (doctor, date, time))

        existing_appointment = cursor.fetchone()

        if existing_appointment:
            connection.close()

            return render_template(
                "book.html",
                error="This doctor is already booked for this date and time."
            )

        # Book appointment
        cursor.execute("""
            INSERT INTO appointments
            (patient_name, email, doctor, date, time)
            VALUES (?, ?, ?, ?, ?)
        """, (patient_name, email, doctor, date, time))

        connection.commit()
        connection.close()

        return render_template(
            "book.html",
            success="Appointment booked successfully!"
        )

    return render_template("book.html")  

# View appointments
@app.route("/appointments")
def appointments():

    connection = sqlite3.connect("appointments.db")
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM appointments")

    appointments = cursor.fetchall()

    connection.close()

    return render_template(
        "appointments.html",
        appointments=appointments
    )
# Cancel appointment
@app.route("/cancel/<int:appointment_id>")
def cancel_appointment(appointment_id):

    connection = sqlite3.connect("appointments.db")
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM appointments WHERE id = ?",
        (appointment_id,)
    )

    connection.commit()
    connection.close()

    return redirect("/appointments")

# Start application
if __name__ == "__main__":
    create_database()
    app.run(debug=True)