"""
This file defines the database models
"""
import datetime
from pydal.validators import *

from .common import Field, db

### Define your table below
#
# db.define_table('thing', Field('name'))
#
## always commit your models to avoid problems later
#
# db.commit()
#

def get_time():
    return datetime.datetime.now()

db.define_table(
    "student",
    Field(fieldname="user_id", type="reference auth_user",
          notnull=True, unique=True,
          requires=[IS_IN_DB(db, "auth_user.id"), IS_NOT_IN_DB(db, "student.user_id")]),
    Field(fieldname="student_id", type="string",
          notnull=True, unique=True,
          requires=[IS_NOT_EMPTY(), IS_NOT_IN_DB(db, "student.student_id")]),
    Field(fieldname="department", type="string"),
    Field(fieldname="major", type="string")
)

db.define_table(
    "course",
    Field(fieldname="number", type="string", notnull=True, unique=True),
    Field(fieldname="name", type="string"),
    Field(fieldname="description", type="text")
)

db.define_table(
    "quarter",
    Field(fieldname="year", type="integer", notnull=True,
          requires=IS_INT_IN_RANGE(1, 10000)),
    Field(fieldname="season", type="string", notnull=True,
          requires=IS_IN_SET(["Spring", "Summer", "Autumn", "Winter"])),
)

db.executesql("""
    CREATE UNIQUE INDEX IF NOT EXISTS quarter_year_season
    ON quarter (year, season)
""")

db.define_table(
    "course_section",
    Field(fieldname="course_id", type="reference course", notnull=True),
    Field(fieldname="quarter_id", type="reference quarter", notnull=True, ondelete="CASCADE"),
    Field(fieldname="section_number", type="string", notnull=True),
    Field(fieldname="instructor", type="string", notnull=True),
    Field(fieldname="active", type="boolean", default=True, notnull=True),
    Field(fieldname="capacity", type="integer", notnull=True,
          requires=IS_INT_IN_RANGE(0, 51))
)

# Enforce section uniqueness in the configured SQLite database.
db.executesql("""
    CREATE UNIQUE INDEX IF NOT EXISTS course_section_course_quarter_section
    ON course_section (course_id, quarter_id, section_number)
""")

db.define_table(
    "meeting_time",
    Field(fieldname="section_id", type="reference course_section", notnull=True),
    Field(fieldname="day_of_week", type="string", notnull=True,
          requires=IS_IN_SET(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])),
    Field(fieldname="start_time", type="time", notnull=True),
    Field(fieldname="end_time", type="time", notnull=True),
    Field(fieldname="location", type="string", notnull=True)
)

db.define_table(
    "registration",
    Field(fieldname="student_id", type="reference student", notnull=True),
    Field(fieldname="course_section_id", type="reference course_section", notnull=True),
    Field(fieldname="status", type="string", notnull=True, default="enrolled",
          requires=IS_IN_SET(["enrolled", "waitlisted", "dropped"])),
    Field(fieldname="message", type="text"),
    Field(fieldname="registration_date", type="datetime", notnull=True,
          default=get_time, writable=False),
)

db.executesql("""
    CREATE UNIQUE INDEX IF NOT EXISTS registration_student_course_section
    ON registration (student_id, course_section_id)
""")

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


db.executesql("""
    CREATE INDEX IF NOT EXISTS registration_section_status_date
    ON registration (course_section_id, status, registration_date, id)
""")

# SQLite triggers protect cross-field rules for both forms and direct DAL writes.
# Adjacent meetings are allowed; overlapping meetings in different sections are
# allowed because this does not represent a room or student scheduling policy.
for operation in ("INSERT", "UPDATE"):
    db.executesql(f"""
        CREATE TRIGGER IF NOT EXISTS meeting_time_valid_{operation.lower()}
        BEFORE {operation} ON meeting_time
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'Meeting end time must be after start time')
            WHERE time(NEW.start_time) IS NULL
               OR time(NEW.end_time) IS NULL
               OR time(NEW.start_time) >= time(NEW.end_time);

            SELECT RAISE(ABORT, 'Meetings in the same section cannot overlap')
            WHERE EXISTS (
                SELECT 1 FROM meeting_time AS existing
                WHERE existing.section_id = NEW.section_id
                  AND existing.day_of_week = NEW.day_of_week
                  AND existing.id != NEW.id
                  AND time(existing.start_time) < time(NEW.end_time)
                  AND time(existing.end_time) > time(NEW.start_time)
            );
        END
    """)

db.commit()
