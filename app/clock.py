from datetime import datetime, timedelta

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def now():
    return datetime.now().replace(microsecond=0).isoformat(timespec="seconds")


def today():
    return datetime.now().date().isoformat()


def at_days_ago(days, hour, minute):
    moment = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    moment -= timedelta(days=days)
    return moment.isoformat(timespec="seconds")


def human_when(value):
    if not value:
        return "—"
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    month = MONTHS[moment.month - 1]
    return f"{moment.day:02d} {month} {moment.year}, {moment.hour:02d}:{moment.minute:02d}"


def human_date(value):
    if not value:
        return "—"
    try:
        moment = datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return str(value)
    month = MONTHS[moment.month - 1]
    return f"{moment.day:02d} {month} {moment.year}"


def human_enum(value):
    if value is None or value == "":
        return "—"
    return str(value).replace("_", " ").title()
