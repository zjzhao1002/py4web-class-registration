# Class registration with py4web

A demo class registration app built with Python, [py4web](https://py4web.com/), and SQLite. It demonstrates authentication, student profiles, database models, grids, CSRF-protected forms, and capacity-based enrollment.

## Run locally

Requirements: Python 3.13 or newer and `uv`. Run these commands from the repository root:

```sh
uv sync
uv run py4web set_password
uv run py4web run apps --dev
```

`set_password` creates a local password for the py4web dashboard; it is separate from student account passwords.

Open <http://127.0.0.1:8000/class_registration/>. Development mode disables signup email verification and relaxes password complexity requirements, so no mail server is needed for this exercise. After signing up, log in manually.

SQLite tables are created automatically on first load. Data is stored in `apps/class_registration/databases/storage.db`. Local database files, `password.txt`, and private settings are ignored by Git.

## Usage

A sample class has been added to the local database through the [py4web dashboard](http://127.0.0.1:8000/_dashboard/). Use that class to try the registration flow. Class data is local and is not included in a fresh Git checkout.

1. Sign up and log in.
2. Click **Registration** on the home page.
3. Enter a unique, nonempty **SUID** when prompted. The app links the student profile to the logged-in account automatically.
4. Find the sample class in the offerings grid, click **Register**, optionally leave a note, and submit the form.
5. To withdraw, click **Cancel** beside the class and confirm cancellation.

When a user opens a class registration URL before creating a student profile, the app returns them to that class after they submit their SUID.

### Registration rules

| Condition | Behavior |
| --- | --- |
| Active class with an available seat | Registration becomes `enrolled`. |
| Active class at capacity, including capacity zero | Registration becomes `waitlisted`. |
| Existing enrolled or waitlisted registration | The row displays **Cancel**. |
| Confirmed cancellation | Registration becomes `dropped`; the record is retained. |
| Register again after dropping | The existing record is reused and capacity is checked again. |
| Inactive class without an existing enrollment or waitlist entry | The row displays **Closed** and new registrations are rejected. |
| Inactive class with an existing enrollment or waitlist entry | Cancellation remains available. |

Register and cancel forms have distinct names for each offering, preventing an immediately repeated submission from reversing the previous action. Registration writes are serialized using SQLite transactions before checking capacity so concurrent requests cannot both take the last seat.

## App structure

The application lives in `apps/class_registration/`:

| File or directory | Purpose |
| --- | --- |
| `controllers.py` | Home page, offerings grid, student profile creation, registration and cancellation. |
| `models.py` | Tables, validators, and unique indexes. |
| `common.py` | Database, authentication, sessions, and shared fixtures. |
| `settings.py` | SQLite, development mode, authentication, and optional services. |
| `templates/` | Page templates using py4web's `[[ ... ]]` syntax. |
| `static/` | CSS, JavaScript, and other static assets. |
| `tasks.py` | Scaffold examples for optional background tasks; disabled by default. |

The main tables are `catalog_class`, `quarter`, `class_offering`, `student`, and `registration`. Students reference py4web's `auth_user` table. Unique indexes enforce one registration per student and offering, one section number per class and quarter, and one quarter per year and season.

### Routes

Paths below are relative to `/class_registration/`. All except the home page require login.

| Path | Purpose |
| --- | --- |
| `index` or the app root | Welcome page and registration link. |
| `offerings` | Class grid; users without a student profile are redirected to create one. |
| `student_profile` | Create a profile, then return to offerings. |
| `student_profile/<offering_id>` | Create a profile, then return to the selected class. |
| `register/<offering_id>` | Register or confirm cancellation for a class. |

Authentication pages are provided under `auth/`, including signup, login, logout, and account profile editing.

## Exercise scope and limitations

- Waitlisting records a status only. Cancellation does not automatically promote waitlisted students, and the app does not display queue positions or a dedicated registration-status page.
- Class data is managed through the shell or dashboard; the student grid is read-only apart from registration actions.
- SUIDs are checked for presence and uniqueness, not verified against a university directory. The student profile form only creates profiles; it does not edit existing SUIDs.
- Capacity locking is specific to the configured SQLite database.
- Email delivery is not configured. Use `--dev` for the local demo.

For a quick manual check, register for the sample class and inspect the `registration` table in the dashboard to confirm the status. Enrollment depends on the offering's configured capacity and current enrollment count. To test waitlisting, register another student after all seats are filled. Try cancelling, registering again, and setting the offering's `active` field to false in the dashboard to exercise the remaining flows.
