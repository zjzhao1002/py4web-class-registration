"""Check registration guards and waitlist positions using the real models."""
import ast
import datetime
from pathlib import Path
import unittest

import test_models


class SectionRegistrationTests(unittest.TestCase):
    def setUp(self):
        test_models.ModelIntegrityTests.setUp(self)
        path = Path(__file__).resolve().parents[1] / "apps/class_registration/controllers.py"
        tree = ast.parse(path.read_text())
        tree.body = [node for node in tree.body
                     if isinstance(node, ast.FunctionDef)
                     and node.name in ("other_registered_section", "get_waitlist")]
        namespace = {"db": self.db}
        exec(compile(tree, str(path), "exec"), namespace)
        self.find_other = namespace["other_registered_section"]
        self.get_waitlist = namespace["get_waitlist"]
        section = self.db.course_section[self.section]
        self.other = self.db.course_section.insert(
            course_id=section.course_id, quarter_id=section.quarter_id,
            section_number="2", instructor="Teacher", capacity=10)

    def test_waitlist_order_and_contiguous_positions(self):
        register = lambda *args, **kwargs: test_models.ModelIntegrityTests.register(
            self, *args, **kwargs)
        first = register("first")
        second = register("second")
        earlier = register("earlier", date=datetime.datetime(2026, 10, 3, 9))
        register("enrolled", status="enrolled")
        rows = self.get_waitlist(self.section)
        self.assertEqual([row["id"] for row in rows], [earlier, first, second])
        self.assertEqual([row["position"] for row in rows], [1, 2, 3])
        self.db.registration[earlier].update_record(status="dropped")
        self.db.registration[first].update_record(status="enrolled")
        rows = self.get_waitlist(self.section)
        self.assertEqual([(row["id"], row["position"]) for row in rows], [(second, 1)])
        self.assertEqual(self.get_waitlist(-1), [])

    def test_enrolled_and_waitlisted_block_until_dropped(self):
        registration_id = test_models.ModelIntegrityTests.register(self, "student", status="enrolled")
        registration = self.db.registration[registration_id]
        target = self.db.course_section[self.other]
        for status in ("enrolled", "waitlisted"):
            registration.update_record(status=status)
            self.assertEqual(self.find_other(registration.student_id, target).id, self.section)
        registration.update_record(status="dropped")
        self.assertIsNone(self.find_other(registration.student_id, target))

    def test_current_section_other_students_and_other_courses_do_not_block(self):
        registration_id = test_models.ModelIntegrityTests.register(self, "student", status="enrolled")
        student_id = self.db.registration[registration_id].student_id
        self.assertIsNone(self.find_other(student_id, self.db.course_section[self.section]))
        self.assertIsNone(self.find_other(-1, self.db.course_section[self.other]))
        course = self.db.course.insert(number="CS102")
        self.db.course_section[self.other].update_record(course_id=course)
        self.assertIsNone(self.find_other(student_id, self.db.course_section[self.other]))
