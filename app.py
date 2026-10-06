"""
MediVault - web routes.

Each route follows the same simple steps:
  1. check permission
  2. load what is needed from a repository
  3. on POST: read the form, validate, save, log, redirect
  4. otherwise: render a template

Run with:  flask --app app run --debug
"""
import os

from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for

import database
import seed
import validation
from access import (EMERGENCY, ROUTINE, AccessControl, AccessDenied, AccessRequest,
                    AuditTrail, EmergencyAccess, RoutineAccess)
from models import Allergy, HistoryEntry, Medication, Patient, Permission
from reports import ReportGenerator
from repositories import (AllergyRepository, HistoryRepository, MedicationRepository,
                          PatientRepository, RoleRepository, UserRepository)
from security import AuthManager, Encryptor, load_or_create_key

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
os.makedirs(database.INSTANCE_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = load_or_create_key(os.path.join(database.INSTANCE_DIR, "session.key"))
# "Lax" means the browser won't send our login cookie along with a form that
# another website submits to us, which blocks cross-site form attacks.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

encryptor = Encryptor(load_or_create_key(os.path.join(database.INSTANCE_DIR, "encryption.key")))

startup_conn = database.connect()
database.create_tables(startup_conn)
seed.seed_if_empty(startup_conn, encryptor)
startup_conn.close()

# Pages you can open without being logged in.
PUBLIC_ENDPOINTS = ["login", "static"]


# ---------------------------------------------------------------------------
# Database connection and repositories (one connection per request)
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = database.connect()
    return g.db


@app.teardown_appcontext
def close_db(error):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def role_repository():
    return RoleRepository(get_db())


def user_repository():
    return UserRepository(get_db(), role_repository())


def patient_repository():
    return PatientRepository(get_db())


def history_repository():
    return HistoryRepository(get_db(), encryptor)


def allergy_repository():
    return AllergyRepository(get_db())


def medication_repository():
    return MedicationRepository(get_db(), encryptor)


def audit_trail():
    return AuditTrail(get_db())


def find_patient_or_404(patient_id):
    patient = patient_repository().find(patient_id)
    if patient is None:
        abort(404)
    return patient


def find_record_or_404(repository, record_id, patient_id):
    """
    Works with any repository that has a find() method (history, allergy or
    medication). Also stops someone from editing patient 2's record through
    patient 1's URL.
    """
    record = repository.find(record_id)
    if record is None or record.patient_id != patient_id:
        abort(404)
    return record


def form_text(name):
    """Read a text field from the submitted form, trimmed of spaces."""
    return request.form.get(name, "").strip()


# ---------------------------------------------------------------------------
# Runs before every request: who is logged in?
# ---------------------------------------------------------------------------
@app.before_request
def load_logged_in_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = user_repository().find_by_id(user_id)
        if user is not None and user.is_active:
            g.user = user
        else:
            session.clear()

    if g.user is None and request.endpoint not in PUBLIC_ENDPOINTS:
        return redirect(url_for("login"))


@app.context_processor
def template_helpers():
    """Values every template can use."""
    return {
        "Permission": Permission,
        "SEX_CHOICES": validation.SEX_CHOICES,
        "BLOOD_TYPE_CHOICES": validation.BLOOD_TYPE_CHOICES,
        "SEVERITY_CHOICES": validation.SEVERITY_CHOICES,
        "MEDICATION_STATUS_CHOICES": validation.MEDICATION_STATUS_CHOICES,
    }


# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------
@app.errorhandler(AccessDenied)
def handle_access_denied(error):
    return render_template("error.html", title="Access denied", message=str(error)), 403


@app.errorhandler(404)
def handle_not_found(error):
    return render_template("error.html", title="Not found",
                           message="That page or record does not exist."), 404


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if g.user.can(Permission.VIEW_DASHBOARD):
        return redirect(url_for("dashboard"))
    return redirect(url_for("patient_list"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        auth = AuthManager(user_repository())
        user = auth.login(form_text("username"), request.form.get("password", ""))
        if user is None:
            flash("Invalid username or password.", "error")
        else:
            # Start a fresh session so an old session id can't be reused.
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------
@app.route("/patients")
def patient_list():
    AccessControl.require_any(g.user, [Permission.VIEW_PATIENTS, Permission.EMERGENCY_ACCESS])
    search_text = request.args.get("q", "").strip()
    patients = patient_repository().search(search_text)
    return render_template("patients.html", patients=patients, search_text=search_text)


@app.route("/patients/new", methods=["GET", "POST"])
@app.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
def patient_form(patient_id=None):
    if patient_id is None:
        AccessControl.require(g.user, Permission.CREATE_PATIENTS)
        patient = Patient()
    else:
        AccessControl.require(g.user, Permission.EDIT_PATIENTS)
        patient = find_patient_or_404(patient_id)

    errors = []
    if request.method == "POST":
        patient.first_name = form_text("first_name")
        patient.last_name = form_text("last_name")
        patient.birth_date = form_text("birth_date")
        patient.sex = form_text("sex")
        patient.blood_type = form_text("blood_type")
        patient.phone = form_text("phone")
        patient.address = form_text("address")
        patient.emergency_contact_name = form_text("emergency_contact_name")
        patient.emergency_contact_phone = form_text("emergency_contact_phone")
        errors = validation.validate_patient(patient)
        if len(errors) == 0:
            if patient.id is None:
                patient_repository().create(patient)
                audit_trail().record(g.user, patient, ROUTINE, "create", "Registered patient")
            else:
                patient_repository().update(patient)
                audit_trail().record(g.user, patient, ROUTINE, "update", "Edited patient profile")
            flash("Patient saved.", "success")
            return redirect(url_for("patient_detail", patient_id=patient.id))

    return render_template("patient_form.html", patient=patient, errors=errors)


@app.route("/patients/<int:patient_id>")
def patient_detail(patient_id):
    access = RoutineAccess(patient_repository(), history_repository(), allergy_repository(),
                           medication_repository(), audit_trail())
    profile = access.open(AccessRequest(g.user, patient_id, "Routine chart view"))
    if profile is None:
        abort(404)
    return render_template("patient_detail.html", profile=profile)


@app.route("/patients/<int:patient_id>/delete", methods=["POST"])
def patient_delete(patient_id):
    AccessControl.require(g.user, Permission.DELETE_PATIENTS)
    patient = find_patient_or_404(patient_id)
    # Log first, while the patient still exists.
    audit_trail().record(g.user, patient, ROUTINE, "delete", "Deleted patient and all records")
    patient_repository().delete(patient_id)
    flash(patient.full_name() + " was deleted.", "success")
    return redirect(url_for("patient_list"))


# ---------------------------------------------------------------------------
# Emergency access
# ---------------------------------------------------------------------------
@app.route("/patients/<int:patient_id>/emergency", methods=["GET", "POST"])
def emergency_access(patient_id):
    AccessControl.require(g.user, Permission.EMERGENCY_ACCESS)
    patient = find_patient_or_404(patient_id)
    reason = ""
    errors = []

    if request.method == "POST":
        reason = form_text("reason")
        access_request = AccessRequest(g.user, patient_id, reason)
        errors = access_request.validate_for_emergency()
        if len(errors) == 0:
            access = EmergencyAccess(patient_repository(), allergy_repository(),
                                     medication_repository(), audit_trail())
            summary = access.open(access_request)
            return render_template("emergency_view.html", summary=summary)

    return render_template("emergency_form.html", patient=patient, reason=reason, errors=errors)


# ---------------------------------------------------------------------------
# Medical history, allergies, medications
# Each has one route for add + edit (same form) and one for delete.
# ---------------------------------------------------------------------------
@app.route("/patients/<int:patient_id>/history/new", methods=["GET", "POST"])
@app.route("/patients/<int:patient_id>/history/<int:entry_id>/edit", methods=["GET", "POST"])
def history_form(patient_id, entry_id=None):
    AccessControl.require(g.user, Permission.EDIT_HISTORY)
    patient = find_patient_or_404(patient_id)
    repository = history_repository()
    if entry_id is None:
        entry = HistoryEntry(patient_id=patient_id)
    else:
        entry = find_record_or_404(repository, entry_id, patient_id)

    errors = []
    if request.method == "POST":
        entry.entry_date = form_text("entry_date")
        entry.diagnosis = form_text("diagnosis")
        entry.treatment_notes = form_text("treatment_notes")
        errors = validation.validate_history_entry(entry)
        if len(errors) == 0:
            repository.save(entry)
            audit_trail().record(g.user, patient, ROUTINE, "save", "Medical history entry")
            flash("Medical history saved.", "success")
            return redirect(url_for("patient_detail", patient_id=patient_id))

    return render_template("history_form.html", patient=patient, entry=entry, errors=errors)


@app.route("/patients/<int:patient_id>/history/<int:entry_id>/delete", methods=["POST"])
def history_delete(patient_id, entry_id):
    AccessControl.require(g.user, Permission.EDIT_HISTORY)
    patient = find_patient_or_404(patient_id)
    repository = history_repository()
    find_record_or_404(repository, entry_id, patient_id)
    repository.delete(entry_id)
    audit_trail().record(g.user, patient, ROUTINE, "delete", "Medical history entry")
    return redirect(url_for("patient_detail", patient_id=patient_id))


@app.route("/patients/<int:patient_id>/allergies/new", methods=["GET", "POST"])
@app.route("/patients/<int:patient_id>/allergies/<int:allergy_id>/edit", methods=["GET", "POST"])
def allergy_form(patient_id, allergy_id=None):
    AccessControl.require(g.user, Permission.EDIT_ALLERGIES)
    patient = find_patient_or_404(patient_id)
    repository = allergy_repository()
    if allergy_id is None:
        allergy = Allergy(patient_id=patient_id)
    else:
        allergy = find_record_or_404(repository, allergy_id, patient_id)

    errors = []
    if request.method == "POST":
        allergy.allergen = form_text("allergen")
        allergy.reaction = form_text("reaction")
        allergy.severity = form_text("severity")
        errors = validation.validate_allergy(allergy)
        if len(errors) == 0:
            repository.save(allergy)
            audit_trail().record(g.user, patient, ROUTINE, "save", "Allergy")
            flash("Allergy saved.", "success")
            return redirect(url_for("patient_detail", patient_id=patient_id))

    return render_template("allergy_form.html", patient=patient, allergy=allergy, errors=errors)


@app.route("/patients/<int:patient_id>/allergies/<int:allergy_id>/delete", methods=["POST"])
def allergy_delete(patient_id, allergy_id):
    AccessControl.require(g.user, Permission.EDIT_ALLERGIES)
    patient = find_patient_or_404(patient_id)
    repository = allergy_repository()
    find_record_or_404(repository, allergy_id, patient_id)
    repository.delete(allergy_id)
    audit_trail().record(g.user, patient, ROUTINE, "delete", "Allergy")
    return redirect(url_for("patient_detail", patient_id=patient_id))


@app.route("/patients/<int:patient_id>/medications/new", methods=["GET", "POST"])
@app.route("/patients/<int:patient_id>/medications/<int:medication_id>/edit", methods=["GET", "POST"])
def medication_form(patient_id, medication_id=None):
    AccessControl.require(g.user, Permission.EDIT_MEDICATIONS)
    patient = find_patient_or_404(patient_id)
    repository = medication_repository()
    if medication_id is None:
        medication = Medication(patient_id=patient_id)
    else:
        medication = find_record_or_404(repository, medication_id, patient_id)

    errors = []
    if request.method == "POST":
        medication.name = form_text("name")
        medication.dosage = form_text("dosage")
        medication.frequency = form_text("frequency")
        medication.status = form_text("status")
        errors = validation.validate_medication(medication)
        if len(errors) == 0:
            repository.save(medication)
            audit_trail().record(g.user, patient, ROUTINE, "save", "Medication")
            flash("Medication saved.", "success")
            return redirect(url_for("patient_detail", patient_id=patient_id))

    return render_template("medication_form.html", patient=patient, medication=medication, errors=errors)


@app.route("/patients/<int:patient_id>/medications/<int:medication_id>/delete", methods=["POST"])
def medication_delete(patient_id, medication_id):
    AccessControl.require(g.user, Permission.EDIT_MEDICATIONS)
    patient = find_patient_or_404(patient_id)
    repository = medication_repository()
    find_record_or_404(repository, medication_id, patient_id)
    repository.delete(medication_id)
    audit_trail().record(g.user, patient, ROUTINE, "delete", "Medication")
    return redirect(url_for("patient_detail", patient_id=patient_id))


# ---------------------------------------------------------------------------
# Admin: dashboard and audit log
# ---------------------------------------------------------------------------
@app.route("/admin/dashboard")
def dashboard():
    AccessControl.require(g.user, Permission.VIEW_DASHBOARD)
    return render_template("dashboard.html",
                           summary=ReportGenerator(get_db()).summary(),
                           recent_emergencies=audit_trail().search(EMERGENCY, "", 10))


@app.route("/admin/audit")
def audit_log():
    AccessControl.require(g.user, Permission.VIEW_AUDIT_LOGS)
    access_type = request.args.get("type", "")
    username = request.args.get("user", "").strip()
    logs = audit_trail().search(access_type, username)
    return render_template("audit_log.html", logs=logs, access_type=access_type, username=username)


@app.route("/admin/audit.csv")
def audit_log_csv():
    AccessControl.require(g.user, Permission.VIEW_AUDIT_LOGS)
    logs = audit_trail().search(request.args.get("type", ""), request.args.get("user", "").strip(), 100000)
    return Response(ReportGenerator.logs_to_csv(logs), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=medivault_audit_log.csv"})


# ---------------------------------------------------------------------------
# Admin: users
# ---------------------------------------------------------------------------
@app.route("/admin/users")
def user_list():
    AccessControl.require(g.user, Permission.MANAGE_USERS)
    return render_template("users.html", users=user_repository().list_all())


@app.route("/admin/users/new", methods=["GET", "POST"])
def user_new():
    AccessControl.require(g.user, Permission.MANAGE_USERS)
    users = user_repository()
    roles = role_repository()
    username = ""
    full_name = ""
    role_id = ""
    errors = []

    if request.method == "POST":
        username = form_text("username").lower()
        full_name = form_text("full_name")
        role_id = form_text("role_id")
        password = request.form.get("password", "")

        role = None
        if role_id.isdigit():
            role = roles.find_by_id(int(role_id))
        username_taken = users.find_by_username(username) is not None

        errors = validation.validate_new_user(username, full_name, password, role, username_taken)
        if len(errors) == 0:
            users.create(username, full_name, AuthManager.hash_password(password), role.id)
            flash("User " + username + " created.", "success")
            return redirect(url_for("user_list"))

    return render_template("user_form.html", username=username, full_name=full_name,
                           role_id=role_id, roles=roles.list_all(), errors=errors)


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
def user_toggle_active(user_id):
    AccessControl.require(g.user, Permission.MANAGE_USERS)
    if user_id == g.user.id:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("user_list"))
    users = user_repository()
    user = users.find_by_id(user_id)
    if user is None:
        abort(404)
    users.set_active(user_id, not user.is_active)
    return redirect(url_for("user_list"))


if __name__ == "__main__":
    app.run(debug=True)
