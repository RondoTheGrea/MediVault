"""
Input validation. Each validate_* function returns a list of error messages.
An empty list means the input is valid.
"""
from datetime import date, datetime

SEX_CHOICES = ["Male", "Female", "Other"]
BLOOD_TYPE_CHOICES = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
SEVERITY_CHOICES = ["Mild", "Moderate", "Severe", "Life-threatening"]
MEDICATION_STATUS_CHOICES = ["current", "past"]
MIN_PASSWORD_LENGTH = 8


def check_required(text, label, errors):
    if text.strip() == "":
        errors.append(label + " is required.")


def check_past_date(text, label, errors):
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        errors.append(label + " must be a valid date.")
        return
    if parsed > date.today():
        errors.append(label + " cannot be in the future.")


def validate_patient(patient):
    errors = []
    check_required(patient.first_name, "First name", errors)
    check_required(patient.last_name, "Last name", errors)
    check_past_date(patient.birth_date, "Birth date", errors)
    if patient.sex not in SEX_CHOICES:
        errors.append("Please choose a sex.")
    if patient.blood_type not in BLOOD_TYPE_CHOICES:
        errors.append("Unknown blood type.")
    return errors


def validate_history_entry(entry):
    errors = []
    check_past_date(entry.entry_date, "Date", errors)
    check_required(entry.diagnosis, "Diagnosis", errors)
    return errors


def validate_allergy(allergy):
    errors = []
    check_required(allergy.allergen, "Allergen", errors)
    check_required(allergy.reaction, "Reaction", errors)
    if allergy.severity not in SEVERITY_CHOICES:
        errors.append("Please choose a severity.")
    return errors


def validate_medication(medication):
    errors = []
    check_required(medication.name, "Medication name", errors)
    check_required(medication.dosage, "Dosage", errors)
    check_required(medication.frequency, "Frequency", errors)
    if medication.status not in MEDICATION_STATUS_CHOICES:
        errors.append("Status must be current or past.")
    return errors


def validate_new_user(username, full_name, password, role, username_taken):
    errors = []
    check_required(username, "Username", errors)
    if username_taken:
        errors.append("That username is already taken.")
    check_required(full_name, "Full name", errors)
    if role is None:
        errors.append("Please choose a role.")
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append("Password must be at least " + str(MIN_PASSWORD_LENGTH) + " characters.")
    return errors
