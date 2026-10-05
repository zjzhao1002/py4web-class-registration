"""Exercise the real model definitions without opening the application database."""
import ast
import datetime
from pathlib import Path
import sqlite3
import unittest

from pydal import DAL, Field


class ModelIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = DAL("sqlite:memory")
        self.addCleanup(self.db.close)
        self.db.define_table("auth_user", Field("email"), Field("username"),
                             Field("first_name"), Field("last_name"))
        path = Path(__file__).resolve().parents[1] / "apps/class_registration/models.py"
        tree = ast.parse(path.read_text(), filename=str(path))
        # Supply fixtures ourselves instead of importing common.py and starting auth.
        tree.body = [node for node in tree.body
                     if not (isinstance(node, ast.ImportFrom)
                             and node.level == 1 and node.module == "common")]
        self.namespace = {"db": self.db, "Field": Field}
        exec(compile(tree, str(path), "exec"), self.namespace)
        course = self.db.course.insert(number="C101")
        quarter = self.db.quarter.insert(year=2026, season="Autumn")
        self.section = self.db.course_section.insert(
            course_id=course, quarter_id=quarter, section_number="1",
            instructor="Teacher", capacity=50)

    def register(self, identifier, status="waitlisted", date=None):
        user = self.db.auth_user.insert(email=f"{identifier}@example.com")
        student = self.db.student.insert(user_id=user, student_id=identifier)
        return self.db.registration.insert(
            student_id=student, course_section_id=self.section, status=status,
            registration_date=date or datetime.datetime(2026, 10, 4, 9))

    def meeting(self, start="09:00:00", end="10:00:00", day="Monday"):
        return self.db.meeting_time.insert(
            section_id=self.section, day_of_week=day,
            start_time=start, end_time=end, location="Room A")

    def test_registration_cannot_be_duplicated(self):
        registration = self.db.registration[self.register("student")]
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.registration.insert(student_id=registration.student_id,
                                        course_section_id=self.section)

    def test_invalid_meeting_intervals(self):
        for start, end in [("10:00:00", "09:00:00"),
                           ("09:00:00", "09:00:00")]:
            with self.subTest(start=start, end=end):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "after start"):
                    self.meeting(start, end)

    def test_overlaps_rejected_but_adjacent_and_other_days_allowed(self):
        self.meeting()
        for start, end in [("09:30:00", "10:30:00"),
                           ("08:00:00", "11:00:00"),
                           ("09:15:00", "09:45:00")]:
            with self.subTest(start=start, end=end):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "overlap"):
                    self.meeting(start, end)
        self.meeting("10:00:00", "11:00:00")
        self.meeting(day="Tuesday")

    def test_meeting_updates_checked_and_self_excluded(self):
        first = self.meeting()
        second = self.meeting("10:00:00", "11:00:00")
        self.db.meeting_time[first].update_record(location="Room B")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "after start"):
            self.db(self.db.meeting_time.id == first).update(end_time="08:00:00")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "overlap"):
            self.db(self.db.meeting_time.id == second).update(start_time="09:30:00")

    def test_other_sections_can_share_meeting_times(self):
        self.meeting()
        section = self.db.course_section[self.section]
        other = self.db.course_section.insert(
            course_id=section.course_id, quarter_id=section.quarter_id,
            section_number="2", instructor="Teacher", capacity=10)
        self.db.meeting_time.insert(section_id=other, day_of_week="Monday",
                                    start_time="09:00:00", end_time="10:00:00",
                                    location="Room B")


if __name__ == "__main__":
    unittest.main()
