"""
Domain classes: the "things" MediVault works with.

These classes know nothing about Flask or SQL. They only hold data and the
rules that belong to that data. Saving/loading them is the job of
repositories.py.
"""
from datetime import date, datetime


class Permission:
    """Every permission name in the system, kept in one place so typos are caught early."""
    VIEW_PATIENTS = "view_patients"
    CREATE_PATIENTS = "create_patients"
    EDIT_PATIENTS = "edit_patients"
    DELETE_PATIENTS = "delete_patients"
    VIEW_HISTORY = "view_history"
    EDIT_HISTORY = "edit_history"
    VIEW_ALLERGIES = "view_allergies"
    EDIT_ALLERGIES = "edit_allergies"
    VIEW_MEDICATIONS = "view_medications"
    EDIT_MEDICATIONS = "edit_medications"
    EMERGENCY_ACCESS = "emergency_access"
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_USERS = "manage_users"


class Role:
    """A staff role (physician, nurse, ...) and the permissions it grants."""

    def __init__(self, id, name, display_name, permission_names):
        self.id = id
        self.name = name
        self.display_name = display_name
        # Encapsulation: the list is "private" (leading underscore). Other code
        # asks questions through can() instead of touching the list directly.
        self._permission_names = permission_names

    def can(self, permission_name):
        return permission_name in self._permission_names


class User:
    """A staff member who can log in."""

    def __init__(self, id, username, full_name, role, is_active, password_hash):
        self.id = id
        self.username = username
        self.full_name = full_name
        self.role = role
        self.is_active = is_active
        self._password_hash = password_hash

    def get_password_hash(self):
        return self._password_hash

    def can(self, permission_name):
        # A deactivated account can do nothing, whatever its role says.
        if not self.is_active:
            return False
        return self.role.can(permission_name)


class Patient:
    """A patient's demographic and identification information."""

    def __init__(self, id=None, first_name="", last_name="", birth_date="", sex="",
                 blood_type="", phone="", address="",
                 emergency_contact_name="", emergency_contact_phone=""):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.birth_date = birth_date
        self.sex = sex
        self.blood_type = blood_type
        self.phone = phone
        self.address = address
        self.emergency_contact_name = emergency_contact_name
        self.emergency_contact_phone = emergency_contact_phone

    def full_name(self):
        return self.first_name + " " + self.last_name

    def age(self):
        born = datetime.strptime(self.birth_date, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - born.year
        had_birthday_this_year = (today.month > born.month) or (
            today.month == born.month and today.day >= born.day)
        if not had_birthday_this_year:
            age = age - 1
        return age


class MedicalRecord:
    """
    Abstract base class for anything stored under a patient's chart.

    Subclasses MUST override kind(), title() and details(). This is how
    Python spells an "abstract method" (in Java/C# you would use the
    `abstract` keyword instead of raising NotImplementedError).
    """

    def __init__(self, id, patient_id):
        self.id = id
        self.patient_id = patient_id

    def kind(self):
        raise NotImplementedError

    def title(self):
        raise NotImplementedError

    def details(self):
        raise NotImplementedError

    def is_essential(self):
        """Should responders see this in an emergency? Most records: no."""
        return False


class HistoryEntry(MedicalRecord):
    """A past diagnosis or treatment note."""

    def __init__(self, id=None, patient_id=None, entry_date="", diagnosis="", treatment_notes=""):
        super().__init__(id, patient_id)
        self.entry_date = entry_date
        self.diagnosis = diagnosis
        self.treatment_notes = treatment_notes

    def kind(self):
        return "History"

    def title(self):
        return self.diagnosis

    def details(self):
        return self.entry_date + ": " + self.treatment_notes


class Allergy(MedicalRecord):
    def __init__(self, id=None, patient_id=None, allergen="", reaction="", severity=""):
        super().__init__(id, patient_id)
        self.allergen = allergen
        self.reaction = reaction
        self.severity = severity

    def kind(self):
        return "Allergy"

    def title(self):
        return self.allergen

    def details(self):
        return self.severity + " - " + self.reaction

    def is_essential(self):
        # Polymorphism: each subclass answers this question its own way.
        return True


class Medication(MedicalRecord):
    def __init__(self, id=None, patient_id=None, name="", dosage="", frequency="", status="current"):
        super().__init__(id, patient_id)
        self.name = name
        self.dosage = dosage
        self.frequency = frequency
        self.status = status

    def kind(self):
        return "Medication"

    def title(self):
        return self.name

    def details(self):
        return self.dosage + ", " + self.frequency

    def is_essential(self):
        # Only medications the patient is CURRENTLY taking matter in an emergency.
        return self.status == "current"


class PatientProfile:
    """
    A patient plus the sections of their chart that the viewer may see.
    A section set to None means "hidden for your role".
    """

    def __init__(self, patient):
        self.patient = patient
        self.history = None
        self.allergies = None
        self.medications = None


class EmergencySummary:
    """What a responder sees during emergency access: only the essentials."""

    def __init__(self, patient, essential_records, reason, accessed_at):
        self.patient = patient
        self.essential_records = essential_records
        self.reason = reason
        self.accessed_at = accessed_at
