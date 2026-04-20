print("LOADING JOB FILTER FILE")

import re

TARGET_PM_TITLES = [
    "product manager",
    "senior product manager",
    "principal product manager",
    "staff product manager",
    "group product manager",
    "lead product manager",
    "forward deployed product manager",
    "platform product manager",
    "growth product manager",
]

ADJACENT_TITLES = [
    "program manager",
    "technical program manager",
    "product operations",
    "product ops",
    "solutions architect",
    "solutions consultant",
    "implementation manager",
    "strategy and operations",
    "business operations",
]

TOO_JUNIOR_WORDS = [
    "intern",
    "associate",
    "junior",
    "new grad",
    "apm",
]

TOO_SENIOR_WORDS = [
    "director",
    "vp ",
    "vice president",
    "chief product officer",
    "cpo",
    "head of product",
]

BAY_AREA_TERMS = [
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
]

REMOTE_POSITIVE_TERMS = [
    "remote",
    "work from home",
    "distributed",
    "anywhere",
]

BROAD_REMOTE_PASS_TERMS = [
    "united states",
    "usa",
    "u.s.",
    "us-only",
    "us only",
    "california",
]

REMOTE_RESTRICTED_TERMS = [
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
]

NON_LOCAL_CITY_TERMS = [
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
]

HYBRID_TERMS = [
    "hybrid",
    "flex",
    "flexible",
]

LOCATION_SPLIT_PATTERN = r"[;/|]|\s+\|\s+|\s+or\s+"

MIN_ACCEPTABLE_MAX_COMP = 200000

DESCRIPTION_LOCATION_REJECT_PHRASES = [
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
]

DEBUG_GEO = False


def score_title_affinity(title):
    title = (title or "").lower().strip()

    if any(word in title for word in TOO_JUNIOR_WORDS):
        return {
            "passed": False,
            "score": 0,
            "reason": "title_reject:too_junior",
            "bucket": "reject",
        }

    if any(word in title for word in TOO_SENIOR_WORDS):
        return {
            "passed": False,
            "score": 0,
            "reason": "title_reject:too_senior",
            "bucket": "reject",
        }

    if any(phrase in title for phrase in TARGET_PM_TITLES):
        return {
            "passed": True,
            "score": 10,
            "reason": "title_soft_pass:target_pm_title",
            "bucket": "core_pm",
        }

    if any(phrase in title for phrase in ADJACENT_TITLES):
        return {
            "passed": True,
            "score": 6,
            "reason": "title_soft_pass:adjacent_title",
            "bucket": "adjacent",
        }

    return {
        "passed": True,
        "score": 3,
        "reason": "title_soft_pass:unknown_title",
        "bucket": "unknown",
    }


def check_comp(comp_min, comp_max):
    if comp_min is None and comp_max is None:
        return {
            "passed": True,
            "reason": "comp_unknown:missing_comp_range",
            "force_review": True,
        }

    if comp_max is not None and comp_max < MIN_ACCEPTABLE_MAX_COMP:
        return {
            "passed": False,
            "reason": f"comp_reject:max_comp_below_{MIN_ACCEPTABLE_MAX_COMP}",
            "force_review": False,
        }

    return {
        "passed": True,
        "reason": "comp_pass:range_ok_or_open_ended",
        "force_review": False,
    }


def normalize_location_text(text):
    return (text or "").lower().strip()


def split_locations(location_text):
    if not location_text:
        return []

    parts = re.split(LOCATION_SPLIT_PATTERN, location_text)
    cleaned = [part.strip() for part in parts if part.strip()]

    if not cleaned:
        return [location_text.strip()]

    return cleaned


def has_any_term(text, terms):
    return any(term in text for term in terms)


