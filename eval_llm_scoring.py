import csv
from pathlib import Path
from datetime import datetime, timezone

print("RUNNING eval_llm_scoring.py")

from job_source_router import fetch_jobs_for_company, fetch_job_detail_for_company
from company_registry import COMPANY_REGISTRY
from normalize import (
    normalize_job,
    extract_comp_from_greenhouse_detail,
    extract_workday_detail_fields,
    fill_missing_comp,
    format_compensation,
)
from job_filter import fast_filter_title_geo, check_comp
from llm_company_score import llm_score_company
from llm_score import llm_score_job
from job_cache import load_cache, save_cache, upsert_cache_job, attach_first_seen_to_job
from job_freshness import compute_freshness
from notion_helper import upsert_eval_job
from run_metrics import append_run_metric
import company_registry

ROLE_INTEREST_THRESHOLD = 7.0
MAX_JOBS_PER_COMPANY = 8

print(f"=== RUN START {datetime.now()} ===")
print("EVAL FILE:", Path(__file__).resolve())
print("REGISTRY FILE:", Path(company_registry.__file__).resolve())
print("REGISTRY COUNT:", len(company_registry.COMPANY_REGISTRY))
print("REGISTRY SLUGS:", [c["company_slug"] for c in company_registry.COMPANY_REGISTRY if c.get("enabled", True)])


def load_text_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error loading file {path}: {e}")
        return ""


CANDIDATE_PROFILE = load_text_file("candidate_data/candidate_profile.txt")


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_strict_non_pm_role(role: dict) -> bool:
    title = str(role.get("title", "")).lower()

    strict_terms = [
        "software engineer",
        "staff engineer",
        "senior engineer",
        "backend engineer",
        "frontend engineer",
        "full stack engineer",
        "full-stack engineer",
        "platform engineer",
        "data engineer",
        "machine learning engineer",
        "ml engineer",
        "research engineer",
        "research scientist",
        "security engineer",
        "site reliability engineer",
        "sre",
        "developer advocate",
        "account executive",
        "sales engineer",
        "customer success",
        "designer",
        "product designer",
    ]

    return any(term in title for term in strict_terms)


def role_fit_score(role: dict) -> float:
    """
    Role-fit score intentionally excludes company attractiveness.
    This is the score that should govern whether non-PM / unknown roles survive.
    """
    return round(
        to_float(role.get("strength_overlap")) * 0.40
        + to_float(role.get("role_interest")) * 0.25
        + to_float(role.get("level_fit")) * 0.20
        + to_float(role.get("job_confidence")) * 0.10
        + to_float(role.get("title_score")) * 0.05,
        2,
    )


def compute_apply_score(role: dict) -> float:
    """
    Keep an overall prioritization score for ranking, but make role fit dominant.
    Company fit is intentionally de-emphasized.
    """
    return round(
        to_float(role.get("strength_overlap")) * 0.35
        + to_float(role.get("role_interest")) * 0.25
        + to_float(role.get("level_fit")) * 0.15
        + to_float(role.get("job_confidence")) * 0.10
        + to_float(role.get("overall_interest_score")) * 0.05
        + to_float(role.get("title_score")) * 0.05
        + to_float(role.get("company_interest_score")) * 0.05,
        2,
    )


def is_apply_worthy(role: dict) -> bool:
    title_bucket = role.get("title_bucket", "unknown")

    if title_bucket == "core_pm":
        return (
            to_float(role.get("strength_overlap")) >= 8
            and to_float(role.get("role_interest")) >= 7
            and to_float(role.get("level_fit")) >= 7
            and to_float(role.get("overall_interest_score")) >= 7
            and compute_apply_score(role) >= 7.5
        )

    if title_bucket == "adjacent":
        return (
            to_float(role.get("strength_overlap")) >= 8
            and to_float(role.get("role_interest")) >= 7
            and to_float(role.get("level_fit")) >= 7
            and to_float(role.get("job_confidence")) >= 7
            and role_fit_score(role) >= 7.6
            and compute_apply_score(role) >= 7.4
        )

    # unknown / non-PM roles need extraordinary role-fit evidence
    return (
        not is_strict_non_pm_role(role)
        and to_float(role.get("strength_overlap")) >= 8
        and to_float(role.get("role_interest")) >= 8
        and to_float(role.get("level_fit")) >= 8
        and to_float(role.get("job_confidence")) >= 8
        and role_fit_score(role) >= 8.0
        and compute_apply_score(role) >= 7.8
    )


