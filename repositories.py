"""
Repositories: the only place that writes SQL for users, roles, patients and
medical records.

Pattern: each repository receives a database connection in its constructor
("dependency injection") and turns rows into objects and objects into rows.
The rest of the app works with objects and never sees SQL.

Always use "?" placeholders for values. Never glue user input into the SQL
string yourself - that is how SQL injection happens.
"""
from datetime import datetime

from models import Role, User, Patient, HistoryEntry, Allergy, Medication


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RoleRepository:
    def __init__(self, conn):
        self.conn = conn

    def find_by_id(self, role_id):
        row = self.conn.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_role(row)

    def find_by_name(self, name):
        row = self.conn.execute("SELECT * FROM roles WHERE name = ?", (name,)).fetchone()
        if row is None:
            return None
        return self._row_to_role(row)

    def list_all(self):
        rows = self.conn.execute("SELECT * FROM roles ORDER BY id").fetchall()
        roles = []
        for row in rows:
            roles.append(self._row_to_role(row))
        return roles

    def create(self, name, display_name, permission_names):
        cursor = self.conn.execute(
            "INSERT INTO roles (name, display_name) VALUES (?, ?)", (name, display_name))
        for permission_name in permission_names:
            self.conn.execute(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT ?, id FROM permissions WHERE name = ?",
                (cursor.lastrowid, permission_name))
        self.conn.commit()

    def create_permission(self, name):
        self.conn.execute("INSERT INTO permissions (name) VALUES (?)", (name,))
        self.conn.commit()

    def _row_to_role(self, row):
        permission_rows = self.conn.execute(
            "SELECT p.name FROM permissions p "
            "JOIN role_permissions rp ON rp.permission_id = p.id "
            "WHERE rp.role_id = ?",
            (row["id"],)).fetchall()
        permission_names = []
        for permission_row in permission_rows:
            permission_names.append(permission_row["name"])
        return Role(row["id"], row["name"], row["display_name"], permission_names)


class UserRepository:
    def __init__(self, conn, role_repository):
        self.conn = conn
        self.roles = role_repository

    def find_by_id(self, user_id):
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def find_by_username(self, username):
        row = self.conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def list_all(self):
        rows = self.conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()
        users = []
        for row in rows:
            users.append(self._row_to_user(row))
        return users

    def create(self, username, full_name, password_hash, role_id):
        self.conn.execute(
            "INSERT INTO users (username, full_name, password_hash, role_id, is_active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (username, full_name, password_hash, role_id, now_text()))
        self.conn.commit()

    def set_active(self, user_id, is_active):
        value = 0
        if is_active:
            value = 1
        self.conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (value, user_id))
        self.conn.commit()

    def _row_to_user(self, row):
        role = self.roles.find_by_id(row["role_id"])
        return User(row["id"], row["username"], row["full_name"], role,
                    row["is_active"] == 1, row["password_hash"])


