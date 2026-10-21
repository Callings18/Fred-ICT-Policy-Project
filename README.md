# ICT Policy Monitoring and Compliance Management System

A local web application for an organisation that needs to watch selected computer activity, compare it with written ICT policy rules, and keep a record of what a person decided. An alert is a lead for review. It is not an automatic finding that someone broke a policy.

The system keeps its own record of employees, devices, activity, rules, alerts, findings, access reviews, reports, and an audit log. It does not replace the organisation’s human-resources system or its identity system. Staff status is entered here, or posted in by a collector. Signing in uses accounts stored in this application.

## What you need

- Python 3.11 or newer
- MySQL 8, or MariaDB 10.4 or newer, listening on port 3306
- The Python packages in `requirements.txt` (Flask and PyMySQL)

The full install for Windows, macOS, and Linux is in [HOW_TO_RUN.md](HOW_TO_RUN.md).

## How to run it

Start the database, then from this folder:

```text
python -m venv .venv
```

Windows: `.venv\Scripts\activate`

macOS and Linux: `source .venv/bin/activate`

```text
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5050

If the database user is not `root` with an empty password, set `IPMCS_DB_PASSWORD` and the other variables in [HOW_TO_RUN.md](HOW_TO_RUN.md) before `python run.py`. A `.env` file is not loaded on its own.

The first launch creates a database named `ipmcs` and loads demonstration employees, devices, rules, activities, and alerts. Later launches keep the data that is already there.

Sign in with one of these demonstration accounts. Every account uses the password `Monitor#2026`.

| Username | Name | Role |
| --- | --- | --- |
| admin | Fred Likasi | System Administrator |
| officer | Bupe Zulu | ICT/Security Officer |
| manager | Patrick Sakala | Management |
| hr | Thandiwe Lungu | HR Officer |

Change the password, `IPMCS_SECRET`, and `IPMCS_API_KEY` before anyone other than you uses the application. The demonstration password is for a local walkthrough.

## Connection settings

Copy `.env.example` if you want a reminder of the settings. The application reads them from the environment. When a setting is absent, it uses the value shown here, which matches a local XAMPP install with an empty root password.

```text
IPMCS_DB_HOST=127.0.0.1
IPMCS_DB_PORT=3306
IPMCS_DB_USER=root
IPMCS_DB_PASSWORD=
IPMCS_DB_NAME=ipmcs
IPMCS_SECRET=change-me
IPMCS_API_KEY=change-me
```

`IPMCS_SECRET` signs the browser session. `IPMCS_API_KEY` is the key a collector must send. Set both to long private values outside a demonstration.

To pass them in PowerShell for one session:

```text
$env:IPMCS_DB_PASSWORD = "your-database-password"
$env:IPMCS_SECRET = "a-long-random-string"
$env:IPMCS_API_KEY = "a-different-long-random-string"
python run.py
```

## Guidelines for using the system

Each person has one role. The role decides which screens they can open. A system administrator assigns the role from Users. The Roles and permissions screen shows the matrix and cannot be edited there.

| Role | What that person does |
| --- | --- |
| System Administrator | Manages accounts, policy rules, devices, organisation settings, and the backup. Sees every screen. |
| ICT/Security Officer | Reviews activities and alerts, opens and closes compliance findings, and completes access reviews. |
| Management | Reads the dashboard, alerts, findings, and reports. Does not browse activity detail or administer accounts. |
| HR Officer | Maintains employee records and submits leavers or transfers for an ICT access review. Does not see activity content or findings. |

Working rules for the people using it:

- Treat an open alert as something a person still has to look at. Mark it reviewed, dismissed, or escalated, and write a note.
- Escalate an alert when the case needs a written investigation. That opens a compliance finding. Closing a finding records a conclusion. It does not, by itself, confirm a breach.
- Deactivate a policy rule when it should stop applying. Rules are not deleted, so older alerts still show the rule name and severity they were raised with.
- Do not delete users or employees. Set a user inactive, or record that an employee has left, so the audit history remains.
- When HR records that someone has left or transferred, the system opens one pending access review. An officer completes it. “Revoke access” updates the employee and device records kept in this application. It does not reach into another identity system.
- A rule applies to new events. It does not go back and re-judge activity that was already stored.
- The activity after someone has left is compared with that person’s leaving date. Activity before the leaving date does not raise the leaver rule.
- Use Sign out when you finish. The session lasts eight hours.

The in-application page **How to use** repeats the operating steps for someone who is already signed in.

## What the demonstration data shows

The loaded story is there so you can click through a real review without inventing records:

- Several ordinary working-day events that do not raise an alert.
- Six alerts. Four are still open. One has been reviewed. One has been dismissed.
- Gift Bwalya (EMP-1155), in Finance, has left and still has active ICT access. One access review is waiting.
- Fred Likasi is the system administrator. His employee email is likasifred@gmail.com.

Recording an activity on **Activities → Record activity** stands in for a monitoring agent. The collector API below is the other way to send an event.

## Collector API

A collector can post an event without a browser session:

```text
POST /api/v1/activities
X-API-Key: ipmcs-demo-collector
```

```json
{
  "employee_number": "EMP-1108",
  "hostname": "HR-WS-02",
  "activity_type": "RESOURCE_ACCESS",
  "resource": "payroll-register",
  "occurred_at": "2026-10-08T11:00:00",
  "details": "Opened the monthly payroll register"
}
```

`activity_type` is one of `LOGIN`, `LOGOUT`, `APPLICATION`, `RESOURCE_ACCESS`, or `NETWORK`. The employee number and hostname must already exist. Replace `ipmcs-demo-collector` with the value of `IPMCS_API_KEY` when you have set one.

## Backup and recovery

A system administrator downloads a SQL copy from **System settings**. To recover, stop the application and import that file into the `ipmcs` database, then start the application again.

## Checks

With the database server running:

```text
python -m unittest discover -s tests -v
```

The tests use a separate database named `ipmcs_test` and remove it when they finish. They do not change `ipmcs`.

## Files

```text
HOW_TO_RUN.md           Step-by-step setup for Windows, macOS, and Linux
run.py                  Starts the application on http://127.0.0.1:5050
requirements.txt        Python packages to install
.env.example            Names of the settings the application reads
README.md               What the system is and how the roles work

app/__init__.py         Application setup, security headers, and navigation data
app/auth.py             Sign-in, sessions, and permission checks
app/constants.py        Roles, permissions, and the allowed status values
app/db.py               MySQL connection, tables, and SQL backup
app/seed.py             Demonstration people, devices, rules, and events
app/services.py         Policy checks, alerts, findings, reviews, and notifications
app/reports.py          Report content
app/views/              One module for each area of the application
app/templates/          HTML pages
app/static/             Stylesheet, script, and icon

tests/test_system.py    Checks for the policy rules, pages, and demonstration story
```

`instance/` is created locally and is not part of the source. Do not commit `.env`, database files, or the virtual environment.
