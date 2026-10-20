import os
from datetime import timedelta
from urllib.parse import urlencode

from flask import Flask, abort, render_template, request

from app.auth import can, csrf_ok, csrf_token, current_user
from app.clock import human_date, human_enum, human_when
from app.db import close_db, get_db, init_db
from app.nav import NAV
from app.services import organisation_name


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("IPMCS_SECRET", "dev-ipmcs-change-me"),
        DB_HOST=os.environ.get("IPMCS_DB_HOST", "127.0.0.1"),
        DB_PORT=int(os.environ.get("IPMCS_DB_PORT", "3306")),
        DB_USER=os.environ.get("IPMCS_DB_USER", "root"),
        DB_PASSWORD=os.environ.get("IPMCS_DB_PASSWORD", ""),
        DB_NAME=os.environ.get("IPMCS_DB_NAME", "ipmcs"),
        COLLECTOR_API_KEY=os.environ.get("IPMCS_API_KEY", "ipmcs-demo-collector"),
        SEED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=1_000_000,
    )
    if overrides:
        app.config.update(overrides)

    app.teardown_appcontext(close_db)
    init_db(app)

    @app.before_request
    def protect_csrf():
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return None
        if request.path.startswith("/api/"):
            return None
        if not csrf_ok():
            abort(400)
        return None

    @app.context_processor
    def inject():
        user = current_user()
        open_alerts = 0
        pending_reviews = 0
        open_findings = 0
        unread_notifications = 0
        sections = []
        org_name = "ICT Policy Monitoring"
        if user:
            connection = get_db()
            org_name = organisation_name(connection)
            permissions = user["permissions"]
            unread_notifications = connection.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
                (user["id"],),
            ).fetchone()[0]
            if "view_alerts" in permissions:
                open_alerts = connection.execute(
                    "SELECT COUNT(*) FROM alerts WHERE status = 'OPEN'"
                ).fetchone()[0]
            if "view_findings" in permissions:
                open_findings = connection.execute(
                    "SELECT COUNT(*) FROM findings WHERE status = 'OPEN'"
                ).fetchone()[0]
            if "view_reviews" in permissions:
                pending_reviews = connection.execute(
                    "SELECT COUNT(*) FROM access_reviews WHERE status = 'PENDING'"
                ).fetchone()[0]
            for title, items in NAV:
                visible = []
                for endpoint, label, permission, badge in items:
                    if permission in permissions:
                        visible.append(
                            {
                                "endpoint": endpoint,
                                "label": label,
                                "badge": badge,
                                "active": _active(endpoint),
                            }
                        )
                if visible:
                    sections.append({"title": title, "links": visible})

        def page_url(page):
            args = request.args.to_dict(flat=True)
            args["page"] = str(page)
            return "?" + urlencode(args)

        return {
            "csrf": csrf_token,
            "can": can,
            "current_user": user,
            "nav_sections": sections,
            "open_alerts": open_alerts,
            "open_findings": open_findings,
            "pending_reviews": pending_reviews,
            "unread_notifications": unread_notifications,
            "organisation_name": org_name,
            "page_url": page_url,
        }

    @app.template_filter("when")
    def when(value):
        return human_when(value)

    @app.template_filter("day")
    def day(value):
        return human_date(value)

    @app.template_filter("nice")
    def nice(value):
        return human_enum(value)

    def render_error(code, message):
        template = "error.html" if current_user() else "error_public.html"
        return render_template(template, code=code, message=message), code

    @app.errorhandler(403)
    def forbidden(_error):
        return render_error(403, "You do not have permission to open that page.")

    @app.errorhandler(404)
    def missing(_error):
        return render_error(404, "That page does not exist.")

    @app.errorhandler(400)
    def bad_request(_error):
        return render_error(400, "The form could not be submitted. Refresh the page and try again.")

    from app.views import register

    register(app)
    return app


def _active(endpoint):
    current = request.endpoint or ""
    if endpoint in ("dashboard.index", "dashboard.help"):
        return current == endpoint
    return current.startswith(endpoint.split(".")[0] + ".")


def paging(total, per_page=15):
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(page, 1), pages)
    return {
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "offset": (page - 1) * per_page,
        "total": total,
    }


def like(term):
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"