class PatientRepository:
    def __init__(self, conn):
        self.conn = conn

    def search(self, text):
        """All patients, or only those whose name contains `text`."""
        pattern = "%" + text + "%"
        rows = self.conn.execute(
            "SELECT * FROM patients WHERE first_name LIKE ? OR last_name LIKE ? "
            "ORDER BY last_name, first_name",
            (pattern, pattern)).fetchall()
        patients = []
        for row in rows:
            patients.append(self._row_to_patient(row))
        return patients

    def find(self, patient_id):
        row = self.conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_patient(row)

    def create(self, patient):
        cursor = self.conn.execute(
            "INSERT INTO patients (first_name, last_name, birth_date, sex, blood_type, phone, "
            "address, emergency_contact_name, emergency_contact_phone, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (patient.first_name, patient.last_name, patient.birth_date, patient.sex,
             patient.blood_type, patient.phone, patient.address,
             patient.emergency_contact_name, patient.emergency_contact_phone,
             now_text(), now_text()))
        self.conn.commit()
        patient.id = cursor.lastrowid

    def update(self, patient):
        self.conn.execute(
            "UPDATE patients SET first_name = ?, last_name = ?, birth_date = ?, sex = ?, "
            "blood_type = ?, phone = ?, address = ?, emergency_contact_name = ?, "
            "emergency_contact_phone = ?, updated_at = ? WHERE id = ?",
            (patient.first_name, patient.last_name, patient.birth_date, patient.sex,
             patient.blood_type, patient.phone, patient.address,
             patient.emergency_contact_name, patient.emergency_contact_phone,
             now_text(), patient.id))
        self.conn.commit()

    def delete(self, patient_id):
        # history, allergies and medications are removed too (ON DELETE CASCADE).
        self.conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        self.conn.commit()

    def _row_to_patient(self, row):
        return Patient(
            id=row["id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            birth_date=row["birth_date"],
            sex=row["sex"],
            blood_type=row["blood_type"],
            phone=row["phone"],
            address=row["address"],
            emergency_contact_name=row["emergency_contact_name"],
            emergency_contact_phone=row["emergency_contact_phone"],
        )


class HistoryRepository:
    """Medical history. diagnosis and treatment_notes are encrypted in the database."""

    def __init__(self, conn, encryptor):
        self.conn = conn
        self.encryptor = encryptor

    def list_for_patient(self, patient_id):
        rows = self.conn.execute(
            "SELECT * FROM history_entries WHERE patient_id = ? ORDER BY entry_date DESC",
            (patient_id,)).fetchall()
        entries = []
        for row in rows:
            entries.append(self._row_to_entry(row))
        return entries

    def find(self, entry_id):
        row = self.conn.execute("SELECT * FROM history_entries WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def save(self, entry):
        """Insert when the entry is new (id is None), otherwise update."""
        diagnosis = self.encryptor.encrypt(entry.diagnosis)
        notes = self.encryptor.encrypt(entry.treatment_notes)
        if entry.id is None:
            cursor = self.conn.execute(
                "INSERT INTO history_entries (patient_id, entry_date, diagnosis, treatment_notes) "
                "VALUES (?, ?, ?, ?)",
                (entry.patient_id, entry.entry_date, diagnosis, notes))
            entry.id = cursor.lastrowid
        else:
            self.conn.execute(
                "UPDATE history_entries SET entry_date = ?, diagnosis = ?, treatment_notes = ? WHERE id = ?",
                (entry.entry_date, diagnosis, notes, entry.id))
        self.conn.commit()

    def delete(self, entry_id):
        self.conn.execute("DELETE FROM history_entries WHERE id = ?", (entry_id,))
        self.conn.commit()

    def _row_to_entry(self, row):
        return HistoryEntry(
            id=row["id"],
            patient_id=row["patient_id"],
            entry_date=row["entry_date"],
            diagnosis=self.encryptor.decrypt(row["diagnosis"]),
            treatment_notes=self.encryptor.decrypt(row["treatment_notes"]),
        )


class AllergyRepository:
    def __init__(self, conn):
        self.conn = conn

    def list_for_patient(self, patient_id):
        rows = self.conn.execute(
            "SELECT * FROM allergies WHERE patient_id = ? ORDER BY allergen", (patient_id,)).fetchall()
        allergies = []
        for row in rows:
            allergies.append(self._row_to_allergy(row))
        return allergies

    def find(self, allergy_id):
        row = self.conn.execute("SELECT * FROM allergies WHERE id = ?", (allergy_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_allergy(row)

    def save(self, allergy):
        if allergy.id is None:
            cursor = self.conn.execute(
                "INSERT INTO allergies (patient_id, allergen, reaction, severity) VALUES (?, ?, ?, ?)",
                (allergy.patient_id, allergy.allergen, allergy.reaction, allergy.severity))
            allergy.id = cursor.lastrowid
        else:
            self.conn.execute(
                "UPDATE allergies SET allergen = ?, reaction = ?, severity = ? WHERE id = ?",
                (allergy.allergen, allergy.reaction, allergy.severity, allergy.id))
        self.conn.commit()

    def delete(self, allergy_id):
        self.conn.execute("DELETE FROM allergies WHERE id = ?", (allergy_id,))
        self.conn.commit()

    def _row_to_allergy(self, row):
        return Allergy(
            id=row["id"],
            patient_id=row["patient_id"],
            allergen=row["allergen"],
            reaction=row["reaction"],
            severity=row["severity"],
        )


class MedicationRepository:
    """Medications. name and dosage are encrypted in the database."""

    def __init__(self, conn, encryptor):
        self.conn = conn
        self.encryptor = encryptor

    def list_for_patient(self, patient_id):
        # Name is encrypted, so we can't ORDER BY it in SQL. Order by status then id.
        rows = self.conn.execute(
            "SELECT * FROM medications WHERE patient_id = ? ORDER BY status, id", (patient_id,)).fetchall()
        medications = []
        for row in rows:
            medications.append(self._row_to_medication(row))
        return medications

    def find(self, medication_id):
        row = self.conn.execute("SELECT * FROM medications WHERE id = ?", (medication_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_medication(row)

    def save(self, medication):
        name = self.encryptor.encrypt(medication.name)
        dosage = self.encryptor.encrypt(medication.dosage)
        if medication.id is None:
            cursor = self.conn.execute(
                "INSERT INTO medications (patient_id, name, dosage, frequency, status) VALUES (?, ?, ?, ?, ?)",
                (medication.patient_id, name, dosage, medication.frequency, medication.status))
            medication.id = cursor.lastrowid
        else:
            self.conn.execute(
                "UPDATE medications SET name = ?, dosage = ?, frequency = ?, status = ? WHERE id = ?",
                (name, dosage, medication.frequency, medication.status, medication.id))
        self.conn.commit()

    def delete(self, medication_id):
        self.conn.execute("DELETE FROM medications WHERE id = ?", (medication_id,))
        self.conn.commit()

    def _row_to_medication(self, row):
        return Medication(
            id=row["id"],
            patient_id=row["patient_id"],
            name=self.encryptor.decrypt(row["name"]),
            dosage=self.encryptor.decrypt(row["dosage"]),
            frequency=row["frequency"],
            status=row["status"],
        )
