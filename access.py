"""
Access control, access logging, and the two ways of opening a patient chart:
routine access and emergency access.
"""
from models import Permission, PatientProfile, EmergencySummary
from repositories import now_text

ROUTINE = "routine"
EMERGENCY = "emergency"

MIN_EMERGENCY_REASON_LENGTH = 10


class AccessDenied(Exception):
    """Raised when a user tries to do something their role does not allow."""


class AccessControl:
    """Central place for permission checks, so every screen enforces the same rules."""

    @staticmethod
    def require(user, permission_name):
        if not user.can(permission_name):
            raise AccessDenied("Your role does not allow this action (" + permission_name + ").")

    @staticmethod
    def require_any(user, permission_names):
        for permission_name in permission_names:
            if user.can(permission_name):
                return
        raise AccessDenied("Your role does not allow this action.")


class AccessLog:
    """One row of the audit trail."""

    def __init__(self, id, username, user_full_name, patient_id, patient_name,
                 access_type, action, reason, created_at):
        self.id = id
        self.username = username
        self.user_full_name = user_full_name
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.access_type = access_type
        self.action = action
        self.reason = reason
        self.created_at = created_at


class AuditTrail:
    """Writes and reads access logs. Logs are only ever added, never edited."""

    def __init__(self, conn):
        self.conn = conn

    def record(self, user, patient, access_type, action, reason):
        self.conn.execute(
            "INSERT INTO access_logs (user_id, patient_id, patient_name, access_type, action, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user.id, patient.id, patient.full_name(), access_type, action, reason, now_text()))
        self.conn.commit()

    def search(self, access_type="", username="", limit=500):
        """
        Filters are optional. We build the WHERE clause piece by piece, and
        still pass every value through "?" placeholders.
        """
        sql = ("SELECT l.*, u.username, u.full_name AS user_full_name FROM access_logs l "
               "JOIN users u ON u.id = l.user_id")
        conditions = []
        values = []
        if access_type != "":
            conditions.append("l.access_type = ?")
            values.append(access_type)
        if username != "":
            conditions.append("u.username LIKE ?")
            values.append("%" + username + "%")
        if len(conditions) > 0:
            sql = sql + " WHERE " + " AND ".join(conditions)
        sql = sql + " ORDER BY l.id DESC LIMIT ?"
        values.append(limit)

        rows = self.conn.execute(sql, values).fetchall()
        logs = []
        for row in rows:
            logs.append(AccessLog(row["id"], row["username"], row["user_full_name"],
                                  row["patient_id"], row["patient_name"], row["access_type"],
                                  row["action"], row["reason"], row["created_at"]))
        return logs


class AccessRequest:
    """Who wants to open which patient's chart, and why."""

    def __init__(self, user, patient_id, reason):
        self.user = user
        self.patient_id = patient_id
        self.reason = reason.strip()

    def validate_for_emergency(self):
        errors = []
        if len(self.reason) < MIN_EMERGENCY_REASON_LENGTH:
            errors.append("Please describe the emergency (at least "
                          + str(MIN_EMERGENCY_REASON_LENGTH) + " characters).")
        return errors


class RoutineAccess:
    """Normal chart view. Each section is shown only if the role allows it."""

    def __init__(self, patient_repository, history_repository, allergy_repository,
                 medication_repository, audit_trail):
        self.patients = patient_repository
        self.history = history_repository
        self.allergies = allergy_repository
        self.medications = medication_repository
        self.audit_trail = audit_trail

    def open(self, access_request):
        user = access_request.user
        AccessControl.require(user, Permission.VIEW_PATIENTS)

        patient = self.patients.find(access_request.patient_id)
        if patient is None:
            return None

        profile = PatientProfile(patient)
        if user.can(Permission.VIEW_HISTORY):
            profile.history = self.history.list_for_patient(patient.id)
        if user.can(Permission.VIEW_ALLERGIES):
            profile.allergies = self.allergies.list_for_patient(patient.id)
        if user.can(Permission.VIEW_MEDICATIONS):
            profile.medications = self.medications.list_for_patient(patient.id)

        self.audit_trail.record(user, patient, ROUTINE, "view", access_request.reason)
        return profile


class EmergencyAccess:
    """
    Break-glass access: shows only the essentials (allergies, current
    medications, blood type, emergency contact), even if the role normally
    cannot see them. A reason is mandatory and the event is logged as EMERGENCY.
    """

    def __init__(self, patient_repository, allergy_repository, medication_repository, audit_trail):
        self.patients = patient_repository
        self.allergies = allergy_repository
        self.medications = medication_repository
        self.audit_trail = audit_trail

    def open(self, access_request):
        user = access_request.user
        AccessControl.require(user, Permission.EMERGENCY_ACCESS)

        errors = access_request.validate_for_emergency()
        if len(errors) > 0:
            raise ValueError(errors[0])

        patient = self.patients.find(access_request.patient_id)
        if patient is None:
            return None

        all_records = []
        all_records.extend(self.allergies.list_for_patient(patient.id))
        all_records.extend(self.medications.list_for_patient(patient.id))

        # We don't care whether a record is an Allergy or a Medication here;
        # each object decides for itself whether it is essential.
        essential_records = []
        for record in all_records:
            if record.is_essential():
                essential_records.append(record)

        self.audit_trail.record(user, patient, EMERGENCY, "emergency view", access_request.reason)
        return EmergencySummary(patient, essential_records, access_request.reason, now_text())
