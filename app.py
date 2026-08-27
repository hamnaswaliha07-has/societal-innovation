from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)

# =========================================================
# APP CONFIGURATION
# =========================================================

app.secret_key = "societal-innovation-demo-key"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_database():
    connection = sqlite3.connect("database.db", timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

def create_database():

    connection = get_database()

    # -----------------------------------------------------
    # CITIZEN SUBMISSIONS
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            address TEXT NOT NULL,
            district TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            photo TEXT,
            video TEXT,
            status TEXT DEFAULT 'Submitted'
        )
    """)

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT DEFAULT '',
            district TEXT DEFAULT '',
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # UPDATE OLD USERS TABLE
    # -----------------------------------------------------

    user_columns = connection.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    user_column_names = [
        column["name"] for column in user_columns
    ]

    if "address" not in user_column_names:
        connection.execute("""
            ALTER TABLE users
            ADD COLUMN address TEXT DEFAULT ''
        """)

    if "district" not in user_column_names:
        connection.execute("""
            ALTER TABLE users
            ADD COLUMN district TEXT DEFAULT ''
        """)

    # -----------------------------------------------------
    # UNIVERSITY PROJECTS
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS university_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            university_id INTEGER NOT NULL,
            project_title TEXT NOT NULL,
            project_description TEXT,
            faculty_name TEXT,
            student_team TEXT,
            industry_partner TEXT,
            status TEXT DEFAULT 'Planning',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES submissions(id),
            FOREIGN KEY (university_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # COLLABORATIONS
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS collaborations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            industry_id INTEGER NOT NULL,
            university_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id)
                REFERENCES university_projects(id),
            FOREIGN KEY (industry_id)
                REFERENCES users(id),
            FOREIGN KEY (university_id)
                REFERENCES users(id)
        )
    """)

    connection.commit()
    connection.close()


create_database()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")

