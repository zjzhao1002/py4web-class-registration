# Class registration with py4web

A demo class registration app built with Python, [py4web](https://py4web.com/), and SQLite. It demonstrates authentication, student profiles, database models, grids, CSRF-protected forms, and capacity-based enrollment.

## Run locally

Requirements: Python 3.13 or newer and `uv`. Run these commands from the repository root:

```sh
uv sync
uv run py4web set_password
uv run py4web run apps
```

`set_password` creates a local password for the py4web dashboard; it is separate from student account passwords.

Open <http://127.0.0.1:8000/class_registration/>. To run in development mode, use `uv run py4web run apps --dev`; this disables signup email verification and relaxes password complexity requirements. After signing up, log in manually.

SQLite tables are created automatically on first load. Data is stored in `apps/class_registration/databases/storage.db`. Local database files, `password.txt`, and private settings are ignored by Git.

## Usage

Sample courses, quarters, sections, and meeting times can be added to the local database through the [py4web dashboard](http://127.0.0.1:8000/_dashboard/). Add at least one meeting time for each section so it appears in the sections grid. Course data is local and is not included in a fresh Git checkout.

1. Sign up and log in.
2. Click **Registration** on the home page.
3. Open **Edit Profile** and enter a unique, nonempty **Student ID**, plus your department and major. Saving creates or updates the student record linked to your account. Users without a student record are sent to this page before browsing sections.
4. Find a class in the sections grid, check **Available Seats**, click **Register**, optionally leave a note, and submit the form.
5. To withdraw, click **Cancel** beside the class and confirm cancellation.

After completing a profile prompted by the sections page, the app returns the user to sections. There is no separate `student_profile` page.

Available seats are the section's capacity minus its enrolled students, with a minimum of zero. Waitlisted and dropped registrations do not consume seats.

After registration, the app returns to the sections page and displays either:

- **Enrolled:** “You have successfully registered for the {course number}-{section number} {course name}.”
- **Waitlisted:** “You have been added to the waitlist. Your position is {position}.” Positions start at 1 and are ordered by registration date, then registration ID to break ties.

### Registration rules

| Condition | Behavior |
| --- | --- |
| Active class with an available seat | Registration becomes `enrolled`. |
| Active class at capacity, including capacity zero | Registration becomes `waitlisted`. |
| Existing enrolled or waitlisted registration | The row displays **Cancel**. |
| Enrolled or waitlisted in another section of the same course | Registration is blocked; the app returns to sections with a message identifying the registration to cancel first. This applies across quarters. |
| Confirmed cancellation | Registration becomes `dropped`; the record is retained. |
| Register again after dropping | The existing record is reused and capacity is checked again. |
| Inactive class without an existing enrollment or waitlist entry | The row displays **Closed** and new registrations are rejected. |
| Inactive class with an existing enrollment or waitlist entry | Cancellation remains available. |

Register and cancel forms have distinct names for each section, preventing an immediately repeated submission from reversing the previous action. Registration writes are serialized using SQLite transactions before checking capacity and existing course registrations so concurrent requests cannot both take the last seat or register the same student in different sections of a course.

## App structure

The application lives in `apps/class_registration/`:

| File or directory | Purpose |
| --- | --- |
| `controllers.py` | Home page, sections grid, available seats, registration, cancellation, and waitlist positions. |
| `models.py` | Tables, validators, and unique indexes. |
| `profile_forms.py` | Account profile form with student ID, department, and major. |
| `common.py` | Database, authentication, sessions, and shared fixtures. |
| `settings.py` | SQLite, development mode, authentication, and optional services. |
| `templates/` | Page templates using py4web's `[[ ... ]]` syntax. |
| `static/` | CSS, JavaScript, and other static assets. |
| `tasks.py` | Scaffold examples for optional background tasks; disabled by default. |

The main tables are `course`, `quarter`, `course_section`, `meeting_time`, `student`, and `registration`. Students reference py4web's `auth_user` table. Unique indexes enforce one registration record per student and section, one section number per course and quarter, and one quarter per year and season. The registration action enforces the rule that a student can be enrolled or waitlisted in only one section of a course at a time.

### Routes

Paths below are relative to `/class_registration/`. All except the home page require login.

| Path | Purpose |
| --- | --- |
| `index` or the app root | Welcome page and registration link. |
| `sections` | Sections grid with available seats; users without a student profile are redirected to create one. |
| `auth/profile` | Edit account information, student ID, department, and major together. |
| `register/<section_id>` | Register or confirm cancellation for a section. |

Authentication pages are provided under `auth/`, including signup, login, logout, and account profile editing.

## Exercise scope and limitations

- Cancellation does not automatically promote waitlisted students. The app shows a waitlist position after registration, but has no dedicated page for checking current positions.
- Class data is managed through the shell or dashboard; the student grid is read-only apart from registration actions.
- Student IDs are checked for presence and uniqueness, not verified against a university directory. The account profile form creates and edits the linked student record.
- Capacity locking is specific to the configured SQLite database.
- Email delivery is not configured.

For a quick manual check, register for a sample section and confirm the success message and reduced available-seat count. To test waitlisting, register another student after all seats are filled and check the position message. With two sections of the same course, try registering for the second section before and after cancelling the first. Also try registering again after dropping and setting the section's `active` field to false in the dashboard.

## Tests

Run the model, profile-form, and section-registration tests with:

```sh
uv run python -m unittest discover -s tests
```
