import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.ycombinator.com"
JOBS_URL = f"{BASE_URL}/jobs"
JOB_PATH_RE = re.compile(r"^/companies/([^/]+)/jobs/([^/?#]+)$")
MONEY_RANGE_RE = re.compile(
    r'([$£€₹]\s?[0-9][0-9,]*(?:\s?[KMB])?)\s*-\s*([$£€₹]\s?[0-9][0-9,]*(?:\s?[KMB])?)',
    re.IGNORECASE,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

LOCATION_HINTS = [
    "remote",
    "san francisco",
    "new york",
    "los angeles",
    "bay area",
    "california",
    "usa",
    "united states",
    "hybrid",
    "in-person",
    "on-site",
    "onsite",
    "canada",
    "london",
    "berlin",
    "singapore",
    "india",
    "austin",
    "seattle",
]


def _clean_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_value_after(lines: List[str], label: str) -> str:
    for i, line in enumerate(lines):
        if line == label and i + 1 < len(lines):
            return lines[i + 1]
    return ""


def _extract_section(lines: List[str], start_label: str, stop_labels: set) -> str:
    if start_label not in lines:
        return ""

    start_idx = lines.index(start_label) + 1
    collected = []

    for line in lines[start_idx:]:
        if line in stop_labels:
            break
        collected.append(line)

    return "\n".join(collected).strip()


def _parse_salary_bounds(salary_text: str):
    if not salary_text:
        return None, None

    match = MONEY_RANGE_RE.search(salary_text)
    if not match:
        return None, None

    return match.group(1), match.group(2)


def _looks_like_location(text: str) -> bool:
    if not text:
        return False

    lowered = text.lower()

    if any(hint in lowered for hint in LOCATION_HINTS):
        return True

    if "," in text and len(text) < 80:
        return True

    return False


def _extract_location_from_summary_parts(parts: List[str]) -> str:
    # Prefer the rightmost part that looks like location
    for part in reversed(parts):
        if _looks_like_location(part):
            return part.strip()
    return ""


def _collect_job_links() -> List[str]:
    response = requests.get(JOBS_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        parsed = urlparse(href)
        path = parsed.path if parsed.scheme else href
        match = JOB_PATH_RE.match(path)
        if not match:
            continue

        absolute_url = urljoin(BASE_URL, path)
        if absolute_url in seen:
            continue

        seen.add(absolute_url)
        links.append(absolute_url)

    return links

def _extract_location_from_html(soup) -> str:
    """
    Extract location using structured HTML elements instead of text parsing.
    """
    # Try common YC patterns (these may evolve slightly)
    candidates = []

    # Look for pill-style metadata near title
    for div in soup.find_all("div"):
        text = div.get_text(" ", strip=True)
        if not text:
            continue

        # Heuristic: short text with separators
        if "•" in text and len(text) < 120:
            parts = [p.strip() for p in text.split("•") if p.strip()]
            for part in parts:
                if _looks_like_location(part):
                    candidates.append(part)

    # Fallback: scan spans
    for span in soup.find_all("span"):
        text = span.get_text(" ", strip=True)
        if _looks_like_location(text):
            candidates.append(text)

    # Return first good candidate
    return candidates[0] if candidates else ""

def get_yc_job_detail(job_url: str) -> dict:
    response = requests.get(job_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    lines = _clean_lines(soup.get_text("\n"))

    parsed = urlparse(job_url)
    parts = [p for p in parsed.path.split("/") if p]

    company_slug = parts[1] if len(parts) >= 2 else ""
    yc_job_id = parts[3] if len(parts) >= 4 else parsed.path.strip("/").replace("/", "-")

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)

    company_name = ""
    h2 = soup.find("h2")
    if h2:
        company_name = h2.get_text(" ", strip=True)

    summary_line = ""
    if title in lines:
        idx = lines.index(title)
        if idx + 1 < len(lines):
            summary_line = lines[idx + 1]

    summary_parts = [part.strip() for part in summary_line.split("•") if part.strip()]

    salary_text = ""
    equity_text = ""
    location = ""

    for part in summary_parts:
        if MONEY_RANGE_RE.search(part) and not salary_text:
            salary_text = part
        elif "%" in part and not equity_text:
            equity_text = part

    location = _extract_location_from_summary_parts(summary_parts)

    job_type = _extract_value_after(lines, "Job type")
    role = _extract_value_after(lines, "Role")
    experience = _extract_value_after(lines, "Experience")
    visa = _extract_value_after(lines, "Visa")
    skills = _extract_value_after(lines, "Skills")

    # NEW: structured HTML extraction
    if not location:
        location = _extract_location_from_html(soup)

    # Existing fallback
    if not location:
        for label in ["Location", "Locations"]:
            value = _extract_value_after(lines, label)
            if value:
                location = value
                break

    # FINAL fallback: title
    if not location or location == "Unknown":
        title_lower = title.lower()

        if " - " in title:
            parts = [p.strip() for p in title.split(" - ") if p.strip()]
            for part in reversed(parts):
                if _looks_like_location(part):
                    location = part
                    break

        if not location:
            for hint in LOCATION_HINTS:
                if hint in title_lower:
                    location = hint
                    break

    if not location:
        location = "Unknown"

    stop_labels = {
        "About the role",
        "What you’ll work on",
        "Your experience",
        "Who you are",
        "Benefits",
        "Connect directly with founders of the best YC-funded startups.",
        "Apply to role ›",
    }

    description_sections = []

    for section_name in [
        "About the role",
        "What you’ll work on",
        "Your experience",
        "Who you are",
        "Benefits",
    ]:
        section_text = _extract_section(lines, section_name, stop_labels - {section_name})
        if section_text:
            description_sections.append("## " + section_name + "\n" + section_text)

    job_description = "\n\n".join(description_sections).strip()

    apply_url = ""
    for a in soup.find_all("a", href=True):
        anchor_text = a.get_text(" ", strip=True)
        if "Apply to role" in anchor_text or "Apply Now" in anchor_text:
            apply_url = urljoin(BASE_URL, a["href"])
            break

    salary_min_text, salary_max_text = _parse_salary_bounds(salary_text)

    return {
        "company_slug": company_slug.lower(),
        "company_name": company_name or company_slug,
        "title": title,
        "job_url": job_url,
        "apply_url": apply_url,
        "yc_job_id": yc_job_id,
        "salary_text": salary_text,
        "salary_min_text": salary_min_text,
        "salary_max_text": salary_max_text,
        "equity_text": equity_text,
        "location": location,
        "job_type": job_type,
        "role": role,
        "experience": experience,
        "visa": visa,
        "skills": skills,
        "job_description": job_description,
        "source": "yc_jobs",
    }



def get_yc_jobs(max_jobs: Optional[int] = None) -> List[dict]:
    job_links = _collect_job_links()

    if max_jobs is not None:
        job_links = job_links[:max_jobs]

    jobs = []
    for job_url in job_links:
        try:
            jobs.append(get_yc_job_detail(job_url))
        except Exception as e:
            print(f"[yc_jobs] failed to fetch {job_url}: {e}")

    print(f"[yc_jobs] Found {len(jobs)} YC job pages")
    return jobs
