"""
Pre-LLM job filter lists — optional JSON in candidate_data/candidate_profile.txt.

Merge: any key omitted or invalid falls back to defaults. Empty string lists
use defaults (empty target list would reject everything).
"""

import json
import re
from copy import deepcopy
from pathlib import Path

START_MARKER = "=== JOB FILTER CONFIG ==="
END_MARKER = "=== END JOB FILTER CONFIG ==="

DEFAULT_JOB_FILTER = {
    "target_titles": [
        "product manager",
        "senior product manager",
        "principal product manager",
        "staff product manager",
        "group product manager",
        "lead product manager",
        "forward deployed product manager",
        "platform product manager",
        "growth product manager",
    ],
    "adjacent_titles": [
        "program manager",
        "technical program manager",
        "product operations",
        "product ops",
        "solutions architect",
        "solutions consultant",
        "implementation manager",
        "strategy and operations",
        "business operations",
    ],
    "too_junior_words": [
        "intern",
        "associate",
        "junior",
        "new grad",
        "apm",
    ],
    "too_senior_words": [
        "director",
        "vp ",
        "vice president",
        "chief product officer",
        "cpo",
        "head of product",
    ],
    "local_region_terms": [
        "san francisco",
        "sf, ca",
        "san jose",
        "santa clara",
        "mountain view",
        "palo alto",
        "menlo park",
        "redwood city",
        "sunnyvale",
        "south san francisco",
        "bay area",
        "cupertino",
        "foster city",
        "burlingame",
        "milpitas",
        "oakland",
        "berkeley",
        "san mateo",
    ],
    "remote_positive_terms": [
        "remote",
        "work from home",
        "distributed",
        "anywhere",
    ],
    "remote_broad_pass_terms": [
        "united states",
        "usa",
        "u.s.",
        "us-only",
        "us only",
        "california",
    ],
    "remote_restricted_terms": [
        "emea",
        "europe",
        "india",
        "canada",
        "uk",
        "united kingdom",
        "apac",
        "singapore",
        "australia",
        "japan",
        "germany",
        "france",
        "prague",
        "pristina",
        "czech republic",
        "czechia",
        "kosovo",
    ],
    "non_local_city_terms": [
        "new york",
        "new york, ny",
        "ny, ny",
        "nyc",
        "seattle",
        "austin",
        "boston",
        "chicago",
        "los angeles",
        "san diego",
        "atlanta",
        "denver",
        "washington, dc",
        "washington dc",
        "london",
        "toronto",
        "prague",
        "pristina",
    ],
    "hybrid_terms": [
        "hybrid",
        "flex",
        "flexible",
    ],
    "location_split_pattern": r"[;/|]|\s+\|\s+|\s+or\s+",
    "min_acceptable_max_comp": 200000,
    "description_location_reject_phrases": [
        "not eligible to be hired in san jose, ca",
        "not eligible to be hired in california",
        "not open to candidates in california",
        "cannot hire in california",
        "we are unable to employ in california",
        "not hiring in california",
        "excluding california",
        "except california",
        "remote but not eligible to be hired in san jose, ca",
        "remote but not eligible to be hired in california",
    ],
}


def _coerce_str_list(val, fallback: list[str], key: str) -> list[str]:
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        print(f"[job_filter_config] invalid list for {key!r}, using default")
        return list(fallback)
    out = [x.strip() for x in val if x.strip()]
    return out if out else list(fallback)


def _merge_job_filter_overrides(raw: dict) -> dict:
    cfg = deepcopy(DEFAULT_JOB_FILTER)
    if not isinstance(raw, dict):
        print("[job_filter_config] JOB FILTER CONFIG must be a JSON object, using defaults")
        return cfg

    for key in DEFAULT_JOB_FILTER:
        if key not in raw:
            continue
        val = raw[key]
        if key in (
            "target_titles",
            "adjacent_titles",
            "too_junior_words",
            "too_senior_words",
            "local_region_terms",
            "remote_positive_terms",
            "remote_broad_pass_terms",
            "remote_restricted_terms",
            "non_local_city_terms",
            "hybrid_terms",
            "description_location_reject_phrases",
        ):
            cfg[key] = _coerce_str_list(val, DEFAULT_JOB_FILTER[key], key)
        elif key == "location_split_pattern":
            if not isinstance(val, str) or not val.strip():
                print(f"[job_filter_config] invalid {key!r}, using default")
                continue
            try:
                re.compile(val)
            except re.error as e:
                print(f"[job_filter_config] invalid regex for {key!r}: {e}, using default")
                continue
            cfg[key] = val.strip()
        elif key == "min_acceptable_max_comp":
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                print(f"[job_filter_config] invalid {key!r}, using default")
                continue
            num = int(float(val))
            if num <= 0:
                print(f"[job_filter_config] invalid {key!r}, using default")
                continue
            cfg[key] = num

    return cfg


def parse_job_filter_config_from_profile(profile_text: str) -> dict:
    if START_MARKER not in profile_text or END_MARKER not in profile_text:
        return deepcopy(DEFAULT_JOB_FILTER)

    try:
        start_idx = profile_text.index(START_MARKER) + len(START_MARKER)
        end_idx = profile_text.index(END_MARKER, start_idx)
        raw = profile_text[start_idx:end_idx].strip()
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[job_filter_config] invalid JOB FILTER CONFIG JSON, using defaults: {e}")
        return deepcopy(DEFAULT_JOB_FILTER)

    return _merge_job_filter_overrides(data)


def load_job_filter_config(profile_path: Path) -> dict:
    if not profile_path.exists():
        print(
            f"[job_filter_config] profile not found at {profile_path}, "
            "using default job filter config"
        )
        return deepcopy(DEFAULT_JOB_FILTER)
    try:
        text = profile_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[job_filter_config] failed to read {profile_path}: {e}, using defaults")
        return deepcopy(DEFAULT_JOB_FILTER)
    return parse_job_filter_config_from_profile(text)
