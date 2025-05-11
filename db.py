import sqlite3

def init_db():
    conn = sqlite3.connect("students.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            topic TEXT,
            difficulty TEXT,
            score REAL,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)
    conn.commit()
    conn.close()

def register_student(username, password):
    conn = sqlite3.connect("students.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO students (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_student(username, password):
    conn = sqlite3.connect("students.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user

def save_progress(student_id, topic, difficulty, score):
    conn = sqlite3.connect("students.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO progress (student_id, topic, difficulty, score) VALUES (?, ?, ?, ?)",
                   (student_id, topic, difficulty, score))
    conn.commit()
    conn.close()

def get_progress(student_id):
    conn = sqlite3.connect("students.db")
    cursor = conn.cursor()
    cursor.execute("SELECT topic, difficulty, score FROM progress WHERE student_id=?", (student_id,))
    data = cursor.fetchall()
    conn.close()
    return data
