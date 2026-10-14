# MediVault

Secure medical information management with role-based access control and
logged emergency ("break-glass") access. Built with Flask and SQLite.

## How to Run it

```
pip install -r requirements.txt
.venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --debug
```

Open http://127.0.0.1:5000. On the first run, `instance/` is created with the
database, the encryption key and demo data. Delete `instance/` to start over.

| Username    | Password    | Role                |
|-------------|-------------|---------------------|
| admin       | Admin1234   | Administrator       |
| dr.reyes    | Doctor1234  | Physician           |
| nurse.cruz  | Nurse1234   | Nurse               |
| records.lim | Records1234 | Records Staff       |
| medic.tan   | Medic1234   | Emergency Responder |

## Where things are

| File               | What it does                                                        | Classes from the proposal |
|--------------------|---------------------------------------------------------------------|---------------------------|
| `models.py`        | Domain classes: plain data plus the rules that belong to it         | User, Role, Permission, Patient, PatientProfile, MedicalRecord, HistoryEntry, Allergy, Medication |
| `repositories.py`  | The only place with SQL for these objects                          | (data access layer)       |
| `access.py`        | Permission checks, audit log, routine and emergency access          | AccessControl, AccessRequest, EmergencyAccess, AccessLog, AuditTrail |
| `security.py`      | Password hashing (bcrypt), login, field encryption (Fernet)         | AuthManager               |
| `reports.py`       | Dashboard numbers and CSV export                                   | ReportGenerator           |
| `validation.py`    | Form checks; each function returns a list of errors                |                           |
| `database.py`      | SQLite connection and table definitions                            |                           |
| `seed.py`          | Default roles and permissions, demo users and patients             |                           |
| `app.py`           | Flask routes (the web pages)                                        |                           |
| `templates/`, `static/` | HTML pages and the stylesheet                                 |                           |

## OOP in this project

- **Encapsulation:** `Role._permission_names` and `User._password_hash` are private. Other code calls `can()` or `get_password_hash()` instead of reading them directly.
- **Inheritance:** `HistoryEntry`, `Allergy` and `Medication` extend `MedicalRecord`.
- **Polymorphism:** the emergency view calls `record.is_essential()`, `kind()`, `title()` and `details()` without checking the record's type.
- **Abstraction:** `MedicalRecord` is an abstract base class. It defines *what* its subclasses must do, not *how*.

## Differences from the proposal

- SQLite instead of MySQL. The SQL is standard; to switch, change `AUTOINCREMENT` to `AUTO_INCREMENT` and swap the connection in `database.py`.
- Login sessions are written by hand instead of using Flask-Login, so you can see how they work. Forms are validated in `validation.py` instead of with Flask-WTF.
- Cross-site form attacks are blocked by the `SameSite=Lax` session cookie rather than per-form tokens.
- The audit log exports to CSV (it opens in Excel), not to PDF with reportlab.

## Why it matters

Many small clinics still keep patient records on paper or in scattered files.
Those records are slow to search and easy to lose. That becomes dangerous in an
emergency, when a patient may be unconscious or unable to speak and responders
have only minutes to learn about a life-threatening allergy or a medication
that could interact with treatment.

Medical records are also some of the most sensitive personal data there is, so
making them easy to reach cannot mean letting everyone see everything. MediVault
handles both needs:

- **Fast access when it counts.** Emergency access shows a patient's allergies,
  current medications, blood type and emergency contact on one screen.
- **Privacy the rest of the time.** Each role sees only what its job needs. For
  example, records staff can register patients but cannot read diagnoses, and
  responders see only the emergency essentials.
- **Accountability.** Every view and change, routine or emergency, is logged with
  who did it, when and why. Emergency access requires a written reason, so it
  can be reviewed later and is hard to misuse without leaving a trace.
- **Protection if data leaks.** Passwords are hashed, and diagnoses, treatment
  notes and medications are encrypted. A copied database file is unreadable
  without the key.

MediVault does not diagnose or recommend treatment. It keeps the right
information in front of the right people, and records every time someone looks.
