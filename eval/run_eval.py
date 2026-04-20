import csv
from datetime import datetime, timezone
from pathlib import Path

from company_registry import COMPANY_REGISTRY
from llm_company_score import llm_score_company

CANDIDATE_PROFILE_PATH = Path("candidate_data/candidate_profile.txt")
OUTPUT_CSV = Path("company_score_eval_results.csv")


def load_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Failed to load {path}: {e}")
        return ""


def main():
    candidate_profile = load_text_file(CANDIDATE_PROFILE_PATH)

    rows = []
    started_at = datetime.now(timezone.utc).isoformat()

    active_companies = [c for c in COMPANY_REGISTRY if c.get("enabled", True)]
    print(f"Evaluating {len(active_companies)} active companies")

    for company_config in active_companies:
        company_slug = company_config["company_slug"]

        try:
            result = llm_score_company(company_slug, candidate_profile)

            row = {
                "evaluated_at": started_at,
                "company_slug": company_slug,
                "source": company_config.get("source", ""),
                "company_interest_score": result.get("company_interest_score", ""),
                "moat_durability": result.get("moat_durability",""),
                "growth_trajectory":result.get("growth_trajectory",""),
                "product_culture":result.get("product_culture",""),
                "ai_leverage":result.get("ai_leverage",""),
                "leadership_quality":{"leadership_quality",""},
                "market_category":{"market_category",""},
                "confidence": result.get("confidence", ""),
                "company_interest": result.get("company_interest", ""),
                "company_interest_reason": result.get("company_interest_reason", ""),
                "company_prompt_version": result.get("company_prompt_version", ""),
            }
            rows.append(row)

            print(
                f"{company_slug}: "
                f"score={row['company_interest_score']} "
                f"confidence={row['confidence']} "
                f"interest={row['company_interest']}"
            )

        except Exception as e:
            print(f"Error scoring {company_slug}: {e}")
            rows.append(
                {
                    "evaluated_at": started_at,
                    "company_slug": company_slug,
                    "source": company_config.get("source", ""),
                    "company_interest_score": "",
                    "moat_durability":"",
                    "product_culture":"",
                    "ai_leverage":"",
                    "leadership_quality":"",
                    "market_category":"",
                    "confidence": "",
                    "company_interest": "",
                    "company_interest_reason": f"ERROR: {e}",
                    "company_prompt_version": "company_v6",
                }
            )

    if rows:
        with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nWrote {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()