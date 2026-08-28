import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# ============================================================
# MASTER DATABASE MERGER
# ============================================================
# This script creates ONE master database from the databases
# found in your previous Societal Innovation project copies.
#
# The most complete database is used as the starting point:
#   S.I Backup / societal-innovation (1)
#
# Other databases are then merged into it.
# Existing records are not deleted.
# Duplicate users are identified by email.
# Duplicate submissions/projects/collaborations are avoided
# where they can be safely identified.
# ============================================================

CURRENT_PROJECT = Path.cwd()
MASTER = CURRENT_PROJECT / "database.db"

SOURCE_DATABASES = [
    Path(r"C:\Users\user\OneDrive\Desktop\societal-innovation\database.db"),
    Path(r"C:\Users\user\OneDrive\Documents\societal-innovation backup working\societal-innovation\database.db"),
    Path(r"C:\Users\user\OneDrive\S.I Backup\societal-innovation\database.db"),
    Path(r"C:\Users\user\OneDrive\SOCIETAL INNOVATION\societal-innovation (1)\societal-innovation\database.db"),
]

# The ZIP database was found to have no users table, so it is ignored.
# The current project database, if it already exists, is also not used
# as a source because this script is intended to build the master here.

def connect(path):
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c

def table_exists(c, table):
    return c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone() is not None

