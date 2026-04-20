import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dotenv import load_dotenv
from openai import OpenAI


DEBUG = False
VERBOSE_LOGGING = False

load_dotenv()

client = OpenAI(timeout=30.0)

BASE_DIR = Path(__file__).resolve().parent
CACHE_FILE = BASE_DIR / "llm_job_cache.json"
MODEL_NAME = "gpt-4o-mini"
JOB_PROMPT_VERSION = "job_v36"

CANDIDATE_PROFILE_FILE = BASE_DIR / "candidate_data" / "candidate_profile.txt"
RESUME_FILE = BASE_DIR / "candidate_data" / "resume.md"
ANCHOR_STORIES_FILE = BASE_DIR / "candidate_data" / "anchor_stories.yaml"
PROMPT_TEMPLATE_FILE = BASE_DIR / "prompts" / "role_eval_prompt.txt"


def debug_print(*args: Any) -> None:
    if DEBUG:
        print(*args)


def verbose_print(*args: Any) -> None:
    if VERBOSE_LOGGING:
        print(*args)


def load_text_file(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return default


def load_yaml_file(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if default is None:
        default = {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else default
    except (OSError, yaml.YAMLError):
        return default


PROMPT_TEMPLATE = load_text_file(PROMPT_TEMPLATE_FILE)
DEFAULT_CANDIDATE_PROFILE = load_text_file(CANDIDATE_PROFILE_FILE)
RESUME_TEXT = load_text_file(RESUME_FILE)
ANCHOR_STORIES = load_yaml_file(ANCHOR_STORIES_FILE, default={"stories": []})

if DEBUG:
    debug_print("ANCHOR STORIES LOADED:", len(ANCHOR_STORIES.get("stories", [])))


def load_job_cache() -> Dict[str, Any]:
    if not CACHE_FILE.exists():
        return {}

    try:
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_job_cache(cache: Dict[str, Any]) -> None:
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def normalize_text(value: Any, default: str = "N/A") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        return value if value else default
    return str(value)


def normalize_keyword(value: str) -> str:
    return value.lower().strip().replace("_", " ")


def extract_job_description(job: Dict[str, Any]) -> str:
    candidates = [
        job.get("description"),
        job.get("job_description"),
        job.get("content"),
        job.get("body"),
        job.get("text"),
        job.get("requirements"),
        job.get("responsibilities"),
        job.get("summary"),
        job.get("details"),
    ]

    for candidate in candidates:
        normalized = normalize_text(candidate, "")
        if normalized:
            return normalized

    return "No job description provided."


def get_keyword_weight(keyword: str) -> int:
    high_signal_terms = {
        "security": 5,
        "governance": 5,
        "privacy": 5,
        "compliance": 5,
        "policy": 4,
        "policies": 4,
        "permissions": 4,
        "access": 3,
        "controls": 4,
        "audit": 4,
        "risk": 4,
        "trust": 4,
        "gdpr": 5,
        "data protection": 5,
        "user data": 4,
        "deletion": 4,
        "reporting": 3,
        "api": 3,
        "platform": 2,
        "developer": 2,
        "ecosystem": 2,
        "migration": 3,
        "growth": 3,
        "monetization": 4,
        "conversion": 4,
        "experimentation": 4,
        "onboarding": 3,
        "productivity": 3,
        "workflow": 2,
        "ai": 3,
        "agent": 4,
        "agents": 4,
        "automation": 3,
        "enterprise": 3,
        "integration": 3,
        "integrations": 3,
    }
    return high_signal_terms.get(keyword, 2)


def score_story_against_jd(story: Dict[str, Any], jd: str) -> int:
    score = 0

    for keyword in story.get("keywords", []):
        if isinstance(keyword, str):
            normalized = keyword.lower().strip()
            if normalized and normalized in jd:
                score += get_keyword_weight(normalized)

    theme = story.get("theme", "")
    if isinstance(theme, str):
        theme_normalized = normalize_keyword(theme)
        if theme_normalized and theme_normalized in jd:
            score += 4

    for strength in story.get("strengths", []):
        if isinstance(strength, str):
            strength_normalized = normalize_keyword(strength)
            if strength_normalized and strength_normalized in jd:
                score += 2

    title = story.get("title", "")
    if isinstance(title, str):
        for token in title.lower().replace("/", " ").split():
            if len(token) >= 5 and token in jd:
                score += get_keyword_weight(token)

    jd_security_governance = any(
        term in jd
        for term in [
            "security",
            "governance",
            "privacy",
            "compliance",
            "policy",
            "risk",
            "trust",
            "permissions",
            "access control",
            "data protection",
        ]
    )
    if jd_security_governance and story.get("id") == "privacy_platform":
        score += 8

    jd_growth = any(
        term in jd
        for term in [
            "growth",
            "conversion",
            "activation",
            "onboarding",
            "retention",
            "monetization",
            "funnel",
        ]
    )
    if jd_growth and story.get("id") == "trello_growth":
        score += 6

    jd_platform = any(
        term in jd
        for term in [
            "platform",
            "developer",
            "ecosystem",
            "migration",
            "integration",
            "integrations",
            "api",
            "infrastructure",
        ]
    )
    if jd_platform and story.get("id") == "migration_platform":
        score += 5

    jd_ai = any(
        term in jd
        for term in [
            "ai",
            "artificial intelligence",
            "llm",
            "agent",
            "agents",
            "copilot",
            "workflow automation",
            "automation",
        ]
    )
    if jd_ai and story.get("id") == "ai_augmented_product_development":
        score += 5

    return score


def select_relevant_stories(
    anchor_data: Dict[str, Any],
    job_description: str,
    max_stories: int = 3,
) -> List[Dict[str, Any]]:
    jd = normalize_text(job_description, "").lower()
    stories = anchor_data.get("stories", [])

    if not isinstance(stories, list) or not stories:
        return []

    if not jd or jd in {"n/a", "no job description provided."}:
        return [s for s in stories if isinstance(s, dict)][:max_stories]

    scored: List[Tuple[int, Dict[str, Any]]] = []

    for story in stories:
        if not isinstance(story, dict):
            continue
        score = score_story_against_jd(story, jd)
        scored.append((score, story))

    scored.sort(key=lambda x: x[0], reverse=True)

    if DEBUG:
        debug_print("\n=== DEBUG: STORY SCORES ===")
        for score, story in scored:
            debug_print(f"{story.get('id')}: {score}")
        debug_print("=== END STORY SCORES ===\n")

    return [story for score, story in scored[:max_stories]]


def format_anchor_stories(stories: List[Dict[str, Any]]) -> str:
    if not stories:
        return "No anchor stories provided."

    chunks = []

    for story in stories:
        title = normalize_text(story.get("title"), "Untitled story")
        theme = normalize_text(story.get("theme"), "N/A")
        strengths = ", ".join(
            s for s in story.get("strengths", []) if isinstance(s, str)
        ) or "N/A"
        summary = normalize_text(story.get("summary"), "N/A")

        chunks.append(
            f"- {title}\n"
            f"  Theme: {theme}\n"
            f"  Proven strengths demonstrated: {strengths}\n"
            f"  Summary: {summary}"
        )

    return "\n\n".join(chunks)


def build_candidate_context(
    job_description: str,
    candidate_profile_override: str = "",
) -> Dict[str, str]:
    candidate_profile = normalize_text(
        candidate_profile_override or DEFAULT_CANDIDATE_PROFILE,
        "No candidate profile provided.",
    )

    all_stories = ANCHOR_STORIES.get("stories", [])
    if not isinstance(all_stories, list):
        all_stories = []

    relevant_stories = select_relevant_stories(
        ANCHOR_STORIES,
        job_description=job_description,
        max_stories=3,
    )

    if not relevant_stories:
        relevant_stories = [s for s in all_stories if isinstance(s, dict)][:3]

    if DEBUG:
        debug_print("RELEVANT STORIES COUNT:", len(relevant_stories))

    return {
        "candidate_profile": candidate_profile,
        "resume_text": normalize_text(RESUME_TEXT, "No resume provided."),
        "anchor_stories": format_anchor_stories(relevant_stories),
    }


def make_job_cache_key(
    job: Dict[str, Any],
    company_result: Dict[str, Any],
    candidate_profile_override: str = "",
) -> str:
    effective_candidate_profile = candidate_profile_override or DEFAULT_CANDIDATE_PROFILE

    key_payload = {
        "job_prompt_version": JOB_PROMPT_VERSION,
        "model_name": MODEL_NAME,
        "candidate_profile_hash": hashlib.md5(
            effective_candidate_profile.encode("utf-8")
        ).hexdigest(),
        "resume_hash": hashlib.md5(RESUME_TEXT.encode("utf-8")).hexdigest(),
        "anchor_stories_hash": hashlib.md5(
            json.dumps(ANCHOR_STORIES, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "prompt_template_hash": hashlib.md5(PROMPT_TEMPLATE.encode("utf-8")).hexdigest(),
        "company": normalize_text(job.get("company")),
        "title": normalize_text(job.get("title")),
        "url": normalize_text(job.get("url")),
        "location": normalize_text(job.get("location")),
        "compensation": normalize_text(job.get("compensation")),
        "job_description": extract_job_description(job),
        "company_interest_score": company_result.get("company_interest_score"),
        "company_interest_reason": normalize_text(
            company_result.get("company_interest_reason")
            or company_result.get("company_interest")
            or ""
        ),
    }
    key_str = json.dumps(key_payload, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(key_str.encode("utf-8")).hexdigest()


def build_prompt(
    job: Dict[str, Any],
    candidate_profile: str,
    company_result: Dict[str, Any],
) -> str:
    background_company_context = company_result.get(
        "company_interest_reason",
        company_result.get("company_interest", "No company context provided."),
    )

    job_description = extract_job_description(job)

    candidate_context = build_candidate_context(
        job_description=job_description,
        candidate_profile_override=candidate_profile,
    )

    if DEBUG:
        debug_print("\n=== DEBUG: CANDIDATE CONTEXT ===")
        debug_print("ANCHOR STORIES RAW:")
        debug_print(candidate_context["anchor_stories"])
        debug_print("=== END DEBUG ===\n")

    if not PROMPT_TEMPLATE:
        raise ValueError(
            f"Prompt template file is missing or empty: {PROMPT_TEMPLATE_FILE}"
        )

    hard_guardrails = """
CRITICAL ROLE-FIT GUARDRAILS

Treat company attractiveness and role attractiveness separately.
A strong company must NOT rescue a weak role.

This candidate is a Senior Product Manager / platform / growth / ecosystem product leader.
She has NOT worked as a software engineer and should be treated as having no current hands-on
software engineering fit for roles whose success depends on coding, architecture ownership,
backend/frontend/full-stack implementation, ML engineering, infra engineering, security engineering,
or research engineering.

For clearly engineering roles:
- strength_overlap should usually be 2-4
- level_fit should usually be 2-4
- role_interest should usually be 2-5
- overall_interest_score should usually be 2-5
- preliminary_route should usually be Skip
Only score above those ranges if the JD gives unusually strong evidence that the role is actually
product-shaping, forward-deployed, customer-facing, or otherwise nontraditional in a way that
fits this candidate truthfully.

If the role would require narrative stretching to sound credible in an interview, score it down.
If the candidate lacks obvious hard prerequisites, say so directly in main_reservation.
Do not hide role-family mismatch behind vague reservations like product culture, durability, or domain uncertainty.

For non-PM / unknown-title roles:
- extremely strong evidence of job fit is required
- company score should not meaningfully increase role_interest or overall_interest_score
- if the title is software engineer / engineer / developer / architect / researcher and the work is primarily hands-on technical implementation, the candidate is a poor fit unless the JD clearly proves otherwise
"""

    rendered_template = PROMPT_TEMPLATE.format(
        candidate_profile=candidate_context["candidate_profile"],
        resume_text=candidate_context["resume_text"],
        anchor_stories=candidate_context["anchor_stories"],
        background_company_context=normalize_text(
            background_company_context, "No company context provided."
        ),
        company_interest_score=company_result.get("company_interest_score", "N/A"),
        company=normalize_text(job.get("company")),
        job_title=normalize_text(job.get("title")),
        location=normalize_text(job.get("location")),
        compensation=normalize_text(job.get("compensation")),
        job_description=job_description,
    )

    rendered_prompt = hard_guardrails.strip() + "\n\n" + rendered_template

    if DEBUG:
        debug_print("\n=== DEBUG: RENDERED PROMPT CHECK ===")
        anchor_section_start = rendered_prompt.find("MOST RELEVANT ANCHOR STORIES")
        if anchor_section_start != -1:
            debug_print(rendered_prompt[anchor_section_start:anchor_section_start + 1500])
        else:
            debug_print("Anchor stories section not found in rendered prompt.")
        debug_print("=== END DEBUG ===\n")

    return rendered_prompt


def get_json_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "company_interest_score": {"type": "number"},
            "role_interest": {"type": "number"},
            "overall_interest_score": {"type": "number"},
            "scope_interest": {"type": "number"},
            "strength_overlap": {"type": "number"},
            "level_fit": {"type": "number"},
            "job_confidence": {"type": "number"},
            "preliminary_route": {
                "type": "string",
                "enum": ["Apply", "Network", "Review", "Skip"],
            },
            "differentiation_reason": {"type": "string"},
            "main_reservation": {"type": "string"},
        },
        "required": [
            "company_interest_score",
            "role_interest",
            "overall_interest_score",
            "scope_interest",
            "strength_overlap",
            "level_fit",
            "job_confidence",
            "preliminary_route",
            "differentiation_reason",
            "main_reservation",
        ],
        "additionalProperties": False,
    }


def fallback_result(company_result: Dict[str, Any]) -> Dict[str, Any]:
    try:
        company_interest_score = float(company_result.get("company_interest_score", 5))
    except (TypeError, ValueError):
        company_interest_score = 5.0

    return {
        "company_interest_score": company_interest_score,
        "role_interest": 5.0,
        "overall_interest_score": 5.0,
        "scope_interest": 5.0,
        "strength_overlap": 5.0,
        "level_fit": 5.0,
        "job_confidence": 3.0,
        "preliminary_route": "Review",
        "differentiation_reason": "",
        "main_reservation": "Failed to parse LLM output",
    }


def llm_score_job(
    job: Dict[str, Any],
    candidate_profile: str,
    company_result: Dict[str, Any],
) -> Dict[str, Any]:
    cache = load_job_cache()
    cache_key = make_job_cache_key(job, company_result, candidate_profile)

    if DEBUG:
        debug_print("\n=== DEBUG: RAW JOB PAYLOAD ===")
        debug_print(json.dumps(job, indent=2, default=str))
        debug_print("=== END RAW JOB PAYLOAD ===\n")

    if cache_key in cache:
        verbose_print(
            f"[role eval cache hit] company={normalize_text(job.get('company'))} "
            f"title={normalize_text(job.get('title'))}"
        )
        return cache[cache_key]

    prompt = build_prompt(job, candidate_profile, company_result)

    verbose_print(
        f"[role eval] company={normalize_text(job.get('company'))} "
        f"title={normalize_text(job.get('title'))}"
    )
    verbose_print(f"[role eval] prompt length={len(prompt)}")

    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "job_interest_score",
                "strict": True,
                "schema": get_json_schema(),
            }
        },
    )

    content = response.output_text

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = fallback_result(company_result)

    result["job_prompt_version"] = JOB_PROMPT_VERSION

    cache[cache_key] = result
    save_job_cache(cache)

    return result