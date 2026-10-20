import io
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from app.auth import current_user, permission_required
from app.db import dump_sql, get_db, write_tx
from app.services import organisation_name, write_audit
from app.validate import clean

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"], strict_slashes=False)
@permission_required("manage_users")
def index():
    connection = get_db()
    form = {"organisation_name": organisation_name(connection)}
    errors = []
    if request.method == "POST":
        form["organisation_name"] = clean(request.form.get("organisation_name"), 80)
        if len(form["organisation_name"]) < 3:
            errors.append("Enter the organisation or system name.")
        if not errors:
            actor = current_user()
            with write_tx() as tx:
                tx.execute(
                    """
                    INSERT INTO settings (`key`, value) VALUES ('organisation_name', ?)
                    ON DUPLICATE KEY UPDATE value = VALUES(value)
                    """,
                    (form["organisation_name"],),
                )
                write_audit(tx, actor["id"], "Updated system settings", "settings", None, form["organisation_name"])
            flash("System settings saved.")
            return redirect(url_for("settings.index"))
    counts = {
        "users": connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "activities": connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0],
        "alerts": connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
        "audit": connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0],
    }
    return render_template("settings/index.html", form=form, errors=errors, counts=counts)


@bp.route("/backup", methods=["POST"])
@permission_required("manage_users")
def backup():
    actor = current_user()
    source = get_db()
    payload = dump_sql(source).encode("utf-8")
    with write_tx() as connection:
        write_audit(connection, actor["id"], "Downloaded database backup", "settings", None, "MySQL backup file.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return send_file(
        io.BytesIO(payload),
        as_attachment=True,
        download_name=f"ipmcs-backup-{stamp}.sql",
        mimetype="application/sql",
    )
