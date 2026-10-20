from flask import Blueprint, render_template

from app.auth import permission_required
from app.constants import ROLE_DESCRIPTIONS
from app.db import get_db

bp = Blueprint("roles", __name__, url_prefix="/roles")


@bp.route("/", strict_slashes=False)
@permission_required("manage_users")
def index():
    connection = get_db()
    roles = connection.execute("SELECT id, name, description FROM roles ORDER BY name").fetchall()
    permissions = connection.execute("SELECT id, code, name FROM permissions ORDER BY name").fetchall()
    granted = {
        (row["role_id"], row["permission_id"])
        for row in connection.execute("SELECT role_id, permission_id FROM role_permissions")
    }
    return render_template(
        "roles/index.html",
        roles=roles,
        permissions=permissions,
        granted=granted,
        descriptions=ROLE_DESCRIPTIONS,
    )
