import csv
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

LOCAL_RUN_HISTORY_CSV = Path("run_history.csv")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
RUN_METRICS_DATABASE_ID = os.getenv("RUN_METRICS_DATABASE_ID")

notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN and RUN_METRICS_DATABASE_ID else None


def _safe_number(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truncate(value: Any, max_len: int = 1900) -> str:
    if value is None:
        return ""
    return str(value)[:max_len]


def _normalize_run(run: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "script": run.get("script", ""),
        "run_started_at": run.get("run_started_at", ""),
        "run_finished_at": run.get("run_finished_at", ""),
        "status": run.get("status", "unknown"),
        "active_companies": run.get("active_companies", 0),
        "companies_checked": run.get("companies_checked", 0),
        "jobs_fetched": run.get("jobs_fetched", 0),
        "jobs_evaluated": run.get("jobs_evaluated", 0),
        "apply_writes": run.get("apply_writes", 0),
        "network_writes": run.get("network_writes", 0),
        "review_writes": run.get("review_writes", 0),
        "skip_count": run.get("skip_count", 0),
        "high_role_interest_but_skip": run.get("high_role_interest_but_skip", 0),
        "discovery_candidates": run.get("discovery_candidates", 0),
        "discovery_promoted": run.get("discovery_promoted", 0),
        "notes": run.get("notes", ""),
    }


def _append_local_csv(run: Dict[str, Any]) -> None:
    run = _normalize_run(run)
    file_exists = LOCAL_RUN_HISTORY_CSV.exists()

    with LOCAL_RUN_HISTORY_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(run.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(run)


def _get_data_source_id(database_id: str) -> str:
    database = notion.databases.retrieve(database_id=database_id)
    data_sources = database.get("data_sources", [])
    if not data_sources:
        raise ValueError("No data sources found for run metrics database.")
    return data_sources[0]["id"]


def _append_notion(run: Dict[str, Any]) -> None:
    if not notion or not RUN_METRICS_DATABASE_ID:
        return

    run = _normalize_run(run)
    data_source_id = _get_data_source_id(RUN_METRICS_DATABASE_ID)

    name = f"{run['script']} | {run['run_started_at'][:19]}"

    notion.pages.create(
        parent={"data_source_id": data_source_id},
        properties={
            "Name": {
                "title": [{"text": {"content": _truncate(name, 200)}}]
            },
            "Script": {
                "select": {"name": _truncate(run["script"], 100) or "unknown"}
            },
            "Run Started": {
                "date": {"start": run["run_started_at"] or None}
            },
            "Run Finished": {
                "date": {"start": run["run_finished_at"] or None}
            },
            "Status": {
                "select": {"name": _truncate(run["status"], 100) or "unknown"}
            },
            "Active Companies": {
                "number": _safe_number(run["active_companies"])
            },
            "Companies Checked": {
                "number": _safe_number(run["companies_checked"])
            },
            "Jobs Fetched": {
                "number": _safe_number(run["jobs_fetched"])
            },
            "Jobs Evaluated": {
                "number": _safe_number(run["jobs_evaluated"])
            },
            "Apply Writes": {
                "number": _safe_number(run["apply_writes"])
            },
            "Network Writes": {
                "number": _safe_number(run["network_writes"])
            },
            "Review Writes": {
                "number": _safe_number(run["review_writes"])
            },
            "Skip Count": {
                "number": _safe_number(run["skip_count"])
            },
            "High Role Interest But Skip": {
                "number": _safe_number(run["high_role_interest_but_skip"])
            },
            "Discovery Candidates": {
                "number": _safe_number(run["discovery_candidates"])
            },
            "Discovery Promoted": {
                "number": _safe_number(run["discovery_promoted"])
            },
            "Notes": {
                "rich_text": (
                    [{"text": {"content": _truncate(run["notes"])}}]
                    if run["notes"] else []
                )
            },
        },
    )


def append_run_metric(run: Dict[str, Any]) -> None:
    _append_local_csv(run)
    try:
        _append_notion(run)
    except Exception as e:
        print(f"[run_metrics] notion write failed: {e}")