def is_network_worthy(role: dict) -> bool:
    title_bucket = role.get("title_bucket", "unknown")

    if title_bucket == "core_pm":
        return (
            to_float(role.get("overall_interest_score")) >= 7
            and compute_apply_score(role) >= 7.0
            and (
                to_float(role.get("strength_overlap")) >= 7
                or to_float(role.get("role_interest")) >= 8
                or to_float(role.get("level_fit")) >= 8
            )
        )

    if title_bucket == "adjacent":
        return (
            to_float(role.get("overall_interest_score")) >= 6.8
            and to_float(role.get("job_confidence")) >= 6.5
            and role_fit_score(role) >= 7.0
            and (
                to_float(role.get("strength_overlap")) >= 7
                or to_float(role.get("role_interest")) >= 7.5
                or to_float(role.get("level_fit")) >= 7.5
            )
        )

    # unknown titles must survive on role fit alone, not company fit
    if is_strict_non_pm_role(role):
        return False

    return (
        to_float(role.get("job_confidence")) >= 7
        and to_float(role.get("strength_overlap")) >= 8
        and to_float(role.get("role_interest")) >= 7.5
        and to_float(role.get("level_fit")) >= 7.5
        and role_fit_score(role) >= 7.6
    )


def assign_final_routes(scored_roles: list[dict]) -> list[dict]:
    if not scored_roles:
        return scored_roles

    for role in scored_roles:
        role["role_fit_score"] = role_fit_score(role)
        role["apply_score"] = compute_apply_score(role)

    ranked = sorted(
        scored_roles,
        key=lambda r: (
            to_float(r.get("apply_score")),
            to_float(r.get("role_fit_score")),
            to_float(r.get("strength_overlap")),
            to_float(r.get("role_interest")),
            to_float(r.get("level_fit")),
        ),
        reverse=True,
    )

    for idx, role in enumerate(ranked, start=1):
        role["company_rank"] = idx

    top_role = ranked[0]

    if is_apply_worthy(top_role):
        top_role["final_route"] = "Apply"
    elif is_network_worthy(top_role):
        top_role["final_route"] = "Network"
    else:
        top_role["final_route"] = "Skip"

    for role in ranked[1:]:
        prelim = role.get("preliminary_route", "Skip")

        if is_network_worthy(role) and prelim in {"Apply", "Network", "Review"}:
            role["final_route"] = "Network"
        elif prelim == "Review":
            role["final_route"] = "Review"
        else:
            role["final_route"] = "Skip"

    return ranked


def build_output_row(job: dict, company_result: dict, llm_result: dict) -> dict:
    return {
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "url": job.get("url", ""),
        "source": job.get("source", ""),
        "source_job_id": job.get("source_job_id", ""),
        "comp_min": job.get("comp_min", ""),
        "comp_max": job.get("comp_max", ""),
        "compensation": job.get("compensation", ""),
        "company_interest_score": company_result.get("company_interest_score", ""),
        "disqualifier_flags": " | ".join(llm_result.get("disqualifier_flags",[])),
        "role_interest": llm_result.get("role_interest", ""),
        "overall_interest_score": llm_result.get("overall_interest_score", ""),
        "strength_overlap": llm_result.get("strength_overlap", ""),
        "level_fit": llm_result.get("level_fit", ""),
        "job_confidence": llm_result.get("job_confidence", ""),
        "title_score": llm_result.get("title_score", ""),
        "title_bucket": llm_result.get("title_bucket", ""),
        "preliminary_route": llm_result.get("preliminary_route", ""),
        "final_route": llm_result.get("final_route", ""),
        "company_rank": llm_result.get("company_rank", ""),
        "apply_score": llm_result.get("apply_score", ""),
        "alert_priority": llm_result.get("alert_priority", ""),
        "differentiation_reason": llm_result.get("differentiation_reason", ""),
        "main_reservation": llm_result.get("main_reservation", ""),
        "first_seen_at": job.get("first_seen_at", ""),
        "first_seen_age_days": job.get("first_seen_age_days", ""),
        "freshness_bucket": job.get("freshness_bucket", ""),
    }