# =========================================================
# SERVE UPLOADED FILES
# =========================================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )
# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        district = request.form.get("district", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()

        allowed_roles = [
            "citizen",
            "university",
            "industry"
        ]

        if (
            not name
            or not email
            or not address
            or not district
            or not password
            or not role
        ):
            return render_template(
                "register.html",
                error="Please fill in all required fields."
            )

        if role not in allowed_roles:
            return render_template(
                "register.html",
                error="Please select a valid account type."
            )

        if len(password) < 6:
            return render_template(
                "register.html",
                error="Password must contain at least 6 characters."
            )

        connection = get_database()

        existing_user = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            connection.close()

            return render_template(
                "register.html",
                error="An account with this email already exists."
            )

        password_hash = generate_password_hash(password)

        connection.execute("""
            INSERT INTO users (
                name,
                email,
                phone,
                address,
                district,
                password,
                role
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            phone,
            address,
            district,
            password_hash,
            role
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        selected_role = request.form.get("role", "").strip()

        connection = get_database()

        user = connection.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        connection.close()

        if not user:
            return render_template(
                "login.html",
                error="Account not found. Please register first."
            )

        if not check_password_hash(
            user["password"],
            password
        ):
            return render_template(
                "login.html",
                error="Incorrect password."
            )

        if user["role"] != selected_role:
            return render_template(
                "login.html",
                error="The selected account type does not match this account."
            )

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["user_role"] = user["role"]

        if user["role"] == "citizen":
            return redirect(url_for("citizen"))

        if user["role"] == "university":
            return redirect(url_for("university"))

        if user["role"] == "industry":
            return redirect(url_for("industry"))
        
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))




    return render_template("login.html")
# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        if not email:
            return render_template(
                "forgot_password.html",
                error="Please enter your email address."
            )

        connection = get_database()

        user = connection.execute("""
            SELECT id
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        connection.close()

        if not user:
            return render_template(
                "forgot_password.html",
                error="No account was found with this email."
            )

        return redirect(
            url_for("reset_password", email=email)
        )

    return render_template("forgot_password.html")
# =========================================================
# RESET PASSWORD
# =========================================================

@app.route("/reset-password/<email>", methods=["GET", "POST"])
def reset_password(email):

    connection = get_database()

    user = connection.execute("""
        SELECT id
        FROM users
        WHERE email = ?
    """, (email,)).fetchone()

    if not user:
        connection.close()
        return "Account not found.", 404

    if request.method == "POST":

        new_password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not new_password:
            connection.close()
            return render_template(
                "reset_password.html",
                email=email,
                error="Please enter a new password."
            )

        if new_password != confirm_password:
            connection.close()
            return render_template(
                "reset_password.html",
                email=email,
                error="Passwords do not match."
            )

        hashed_password = generate_password_hash(
            new_password
        )

        connection.execute("""
            UPDATE users
            SET password = ?
            WHERE id = ?
        """, (
            hashed_password,
            user["id"]
        ))

        connection.commit()
        connection.close()

        return redirect(
            url_for("login")
        )

    connection.close()

    return render_template(
        "reset_password.html",
        email=email
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# =========================================================
# CITIZEN PORTAL
# =========================================================

@app.route("/citizen")
def citizen():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "citizen":
        return "Access denied. Citizen account required.", 403

    return render_template("citizen.html")


# =========================================================
# CITIZEN DASHBOARD
# =========================================================

@app.route("/citizen/dashboard")
def citizen_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "citizen":
        return "Access denied. Citizen account required.", 403

    connection = get_database()

    submissions = connection.execute("""
        SELECT *
        FROM submissions
        WHERE email = ?
        ORDER BY id DESC
    """, (
        session.get("user_email"),
    )).fetchall()

    connection.close()

    return render_template(
        "citizen_dashboard.html",
        submissions=submissions
    )


# =========================================================
# PROBLEM SUBMISSION
# =========================================================

@app.route("/problem", methods=["GET", "POST"])
def problem():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "citizen":
        return "Access denied. Citizen account required.", 403

    if request.method == "GET":
        return render_template("problem.html")

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    priority = request.form.get("priority", "").strip()

    if (
        not title
        or not description
        or not category
        or not priority
    ):
        return render_template(
            "problem.html",
            error="Please fill in all required problem details."
        )

    connection = get_database()

    user = connection.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        session.get("user_id"),
    )).fetchone()

    connection.close()

    if not user:
        session.clear()
        return redirect(url_for("login"))

    name = user["name"]
    email = user["email"]
    phone = user["phone"] or ""
    address = user["address"] or "Not provided"
    district = user["district"] or "Not provided"

    photo = request.files.get("photo")
    video = request.files.get("video")

    photo_filename = None
    video_filename = None

    if photo and photo.filename:

        extension = os.path.splitext(
            photo.filename
        )[1]

        photo_filename = secure_filename(
            f"{uuid.uuid4().hex}{extension}"
        )

        photo.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                photo_filename
            )
        )

    if video and video.filename:

        extension = os.path.splitext(
            video.filename
        )[1]

        video_filename = secure_filename(
            f"{uuid.uuid4().hex}{extension}"
        )

        video.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                video_filename
            )
        )

    connection = get_database()

    cursor = connection.execute("""
        INSERT INTO submissions (
            name,
            email,
            phone,
            address,
            district,
            title,
            description,
            category,
            priority,
            photo,
            video
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        email,
        phone,
        address,
        district,
        title,
        description,
        category,
        priority,
        photo_filename,
        video_filename
    ))

    submission_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return render_template(
        "success.html",
        submission_id=submission_id
    )


# =========================================================
# UNIVERSITY PORTAL
# =========================================================

@app.route("/university")
def university():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    return render_template("university.html")


# =========================================================
# UNIVERSITY DASHBOARD
# =========================================================

@app.route("/university/dashboard")
def university_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    submissions = connection.execute("""
        SELECT *
        FROM submissions
        ORDER BY id DESC
    """).fetchall()

    projects = connection.execute("""
        SELECT
            university_projects.*,
            submissions.title AS challenge_title
        FROM university_projects
        LEFT JOIN submissions
        ON university_projects.submission_id = submissions.id
        WHERE university_projects.university_id = ?
        ORDER BY university_projects.id DESC
    """, (
        session.get("user_id"),
    )).fetchall()

    connection.close()

    return render_template(
        "university_dashboard.html",
        submissions=submissions,
        projects=projects
    )


# =========================================================
# VIEW UNIVERSITY CHALLENGE
# =========================================================

@app.route("/university/challenge/<int:submission_id>")
def view_challenge(submission_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    submission = connection.execute("""
        SELECT *
        FROM submissions
        WHERE id = ?
    """, (
        submission_id,
    )).fetchone()
    

    existing_project = connection.execute("""
        SELECT *
        FROM university_projects
        WHERE submission_id = ?
        AND university_id = ?
    """, (
        submission_id,
        session.get("user_id"),
    )).fetchone()

    connection.close()

    if not submission:
        return "Challenge not found.", 404

    return render_template(
        "university_challenge.html",
        submission=submission,
        existing_project=existing_project
    )


# =========================================================
# ACCEPT CHALLENGE
# =========================================================

@app.route(
    "/university/challenge/<int:submission_id>/accept",
    methods=["POST"]
)
def accept_challenge(submission_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    submission = connection.execute("""
        SELECT *
        FROM submissions
        WHERE id = ?
    """, (
        submission_id,
    )).fetchone()

    if not submission:
        connection.close()
        return "Challenge not found.", 404

    connection.execute("""
        UPDATE submissions
        SET status = ?
        WHERE id = ?
    """, (
        "Accepted by University",
        submission_id
    ))

    connection.commit()
    connection.close()

    return redirect(
        url_for(
            "create_project",
            submission_id=submission_id
        )
    )


# =========================================================
# DENY CHALLENGE
# =========================================================

@app.route(
    "/university/challenge/<int:submission_id>/deny",
    methods=["POST"]
)
def deny_challenge(submission_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    connection.execute("""
        UPDATE submissions
        SET status = ?
        WHERE id = ?
    """, (
        "Declined by University",
        submission_id
    ))

    connection.commit()
    connection.close()

    return redirect(
        url_for("university_dashboard")
    )


# =========================================================
# CREATE UNIVERSITY PROJECT
# =========================================================

@app.route(
    "/university/project/create/<int:submission_id>",
    methods=["GET", "POST"]
)
def create_project(submission_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    submission = connection.execute("""
        SELECT *
        FROM submissions
        WHERE id = ?
    """, (
        submission_id,
    )).fetchone()

    if not submission:
        connection.close()
        return "Challenge not found.", 404

    if request.method == "POST":

        project_title = request.form.get(
            "project_title",
            ""
        ).strip()

        project_description = request.form.get(
            "project_description",
            ""
        ).strip()

        faculty_name = request.form.get(
            "faculty_name",
            ""
        ).strip()

        student_team = request.form.get(
            "student_team",
            ""
        ).strip()

        industry_partner = request.form.get(
            "industry_partner",
            ""
        ).strip()

        if not project_title:

            connection.close()

            return render_template(
                "university_project.html",
                submission=submission,
                error="Please enter a project title."
            )

        connection.execute("""
            INSERT INTO university_projects (
                submission_id,
                university_id,
                project_title,
                project_description,
                faculty_name,
                student_team,
                industry_partner,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            submission_id,
            session.get("user_id"),
            project_title,
            project_description,
            faculty_name,
            student_team,
            industry_partner,
            "Planning"
        ))

        connection.execute("""
            UPDATE submissions
            SET status = ?
            WHERE id = ?
        """, (
            "University Project Created",
            submission_id
        ))

        connection.commit()
        connection.close()

        return redirect(
            url_for("university_dashboard")
        )

    connection.close()

    return render_template(
        "university_project.html",
        submission=submission
    )


