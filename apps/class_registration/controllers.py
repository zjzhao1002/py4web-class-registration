"""
This file defines actions, i.e. functions the URLs are mapped into
The @action(path) decorator exposed the function at URL:

    http://127.0.0.1:8000/{app_name}/{path}

If app_name == '_default' then simply

    http://127.0.0.1:8000/{path}

If path == 'index' it can be omitted:

    http://127.0.0.1:8000/

The path follows the bottlepy syntax.

@action.uses('generic.html')  indicates that the action uses the generic.html template
@action.uses(session)         indicates that the action uses the session
@action.uses(db)              indicates that the action uses the db
@action.uses(T)               indicates that the action uses the i18n & pluralization
@action.uses(auth.user)       indicates that the action requires a logged in user
@action.uses(auth)            indicates that the action requires the auth object

session, db, T, auth, and tempates are examples of Fixtures.
Warning: Fixtures MUST be declared with @action.uses({fixtures}) else your app will result in undefined behavior
"""
import datetime
from py4web import action, redirect, HTTP, URL, request
from py4web.utils.grid import Grid, GridClassStyleBulma
from py4web.utils.form import Form, FormStyleBulma

from .common import T, auth, cache, db, session, Field
from yatl.helpers import A, SPAN

def GridRegisterButton(row):
    registration = db(
        (db.student.user_id == auth.user_id)
        & (db.registration.student_id == db.student.id)
        & (db.registration.class_offering_id == row.id)
        & (db.registration.status.belongs(["enrolled", "waitlisted"]))
    ).select(db.registration.id, limitby=(0, 1)).first()
    if not registration and not row.active:
        return SPAN("Closed", _class="button", _aria_disabled="true")
    return A(
        "Cancel" if registration else "Register",
        _href=URL("register", row.id),
        _class="button is-danger" if registration else "button is-primary",
    )

@action("index")
@action.uses("index.html", auth, T)
def index():
    user = auth.get_user()
    if user:
        message = T("Hello {first_name}! Click the Registration button to start registering classes.").format(
            first_name=user.get("first_name", "")
        )
    else:
        message = T("Hello! Please login to register classes.")
    return dict(message=message, user=user)

@action("offerings", method=["GET", "POST"])
@action.uses("offerings.html", auth.user, db)
def offerings():
    if not db(db.student.user_id == auth.user_id).select(db.student.id).first():
        redirect(URL("student_profile"))
    grid = Grid(
        query=db.class_offering.id > 0,
        search_queries="auto",
        search_form=None,
        editable=False, 
        deletable=False,
        details=False,
        create=False,
        grid_class_style=GridClassStyleBulma,
        formstyle=FormStyleBulma,
        post_action_buttons=[GridRegisterButton]
    )
    return dict(grid=grid)

@action("student_profile", method=["GET", "POST"])
@action("student_profile/<offering_id:int>", method=["GET", "POST"])
@action.uses("student_profile.html", db, session, auth.user)
def student_profile(offering_id=None):
    if offering_id is not None and db.class_offering[offering_id] is None:
        raise HTTP(404)
    destination = URL("register", offering_id) if offering_id is not None else URL("offerings")
    if db(db.student.user_id == auth.user_id).select(db.student.id).first():
        redirect(destination)
    form = Form(
        [Field("suid", label="SUID", requires=db.student.suid.requires)],
        form_name="student_profile",
        csrf_session=session,
        formstyle=FormStyleBulma,
        submit_value="Continue to registration",
    )
    if form.accepted:
        result = db.student.validate_and_insert(
            user_id=auth.user_id, suid=form.vars["suid"]
        )
        if result.get("errors"):
            form.errors.update(result["errors"])
            form.accepted = False
        else:
            redirect(destination)
    return dict(form=form)

@action("register/<offering_id:int>", method=["GET", "POST"])
@action.uses("register.html", db, session, auth.user)
def register(offering_id=None):
    if request.method == "POST":
        # SQLite serializes writers. Lock before reading registrations/capacity
        # so concurrent requests cannot both claim the last available seat.
        db(db.class_offering.id == offering_id).update(
            capacity=db.class_offering.capacity
        )
    offering_info = db(
        (db.class_offering.id == offering_id) &
        (db.class_offering.quarter_id == db.quarter.id) &
        (db.class_offering.catalog_class_id == db.catalog_class.id)
    ).select().first()
    if offering_info is None:
        raise HTTP(404)
    student = db(db.student.user_id == auth.user_id).select().first()
    if student is None:
        redirect(URL("student_profile", offering_id))
    registration = db(
        (db.registration.student_id == student.id)
        & (db.registration.class_offering_id == offering_id)
    ).select().first()
    cancelling = registration is not None and registration.status in ("enrolled", "waitlisted")
    if not cancelling and not offering_info.class_offering.active:
        raise HTTP(403, "Registration for this class is closed.")
    form = Form([] if cancelling else [Field(fieldname="note", type="text")],
                form_name=f"{'cancel' if cancelling else 'register'}_{offering_id}",
                csrf_session=session, 
                formstyle=FormStyleBulma,
                submit_value="Cancel registration" if cancelling else "Register",
                )
    form.param.sidecar.append(SPAN(" ", A('Back', _class="button", _href=URL('offerings'))))
    if form.accepted:
        if cancelling:
            registration.update_record(status="dropped")
        else:
            enrolled_count = db(
                (db.registration.class_offering_id == offering_id)
                & (db.registration.status == "enrolled")
            ).count()
            values = dict(
                status=("enrolled" if enrolled_count < offering_info.class_offering.capacity
                        else "waitlisted"),
                note=form.vars["note"],
                registration_date=datetime.datetime.now(),
            )
            if registration:
                registration.update_record(**values)
            else:
                db.registration.insert(
                    student_id=student.id,
                    class_offering_id=offering_id,
                    **values,
                )
        redirect(URL("offerings"))
    return dict(offering_info=offering_info, form=form, cancelling=cancelling)
