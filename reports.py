"""
Numbers and exports for the admin dashboard.
"""
import csv
import io
from datetime import date

from access import EMERGENCY, ROUTINE


class ReportGenerator:
    def __init__(self, conn):
        self.conn = conn

    def _count(self, sql, values):
        return self.conn.execute(sql, values).fetchone()[0]

    def summary(self):
        today_pattern = date.today().strftime("%Y-%m-%d") + "%"
        return {
            "patients": self._count("SELECT COUNT(*) FROM patients", ()),
            "active_users": self._count("SELECT COUNT(*) FROM users WHERE is_active = 1", ()),
            "routine_accesses": self._count(
                "SELECT COUNT(*) FROM access_logs WHERE access_type = ?", (ROUTINE,)),
            "emergency_accesses": self._count(
                "SELECT COUNT(*) FROM access_logs WHERE access_type = ?", (EMERGENCY,)),
            "accesses_today": self._count(
                "SELECT COUNT(*) FROM access_logs WHERE created_at LIKE ?", (today_pattern,)),
        }

    @staticmethod
    def logs_to_csv(logs):
        """Turn a list of AccessLog objects into CSV text (opens in Excel)."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Time", "Username", "User", "Patient ID", "Patient",
                         "Access type", "Action", "Reason"])
        for log in logs:
            writer.writerow([log.created_at, log.username, log.user_full_name, log.patient_id,
                             log.patient_name, log.access_type, log.action, log.reason])
        return output.getvalue()
