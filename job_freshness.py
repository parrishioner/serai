print("LOADING JOB FRESHNESS FILE")

from datetime import datetime, timezone


def score_freshness(first_seen_iso):
    if not first_seen_iso:
        return 0, "no first seen date"

    first_seen_iso = first_seen_iso.replace("Z", "+00:00")
    first_seen = datetime.fromisoformat(first_seen_iso)

    if first_seen.tzinfo is None:
        first_seen = first_seen.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_hours = (now - first_seen).total_seconds() / 3600

    if age_hours <= 6:
        return 15, "first seen within 6 hours"
    if age_hours <= 24:
        return 10, "first seen within 24 hours"
    if age_hours <= 72:
        return 5, "first seen within 3 days"

    return 0, "first seen more than 3 days ago"

def compute_freshness(job):
    first_seen = job.get("first_seen_at")
    if not first_seen:
        return job

    first_seen_dt = datetime.fromisoformat(first_seen)
    now = datetime.now()

    age_days = (now - first_seen_dt).total_seconds() / 86400

    job["first_seen_age_days"] = round(age_days, 2)

    if age_days < 1:
        job["freshness_bucket"] = "new_today"
    elif age_days < 3:
        job["freshness_bucket"] = "new_3d"
    elif age_days < 7:
        job["freshness_bucket"] = "new_7d"
    else:
        job["freshness_bucket"] = "older"

    return job