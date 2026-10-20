import hmac

from flask import Blueprint, current_app, jsonify, request

from app.db import write_tx
from app.services import record_activity, write_audit
from app.validate import validate_activity

bp = Blueprint("api", __name__, url_prefix="/api/v1")


@bp.post("/activities")
def ingest():
    expected = current_app.config["COLLECTOR_API_KEY"]
    sent = request.headers.get("X-API-Key", "")
    if not sent or len(sent) != len(expected) or not hmac.compare_digest(sent, expected):
        return jsonify(error="Invalid collector API key."), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Expected a JSON object."), 422
    with write_tx() as connection:
        fields, errors = validate_activity(connection, payload)
        if errors:
            return jsonify(error="The activity could not be recorded.", errors=errors), 422
        activity_id, alerts = record_activity(connection, fields, "AGENT")
        write_audit(
            connection,
            None,
            "Recorded activity",
            "activity",
            activity_id,
            "Accepted from the collector API.",
        )
    return jsonify(activity_id=activity_id, alerts=alerts), 201
