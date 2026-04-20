import requests

def get_ashby_jobs(board_token):
    """
    Fetch all public jobs from an Ashby job board.
    """

    url = f"https://api.ashbyhq.com/posting-api/job-board/{board_token}?includeCompensation=true"
    print(f"Fetching jobs from: {url}")

    response = requests.get(url,timeout=30)
    response.raise_for_status()

    data = response.json()
    return data.get("jobs",[])

def get_ashby_job_detail(board_token, source_job_id):

    """
    Ashby's public job board API already returns full job details in the job list, inlcuding descriptionPlain / descriptionHtml and compensation. So for now, just return an empty dict and rely on the normalized row.
    """
    return{}
