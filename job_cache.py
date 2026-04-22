print("LOADING JOB CACHE FILE")

import json
import os
from datetime import datetime

CACHE_FILE = "cache.json"


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}

    with open(CACHE_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def make_cache_key(job):
    return f"{job['source']}:{job['source_job_id']}"


def upsert_cache_job(cache, job, passed_filter):
    key = make_cache_key(job)
    now = datetime.now().isoformat()

    if key not in cache:
        cache[key] = {
            "company": job["company"],
            "title": job["title"],
            "first_seen": now,
            "last_seen": now,
            "passed_filter": passed_filter,
        }
    else:
        cache[key]["last_seen"] = now
        cache[key]["passed_filter"] = passed_filter

    return key


def get_cached_job(cache, job):
    key = make_cache_key(job)
    return cache.get(key)


def is_new_job(cache, job):
    key = make_cache_key(job)
    return key not in cache

def get_first_seen_from_cache(cache,job):
    key = make_cache_key(job)
    cached_job = cache.get(key)

    if not cached_job:
        return None
    
    return cached_job.get("first_seen")

def attach_first_seen_to_job(cache, job):
    first_seen = get_first_seen_from_cache(cache, job)
    if first_seen:
        job["first_seen_at"] = first_seen
    return job