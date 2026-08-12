const express = require('express');
const Database = require('better-sqlite3');
const fetch = require('node-fetch');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Initialize SQLite Database
const db = new Database('results.db');
db.exec(`
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
`);

const insertStmt = db.prepare(`
    INSERT OR REPLACE INTO students 
    (seat_no, name, school, division, specialization, score, grade, percentage, pct_str)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
`);

let scraperState = {
    isRunning: false,
    currentSeat: 0,
    statusMessage: "Idle"
};

const baseUrl = "https://nategafany.com/api/result.php";

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function runScraper(startSeat, endSeat) {
    scraperState.isRunning = true;
    scraperState.statusMessage = "Processing...";

    for (let seatNo = startSeat; seatNo <= endSeat; seatNo++) {
        if (!scraperState.isRunning) {
            scraperState.statusMessage = "Stopped by user.";
            break;
        }

        scraperState.currentSeat = seatNo;
        let success = false;

        while (!success && scraperState.isRunning) {
            try {
                const response = await fetch(`${baseUrl}?seat_no=${seatNo}`);

                if (response.status === 429) {
                    scraperState.statusMessage = `Rate limited at ${seatNo}. Retrying in 10s...`;
                    await sleep(10000);
                    continue;
                }

                if (response.ok) {
                    const payload = await response.json();

                    if (payload.status === "success" && payload.data && payload.data.name) {
                        const data = payload.data;
                        const pctStr = data.percentage || "0%";
                        const pctFloat = parseFloat(pctStr.replace("%", "").trim());

                        insertStmt.run(
                            seatNo,
                            data.name || "غير معروف",
                            data.school || "-",
                            data.division || "-",
                            data.specialization || "-",
                            data.total || "0",
                            data.grade || "-",
                            pctFloat,
                            pctStr
                        );
                    }
                    success = true;
                } else {
                    success = true;
                }
            } catch (error) {
                await sleep(3000);
            }
        }

        await sleep(1200); // 1.2s delay between requests
    }

    scraperState.isRunning = false;
    if (scraperState.statusMessage.startsWith("Processing")) {
        scraperState.statusMessage = "Completed!";
    }
}

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.post('/api/start', (req, res) => {
    if (scraperState.isRunning) {
        return res.status(400).json({ status: "error", message: "Already running." });
    }

    const startSeat = parseInt(req.body.start_seat) || 2910001;
    const endSeat = parseInt(req.body.end_seat) || 2910050;

    runScraper(startSeat, endSeat);
    res.json({ status: "success" });
});

app.post('/api/stop', (req, res) => {
    scraperState.isRunning = false;
    res.json({ status: "success" });
});

app.get('/api/status', (req, res) => {
    const rows = db.prepare("SELECT * FROM students ORDER BY percentage DESC").all();
    res.json({
        is_running: scraperState.isRunning,
        current_seat: scraperState.currentSeat,
        status_message: scraperState.statusMessage,
        total_found: rows.length,
        results: rows
    });
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
