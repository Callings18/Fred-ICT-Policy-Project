import unittest
from datetime import datetime

from app import create_app
from app.db import drop_database, get_db, write_tx
from app.seed import DEMO_PASSWORD
from app.services import complete_access_review, record_activity, rule_matches


def activity(**overrides):
    base = {
        "activity_type": "LOGIN",
        "application": "",
        "resource": "",
        "details": "",
        "occurred_at": "2026-10-08T10:00:00",
        "duration_minutes": None,
        "employment_status": "ACTIVE",
        "left_date": None,
    }
    base.update(overrides)
    return base


def rule(**overrides):
    base = {
        "activity_type": "ANY",
        "condition_type": "OUTSIDE_HOURS",
        "condition_value": "08:00-17:00",
    }
    base.update(overrides)
    return base


class RuleTests(unittest.TestCase):
    def test_hours_weekend_and_sensitive_cases(self):
        hours = rule()
        self.assertFalse(rule_matches(hours, activity()))
        self.assertTrue(rule_matches(hours, activity(occurred_at="2026-10-08T22:15:00")))
        self.assertFalse(rule_matches(rule(activity_type="APPLICATION"), activity(occurred_at="2026-10-08T22:15:00")))
        weekend = rule(condition_type="WEEKEND", condition_value="SAT,SUN")
        self.assertTrue(rule_matches(weekend, activity(occurred_at="2026-10-10T10:20:00")))
        self.assertFalse(rule_matches(weekend, activity()))
        apps = rule(activity_type="APPLICATION", condition_type="APPLICATION_IN", condition_value="utorrent, anydesk")
        self.assertTrue(rule_matches(apps, activity(activity_type="APPLICATION", application="uTorrent")))
        self.assertFalse(rule_matches(apps, activity(activity_type="APPLICATION", application="Microsoft Excel")))
        resources = rule(activity_type="RESOURCE_ACCESS", condition_type="RESOURCE_CONTAINS", condition_value="payroll,salary")
        self.assertTrue(rule_matches(resources, activity(activity_type="RESOURCE_ACCESS", resource="payroll-register")))
        duration = rule(activity_type="APPLICATION", condition_type="DURATION_OVER", condition_value="240")
        self.assertTrue(rule_matches(duration, activity(activity_type="APPLICATION", duration_minutes=300)))
        self.assertFalse(rule_matches(duration, activity(activity_type="APPLICATION", duration_minutes=55)))
        leaver = rule(condition_type="EMPLOYEE_NOT_ACTIVE", condition_value="NOT_ACTIVE")
        self.assertFalse(rule_matches(leaver, activity()))
        self.assertFalse(
            rule_matches(
                leaver,
                activity(employment_status="LEFT", left_date="2026-10-04", occurred_at="2026-10-02T10:00:00"),
            )
        )
        self.assertTrue(
            rule_matches(
                leaver,
                activity(employment_status="LEFT", left_date="2026-10-04", occurred_at="2026-10-09T10:05:00"),
            )
        )


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.db_config = {
            "DB_HOST": "127.0.0.1",
            "DB_PORT": 3306,
            "DB_USER": "root",
            "DB_PASSWORD": "",
            "DB_NAME": "ipmcs_test",
        }
        drop_database(self.db_config)
        self.app = create_app({**self.db_config, "SEED": True, "TESTING": True, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            from flask import g

            connection = g.pop("db", None)
            if connection is not None:
                connection.close()
        drop_database(self.db_config)

    def sign_in(self, username):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            token = session["_csrf"]
        response = self.client.post(
            "/login",
            data={"username": username, "password": DEMO_PASSWORD, "csrf_token": token},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

    def test_seed_story(self):
        with self.app.app_context():
            connection = get_db()
            total = connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            open_alerts = connection.execute("SELECT COUNT(*) FROM alerts WHERE status = 'OPEN'").fetchone()[0]
            pending = connection.execute("SELECT COUNT(*) FROM access_reviews WHERE status = 'PENDING'").fetchone()[0]
            leaver = connection.execute("SELECT * FROM employees WHERE employee_number = 'EMP-1155'").fetchone()
            admin = connection.execute(
                """
                SELECT u.full_name, e.email
                FROM users u
                JOIN employees e ON e.id = u.employee_id
                WHERE u.username = 'admin'
                """
            ).fetchone()
        self.assertEqual(total, 6)
        self.assertEqual(open_alerts, 4)
        self.assertEqual(pending, 1)
        self.assertEqual(leaver["full_name"], "Gift Bwalya")
        self.assertEqual(leaver["employment_status"], "LEFT")
        self.assertEqual(leaver["ict_access_status"], "ACTIVE")
        self.assertEqual(admin["full_name"], "Fred Likasi")
        self.assertEqual(admin["email"], "likasifred@gmail.com")

    def test_roles_and_pages(self):
        self.sign_in("admin")
        for path in (
            "/",
            "/help",
            "/activities",
            "/activities/new",
            "/alerts",
            "/findings",
            "/policies",
            "/policies/new",
            "/employees",
            "/employees/new",
            "/devices",
            "/devices/new",
            "/reviews",
            "/reports",
            "/reports/new",
            "/audit",
            "/users",
            "/users/new",
            "/roles",
            "/settings",
            "/account",
            "/notifications",
            "/hr",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
        with self.app.app_context():
            connection = get_db()
            activity_id = connection.execute("SELECT id FROM activities LIMIT 1").fetchone()[0]
            alert_id = connection.execute("SELECT id FROM alerts LIMIT 1").fetchone()[0]
            employee_id = connection.execute("SELECT id FROM employees LIMIT 1").fetchone()[0]
            device_id = connection.execute("SELECT id FROM devices LIMIT 1").fetchone()[0]
            review_id = connection.execute("SELECT id FROM access_reviews LIMIT 1").fetchone()[0]
            report_id = connection.execute("SELECT id FROM reports LIMIT 1").fetchone()[0]
            user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
            rule_id = connection.execute("SELECT id FROM policy_rules LIMIT 1").fetchone()[0]
        for path in (
            f"/activities/{activity_id}",
            f"/alerts/{alert_id}",
            f"/employees/{employee_id}",
            f"/employees/{employee_id}/edit",
            f"/devices/{device_id}",
            f"/devices/{device_id}/edit",
            f"/reviews/{review_id}",
            f"/reports/{report_id}",
            f"/policies/{rule_id}/edit",
            f"/users/{user_id}/edit",
        ):
            self.assertEqual(self.client.get(path).status_code, 200, path)

        self.client.post("/logout", data=self._token(), follow_redirects=False)
        self.sign_in("officer")
        self.assertEqual(self.client.get("/users").status_code, 403)
        self.assertEqual(self.client.get("/settings").status_code, 403)
        self.assertEqual(self.client.get("/roles").status_code, 403)
        self.assertEqual(self.client.get("/findings").status_code, 200)
        self.assertEqual(self.client.get("/account").status_code, 200)
        self.assertEqual(self.client.get("/notifications").status_code, 200)
        self.assertEqual(self.client.get("/policies/new").status_code, 403)
        self.assertEqual(self.client.get("/hr").status_code, 403)
        self.assertEqual(self.client.get("/alerts").status_code, 200)

        self.client.post("/logout", data=self._token(), follow_redirects=False)
        self.sign_in("manager")
        self.assertEqual(self.client.get("/activities").status_code, 403)
        self.assertEqual(self.client.get("/alerts").status_code, 200)
        self.assertEqual(self.client.get("/findings").status_code, 200)
        self.assertIn(b"Open alerts", self.client.get("/").data)

        self.client.post("/logout", data=self._token(), follow_redirects=False)
        self.sign_in("hr")
        self.assertEqual(self.client.get("/activities").status_code, 403)
        self.assertEqual(self.client.get("/employees").status_code, 200)
        self.assertEqual(self.client.get("/reviews").status_code, 200)
        self.assertEqual(self.client.get("/hr").status_code, 200)
        self.assertEqual(self.client.get("/findings").status_code, 403)

    def test_escalation_opens_a_finding(self):
        self.sign_in("officer")
        with self.app.app_context():
            alert_id = get_db().execute("SELECT id FROM alerts WHERE status = 'OPEN' LIMIT 1").fetchone()[0]
        reviewed = self.client.post(
            f"/alerts/{alert_id}",
            data={
                "status": "ESCALATED",
                "review_notes": "Needs a written check with the line manager.",
                **self._token(),
            },
            follow_redirects=True,
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertIn(b"Open the compliance finding", reviewed.data)
        with self.app.app_context():
            finding_id = get_db().execute("SELECT id FROM findings WHERE alert_id = ?", (alert_id,)).fetchone()[0]
        closed = self.client.post(
            f"/findings/{finding_id}",
            data={"conclusion": "Checked with the manager. No further ICT action.", **self._token()},
            follow_redirects=True,
        )
        self.assertEqual(closed.status_code, 200)
        self.assertIn(b"This finding is closed.", closed.data)
        self.client.post("/logout", data=self._token(), follow_redirects=False)
        self.sign_in("manager")
        self.assertEqual(self.client.get(f"/findings/{finding_id}").status_code, 200)
        denied = self.client.post(
            f"/findings/{finding_id}",
            data={"conclusion": "Management cannot close this.", **self._token()},
        )
        self.assertEqual(denied.status_code, 403)

    def test_manual_event_and_revoke(self):
        self.sign_in("officer")
        page = self.client.get("/activities/new")
        self.assertEqual(page.status_code, 200)
        with self.app.app_context():
            connection = get_db()
            employee = connection.execute("SELECT id FROM employees WHERE employee_number = 'EMP-1042'").fetchone()
            device = connection.execute("SELECT id FROM devices WHERE hostname = 'FIN-WS-14'").fetchone()
            with write_tx() as tx:
                activity_id, alerts = record_activity(
                    tx,
                    {
                        "employee_id": employee["id"],
                        "device_id": device["id"],
                        "activity_type": "LOGIN",
                        "application": "",
                        "resource": "",
                        "occurred_at": datetime.now().replace(hour=22, minute=5, second=0, microsecond=0).isoformat(timespec="seconds"),
                        "duration_minutes": None,
                        "details": "Test sign-in.",
                    },
                    "MANUAL",
                )
            self.assertTrue(any(item["rule"] == "After-hours sign-in" for item in alerts))
            review = connection.execute("SELECT id FROM access_reviews WHERE status = 'PENDING'").fetchone()
            noah_device = connection.execute("SELECT status FROM devices WHERE hostname = 'FIN-WS-22'").fetchone()
            self.assertEqual(noah_device["status"], "ACTIVE")
            with write_tx() as tx:
                done = complete_access_review(tx, review["id"], 1, "REVOKE_ACCESS", "Access is no longer required.")
                self.assertTrue(done)
                again = complete_access_review(tx, review["id"], 1, "REVIEW_ONLY", "Second pass.")
                self.assertFalse(again)
            noah = get_db().execute("SELECT ict_access_status FROM employees WHERE employee_number = 'EMP-1155'").fetchone()
            noah_device = get_db().execute("SELECT status FROM devices WHERE hostname = 'FIN-WS-22'").fetchone()
        self.assertEqual(noah["ict_access_status"], "REVOKED")
        self.assertEqual(noah_device["status"], "INACTIVE")
        self.assertTrue(activity_id)

    def test_collector_api(self):
        response = self.client.post("/api/v1/activities", json={"employee_number": "EMP-1042"}, headers={"X-API-Key": "nope"})
        self.assertEqual(response.status_code, 401)
        response = self.client.post(
            "/api/v1/activities",
            json={
                "employee_number": "EMP-1108",
                "hostname": "HR-WS-02",
                "activity_type": "RESOURCE_ACCESS",
                "resource": "payroll-register",
                "occurred_at": "2026-10-08T11:00:00",
                "details": "API test",
            },
            headers={"X-API-Key": "ipmcs-demo-collector"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.get_json()["alerts"])

    def test_profile_notifications_and_backup(self):
        self.sign_in("admin")
        page = self.client.get("/notifications")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Alert for review", page.data)
        saved = self.client.post(
            "/account",
            data={
                "full_name": "Fred Likasi",
                "current_password": "",
                "new_password": "",
                "confirm_password": "",
                "csrf_token": self._token()["csrf_token"],
            },
            follow_redirects=False,
        )
        self.assertEqual(saved.status_code, 302)
        renamed = self.client.post(
            "/settings",
            data={"organisation_name": "Harbour ICT", "csrf_token": self._token()["csrf_token"]},
            follow_redirects=True,
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertIn(b"Harbour ICT", renamed.data)
        backup = self.client.post("/settings/backup", data=self._token())
        self.assertEqual(backup.status_code, 200)
        self.assertIn(b"CREATE TABLE", backup.data)
        self.client.post("/logout", data=self._token(), follow_redirects=False)
        self.sign_in("hr")
        self.assertEqual(self.client.get("/settings").status_code, 403)
        self.assertNotIn(b"Alert for review", self.client.get("/notifications").data)

    def _token(self):
        with self.client.session_transaction() as session:
            return {"csrf_token": session["_csrf"]}


if __name__ == "__main__":
    unittest.main()
