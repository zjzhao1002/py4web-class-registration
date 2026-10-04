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

from py4web import action, redirect, HTTP, URL
from py4web.utils.grid import Column, Grid, GridClassStyleBulma
from py4web.utils.form import Form, FormStyleBulma

from .common import T, auth, cache, db, session, Field
from yatl.helpers import A, SPAN

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
            db.course_section.capacity,
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
