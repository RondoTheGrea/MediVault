"""MediVault tests. Run with: python test.py (inside the active venv)."""
import csv
import io
import unittest

from cryptography.fernet import Fernet

import database
import seed
import validation
from access import (AccessControl, AccessDenied, AccessRequest, AuditTrail,
                    EmergencyAccess, RoutineAccess)
from models import HistoryEntry, Patient, Permission
from reports import ReportGenerator
from repositories import (AllergyRepository, HistoryRepository, MedicationRepository,
                          PatientRepository, RoleRepository, UserRepository)
from security import AuthManager, Encryptor


class MediVaultTests(unittest.TestCase):
    def setUp(self):
        # Every test starts fresh; the project's real database is never opened.
        self.conn = database.connect(":memory:")
        self.addCleanup(self.conn.close)
        database.create_tables(self.conn)
        self.encryptor = Encryptor(Fernet.generate_key())
        seed.seed_if_empty(self.conn, self.encryptor)
        self.patients = PatientRepository(self.conn)
        self.users = UserRepository(self.conn, RoleRepository(self.conn))
        self.history = HistoryRepository(self.conn, self.encryptor)
        self.allergies = AllergyRepository(self.conn)
        self.medications = MedicationRepository(self.conn, self.encryptor)
        self.audit = AuditTrail(self.conn)

    # -------------------- Login --------------------
    def test_login(self):
        auth = AuthManager(self.users)
        user = auth.login("admin", "Admin1234")
        self.assertEqual(user.username, "admin")
        self.assertNotEqual(user.get_password_hash(), "Admin1234")
        self.assertIsNone(auth.login("admin", "wrong-password"))
        self.assertIsNone(auth.login("unknown", "Admin1234"))
        self.users.set_active(user.id, False)
        self.assertIsNone(auth.login("admin", "Admin1234"))

    # -------------------- Permissions --------------------
    def test_role_permissions(self):
        nurse = self.users.find_by_username("nurse.cruz")
        AccessControl.require(nurse, Permission.VIEW_HISTORY)
        with self.assertRaises(AccessDenied):
            AccessControl.require(nurse, Permission.EDIT_HISTORY)
        nurse.is_active = False
        self.assertFalse(nurse.can(Permission.VIEW_HISTORY))

    # -------------------- Patient CRUD --------------------
    def test_patient_create_search_update_delete(self):
        patient = Patient(first_name="Test", last_name="Patient",
                          birth_date="2000-01-01", sex="Other", blood_type="AB+")
        self.patients.create(patient)
        self.assertEqual(self.patients.search("Test")[0].id, patient.id)
        patient.phone = "00000000000"
        self.patients.update(patient)
        self.assertEqual(self.patients.find(patient.id).phone, patient.phone)
        self.history.save(HistoryEntry(patient_id=patient.id, entry_date="2025-01-01",
                                       diagnosis="Demo assessment"))
        self.patients.delete(patient.id)
        self.assertIsNone(self.patients.find(patient.id))
        self.assertEqual(self.history.list_for_patient(patient.id), [])

    # -------------------- Form Validation --------------------
    def test_patient_validation(self):
        patient = self.patients.find(1)
        self.assertEqual(validation.validate_patient(patient), [])
        patient.birth_date = "not-a-date"
        patient.first_name = ""
        patient.blood_type = "invalid"
        self.assertEqual(len(validation.validate_patient(patient)), 3)

    # -------------------- Encryption --------------------
    def test_clinical_data_encryption(self):
        entry = self.history.list_for_patient(1)[0]
        stored = self.conn.execute("SELECT diagnosis FROM history_entries WHERE id = ?",
                                   (entry.id,)).fetchone()[0]
        self.assertNotEqual(stored, entry.diagnosis)
        self.assertEqual(self.encryptor.decrypt(stored), entry.diagnosis)
        medication = self.medications.list_for_patient(1)[0]
        stored = self.conn.execute("SELECT name FROM medications WHERE id = ?",
                                   (medication.id,)).fetchone()[0]
        self.assertNotEqual(stored, medication.name)
        self.assertEqual(self.encryptor.decrypt(stored), medication.name)

    # -------------------- Routine Access --------------------
    def test_routine_access_hides_restricted_sections(self):
        access = RoutineAccess(self.patients, self.history, self.allergies,
                               self.medications, self.audit)
        admin = self.users.find_by_username("admin")
        profile = access.open(AccessRequest(admin, 1, "Routine chart view"))
        self.assertIsNone(profile.history)
        self.assertIsNone(profile.allergies)
        self.assertIsNone(profile.medications)
        doctor = self.users.find_by_username("dr.reyes")
        self.assertTrue(access.open(AccessRequest(doctor, 1, "Chart review")).history)
        self.assertEqual(len(self.audit.search("routine")), 2)

    # -------------------- Emergency Access --------------------
    def test_emergency_access_requires_reason_and_logs_essentials(self):
        access = EmergencyAccess(self.patients, self.allergies, self.medications, self.audit)
        responder = self.users.find_by_username("medic.tan")
        with self.assertRaises(ValueError):
            access.open(AccessRequest(responder, 1, "short"))
        with self.assertRaises(AccessDenied):
            access.open(AccessRequest(self.users.find_by_username("admin"), 1,
                                      "Fictional emergency demonstration"))
        self.assertEqual(self.audit.search(), [])
        summary = access.open(AccessRequest(responder, 1, "Fictional emergency demonstration"))
        self.assertEqual({record.title() for record in summary.essential_records},
                         {"Peanuts", "Penicillin", "Metformin"})
        log = self.audit.search("emergency", "medic.tan")[0]
        self.assertEqual(log.patient_id, 1)
        self.assertEqual(log.reason, summary.reason)

    # -------------------- Additional Seed Records --------------------
    def test_additional_patient_seeds_are_valid_and_repeatable(self):
        patients = self.patients.search("")
        self.assertEqual(len(patients), 103)
        added = [p for p in patients if p.address.startswith("Fictional demo address ")]
        self.assertEqual(len(added), 100)
        self.assertEqual(len({(p.first_name, p.last_name) for p in added}), 100)
        for patient in added:
            self.assertEqual(validation.validate_patient(patient), [])
        self.assertEqual(seed.seed_additional_patients(self.conn), 0)
        self.assertEqual(len(self.patients.search("")), 103)

    # -------------------- Dashboard and CSV Export --------------------
    def test_dashboard_and_csv_export(self):
        reason = "Demo review, with a comma\nand a new line"
        self.audit.record(self.users.find_by_username("dr.reyes"), self.patients.find(1),
                          "routine", "view", reason)
        summary = ReportGenerator(self.conn).summary()
        self.assertEqual(summary["patients"], 103)
        self.assertEqual(summary["active_users"], 5)
        self.assertEqual(summary["routine_accesses"], 1)
        self.assertEqual(summary["emergency_accesses"], 0)
        rows = list(csv.DictReader(io.StringIO(ReportGenerator.logs_to_csv(self.audit.search()))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Username"], "dr.reyes")
        self.assertEqual(rows[0]["Reason"], reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