def ensure_schema(c):
    # Same schema as the Flask application.
    c.execute("""
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

    c.execute("""
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

    c.execute("""
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS collaborations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            industry_id INTEGER NOT NULL,
            university_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES university_projects(id),
            FOREIGN KEY (industry_id) REFERENCES users(id),
            FOREIGN KEY (university_id) REFERENCES users(id)
        )
    """)
    c.commit()

def count(c, table):
    if not table_exists(c, table):
        return 0
    return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

# ------------------------------------------------------------
# Safety checks
# ------------------------------------------------------------
if MASTER.exists():
    backup = CURRENT_PROJECT / (
        "database_before_master_merge_" +
        datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
    )
    shutil.copy2(MASTER, backup)
    print(f"Backup created: {backup}")

# Use the most complete known database as the starting point.
base = Path(r"C:\Users\user\OneDrive\SOCIETAL INNOVATION\societal-innovation (1)\societal-innovation\database.db")

if not base.exists():
    raise FileNotFoundError(f"Master source database not found:\n{base}")

# If current project already has a database, remove it only AFTER
# making a backup above. The master is recreated from the selected base.
if MASTER.exists():
    MASTER.unlink()

shutil.copy2(base, MASTER)
print(f"\nStarting master database from:\n{base}")

master = connect(MASTER)
ensure_schema(master)

# ------------------------------------------------------------
# Merge each source
# ------------------------------------------------------------
total_added_users = 0
total_added_submissions = 0
total_added_projects = 0
total_added_collaborations = 0

for source in SOURCE_DATABASES:
    if not source.exists():
        print(f"\nSKIP: {source} (not found)")
        continue

    if source.resolve() == MASTER.resolve():
        print(f"\nSKIP master source: {source}")
        continue

    try:
        src = connect(source)
        if not table_exists(src, "users"):
            print(f"\nSKIP: {source} (no users table)")
            src.close()
            continue

        print(f"\nMERGING: {source}")

        # ----------------------------------------------------
        # USERS: unique by email
        # ----------------------------------------------------
        user_map = {}

        for u in src.execute("SELECT * FROM users ORDER BY id").fetchall():
            existing = master.execute(
                "SELECT id FROM users WHERE lower(email)=lower(?)",
                (u["email"],)
            ).fetchone()

            if existing:
                master_id = existing["id"]
            else:
                master.execute("""
                    INSERT INTO users
                    (name,email,phone,address,district,password,role)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    u["name"],
                    u["email"],
                    u["phone"],
                    u["address"] if "address" in u.keys() else "",
                    u["district"] if "district" in u.keys() else "",
                    u["password"],
                    u["role"]
                ))
                master_id = master.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]
                total_added_users += 1

            user_map[u["id"]] = master_id

        master.commit()

        # ----------------------------------------------------
        # SUBMISSIONS: avoid exact duplicates
        # ----------------------------------------------------
        submission_map = {}

        if table_exists(src, "submissions"):
            for s in src.execute(
                "SELECT * FROM submissions ORDER BY id"
            ).fetchall():

                existing = master.execute("""
                    SELECT id
                    FROM submissions
                    WHERE lower(email)=lower(?)
                      AND title=?
                      AND description=?
                """, (
                    s["email"],
                    s["title"],
                    s["description"]
                )).fetchone()

                if existing:
                    master_id = existing["id"]

                    # Preserve media/status if the master copy is missing them.
                    master.execute("""
                        UPDATE submissions
                        SET
                            photo=COALESCE(photo, ?),
                            video=COALESCE(video, ?),
                            status=CASE
                                WHEN status IS NULL OR status='' THEN ?
                                ELSE status
                            END
                        WHERE id=?
                    """, (
                        s["photo"],
                        s["video"],
                        s["status"],
                        master_id
                    ))
                else:
                    master.execute("""
                        INSERT INTO submissions
                        (name,email,phone,address,district,title,description,
                         category,priority,photo,video,status)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        s["name"], s["email"], s["phone"], s["address"],
                        s["district"], s["title"], s["description"],
                        s["category"], s["priority"], s["photo"],
                        s["video"], s["status"]
                    ))
                    master_id = master.execute(
                        "SELECT last_insert_rowid()"
                    ).fetchone()[0]
                    total_added_submissions += 1

                submission_map[s["id"]] = master_id

        master.commit()

        # ----------------------------------------------------
        # PROJECTS
        # ----------------------------------------------------
        project_map = {}

        if table_exists(src, "university_projects"):
            for p in src.execute(
                "SELECT * FROM university_projects ORDER BY id"
            ).fetchall():

                new_submission_id = submission_map.get(p["submission_id"])
                new_university_id = user_map.get(p["university_id"])

                if not new_submission_id or not new_university_id:
                    print(f"  WARNING: could not map project {p['id']}; skipped")
                    continue

                existing = master.execute("""
                    SELECT id
                    FROM university_projects
                    WHERE submission_id=?
                      AND university_id=?
                      AND project_title=?
                """, (
                    new_submission_id,
                    new_university_id,
                    p["project_title"]
                )).fetchone()

                if existing:
                    master_id = existing["id"]
                else:
                    master.execute("""
                        INSERT INTO university_projects
                        (submission_id,university_id,project_title,
                         project_description,faculty_name,student_team,
                         industry_partner,status,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (
                        new_submission_id,
                        new_university_id,
                        p["project_title"],
                        p["project_description"],
                        p["faculty_name"],
                        p["student_team"],
                        p["industry_partner"],
                        p["status"],
                        p["created_at"]
                    ))
                    master_id = master.execute(
                        "SELECT last_insert_rowid()"
                    ).fetchone()[0]
                    total_added_projects += 1

                project_map[p["id"]] = master_id

        master.commit()

        # ----------------------------------------------------
        # COLLABORATIONS
        # ----------------------------------------------------
        if table_exists(src, "collaborations"):
            for col in src.execute(
                "SELECT * FROM collaborations ORDER BY id"
            ).fetchall():

                new_project_id = project_map.get(col["project_id"])
                new_industry_id = user_map.get(col["industry_id"])
                new_university_id = user_map.get(col["university_id"])

                if not new_project_id or not new_industry_id or not new_university_id:
                    print(f"  WARNING: could not map collaboration {col['id']}; skipped")
                    continue

                existing = master.execute("""
                    SELECT id
                    FROM collaborations
                    WHERE project_id=?
                      AND industry_id=?
                      AND university_id=?
                      AND COALESCE(message,'')=COALESCE(?, '')
                      AND status=?
                """, (
                    new_project_id,
                    new_industry_id,
                    new_university_id,
                    col["message"],
                    col["status"]
                )).fetchone()

                if not existing:
                    master.execute("""
                        INSERT INTO collaborations
                        (project_id,industry_id,university_id,message,status,created_at)
                        VALUES (?,?,?,?,?,?)
                    """, (
                        new_project_id,
                        new_industry_id,
                        new_university_id,
                        col["message"],
                        col["status"],
                        col["created_at"]
                    ))
                    total_added_collaborations += 1

        master.commit()
        src.close()

    except Exception as e:
        print(f"  ERROR while merging {source}: {e}")

# ------------------------------------------------------------
# Final report
# ------------------------------------------------------------
print("\n" + "=" * 60)
print("MASTER DATABASE CREATED")
print("=" * 60)
print(f"Location: {MASTER}")
print()
print("Final counts:")
print(f"  Users:          {count(master, 'users')}")
print(f"  Submissions:    {count(master, 'submissions')}")
print(f"  Projects:       {count(master, 'university_projects')}")
print(f"  Collaborations: {count(master, 'collaborations')}")
print()
print("New records added during merge:")
print(f"  Users:          {total_added_users}")
print(f"  Submissions:    {total_added_submissions}")
print(f"  Projects:       {total_added_projects}")
print(f"  Collaborations: {total_added_collaborations}")
print()
print("Your master database is ready.")
print("Close this script with Ctrl+C only after the report appears.")
master.close()
