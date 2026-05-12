import csv
import sqlite3
import re
import os

# --- Configuration ---
# Update these names to match your exact filenames if necessary.
CSV_FILE = "student_scores (1).csv"
TXT_FILE = "student_comments.txt"
DB_FILE = "elt_student_data.db"


# ==========================================
# E - Extract Phase
# ==========================================

def extract_structured_data():
    """Reads data from the structured CSV file."""
    records = []
    print(f"--- Extracting structured data from {CSV_FILE} ---")
    
    if not os.path.exists(CSV_FILE):
        print(f"Error: File '{CSV_FILE}' not found.")
        return []

    with open(CSV_FILE, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        # Ensure header names are normalized (stripped of whitespace)
        reader.fieldnames = [field.strip() for field in reader.fieldnames]

        for row in reader:
            # We also strip the values to prevent spacing issues
            clean_row = {k: v.strip() for k, v in row.items()}
            records.append(clean_row)

    print(f"Successfully extracted {len(records)} records.")
    return records


def extract_unstructured_data():
    """Reads data from the unstructured text file."""
    records = []
    print(f"--- Extracting unstructured data from {TXT_FILE} ---")

    if not os.path.exists(TXT_FILE):
        print(f"Error: File '{TXT_FILE}' not found.")
        return []

    with open(TXT_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            # Only add non-empty lines
            if line:
                records.append(line)

    print(f"Successfully extracted {len(records)} raw lines.")
    return records


# ==========================================
# L - Load Phase
# ==========================================

def connect_database():
    """Establishes a connection to the SQLite database."""
    print(f"--- Connecting to database: {DB_FILE} ---")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    return conn, cursor


def create_raw_tables(cursor):
    """
    TODO #1: CREATE TABLE (IMPLEMENTED)
    Creates the necessary tables for raw data storage.
    """
    print("--- Creating raw tables ---")
    
    # Table 1: raw_student_scores
    cursor.execute("DROP TABLE IF EXISTS raw_student_scores")
    cursor.execute("""
        CREATE TABLE raw_student_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            name TEXT,
            course TEXT,
            quiz TEXT,
            exam TEXT,
            attendance TEXT
        )
    """)

    # Table 2: raw_student_comments
    cursor.execute("DROP TABLE IF EXISTS raw_student_comments")
    cursor.execute("""
        CREATE TABLE raw_student_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text TEXT
        )
    """)


def insert_structured_records(cursor, records):
    """
    TODO #2A: INSERT INTO (IMPLEMENTED)
    Inserts extracted CSV data into the raw_student_scores table.
    """
    if not records:
        print("No structured records to insert.")
        return

    print(f"--- Inserting {len(records)} structured records into raw_student_scores ---")
    query = """
        INSERT INTO raw_student_scores (student_id, name, course, quiz, exam, attendance)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    
    # Prepare the data as a list of tuples
    # We rely on the normalized header names ('student_id', etc.)
    data_to_insert = [
        (
            r['student_id'],
            r['name'],
            r['course'],
            r['quiz'],
            r['exam'],
            r['attendance']
        )
        for r in records
    ]
    
    cursor.executemany(query, data_to_insert)


def insert_unstructured_records(cursor, records):
    """
    TODO #2B: INSERT INTO (IMPLEMENTED)
    Inserts extracted raw text lines into the raw_student_comments table.
    """
    if not records:
        print("No unstructured records to insert.")
        return

    print(f"--- Inserting {len(records)} raw lines into raw_student_comments ---")
    query = """
        INSERT INTO raw_student_comments (raw_text)
        VALUES (?)
    """
    
    # Prepare data as a list of single-element tuples
    data_to_insert = [(r,) for r in records]
    
    cursor.executemany(query, data_to_insert)


# ==========================================
# T - Transform Phase (Within DB)
# ==========================================

def transform_data_inside_database(cursor):
    """Executes SQL to transform and join raw data into a final report table."""
    print("--- Transforming data inside the database ---")
    
    # Drop existing transformed tables
    cursor.execute("DROP TABLE IF EXISTS transformed_student_scores")
    cursor.execute("DROP TABLE IF EXISTS transformed_student_comments")
    cursor.execute("DROP TABLE IF EXISTS final_student_report")

    # 1. Transform Scores: Clean data, cast types, calculate grade and status
    cursor.execute("""
        CREATE TABLE transformed_student_scores AS
        SELECT
            CAST(student_id AS INTEGER) AS student_id,
            name,
            course,
            CAST(quiz AS INTEGER) AS quiz,
            CAST(exam AS INTEGER) AS exam,
            CAST(attendance AS INTEGER) AS attendance,
            ROUND(
                (CAST(quiz AS REAL) * 0.30) +
                (CAST(exam AS REAL) * 0.50) +
                (CAST(attendance AS REAL) * 0.20),
                2
            ) AS final_grade,
            CASE
                WHEN ROUND(
                    (CAST(quiz AS REAL) * 0.30) +
                    (CAST(exam AS REAL) * 0.50) +
                    (CAST(attendance AS REAL) * 0.20),
                    2
                ) >= 75 THEN 'Passed'
                ELSE 'Failed'
            END AS status
        FROM raw_student_scores
    """)

    # 2. Transform Comments: Parse raw text to extract student_id and comment
    # SQL function notes: INSTR(string, substring) finds the index, 
    # SUBSTR(string, start, length) cuts the string.
    cursor.execute("""
        CREATE TABLE transformed_student_comments AS
        SELECT
            CAST(
                SUBSTR(
                    raw_text,
                    INSTR(raw_text, 'Student ID: ') + LENGTH('Student ID: '),
                    INSTR(raw_text, ' |') - (INSTR(raw_text, 'Student ID: ') + LENGTH('Student ID: '))
                ) AS INTEGER
            ) AS student_id,
            TRIM(
                SUBSTR(
                    raw_text,
                    INSTR(raw_text, 'Comment: ') + LENGTH('Comment: ')
                )
            ) AS comment
        FROM raw_student_comments
    """)

    # 3. Create Final Report: Join scores with comments (LEFT JOIN retains all scores)
    cursor.execute("""
        CREATE TABLE final_student_report AS
        SELECT
            s.student_id,
            s.name,
            s.course,
            s.quiz,
            s.exam,
            s.attendance,
            s.final_grade,
            s.status,
            c.comment
        FROM transformed_student_scores s
        LEFT JOIN transformed_student_comments c
        ON s.student_id = c.student_id
    """)


# ==========================================
# Presentation/Output
# ==========================================

def select_final_report(cursor):
    """
    TODO #3: SELECT FROM (IMPLEMENTED)
    Displays all records from the final_student_report.
    """
    print("\n--- Generating Final Student Report ---\n")
    
    # Fetch data
    cursor.execute("""
        SELECT student_id, name, course, quiz, exam, attendance, final_grade, status, comment
        FROM final_student_report
    """)
    rows = cursor.fetchall()
    
    # Define simple headers and layout
    headers = ["ID", "Name", "Course", "Quiz", "Exam", "Att.", "Final", "Status", "Comment"]
    print(f"{headers[0]:<5} | {headers[1]:<15} | {headers[2]:<25} | {headers[3]:<4} | {headers[4]:<4} | {headers[5]:<4} | {headers[6]:<6} | {headers[7]:<7} | {headers[8]}")
    print("-" * 120)

    for row in rows:
        # Unpack the tuple
        s_id, name, course, quiz, exam, att, final, status, comment = row
        # Handle cases where comment is NULL
        comment = comment if comment else "No comment."
        print(f"{s_id:<5} | {name:<15} | {course:<25} | {quiz:<4} | {exam:<4} | {att:<4} | {final:<6.2f} | {status:<7} | {comment}")
    
    print("-" * 120)


# ==========================================
# Main Execution
# ==========================================

def main():
    print("==========================================")
    print("STARTING ELT PIPELINE")
    print("==========================================\n")

    # E - Extract
    structured_records = extract_structured_data()
    unstructured_records = extract_unstructured_data()
    print()

    # L - Load (Initialization)
    conn, cursor = connect_database()
    create_raw_tables(cursor)

    # (Optional but good practice) Ensure raw tables are empty before insertion
    cursor.execute("DELETE FROM raw_student_scores")
    cursor.execute("DELETE FROM raw_student_comments")
    print()

    # L - Load (Insertion)
    insert_structured_records(cursor, structured_records)
    insert_unstructured_records(cursor, unstructured_records)
    print()

    # T - Transform
    transform_data_inside_database(cursor)
    print()

    # Commit changes (saves modifications)
    conn.commit()

    # Display results
    select_final_report(cursor)

    # Cleanup
    conn.close()
    print("\nPIPELINE COMPLETED SUCCESSFULLY.")

if __name__ == "__main__":
    main()
