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
from py4web.utils.grid import Column, Grid, GridClassStyleBulma
from py4web.utils.form import Form, FormStyleBulma

from .common import T, auth, cache, db, session, Field
from yatl.helpers import A, SPAN

def other_registered_section(student_id, section):
    return db(
        (db.registration.student_id == student_id)
        & (db.registration.status.belongs(["enrolled", "waitlisted"]))
        & (db.registration.course_section_id == db.course_section.id)
        & (db.course_section.course_id == section.course_id)
        & (db.course_section.id != section.id)
    ).select(db.course_section.ALL, limitby=(0, 1)).first()

def GridRegisterButton(row):
    section = row.course_section
    registration = db(
        (db.student.user_id == auth.user_id)
        & (db.registration.student_id == db.student.id)
        & (db.registration.course_section_id == section.id)
        & (db.registration.status.belongs(["enrolled", "waitlisted"]))
    ).select(db.registration.id, limitby=(0, 1)).first()
    if not registration and not section.active:
        return SPAN("Closed", _class="button", _aria_disabled="true")
    return A(
        "Cancel" if registration else "Register",
        _href=URL("register", section.id),
        _class="button is-danger" if registration else "button is-primary",
    )

# A waitlist is a view of registrations, not a second source of enrollment state.
# Positions are one-based and are recomputed after cancellations/promotions.
def get_waitlist(course_section_id):
    rows = db(
        (db.registration.course_section_id == course_section_id)
        & (db.registration.status == "waitlisted")
    ).select(
        db.registration.ALL,
        orderby=db.registration.registration_date | db.registration.id,
    )
    return [dict(row.as_dict(), position=position)
            for position, row in enumerate(rows, start=1)]

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

@action("sections", method=["GET", "POST"])
@action.uses("sections.html", auth.user, db, session, auth.flash)
def sections():
    if not db(db.student.user_id == auth.user_id).select(db.student.id).first():
        auth.flash.set("Please add your student ID to your profile first.")
        session["_next_profile"] = URL("sections")
        redirect(URL("auth/profile"))
    enrolled_count = db.registration.id.count()
    enrolled_by_section = {
        row.registration.course_section_id: row[enrolled_count]
        for row in db(db.registration.status == "enrolled").select(
            db.registration.course_section_id,
            enrolled_count,
            groupby=db.registration.course_section_id,
        )
    }
    grid = Grid(
        query=(db.course_section.id > 0)
              & (db.course_section.course_id == db.course.id)
              & (db.course_section.quarter_id == db.quarter.id)
              & (db.course_section.id == db.meeting_time.section_id),
        columns=[
            db.course_section.id,
            Column(
                "Course Section",
                represent=lambda row: f"{row.course.number}-{row.course_section.section_number}",
                required_fields=[db.course.number, db.course_section.section_number],
                orderby=db.course.number | db.course_section.section_number,
            ),
            db.course.name,
            Column(
                "Quarter",
                represent=lambda row: f"{row.quarter.year} {row.quarter.season}",
                required_fields=[db.quarter.year, db.quarter.season],
                orderby=db.quarter.year | db.quarter.season,
            ),
            db.course_section.instructor,
            Column(
                "Time",
                represent=lambda row: (
                    f"{row.meeting_time.day_of_week} "
                    f"{row.meeting_time.start_time:%H:%M}-{row.meeting_time.end_time:%H:%M}"
                ),
                required_fields=[db.meeting_time.day_of_week, db.meeting_time.start_time, db.meeting_time.end_time],
                orderby=db.meeting_time.day_of_week | db.meeting_time.start_time | db.meeting_time.end_time
            ),
            db.meeting_time.location,
            db.course_section.active,
            Column(
                "Available Seats",
                represent=lambda row: max(
                    0, row.course_section.capacity
                    - enrolled_by_section.get(row.course_section.id, 0)
                ),
                required_fields=[db.course_section.id, db.course_section.capacity],
                col_type="integer",
            ),
        ],
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

@action("register/<section_id:int>", method=["GET", "POST"])
@action.uses("register.html", db, session, auth.user, auth.flash)
def register(section_id=None):
    if request.method == "POST":
        # SQLite serializes writers. Lock before reading registrations/capacity
        # so concurrent requests cannot both claim the last available seat.
        db(db.course_section.id == section_id).update(
            capacity=db.course_section.capacity
        )
    section_info = db(
        (db.course_section.id == section_id) 
        & (db.course_section.quarter_id == db.quarter.id)
        & (db.course_section.course_id == db.course.id) 
    ).select().first()
    if section_info is None:
        raise HTTP(404)
    student = db(db.student.user_id == auth.user_id).select().first()
    if student is None:
        redirect(URL("auth/profile"))
    registration = db(
       (db.registration.student_id == student.id)
        & (db.registration.course_section_id == section_id)
    ).select().first()
    cancelling = registration is not None and registration.status in ("enrolled", "waitlisted")
    if not cancelling:
        existing_section = other_registered_section(student.id, section_info.course_section)
        if existing_section:
            auth.flash.set(
                f"You are already registered or waitlisted for {section_info.course.number}-"
                f"{existing_section.section_number}. Cancel that registration before "
                "registering for another section of this course."
            )
            redirect(URL("sections"))
    if not cancelling and not section_info.course_section.active:
        raise HTTP(403, "Registration for this course is closed.")
    form = Form([] if cancelling else [Field(fieldname="message", type="text")],
                form_name=f"{'cancel' if cancelling else 'register'}_{section_id}",
                csrf_session=session, 
                formstyle=FormStyleBulma,
                submit_value="Cancel registration" if cancelling else "Register",
                )
    form.param.sidecar.append(SPAN(" ", A('Back', _class="button", _href=URL('sections'))))
    if form.accepted:
        if cancelling:
            registration.update_record(status="dropped")
        else:
            enrolled_count = db(
                (db.registration.course_section_id == section_id)
                & (db.registration.status == "enrolled")
            ).count()
            values = dict(
                status=("enrolled" if enrolled_count < section_info.course_section.capacity
                        else "waitlisted"),
                message=form.vars["message"],
                registration_date=datetime.datetime.now(),
            )
            if registration:
                registration.update_record(**values)
            else:
                db.registration.insert(
                    student_id=student.id,
                    course_section_id=section_id,
                    **values,
                )
            if values["status"] == "waitlisted":
                position = next(
                    entry["position"] for entry in get_waitlist(section_id)
                    if entry["student_id"] == student.id
                )
                auth.flash.set(
                    f"You have been added to the waitlist. Your position is {position}."
                )
            else:
                auth.flash.set(
                    f"You have successfully registered for the {section_info.course.number}-"
                    f"{section_info.course_section.section_number} {section_info.course.name}."
                )
        redirect(URL("sections"))
    return dict(section_info=section_info, form=form, cancelling=cancelling)
