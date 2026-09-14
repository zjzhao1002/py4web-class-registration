"""
This file defines the database models
"""
import datetime
from pydal.validators import *

from .common import Field, db, auth

### Define your table below
#
# db.define_table('thing', Field('name'))
#
## always commit your models to avoid problems later
#
# db.commit()
#
def get_user_email():
    return auth.current_user.get('email') if auth.current_user else None

def get_time():
    return datetime.datetime.now()

db.define_table(
    "catalog_class",
    Field(fieldname="number", type="string"),
    Field(fieldname="name", type="string"), 
    Field(fieldname="description", type="text"),
)

db.define_table(
    "quarter",
    Field(fieldname="year", type="integer", notnull=True,
          requires=IS_INT_IN_RANGE(1, 10000)),
    Field(fieldname="season", 
          type="string", notnull=True,
          requires=IS_IN_SET(["Spring", "Summer", "Autumn", "Winter"])),
)

db.executesql("""
    CREATE UNIQUE INDEX IF NOT EXISTS quarter_year_season
    ON quarter (year, season)
""")

db.define_table(
    "class_offering", 
    Field(fieldname="catalog_class_id", type="reference catalog_class", notnull=True),
    Field(fieldname="quarter_id", type="reference quarter", notnull=True, ondelete="CASCADE"),
    Field(fieldname="section_number", type="integer", notnull=True),
    Field(fieldname="active", type="boolean", default=True, notnull=True),
    Field(fieldname="capacity", type="integer", notnull=True,
          requires=IS_INT_IN_RANGE(0, None)),
)

# Enforce section uniqueness in the configured SQLite database.
db.executesql("""
    CREATE UNIQUE INDEX IF NOT EXISTS class_offering_class_quarter_section
    ON class_offering (catalog_class_id, quarter_id, section_number)
""")

db.define_table(
    "student",
    Field(fieldname="user_id", type="reference auth_user",
          notnull=True, unique=True,
          requires=[IS_IN_DB(db, "auth_user.id"),
                    IS_NOT_IN_DB(db, "student.user_id")]),
    Field(fieldname="suid", type="string",
          notnull=True, unique=True,
          requires=[IS_NOT_EMPTY(), IS_NOT_IN_DB(db, "student.suid")]),
)

db.define_table(
    "registration", 
    Field(fieldname="student_id", type="reference student", notnull=True),
    Field(fieldname="class_offering_id", type="reference class_offering", notnull=True),
    Field(fieldname="status", type="string", notnull=True, default="enrolled",
          requires=IS_IN_SET(["enrolled", "waitlisted", "dropped"])),
    Field(fieldname="note", type="text"), 
    Field(fieldname="registration_date", type="datetime", notnull=True,
          default=get_time, writable=False),
)

# Derive waitlist positions by ordering waitlisted rows by registration_date, then id.
db.executesql("""
    CREATE UNIQUE INDEX IF NOT EXISTS registration_student_offering
    ON registration (student_id, class_offering_id)
""")

db.commit()
