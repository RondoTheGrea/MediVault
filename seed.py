"""
Fills an empty database with roles, permissions, demo users and demo patients.
Existing demo patients also receive missing medical-record sections on startup.
"""
from models import Permission, Patient, HistoryEntry, Allergy, Medication
from repositories import (RoleRepository, UserRepository, PatientRepository,
                          HistoryRepository, AllergyRepository, MedicationRepository)
from security import AuthManager

ALL_PERMISSIONS = [
    Permission.VIEW_PATIENTS, Permission.CREATE_PATIENTS, Permission.EDIT_PATIENTS,
    Permission.DELETE_PATIENTS, Permission.VIEW_HISTORY, Permission.EDIT_HISTORY,
    Permission.VIEW_ALLERGIES, Permission.EDIT_ALLERGIES, Permission.VIEW_MEDICATIONS,
    Permission.EDIT_MEDICATIONS, Permission.EMERGENCY_ACCESS, Permission.VIEW_DASHBOARD,
    Permission.VIEW_AUDIT_LOGS, Permission.MANAGE_USERS,
]

# role name, display name, permissions
DEFAULT_ROLES = [
    ["admin", "Administrator", [
        Permission.VIEW_PATIENTS, Permission.VIEW_DASHBOARD, Permission.VIEW_AUDIT_LOGS,
        Permission.MANAGE_USERS,
    ]],
    ["physician", "Physician", [
        Permission.VIEW_PATIENTS, Permission.EDIT_PATIENTS,
        Permission.VIEW_HISTORY, Permission.EDIT_HISTORY,
        Permission.VIEW_ALLERGIES, Permission.EDIT_ALLERGIES,
        Permission.VIEW_MEDICATIONS, Permission.EDIT_MEDICATIONS,
        Permission.EMERGENCY_ACCESS,
    ]],
    ["nurse", "Nurse", [
        Permission.VIEW_PATIENTS, Permission.VIEW_HISTORY,
        Permission.VIEW_ALLERGIES, Permission.EDIT_ALLERGIES,
        Permission.VIEW_MEDICATIONS, Permission.EDIT_MEDICATIONS,
        Permission.EMERGENCY_ACCESS,
    ]],
    ["records_staff", "Records Staff", [
        Permission.VIEW_PATIENTS, Permission.CREATE_PATIENTS,
        Permission.EDIT_PATIENTS, Permission.DELETE_PATIENTS,
    ]],
    ["emergency_responder", "Emergency Responder", [
        Permission.EMERGENCY_ACCESS,
    ]],
]

# username, full name, password, role name
DEMO_USERS = [
    ["admin", "Alice Admin", "Admin1234", "admin"],
    ["dr.reyes", "Dr. Jose Reyes", "Doctor1234", "physician"],
    ["nurse.cruz", "Ana Cruz, RN", "Nurse1234", "nurse"],
    ["records.lim", "Ben Lim", "Records1234", "records_staff"],
    ["medic.tan", "Carlo Tan", "Medic1234", "emergency_responder"],
]


def seed_if_empty(conn, encryptor):
    roles = RoleRepository(conn)
    if len(roles.list_all()) > 0:
        seed_additional_medical_records(conn, encryptor)
        return

    for permission_name in ALL_PERMISSIONS:
        roles.create_permission(permission_name)

    for role in DEFAULT_ROLES:
        roles.create(role[0], role[1], role[2])

    users = UserRepository(conn, roles)
    for demo_user in DEMO_USERS:
        role = roles.find_by_name(demo_user[3])
        users.create(demo_user[0], demo_user[1], AuthManager.hash_password(demo_user[2]), role.id)

    seed_patients(conn, encryptor)