# =========================================================
# UNIVERSITY PROJECT DETAILS
# =========================================================

@app.route("/university/project/<int:project_id>")
def university_project(project_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    project = connection.execute("""
        SELECT
            university_projects.*,
            submissions.name AS citizen_name,
            submissions.title AS challenge_title,
            submissions.description AS challenge_description,
            submissions.category AS challenge_category,
            submissions.priority AS challenge_priority,
            submissions.district AS challenge_district,
            submissions.address AS challenge_address
        FROM university_projects
        LEFT JOIN submissions
        ON university_projects.submission_id = submissions.id
        WHERE university_projects.id = ?
        AND university_projects.university_id = ?
    """, (
        project_id,
        session.get("user_id")
    )).fetchone()

    if not project:
        connection.close()
        return "Project not found.", 404

    # Get the latest collaboration request for this project

    collaboration = connection.execute("""
        SELECT
            collaborations.*,
            users.name AS industry_name,
            users.email AS industry_email
        FROM collaborations
        LEFT JOIN users
            ON collaborations.industry_id = users.id
        WHERE collaborations.project_id = ?
        AND collaborations.university_id = ?
        ORDER BY collaborations.id DESC
        LIMIT 1
    """, (
        project_id,
        session.get("user_id")
    )).fetchone()

    connection.close()

    return render_template(
        "university_project_details.html",
        project=project,
        collaboration=collaboration
    )


# =========================================================
# UNIVERSITY PROJECTS
# =========================================================

@app.route("/university/projects")
def university_projects():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    projects = connection.execute("""
        SELECT
            university_projects.*,
            submissions.title AS challenge_title
        FROM university_projects
        LEFT JOIN submissions
        ON university_projects.submission_id = submissions.id
        WHERE university_projects.university_id = ?
        ORDER BY university_projects.id DESC
    """, (
        session.get("user_id"),
    )).fetchall()

    connection.close()

    return render_template(
        "university_projects.html",
        projects=projects
    )


# =========================================================
# UPDATE UNIVERSITY PROJECT STATUS
# =========================================================

@app.route(
    "/university/project/<int:project_id>/status",
    methods=["POST"]
)
def update_project_status(project_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    status = request.form.get(
        "status",
        ""
    ).strip()

    allowed_statuses = [
        "Planning",
        "Team Formed",
        "Prototype",
        "Testing",
        "Implementation",
        "Completed"
    ]

    if status not in allowed_statuses:
        return "Invalid project status.", 400

    connection = get_database()

    connection.execute("""
        UPDATE university_projects
        SET status = ?
        WHERE id = ?
        AND university_id = ?
    """, (
        status,
        project_id,
        session.get("user_id")
    ))

    connection.commit()
    connection.close()

    return redirect(
        url_for(
            "university_project",
            project_id=project_id
        )
    )


# =========================================================
# INDUSTRY DASHBOARD
# =========================================================

@app.route("/industry")
def industry():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "industry":
        return "Access denied. Industry account required.", 403

    connection = get_database()

    projects = connection.execute("""
    SELECT
        university_projects.*,
        submissions.title AS challenge_title,
        submissions.category AS challenge_category,
        submissions.priority AS challenge_priority,
        submissions.district AS challenge_district,
        users.name AS university_name,

       CASE
    WHEN EXISTS (
        SELECT 1
        FROM collaborations
        WHERE collaborations.project_id = university_projects.id
        AND collaborations.industry_id = ?
    )
    THEN 1
    ELSE 0
END AS collaboration_offered,

(
    SELECT collaborations.status
    FROM collaborations
    WHERE collaborations.project_id = university_projects.id
    AND collaborations.industry_id = ?
    ORDER BY collaborations.id DESC
    LIMIT 1
) AS collaboration_status
    FROM university_projects

    LEFT JOIN submissions
        ON university_projects.submission_id = submissions.id

    LEFT JOIN users
        ON university_projects.university_id = users.id

    ORDER BY university_projects.id DESC
""", (
    session.get("user_id"),
    session.get("user_id"),
)).fetchall()

    connection.close()

    return render_template(
        "industry_dashboard.html",
        projects=projects
    )


# =========================================================
# INDUSTRY PROJECT DETAILS
# =========================================================

@app.route("/industry/project/<int:project_id>")
def industry_project(project_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "industry":
        return "Access denied. Industry account required.", 403

    connection = get_database()

    project = connection.execute("""
        SELECT
            university_projects.*,
            submissions.title AS challenge_title,
            submissions.description AS challenge_description,
            submissions.category AS challenge_category,
            submissions.priority AS challenge_priority,
            submissions.district AS challenge_district,
            users.name AS university_name
        FROM university_projects
        LEFT JOIN submissions
            ON university_projects.submission_id = submissions.id
        LEFT JOIN users
            ON university_projects.university_id = users.id
        WHERE university_projects.id = ?
    """, (
        project_id,
    )).fetchone()

    if not project:
        connection.close()
        return "Project not found.", 404

    # Find this industry's latest collaboration request for this project.
    collaboration = connection.execute("""
        SELECT *
        FROM collaborations
        WHERE project_id = ?
        AND industry_id = ?
        AND university_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (
        project_id,
        session.get("user_id"),
        project["university_id"]
    )).fetchone()

    connection.close()

    return render_template(
        "industry_project.html",
        project=project,
        collaboration=collaboration
    )


# =========================================================
# OFFER INDUSTRY COLLABORATION
# =========================================================

@app.route(
    "/industry/project/<int:project_id>/collaborate",
    methods=["GET", "POST"]
)
def offer_collaboration(project_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "industry":
        return "Access denied. Industry account required.", 403

    connection = get_database()

    project = connection.execute("""
        SELECT
            university_projects.*,
            submissions.title AS challenge_title,
            submissions.category AS challenge_category,
            submissions.priority AS challenge_priority,
            users.name AS university_name
        FROM university_projects
        LEFT JOIN submissions
            ON university_projects.submission_id = submissions.id
        LEFT JOIN users
            ON university_projects.university_id = users.id
        WHERE university_projects.id = ?
    """, (
        project_id,
    )).fetchone()

    if not project:
        connection.close()
        return "Project not found.", 404

    industry_id = session.get("user_id")
    university_id = project["university_id"]

    # Look for the latest request from this industry to this project.
    existing_collaboration = connection.execute("""
        SELECT *
        FROM collaborations
        WHERE project_id = ?
        AND industry_id = ?
        AND university_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (
        project_id,
        industry_id,
        university_id
    )).fetchone()

    if request.method == "POST":

        # Never create another request while one is pending.
        if existing_collaboration and existing_collaboration["status"] == "Pending":
            connection.close()
            return render_template(
                "collaboration_success.html",
                project=project,
                already_sent=True,
                message="Your collaboration request has already been sent to the university. Please wait for the university's response."
            )

        # Never create another request after the university accepts it.
        if existing_collaboration and existing_collaboration["status"] == "Accepted":
            connection.close()
            return render_template(
                "collaboration_success.html",
                project=project,
                already_accepted=True,
                message="This collaboration has already been accepted by the university."
            )

        message = request.form.get("message", "").strip()

        if not message:
            connection.close()
            return render_template(
                "collaboration.html",
                project=project,
                existing_collaboration=existing_collaboration,
                error="Please describe how your industry can support the project."
            )

        # A rejected request may be submitted again. The old request
        # remains in the database so the collaboration history is preserved.
        connection.execute("""
            INSERT INTO collaborations (
                project_id,
                industry_id,
                university_id,
                message,
                status
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            project_id,
            industry_id,
            university_id,
            message,
            "Pending"
        ))

        connection.commit()
        connection.close()

        return render_template(
            "collaboration_success.html",
            project=project,
            already_sent=False,
            message="Your collaboration request has been successfully sent to the university."
        )

    connection.close()

    return render_template(
        "collaboration.html",
        project=project,
        existing_collaboration=existing_collaboration
    )


# =========================================================
# UNIVERSITY COLLABORATION REQUESTS
# =========================================================

@app.route("/university/collaborations")
def university_collaborations():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    collaborations = connection.execute("""
        SELECT
            collaborations.*,
            university_projects.project_title,
            users.name AS industry_name,
            users.email AS industry_email
        FROM collaborations
        LEFT JOIN university_projects
            ON collaborations.project_id = university_projects.id
        LEFT JOIN users
            ON collaborations.industry_id = users.id
        WHERE collaborations.university_id = ?
        ORDER BY collaborations.id DESC
    """, (
        session.get("user_id"),
    )).fetchall()

    connection.close()

    return render_template(
        "university_collaborations.html",
        collaborations=collaborations
    )


# =========================================================
# UNIVERSITY ACCEPT COLLABORATION
# =========================================================

@app.route(
    "/university/collaboration/<int:collaboration_id>/accept",
    methods=["POST"]
)
def accept_collaboration(collaboration_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    connection.execute("""
        UPDATE collaborations
        SET status = ?
        WHERE id = ?
        AND university_id = ?
    """, (
        "Accepted",
        collaboration_id,
        session.get("user_id")
    ))

    connection.commit()
    connection.close()

    return redirect(
        url_for("university_collaborations")
    )


# =========================================================
# UNIVERSITY REJECT COLLABORATION
# =========================================================

@app.route(
    "/university/collaboration/<int:collaboration_id>/reject",
    methods=["POST"]
)
def reject_collaboration(collaboration_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "university":
        return "Access denied. University account required.", 403

    connection = get_database()

    connection.execute("""
        UPDATE collaborations
        SET status = ?
        WHERE id = ?
        AND university_id = ?
    """, (
        "Rejected",
        collaboration_id,
        session.get("user_id")
    ))

    connection.commit()
    connection.close()

    return redirect(
        url_for("university_collaborations")
    )


# =========================================================
# COLLABORATION TRACKING
# =========================================================

@app.route("/industry/collaborations")
def industry_collaborations():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "industry":
        return "Access denied. Industry account required.", 403

    connection = get_database()

    collaborations = connection.execute("""
        SELECT
            collaborations.*,
            university_projects.project_title,
            users.name AS university_name
        FROM collaborations
        LEFT JOIN university_projects
            ON collaborations.project_id = university_projects.id
        LEFT JOIN users
            ON collaborations.university_id = users.id
        WHERE collaborations.industry_id = ?
        ORDER BY collaborations.id DESC
    """, (
        session.get("user_id"),
    )).fetchall()

    connection.close()

    return render_template(
        "industry_collaborations.html",
        collaborations=collaborations
    )
# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return "Access denied. Admin account required.", 403

    connection = get_database()

    total_users = connection.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_challenges = connection.execute(
        "SELECT COUNT(*) FROM submissions"
    ).fetchone()[0]

    total_projects = connection.execute(
        "SELECT COUNT(*) FROM university_projects"
    ).fetchone()[0]

    total_collaborations = connection.execute(
        "SELECT COUNT(*) FROM collaborations"
    ).fetchone()[0]
    submitted_challenges = connection.execute(
      "SELECT COUNT(*) FROM submissions WHERE status = 'Submitted'"
    ).fetchone()[0]

    accepted_challenges = connection.execute(
       "SELECT COUNT(*) FROM submissions WHERE status = 'Accepted'"
    ).fetchone()[0]

    denied_challenges = connection.execute(
        "SELECT COUNT(*) FROM submissions WHERE status = 'Denied'"
    ).fetchone()[0]

    pending_collaborations = connection.execute(
        "SELECT COUNT(*) FROM collaborations WHERE status = 'Pending'"
    ).fetchone()[0]

    accepted_collaborations = connection.execute(
    "SELECT COUNT(*) FROM collaborations WHERE status = 'Accepted'"
     ).fetchone()[0]

    connection.close()

    return render_template(
    "admin_dashboard.html",
    total_users=total_users,
    total_challenges=total_challenges,
    total_projects=total_projects,
    total_collaborations=total_collaborations,
    submitted_challenges=submitted_challenges,
    accepted_challenges=accepted_challenges,
    denied_challenges=denied_challenges,
    pending_collaborations=pending_collaborations,
    accepted_collaborations=accepted_collaborations
)
# =========================================================
# ADMIN - VIEW ALL CHALLENGES
# =========================================================

@app.route("/admin/challenges")
def admin_challenges():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return "Access denied. Admin account required.", 403

    connection = get_database()

    challenges = connection.execute("""
        SELECT *
        FROM submissions
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "admin_challenges.html",
        challenges=challenges
    )
# =========================================================
# ADMIN - VIEW USERS
# =========================================================

@app.route("/admin/users")
def admin_users():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return "Access denied. Admin account required.", 403

    connection = get_database()

    users = connection.execute("""
        SELECT id, name, email, phone, district, role
        FROM users
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "admin_users.html",
        users=users
    )
# =========================================================
# ADMIN - VIEW UNIVERSITY PROJECTS
# =========================================================

@app.route("/admin/projects")
def admin_projects():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return "Access denied. Admin account required.", 403

    connection = get_database()

    projects = connection.execute("""
        SELECT
            university_projects.*,
            submissions.title AS challenge_title,
            submissions.category AS challenge_category,
            submissions.priority AS challenge_priority,
            users.name AS university_name

        FROM university_projects

        LEFT JOIN submissions
            ON university_projects.submission_id = submissions.id

        LEFT JOIN users
            ON university_projects.university_id = users.id

        ORDER BY university_projects.id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "admin_projects.html",
        projects=projects
    )
# =========================================================
# ADMIN - VIEW COLLABORATIONS
# =========================================================

@app.route("/admin/collaborations")
def admin_collaborations():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "admin":
        return "Access denied. Admin account required.", 403

    connection = get_database()

    collaborations = connection.execute("""
        SELECT
            collaborations.*,
            university_projects.project_title AS project_title,
            university.name AS university_name,
            industry.name AS industry_name

        FROM collaborations

        LEFT JOIN university_projects
            ON collaborations.project_id = university_projects.id

        LEFT JOIN users AS university
            ON collaborations.university_id = university.id

        LEFT JOIN users AS industry
            ON collaborations.industry_id = industry.id

        ORDER BY collaborations.id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "admin_collaborations.html",
        collaborations=collaborations
    )
# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
