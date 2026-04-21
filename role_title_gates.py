"""
Configurable substring checks for unknown title-bucket routing (eval + YC flows).

When job_filter assigns title_bucket == \"unknown\", these substrings flag titles
that are usually the wrong track for the candidate (e.g. hands-on engineering
titles when the target role family is product). Override via JSON in
candidate_data/candidate_profile.txt — see markers below.
"""

import json
from pathlib import Path

START_MARKER = "=== EVAL UNKNOWN-BUCKET TITLE SUBSTRINGS ==="
END_MARKER = "=== END EVAL UNKNOWN-BUCKET TITLE SUBSTRINGS ==="

# Used when the profile is missing markers or JSON is invalid.
DEFAULT_UNKNOWN_BUCKET_TITLE_SUBSTRINGS = [
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


def role_title_matches_exclusion_substrings(role: dict, substrings: list[str]) -> bool:
    """True if the job title (lowercased) contains any configured substring."""
    if not substrings:
        return False
    title = str(role.get("title", "")).lower()
    return any(substr in title for substr in substrings)


def parse_unknown_bucket_title_substrings(profile_text: str) -> list[str]:
    """
    Parse a JSON array of substrings between markers. Empty array [] is honored
    (no title-based exclusions). Omitted markers fall back to defaults.
    """
    if START_MARKER not in profile_text or END_MARKER not in profile_text:
        return list(DEFAULT_UNKNOWN_BUCKET_TITLE_SUBSTRINGS)

    try:
        start_idx = profile_text.index(START_MARKER) + len(START_MARKER)
        end_idx = profile_text.index(END_MARKER, start_idx)
        raw = profile_text[start_idx:end_idx].strip()
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as e:
        print(
            f"[role_title_gates] invalid EVAL UNKNOWN-BUCKET TITLE SUBSTRINGS JSON, "
            f"using defaults: {e}"
        )
        return list(DEFAULT_UNKNOWN_BUCKET_TITLE_SUBSTRINGS)

    if not isinstance(data, list):
        print(
            "[role_title_gates] EVAL UNKNOWN-BUCKET block must be a JSON array, using defaults"
        )
        return list(DEFAULT_UNKNOWN_BUCKET_TITLE_SUBSTRINGS)

    out = [x.strip() for x in data if isinstance(x, str) and x.strip()]
    return out


def load_unknown_bucket_title_substrings(profile_path: Path) -> list[str]:
    if not profile_path.exists():
        print(
            f"[role_title_gates] profile not found at {profile_path}, "
            "using default unknown-bucket title substrings"
        )
        return list(DEFAULT_UNKNOWN_BUCKET_TITLE_SUBSTRINGS)
    try:
        text = profile_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[role_title_gates] failed to read {profile_path}: {e}, using defaults")
        return list(DEFAULT_UNKNOWN_BUCKET_TITLE_SUBSTRINGS)
    return parse_unknown_bucket_title_substrings(text)
