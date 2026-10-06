"""
Database connection and table definitions (SQLite).

SQLite stores the whole database in a single file, so there is no server to
install. The SQL used here is plain enough to move to MySQL later with only
small changes (mainly AUTOINCREMENT -> AUTO_INCREMENT).
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DATABASE_PATH = os.path.join(INSTANCE_DIR, "medivault.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Many-to-many link: a role has many permissions, a permission belongs to many roles.
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id       INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name              TEXT NOT NULL,
    last_name               TEXT NOT NULL,
    birth_date              TEXT NOT NULL,
    sex                     TEXT NOT NULL,
    blood_type              TEXT NOT NULL DEFAULT '',
    phone                   TEXT NOT NULL DEFAULT '',
    address                 TEXT NOT NULL DEFAULT '',
    emergency_contact_name  TEXT NOT NULL DEFAULT '',
    emergency_contact_phone TEXT NOT NULL DEFAULT '',
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

-- diagnosis and treatment_notes are stored ENCRYPTED.
CREATE TABLE IF NOT EXISTS history_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    entry_date      TEXT NOT NULL,
    diagnosis       TEXT NOT NULL,
    treatment_notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS allergies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    allergen   TEXT NOT NULL,
    reaction   TEXT NOT NULL,
    severity   TEXT NOT NULL
);

-- name and dosage are stored ENCRYPTED.
CREATE TABLE IF NOT EXISTS medications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    dosage     TEXT NOT NULL,
    frequency  TEXT NOT NULL,
    status     TEXT NOT NULL
);

-- patient_id has no foreign key on purpose: logs must survive after a
-- patient is deleted. patient_name is a copy kept for the same reason.
CREATE TABLE IF NOT EXISTS access_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    patient_id   INTEGER,
    patient_name TEXT NOT NULL,
    access_type  TEXT NOT NULL,
    action       TEXT NOT NULL,
    reason       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
"""


def connect(path=DATABASE_PATH):
    """Open a connection. Rows can be read by column name, e.g. row["username"]."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # SQLite ignores foreign keys unless this is switched on for every connection.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables(conn):
    conn.executescript(SCHEMA)
    conn.commit()