def seed_patients(conn, encryptor):
    patients = PatientRepository(conn)
    history = HistoryRepository(conn, encryptor)
    allergies = AllergyRepository(conn)
    medications = MedicationRepository(conn, encryptor)

    juan = Patient(first_name="Juan", last_name="Dela Cruz", birth_date="1980-05-14", sex="Male",
                   blood_type="O+", phone="0917 123 4567", address="12 Mabini St, Manila",
                   emergency_contact_name="Rosa Dela Cruz (wife)",
                   emergency_contact_phone="0917 765 4321")
    patients.create(juan)
    history.save(HistoryEntry(patient_id=juan.id, entry_date="2019-03-02",
                              diagnosis="Type 2 diabetes mellitus",
                              treatment_notes="Started on metformin. Diet counselling given."))
    history.save(HistoryEntry(patient_id=juan.id, entry_date="2021-08-19",
                              diagnosis="Acute appendicitis",
                              treatment_notes="Laparoscopic appendectomy, uneventful recovery."))
    allergies.save(Allergy(patient_id=juan.id, allergen="Penicillin",
                           reaction="Hives and throat swelling", severity="Severe"))
    allergies.save(Allergy(patient_id=juan.id, allergen="Peanuts",
                           reaction="Anaphylaxis", severity="Life-threatening"))
    medications.save(Medication(patient_id=juan.id, name="Metformin", dosage="500 mg",
                                frequency="Twice daily", status="current"))
    medications.save(Medication(patient_id=juan.id, name="Cefuroxime", dosage="500 mg",
                                frequency="Twice daily for 7 days", status="past"))

    maria = Patient(first_name="Maria", last_name="Santos", birth_date="1992-11-02", sex="Female",
                    blood_type="A-", phone="0918 222 3344", address="45 Rizal Ave, Quezon City",
                    emergency_contact_name="Luis Santos (brother)",
                    emergency_contact_phone="0918 555 6677")
    patients.create(maria)
    history.save(HistoryEntry(patient_id=maria.id, entry_date="2005-06-10",
                              diagnosis="Bronchial asthma",
                              treatment_notes="Mild persistent. Reliever inhaler prescribed."))
    allergies.save(Allergy(patient_id=maria.id, allergen="Latex",
                           reaction="Contact rash", severity="Moderate"))
    medications.save(Medication(patient_id=maria.id, name="Salbutamol inhaler", dosage="100 mcg, 2 puffs",
                                frequency="As needed", status="current"))

    pedro = Patient(first_name="Pedro", last_name="Garcia", birth_date="1955-01-20", sex="Male",
                    blood_type="B+", phone="0919 888 9900", address="7 Luna St, Pasig",
                    emergency_contact_name="Carmen Garcia (daughter)",
                    emergency_contact_phone="0919 111 2233")
    patients.create(pedro)
    history.save(HistoryEntry(patient_id=pedro.id, entry_date="2010-04-05",
                              diagnosis="Hypertension",
                              treatment_notes="Lifestyle changes and losartan."))
    history.save(HistoryEntry(patient_id=pedro.id, entry_date="2018-12-11",
                              diagnosis="Myocardial infarction",
                              treatment_notes="PCI with stent to LAD. On dual antiplatelet therapy."))
    medications.save(Medication(patient_id=pedro.id, name="Losartan", dosage="50 mg",
                                frequency="Once daily", status="current"))
    medications.save(Medication(patient_id=pedro.id, name="Aspirin", dosage="81 mg",
                                frequency="Once daily", status="current"))
    medications.save(Medication(patient_id=pedro.id, name="Clopidogrel", dosage="75 mg",
                                frequency="Once daily", status="current"))

    seed_additional_patients(conn)
    seed_additional_medical_records(conn, encryptor)


