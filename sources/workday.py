import requests


def _candidate_workday_bases(company_config):
    host = company_config["workday_host"]
    site = company_config["workday_site"]
    locale = (company_config.get("workday_locale") or "").strip()

    bases = []

    if locale:
        bases.append(f"https://{host}/wday/cxs/{locale}/{site}")

    bases.append(f"https://{host}/wday/cxs/{site}")

    deduped = []
    seen = set()
    for base in bases:
        if base in seen:
            continue
        seen.add(base)
        deduped.append(base)

    return deduped


def _candidate_apply_urls(company_config, external_path):
    host = company_config["workday_host"]
    site = company_config["workday_site"]
    locale = (company_config.get("workday_locale") or "").strip()

    urls = []

    if locale:
        urls.append(f"https://{host}/{locale}/{site}/job/{external_path}")

    urls.append(f"https://{host}/{site}/job/{external_path}")

    deduped = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)

    return deduped


def _headers(company_config):
    host = company_config["workday_host"]
    board_url = company_config.get("board_url") or f"https://{host}/"

    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": f"https://{host}",
        "Referer": board_url,
    }


def get_workday_jobs(company_config):
    limit = 20
    last_error = None
    headers = _headers(company_config)

    for base in _candidate_workday_bases(company_config):
        url = f"{base}/jobs"
        print(f"Fetching jobs from: {url}")

        trial_jobs = []
        offset = 0

        try:
            while True:
                payload = {
                    "limit": limit,
                    "offset": offset,
                    "searchText": "",
                    "appliedFacets": {},
                }

                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()

                data = response.json()
                postings = data.get("jobPostings", [])
                total = data.get("total", 0)

                for posting in postings:
                    external_path = posting.get("externalPath") or ""

                    apply_urls = _candidate_apply_urls(company_config, external_path)
                    posting["applyUrl"] = apply_urls[0] if apply_urls else ""

                    trial_jobs.append(posting)

                offset += len(postings)
                if not postings or offset >= total:
                    break

            print(f"Found {len(trial_jobs)} jobs")
            return trial_jobs

        except Exception as e:
            last_error = e
            continue

    raise last_error if last_error else RuntimeError(
        f"Workday fetch failed for {company_config.get('company_slug', 'unknown')}"
    )


def get_workday_job_detail(company_config, source_job_id):
    headers = _headers(company_config)
    last_error = None

    for base in _candidate_workday_bases(company_config):
        url = f"{base}/job/{source_job_id}"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            last_error = e
            continue

    raise last_error if last_error else RuntimeError(
        f"Workday job detail fetch failed for {company_config.get('company_slug', 'unknown')} "
        f"job_id={source_job_id}"
    )