def classify_single_location(location):
    location = normalize_location_text(location)

    if not location:
        return {
            "category": "missing",
            "passed": False,
            "reason": "geo_reject:missing_location",
            "force_review": False,
        }

    is_hybrid = has_any_term(location, HYBRID_TERMS)

    if has_any_term(location, BAY_AREA_TERMS):
        if is_hybrid:
            return {
                "category": "hybrid_local",
                "passed": True,
                "reason": "geo_pass:hybrid_bay_area",
                "force_review": False,
            }
        return {
            "category": "bay_area",
            "passed": True,
            "reason": "geo_pass:bay_area",
            "force_review": False,
        }

    if has_any_term(location, NON_LOCAL_CITY_TERMS):
        if is_hybrid:
            return {
                "category": "hybrid_non_local",
                "passed": False,
                "reason": "geo_reject:hybrid_non_local_city",
                "force_review": False,
            }
        return {
            "category": "non_local",
            "passed": False,
            "reason": "geo_reject:non_local_city",
            "force_review": False,
        }

    if has_any_term(location, REMOTE_POSITIVE_TERMS):
        if has_any_term(location, REMOTE_RESTRICTED_TERMS):
            return {
                "category": "remote_restricted",
                "passed": False,
                "reason": "geo_reject:remote_outside_target_geo",
                "force_review": False,
            }

        if has_any_term(location, BROAD_REMOTE_PASS_TERMS):
            return {
                "category": "remote_ok",
                "passed": True,
                "reason": "geo_pass:remote_us_or_ca",
                "force_review": False,
            }

        return {
            "category": "remote_ambiguous",
            "passed": False,
            "reason": "geo_reject:remote_scope_unclear",
            "force_review": False,
        }

    if has_any_term(location, BROAD_REMOTE_PASS_TERMS):
        return {
            "category": "remote_ok",
            "passed": True,
            "reason": "geo_pass:broad_remote_region",
            "force_review": False,
        }

    if is_hybrid:
        return {
            "category": "hybrid_ambiguous",
            "passed": False,
            "reason": "geo_reject:hybrid_location_unclear",
            "force_review": False,
        }

    return {
        "category": "ambiguous",
        "passed": False,
        "reason": "geo_reject:unknown_location",
        "force_review": False,
    }


def check_geo(location_text):
    location_parts = split_locations(location_text)

    if DEBUG_GEO:
        print("DEBUG check_geo raw location_text =", repr(location_text))
        print("DEBUG check_geo location_parts =", location_parts)

    if not location_parts:
        return {
            "passed": False,
            "reason": "geo_reject:missing_location",
            "category": "missing",
            "force_review": False,
            "details": [],
        }

    results = [classify_single_location(part) for part in location_parts]
    details = [f"{part} -> {res['reason']}" for part, res in zip(location_parts, results)]

    if DEBUG_GEO:
        print("DEBUG check_geo results =", results)

    if any(result["category"] in ["non_local", "hybrid_non_local", "remote_restricted"] for result in results):
        return {
            "passed": False,
            "reason": "geo_reject:explicit_non_local_or_restricted_location",
            "category": "non_local",
            "force_review": False,
            "details": details,
        }

    for preferred_category in ["bay_area", "hybrid_local", "remote_ok"]:
        for result in results:
            if result["category"] == preferred_category and result["passed"]:
                return {
                    "passed": True,
                    "reason": result["reason"],
                    "category": result["category"],
                    "force_review": result["force_review"],
                    "details": details,
                }

    return {
        "passed": False,
        "reason": "geo_reject:no_acceptable_location_option",
        "category": "ambiguous",
        "force_review": False,
        "details": details,
    }


def check_description_geo_exclusions(description_text):
    text = normalize_location_text(description_text)

    for phrase in DESCRIPTION_LOCATION_REJECT_PHRASES:
        if phrase in text:
            return {
                "passed": False,
                "reason": f"geo_reject:description_exclusion:{phrase}",
            }

    return {
        "passed": True,
        "reason": "geo_pass:no_description_exclusion",
    }


def fast_filter_title_geo(job, llm_geo_classifier=None):
    title = job.get("title", "")
    location = job.get("location", "")
    description = job.get("description", "")

    details = []

    title_result = score_title_affinity(title)
    details.append(title_result["reason"])
    if not title_result["passed"]:
        return {
            "passed": False,
            "reason": title_result["reason"],
            "details": details,
            "force_review": False,
            "geo_category": None,
            "title_score": 0,
            "title_bucket": "reject",
        }

    geo_result = check_geo(location)
    details.extend(geo_result.get("details", []))
    details.append(geo_result["reason"])

    if not geo_result["passed"]:
        return {
            "passed": False,
            "reason": geo_result["reason"],
            "details": details,
            "force_review": False,
            "geo_category": geo_result["category"],
            "title_score": title_result["score"],
            "title_bucket": title_result["bucket"],
        }

    description_geo_result = check_description_geo_exclusions(description)
    details.append(description_geo_result["reason"])

    if not description_geo_result["passed"]:
        return {
            "passed": False,
            "reason": description_geo_result["reason"],
            "details": details,
            "force_review": False,
            "geo_category": geo_result["category"],
            "title_score": title_result["score"],
            "title_bucket": title_result["bucket"],
        }

    return {
        "passed": True,
        "reason": "title_geo_pass",
        "details": details,
        "force_review": geo_result["force_review"],
        "geo_category": geo_result["category"],
        "title_score": title_result["score"],
        "title_bucket": title_result["bucket"],
    }