def seed_additional_patients(conn):
    """Add 100 fictional patient profiles, skipping profiles already seeded.

    Can also be called against an existing database without resetting it.
    Medical records are added separately by seed_additional_medical_records.
    """
    first_names = [
        ("Adrian", "Male"), ("Bianca", "Female"),
        ("Carlo", "Male"), ("Diana", "Female"),
        ("Emilio", "Male"), ("Francesca", "Female"),
        ("Gabriel", "Male"), ("Helena", "Female"),
        ("Isaac", "Male"), ("Julia", "Female"),
    ]
    last_names = [
        "Aquino", "Bautista", "Castillo", "Domingo", "Enriquez",
        "Flores", "Gonzales", "Herrera", "Ignacio", "Jimenez",
    ]
    blood_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", ""]
    patients = PatientRepository(conn)
    existing = {
        (p.first_name, p.last_name, p.birth_date, p.address)
        for p in patients.search("")
    }
    added = 0
    for family_index, last_name in enumerate(last_names):
        for given_index, (first_name, sex) in enumerate(first_names):
            index = family_index * len(first_names) + given_index
            number = index + 1
            birth_date = "{:04d}-{:02d}-{:02d}".format(
                1945 + (index * 7) % 65, 1 + index % 12, 1 + (index * 3) % 28)
            address = "Fictional demo address {:03d}, Manila".format(number)
            identity = (first_name, last_name, birth_date, address)
            if identity in existing:
                continue
            patients.create(Patient(
                first_name=first_name,
                last_name=last_name,
                birth_date=birth_date,
                sex=sex,
                blood_type=blood_types[index % len(blood_types)],
                phone="0000{:07d}".format(number),
                address=address,
                emergency_contact_name="Demo Emergency Contact {:03d}".format(number),
                emergency_contact_phone="0000{:07d}".format(100 + number),
            ))
            existing.add(identity)
            added += 1
    return added


def seed_additional_medical_records(conn, encryptor):
    """Fill empty clinical sections for the 100 generated demo patients only.

    Existing sections are preserved, so repeated startup does not duplicate data.
    Repository saves apply the same encryption used by the application.
    """
    history = HistoryRepository(conn, encryptor)
    allergies = AllergyRepository(conn)
    medications = MedicationRepository(conn, encryptor)
    conditions = [
        ("Hypertension", "Blood pressure monitoring and lifestyle counselling.",
         "Losartan", "50 mg", "Once daily"),
        ("Type 2 diabetes mellitus", "Blood glucose monitoring and diet counselling.",
         "Metformin", "500 mg", "Twice daily"),
        ("Bronchial asthma", "Reviewed inhaler technique and symptom monitoring.",
         "Salbutamol inhaler", "100 mcg, 2 puffs", "As needed"),
        ("Allergic rhinitis", "Reviewed symptoms and avoidance of known triggers.",
         "Cetirizine", "10 mg", "Once daily"),
    ]
    allergy_options = [
        ("Penicillin", "Hives", "Moderate"),
        ("Peanuts", "Anaphylaxis", "Life-threatening"),
        ("Latex", "Contact rash", "Mild"),
        ("Shellfish", "Itching and rash", "Moderate"),
    ]
    for patient in PatientRepository(conn).search(""):
        prefix = "Fictional demo address "
        if not patient.address.startswith(prefix):
            continue
        try:
            number = int(patient.address[len(prefix):].split(",")[0])
        except ValueError:
            continue
        if not 1 <= number <= 100:
            continue
        index = number - 1
        diagnosis, notes, name, dosage, frequency = conditions[index % len(conditions)]
        if not conn.execute("SELECT 1 FROM history_entries WHERE patient_id = ?",
                            (patient.id,)).fetchone():
            history.save(HistoryEntry(patient_id=patient.id, entry_date="2025-06-15",
                                      diagnosis=diagnosis, treatment_notes=notes))
            history.save(HistoryEntry(patient_id=patient.id, entry_date="2026-03-10",
                                      diagnosis=diagnosis + " follow-up",
                                      treatment_notes="Reviewed symptoms and ongoing treatment."))
        if not conn.execute("SELECT 1 FROM allergies WHERE patient_id = ?",
                            (patient.id,)).fetchone():
            allergen, reaction, severity = allergy_options[index % len(allergy_options)]
            allergies.save(Allergy(patient_id=patient.id, allergen=allergen,
                                   reaction=reaction, severity=severity))
        if not conn.execute("SELECT 1 FROM medications WHERE patient_id = ?",
                            (patient.id,)).fetchone():
            medications.save(Medication(patient_id=patient.id, name=name, dosage=dosage,
                                        frequency=frequency, status="current"))
            medications.save(Medication(patient_id=patient.id, name="Paracetamol", dosage="500 mg",
                                        frequency="As needed for fever", status="past"))