def compute_alert_priority(role: dict) -> str:
    final_route = role.get("final_route", "")
    freshness_bucket = role.get("freshness_bucket", "")
    apply_score = to_float(role.get("apply_score"))
    company_interest = to_float(role.get("company_interest_score"))

    if final_route == "Apply" and freshness_bucket in {"new_today", "new_3d"}:
        return "high"

    if final_route == "Apply":
        return "medium"

    if (
        final_route == "Network"
        and freshness_bucket in {"new_today", "new_3d"}
        and company_interest >= 7
        and apply_score >= 7.0
    ):
        return "medium"

    if final_route == "Network":
        return "low"

    if final_route == "Review":
        return "low"

    return "none"


def main():
    run_started_at = datetime.now(timezone.utc).isoformat()
    metrics = {
        "script": "job_monitor",
        "run_started_at": run_started_at,
        "run_finished_at": "",
        "status": "success",
        "active_companies": len([c for c in COMPANY_REGISTRY if c.get("enabled", True)]),
        "companies_checked": 0,
        "jobs_fetched": 0,
        "jobs_evaluated": 0,
        "apply_writes": 0,
        "network_writes": 0,
        "review_writes": 0,
        "skip_count": 0,
        "high_role_interest_but_skip": 0,
        "discovery_candidates": 0,
        "discovery_promoted": 0,
        "notes": "",
    }

    rows = []
    cache = load_cache()
    error_messages = []

    try:
        for company_config in COMPANY_REGISTRY:
            company_slug = company_config["company_slug"]

            try:
                if not company_config.get("enabled", True):
                    continue

                metrics["companies_checked"] += 1
                print(f"Checking company: {company_slug}")

                raw_jobs = fetch_jobs_for_company(company_config)
                metrics["jobs_fetched"] += len(raw_jobs)
                if not raw_jobs:
                    continue

                company_result = llm_score_company(company_slug, CANDIDATE_PROFILE)
                scored_roles_for_company = []

                for raw_job in raw_jobs:
                    if len(scored_roles_for_company) >= MAX_JOBS_PER_COMPANY:
                        break

                    job = normalize_job(raw_job, company_config)

                    filter_result = fast_filter_title_geo(job)
                    upsert_cache_job(cache, job, filter_result["passed"])

                    if not filter_result["passed"]:
                        continue

                    job = attach_first_seen_to_job(cache, job)
                    job = compute_freshness(job)

                    job_detail = None

                    if company_config["source"] == "greenhouse":
                        job_detail = fetch_job_detail_for_company(company_config, job["source_job_id"])
                        comp_min, comp_max = extract_comp_from_greenhouse_detail(job_detail)
                        if comp_min is not None or comp_max is not None:
                            job["comp_min"] = comp_min
                            job["comp_max"] = comp_max

                    elif company_config["source"] == "workday":
                        job_detail = fetch_job_detail_for_company(company_config, job["source_job_id"])
                        detail_fields = extract_workday_detail_fields(job_detail)
                        if detail_fields["description"]:
                            job["description"] = detail_fields["description"]
                            job["job_description"] = detail_fields["description"]
                        if detail_fields["location"] and job.get("location") in {"", "Unknown"}:
                            job["location"] = detail_fields["location"]
                        if detail_fields["url"] and not job.get("url"):
                            job["url"] = detail_fields["url"]
                        if detail_fields["comp_min"] is not None or detail_fields["comp_max"] is not None:
                            job["comp_min"] = detail_fields["comp_min"]
                            job["comp_max"] = detail_fields["comp_max"]

                    job = fill_missing_comp(job, job_detail=job_detail)
                    job["compensation"] = format_compensation(job.get("comp_min"), job.get("comp_max"))

                    comp_result = check_comp(job.get("comp_min"), job.get("comp_max"))
                    if not comp_result["passed"]:
                        continue

                    metrics["jobs_evaluated"] += 1
                    llm_result = llm_score_job(job, CANDIDATE_PROFILE, company_result)

                    combined = {
                        **job,
                        **llm_result,
                        "title_score": filter_result.get("title_score"),
                        "title_bucket": filter_result.get("title_bucket"),
                    }
                    scored_roles_for_company.append(combined)

                if not scored_roles_for_company:
                    continue

                ranked_roles = assign_final_routes(scored_roles_for_company)

                company_disqualifiers = company_result.get("disqualifier_flags", []) or []

                if company_disqualifiers:
                    for role in ranked_roles:
                        role["final_route"] = "Skip"
                        role["main_reservation"] = (
                            f"Candidate disqualifier: {','.join(company_disqualifiers)}"
                        )

                for role in ranked_roles:
                    role["alert_priority"] = compute_alert_priority(role)

                    if role["final_route"] == "Skip":
                        metrics["skip_count"] += 1
                        if to_float(role.get("role_interest")) >= ROLE_INTEREST_THRESHOLD:
                            metrics["high_role_interest_but_skip"] += 1
                        continue

                    # Final safety gate before Notion write:
                    # unknown / strict non-PM roles must have unusually strong role-fit evidence.
                    if (
                        role.get("title_bucket", "unknown") == "unknown"
                        and (
                            is_strict_non_pm_role(role)
                            or to_float(role.get("role_fit_score")) < 7.6
                            or to_float(role.get("job_confidence")) < 7
                        )
                    ):
                        role["final_route"] = "Skip"
                        role["main_reservation"] = (
                            role.get("main_reservation")
                            or "Unknown/non-PM role did not show strong enough job-fit evidence."
                        )
                        metrics["skip_count"] += 1
                        continue

                    try:
                        upsert_eval_job(role)
                        print(f"→ Notion: {role['company']} | {role['title']} | {role['final_route']}")

                        if role["final_route"] == "Apply":
                            metrics["apply_writes"] += 1
                        elif role["final_route"] == "Network":
                            metrics["network_writes"] += 1
                        elif role["final_route"] == "Review":
                            metrics["review_writes"] += 1

                    except Exception as e:
                        msg = f"Notion error for {role.get('company')} | {role.get('title')}: {e}"
                        print(msg)
                        error_messages.append(msg)

                for role in ranked_roles:
                    rows.append(build_output_row(role, company_result, role))

            except Exception as e:
                msg = f"Error processing {company_slug}: {e}"
                print(msg)
                error_messages.append(msg)
                continue

            print("LOOPING COMPANY:", company_config["company_slug"], "| enabled:", company_config.get("enabled", True))

        if rows:
            with open("llm_eval_results.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            print(f"\nWrote {len(rows)} rows to llm_eval_results.csv")
        else:
            print("No rows matched the filter.")

        save_cache(cache)

        if error_messages:
            metrics["status"] = "partial_failure"
            metrics["notes"] = " | ".join(error_messages[:10])

    except Exception as e:
        metrics["status"] = "failed"
        metrics["notes"] = str(e)
        raise

    finally:
        metrics["run_finished_at"] = datetime.now(timezone.utc).isoformat()
        append_run_metric(metrics)


if __name__ == "__main__":
    main()
