import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# --- Database Integration ---
DATABASE = 'tracker.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Create the students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                roll_number INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')
        # Create the grades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS grades (
                roll_number INTEGER,
                subject TEXT NOT NULL,
                grade REAL NOT NULL,
                FOREIGN KEY (roll_number) REFERENCES students(roll_number)
            )
        ''')
        db.commit()

# --- Object-Oriented Design ---

class Student:
    def __init__(self, roll_number, name):
        self.roll_number = roll_number
        self.name = name

    def display_info(self):
        return f"Roll Number: {self.roll_number}, Name: {self.name}"

class StudentTracker:
    def __init__(self, db):
        self.db = db

    def add_student(self, name, roll_number):
        cursor = self.db.cursor()
        try:
            cursor.execute("INSERT INTO students (name, roll_number) VALUES (?, ?)", (name, roll_number))
            self.db.commit()
            return True, "Student added successfully!"
        except sqlite3.IntegrityError:
            return False, "Error: Roll number already exists."

    def get_all_students(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT roll_number, name FROM students")
        return cursor.fetchall()

    def get_student_by_roll(self, roll_number):
        cursor = self.db.cursor()
        cursor.execute("SELECT name FROM students WHERE roll_number = ?", (roll_number,))
        student = cursor.fetchone()
        if student:
            return student['name']
        return None

    def add_grades(self, roll_number, subjects, grades):
        cursor = self.db.cursor()
        try:
            for subject, grade in zip(subjects, grades):
                cursor.execute(
                    "INSERT INTO grades (roll_number, subject, grade) VALUES (?, ?, ?)",
                    (roll_number, subject, grade)
                )
            self.db.commit()
            return True, "Grades added successfully!"
        except Exception as e:
            self.db.rollback()
            return False, f"Error adding grades: {e}"

    def get_student_grades(self, roll_number):
        cursor = self.db.cursor()
        cursor.execute("SELECT subject, grade FROM grades WHERE roll_number = ?", (roll_number,))
        return cursor.fetchall()

    def calculate_average(self, roll_number):
        cursor = self.db.cursor()
        cursor.execute("SELECT AVG(grade) FROM grades WHERE roll_number = ?", (roll_number,))
        average = cursor.fetchone()[0]
        return average

    def get_subjects(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT DISTINCT subject FROM grades")
        return [row[0] for row in cursor.fetchall()]

    def get_subject_topper(self, subject):
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT students.name, grades.grade
            FROM students
            JOIN grades ON students.roll_number = grades.roll_number
            WHERE grades.subject = ?
            ORDER BY grades.grade DESC
            LIMIT 1
        ''', (subject,))
        return cursor.fetchone()

    def get_class_average(self, subject):
        cursor = self.db.cursor()
        cursor.execute("SELECT AVG(grade) FROM grades WHERE subject = ?", (subject,))
        return cursor.fetchone()[0]

# --- Flask Routes ---
@app.route('/')
def index():
    db = get_db()
    tracker = StudentTracker(db)
    students = tracker.get_all_students()
    subjects = tracker.get_subjects()
    
    # Calculate averages for all students to display on the main page
    student_averages = {}
    for student in students:
        avg = tracker.calculate_average(student['roll_number'])
        student_averages[student['roll_number']] = round(avg, 2) if avg is not None else "N/A"
        
    return render_template('index.html', students=students, subjects=subjects, student_averages=student_averages)

@app.route('/add_student', methods=['POST'])
def add_student():
    db = get_db()
    tracker = StudentTracker(db)
    name = request.form['name']
    roll_number = request.form['roll_number']
    
    if not name or not roll_number:
        return "Name and Roll Number are required.", 400
    
    roll_number = int(roll_number)
    success, message = tracker.add_student(name, roll_number)
    
    if success:
        return redirect(url_for('index'))
    else:
        return message, 400

@app.route('/add_grades', methods=['POST'])
def add_grades():
    db = get_db()
    tracker = StudentTracker(db)
    roll_number = int(request.form['roll_number'])
    
    if tracker.get_student_by_roll(roll_number) is None:
        return "Student not found.", 404
        
    subjects = request.form.getlist('subject')
    grades_str = request.form.getlist('grade')
    grades = []
    
    for g in grades_str:
        try:
            grade = float(g)
            if not 0 <= grade <= 100:
                return "Grades must be between 0 and 100.", 400
            grades.append(grade)
        except ValueError:
            return "Grades must be numeric.", 400
            
    success, message = tracker.add_grades(roll_number, subjects, grades)
    
    if success:
        return redirect(url_for('index'))
    else:
        return message, 500

@app.route('/view_details', methods=['GET', 'POST'])
def view_details():
    db = get_db()
    tracker = StudentTracker(db)
    
    if request.method == 'POST':
        roll_number = int(request.form['roll_number'])
        name = tracker.get_student_by_roll(roll_number)
        if name:
            grades = tracker.get_student_grades(roll_number)
            average = tracker.calculate_average(roll_number)
            return render_template('student_details.html', name=name, roll_number=roll_number, grades=grades, average=round(average, 2) if average is not None else "N/A")
        else:
            return "Student not found.", 404
    
    return redirect(url_for('index'))

@app.route('/subject_topper', methods=['POST'])
def subject_topper():
    db = get_db()
    tracker = StudentTracker(db)
    subject = request.form['subject']
    topper = tracker.get_subject_topper(subject)
    if topper:
        return f"The topper in {subject} is {topper['name']} with a grade of {topper['grade']}"
    else:
        return f"No grades found for subject: {subject}", 404

@app.route('/class_average', methods=['POST'])
def class_average():
    db = get_db()
    tracker = StudentTracker(db)
    subject = request.form['subject']
    average = tracker.get_class_average(subject)
    if average is not None:
        return f"The class average for {subject} is {round(average, 2)}"
    else:
        return f"No grades found for subject: {subject}", 404
        
if __name__ == '__main__':
    init_db()
    app.run(debug=True)