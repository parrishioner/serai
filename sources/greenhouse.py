import requests


def get_greenhouse_jobs(company_slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    print(f"Fetching jobs from: {url}")

    response = requests.get(url)

    if response.status_code == 404:
        print(f"That Greenhouse slug was not found: {company_slug}")
        return []

    response.raise_for_status()
    data = response.json()
    jobs = data["jobs"]

    print(f"Found {len(jobs)} jobs")
    return jobs


def get_greenhouse_job_detail(company_slug, job_id):
    url = (
        f"https://boards-api.greenhouse.io/v1/boards/"
        f"{company_slug}/jobs/{job_id}?pay_transparency=true"
    )

    response = requests.get(url)
    response.raise_for_status()
    return response.json()