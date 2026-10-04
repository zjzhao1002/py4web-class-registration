import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from py4web.utils.form import FormStyleDefault
import test_models


path = Path(__file__).resolve().parents[1] / "apps/class_registration/profile_forms.py"
spec = importlib.util.spec_from_file_location("student_profile_forms", path)
profile_forms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile_forms)
form_module = importlib.import_module("py4web.utils.form")


class ProfileFormTests(unittest.TestCase):
    def setUp(self):
        test_models.ModelIntegrityTests.setUp(self)
        self.user_id = self.db.auth_user.insert(
            email="student@example.com", username="original",
            first_name="First", last_name="Last")
        self.auth = SimpleNamespace(
            db=self.db, user_id=self.user_id, session={}, flash=Mock(),
            param=SimpleNamespace(
                exclude_extra_fields_in_profile=None,
                formstyle=FormStyleDefault,
                messages={"buttons": {"submit": "Save"},
                          "flash": {"profile-saved": "Profile saved"}}))
        self.forms = profile_forms.StudentAuthForms(self.auth)
        self.forms._postprocessing = Mock()

    def get_form(self, payload=None):
        payload = payload or {}
        with patch.object(form_module, "request", SimpleNamespace(
                POST=payload, forms=payload, files={})):
            return self.forms.profile()

    def submit(self, student_id="S001", **overrides):
        form = self.get_form()
        payload = dict(
            _formname=form.form_name, _formkey=form.formkey,
            email="student@example.com", first_name="Updated", last_name="Last",
            student_id=student_id, department="Engineering", major="CS")
        payload.update(overrides)
        return self.get_form(payload)

    def test_create_then_edit_linked_student(self):
        # Student and account primary keys are independent.
        other = self.db.auth_user.insert(email="other@example.com")
        self.db.student.insert(user_id=other, student_id="OTHER")
        self.assertTrue(self.submit().accepted)
        student = self.db(self.db.student.user_id == self.user_id).select().first()
        self.assertEqual((student.student_id, student.department, student.major),
                         ("S001", "Engineering", "CS"))
        self.assertEqual(self.db.auth_user[self.user_id].first_name, "Updated")
        form = self.get_form()
        self.assertEqual(form.vars["student_id"], "S001")
        self.assertTrue(self.submit(major="Math").accepted)
        self.assertEqual(self.db(self.db.student.user_id == self.user_id).count(), 1)
        self.assertEqual(self.db.student[student.id].major, "Math")

    def test_duplicate_and_empty_student_ids_do_not_save_account(self):
        other = self.db.auth_user.insert(email="other@example.com")
        self.db.student.insert(user_id=other, student_id="TAKEN")
        for student_id in ("TAKEN", ""):
            with self.subTest(student_id=student_id):
                form = self.submit(student_id)
                self.assertFalse(form.accepted)
                self.assertIn("student_id", form.errors)
                self.assertEqual(self.db.auth_user[self.user_id].first_name, "First")
        self.assertEqual(self.db(self.db.student.user_id == self.user_id).count(), 0)

    def test_post_cannot_change_identity_or_other_student(self):
        other = self.db.auth_user.insert(email="other@example.com")
        other_student = self.db.student.insert(user_id=other, student_id="OTHER")
        form = self.submit(user_id=other, id=other, username="tampered")
        self.assertTrue(form.accepted)
        self.assertEqual(self.db.auth_user[self.user_id].username, "original")
        self.assertEqual(self.db.student[other_student].student_id, "OTHER")
        self.assertEqual(self.db(self.db.student.user_id == self.user_id).count(), 1)

    def test_invalid_csrf_does_not_save(self):
        form = self.submit(_formkey="invalid")
        self.assertFalse(form.accepted)
        self.assertEqual(self.db(self.db.student).count(), 0)


if __name__ == "__main__":
    unittest.main()
