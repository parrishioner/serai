"""
ATS discovery: precise search pattern groups, optional profile-driven keywords.

Precise title lists are in DISCOVERY_PATTERNS. Broad sweep + adjacent substring
keywords default below and can be overridden via JSON in candidate_data/
candidate_profile.txt between COMPANY DISCOVERY CONFIG markers.
"""

import json
from pathlib import Path

START_MARKER = "=== COMPANY DISCOVERY CONFIG ==="
END_MARKER = "=== END COMPANY DISCOVERY CONFIG ==="

# Defaults when the profile is missing or has no valid block (growth PM example).
DEFAULT_ADJACENT_TITLE_KEYWORDS = [
    "product engineer",
    "growth engineer",
    "platform",
    "developer platform",
    "ecosystem",
    "api",
    "solutions",
    "forward deployed",
    "product operations",
    "strategy",
    "ai engineer",
    "ai workflow",
]

DEFAULT_BROAD_SWEEP_TITLES = [
    "product manager",
    "product lead",
    "product",
    "platform product manager",
    "ai product manager",
    "growth product manager",
    "forward deployed product manager",
]

DISCOVERY_PATTERNS = [
    {
        "name": "core_pm",
        "titles": [
            "product manager",
            "senior product manager",
            "principal product manager",
            "staff product manager",
            "group product manager",
            "lead product manager",
        ],
    },
    {
        "name": "platform_pm",
        "titles": [
            "platform product manager",
            "developer platform product manager",
            "ecosystem product manager",
            "api product manager",
            "identity product manager",
            "security product manager",
            "governance product manager",
            "privacy product manager",
            "integrations product manager",
        ],
    },
    {
        "name": "ai_pm",
        "titles": [
            "ai product manager",
            "product manager ai",
            "product manager agents",
            "product manager automation",
            "agent product manager",
            "machine learning product manager",
        ],
    },
    {
        "name": "growth_pm",
        "titles": [
            "growth product manager",
            "monetization product manager",
            "onboarding product manager",
            "retention product manager",
            "activation product manager",
            "product manager growth",
        ],
    },
    {
        "name": "adjacent_roles",
        "titles": [
            "forward deployed product manager",
            "technical program manager",
            "product operations",
            "product ops",
            "solutions architect",
            "solutions consultant",
            "implementation manager",
            "strategy and operations",
            "business operations",
        ],
    },
]


def _normalize_str_list(value, label: str, fallback: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        print(
            f"[discovery_config] {label} must be a JSON array of strings; "
            "using defaults for that list."
        )
        return list(fallback)
    out = [x.strip() for x in value if (x or "").strip()]
    return out if out else list(fallback)


def parse_discovery_config_from_profile(profile_text: str) -> tuple[list[str], list[str]]:
    """
    Parse optional JSON between COMPANY DISCOVERY CONFIG markers.
    Expected shape: {"adjacent_title_keywords": [...], "broad_sweep_titles": [...]}
    """
    if START_MARKER not in profile_text or END_MARKER not in profile_text:
        return list(DEFAULT_ADJACENT_TITLE_KEYWORDS), list(DEFAULT_BROAD_SWEEP_TITLES)

    try:
        start_idx = profile_text.index(START_MARKER) + len(START_MARKER)
        end_idx = profile_text.index(END_MARKER, start_idx)
        raw = profile_text[start_idx:end_idx].strip()
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as e:
        print(
            f"[discovery_config] invalid COMPANY DISCOVERY CONFIG JSON, using defaults: {e}"
        )
        return list(DEFAULT_ADJACENT_TITLE_KEYWORDS), list(DEFAULT_BROAD_SWEEP_TITLES)

    if not isinstance(data, dict):
        print("[discovery_config] COMPANY DISCOVERY CONFIG must be a JSON object, using defaults")
        return list(DEFAULT_ADJACENT_TITLE_KEYWORDS), list(DEFAULT_BROAD_SWEEP_TITLES)

    adjacent = _normalize_str_list(
        data.get("adjacent_title_keywords"),
        "adjacent_title_keywords",
        DEFAULT_ADJACENT_TITLE_KEYWORDS,
    )
    broad = _normalize_str_list(
        data.get("broad_sweep_titles"),
        "broad_sweep_titles",
        DEFAULT_BROAD_SWEEP_TITLES,
    )
    return adjacent, broad


def load_discovery_keywords(profile_path: Path) -> tuple[list[str], list[str]]:
    if not profile_path.exists():
        print(
            f"[discovery_config] profile not found at {profile_path}, "
            "using default discovery keywords"
        )
        return list(DEFAULT_ADJACENT_TITLE_KEYWORDS), list(DEFAULT_BROAD_SWEEP_TITLES)
    try:
        text = profile_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[discovery_config] failed to read {profile_path}: {e}, using defaults")
        return list(DEFAULT_ADJACENT_TITLE_KEYWORDS), list(DEFAULT_BROAD_SWEEP_TITLES)
    return parse_discovery_config_from_profile(text)
