"""Account profile form including the linked student record."""
from pydal.validators import IS_NOT_EMPTY
from py4web.utils.auth import DefaultAuthForms
from py4web.utils.form import Form


class StudentAuthForms(DefaultAuthForms):
    def profile(self, model=False):
        # Keep the built-in account API model; the combined form uses HTML POST.
        if model:
            return super().profile(model=True)

        db = self.auth.db
        user = db.auth_user[self.auth.user_id]
        student = db(db.student.user_id == user.id).select().first()
        locked_field = "username" if "username" in db.auth_user.fields else "email"
        excluded = self.auth.param.exclude_extra_fields_in_profile or []
        account_fields = []
        for field in db.auth_user:
            if field.readable and field.type != "id" and field.name not in excluded:
                profile_field = field.clone()
                profile_field.writable = field.writable and field.name != locked_field
                account_fields.append(profile_field)
        student_fields = [
            db.student.student_id.clone(),
            db.student.department.clone(),
            db.student.major.clone(),
        ]
        student_fields[0].label = "Student ID"
        student_fields[0].requires = IS_NOT_EMPTY()
        record = user.as_dict()
        record.update({name: student[name] if student else ""
                       for name in ("student_id", "department", "major")})

        def validate_student(form):
            if "student_id" in form.errors:
                return
            duplicate = db(
                (db.student.student_id == form.vars.get("student_id"))
                & (db.student.user_id != user.id)
            ).select(db.student.id, limitby=(0, 1)).first()
            if duplicate:
                form.errors["student_id"] = "This student ID is already in use"

        form = Form(
            account_fields + student_fields,
            record=record,
            dbio=False,
            deletable=False,
            form_name="account_student_profile",
            csrf_session=self.auth.session,
            validation=validate_student,
            formstyle=self.formstyle,
            submit_value=self.auth.param.messages["buttons"]["submit"],
        )
        if form.accepted:
            user.update_record(**{field.name: form.vars[field.name]
                                  for field in account_fields if field.writable})
            values = {field.name: form.vars[field.name] for field in student_fields}
            if student:
                student.update_record(**values)
            else:
                db.student.insert(user_id=user.id, **values)
            self._set_flash("profile-saved")
            self._postprocessing("profile", form, user)
        return form
