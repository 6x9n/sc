from flask import Flask, render_template, jsonify, request
import requests
import sqlite3
import time
import threading

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect("results.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            seat_no INTEGER PRIMARY KEY,
            name TEXT,
            school TEXT,
            division TEXT,
            specialization TEXT,
            score TEXT,
            grade TEXT,
            percentage REAL,
            pct_str TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

scraper_state = {
    "is_running": False,
    "current_seat": 0,
    "status_message": "Idle"
}

base_url = "https://nategafany.com/api/result.php"

def run_scraper(start_seat, end_seat):
    global scraper_state
    scraper_state["is_running"] = True
    scraper_state["status_message"] = "Processing..."

    for seat_no in range(start_seat, end_seat + 1):
        if not scraper_state["is_running"]:
            scraper_state["status_message"] = "Stopped by user."
            break

        scraper_state["current_seat"] = seat_no
        params = {'seat_no': seat_no}
        success = False

        while not success and scraper_state["is_running"]:
            try:
                response = requests.get(base_url, params=params, timeout=10)

                if response.status_code == 429:
                    scraper_state["status_message"] = f"Rate limited at {seat_no}. Retrying in 10s..."
                    time.sleep(10)
                    continue

                elif response.status_code == 200:
                    payload = response.json()
                    if payload.get("status") == "success" and "data" in payload and payload["data"].get("name"):
                        data = payload["data"]
                        pct_str = data.get("percentage", "0%")
                        pct_float = float(pct_str.replace("%", "").strip())

                        conn = sqlite3.connect("results.db")
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT OR REPLACE INTO students 
                            (seat_no, name, school, division, specialization, score, grade, percentage, pct_str)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            seat_no,
                            data.get("name", "غير معروف"),
                            data.get("school", "-"),
                            data.get("division", "-"),
                            data.get("specialization", "-"),
                            data.get("total", "0"),
                            data.get("grade", "-"),
                            pct_float,
                            pct_str
                        ))
                        conn.commit()
                        conn.close()

                    success = True

                elif response.status_code in [404, 500]:
                    success = True
                else:
                    success = True

            except Exception:
                time.sleep(3)

        time.sleep(1.2)

    scraper_state["is_running"] = False
    if scraper_state["status_message"].startswith("Processing"):
        scraper_state["status_message"] = "Completed!"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/start", methods=["POST"])
def start_scraping():
    global scraper_state
    if scraper_state["is_running"]:
        return jsonify({"status": "error", "message": "Already running."}), 400

    data = request.json
    start_seat = int(data.get("start_seat", 2910001))
    end_seat = int(data.get("end_seat", 2910050))

    thread = threading.Thread(target=run_scraper, args=(start_seat, end_seat), daemon=True)
    thread.start()
    return jsonify({"status": "success"})

@app.route("/api/stop", methods=["POST"])
def stop_scraping():
    global scraper_state
    scraper_state["is_running"] = False
    return jsonify({"status": "success"})

@app.route("/api/status")
def get_status():
    conn = sqlite3.connect("results.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY percentage DESC")
    rows = cursor.fetchall()
    conn.close()

    results = [dict(row) for row in rows]

    return jsonify({
        "is_running": scraper_state["is_running"],
        "current_seat": scraper_state["current_seat"],
        "status_message": scraper_state["status_message"],
        "total_found": len(results),
        "results": results
    })

if __name__ == "__main__":
    app.run()