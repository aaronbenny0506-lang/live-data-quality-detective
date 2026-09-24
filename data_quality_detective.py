#!/usr/bin/env python3
"""
Live Data Quality Detective
============================
Fetches a real JSON dataset from a public API (dummyjson.com/products),
analyzes it for data-quality issues with pandas, produces a cleaned
dataset and writes a Markdown report summarizing everything found.

Usage:
    python data_quality_detective.py

Outputs (written next to this script):
    quality_report.md   - human-readable findings + stats + cleaning summary
    cleaned_dataset.csv  - the cleaned dataset
    raw_dataset.csv      - the original, unmodified dataset for comparison
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

API_URL = "https://dummyjson.com/products"
FETCH_LIMIT = 100          # minimum records required by the challenge
TIMEOUT_SECONDS = 8
MAX_RETRIES = 3
FALLBACK_FILE = Path(__file__).parent / "sample_products.json"


# ---------------------------------------------------------------------------
# Step 1 + Step 4: Fetch a real dataset, with graceful error handling
# ---------------------------------------------------------------------------
def fetch_dataset() -> tuple[pd.DataFrame, str]:
    """
    Pulls at least FETCH_LIMIT records from a public API.
    Retries on transient failures, and falls back to a bundled local sample
    dataset if the API is completely unreachable (e.g. no network access),
    so the rest of the pipeline can still run and be demonstrated.

    Returns (dataframe, source_description).
    """
    params = {"limit": FETCH_LIMIT, "skip": 0}
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()

            records = payload.get("products", payload if isinstance(payload, list) else [])
            if not records:
                raise ValueError("API returned an empty/unexpected payload")

            df = pd.DataFrame(records)
            if len(df) < FETCH_LIMIT:
                print(f"[warn] API returned only {len(df)} records "
                      f"(wanted {FETCH_LIMIT}); continuing anyway.")

            return df, f"live API ({API_URL}, {len(df)} records)"

        except requests.exceptions.Timeout as e:
            last_error = e
            print(f"[attempt {attempt}/{MAX_RETRIES}] Timed out contacting API. Retrying...")
        except requests.exceptions.ConnectionError as e:
            last_error = e
            print(f"[attempt {attempt}/{MAX_RETRIES}] Connection error. Retrying...")
        except requests.exceptions.HTTPError as e:
            last_error = e
            print(f"[attempt {attempt}/{MAX_RETRIES}] HTTP error: {e}. Retrying...")
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            print(f"[attempt {attempt}/{MAX_RETRIES}] Unexpected/invalid response: {e}. Retrying...")

        time.sleep(1.5 * attempt)  # simple backoff

    # All retries exhausted — degrade gracefully instead of crashing.
    print(f"[error] Could not reach the live API after {MAX_RETRIES} attempts "
          f"({last_error!r}).")

    if FALLBACK_FILE.exists():
        print(f"[fallback] Loading bundled sample dataset from {FALLBACK_FILE.name} "
              f"so the pipeline can still run.")
        with open(FALLBACK_FILE) as f:
            payload = json.load(f)
        records = payload.get("products", payload)
        df = pd.DataFrame(records)
        return df, f"local fallback file ({FALLBACK_FILE.name}, {len(df)} records — API unreachable)"

    print("[fatal] No fallback dataset available either. Exiting cleanly.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Step 2: Detect data-quality issues
# ---------------------------------------------------------------------------
def detect_issues(df: pd.DataFrame) -> dict:
    issues = {}

    # 1. Missing values, per column
    missing = df.isna().sum()
    missing = missing[missing > 0]
    issues["missing_values"] = missing.to_dict()

    # 2. Duplicate records — full-row duplicates, and duplicate ids/skus if present
    issues["duplicate_rows"] = int(df.duplicated().sum())
    key_col = "sku" if "sku" in df.columns else ("id" if "id" in df.columns else None)
    issues["duplicate_key_col"] = key_col
    issues["duplicate_keys"] = int(df.duplicated(subset=[key_col]).sum()) if key_col else None

    # 3. Suspicious / out-of-range numeric values
    suspicious = {}
    if "price" in df.columns:
        suspicious["negative_price"] = int((df["price"] < 0).sum())
    if "stock" in df.columns:
        suspicious["negative_stock"] = int((df["stock"] < 0).sum())
    if "rating" in df.columns:
        suspicious["rating_out_of_0_to_5"] = int(((df["rating"] < 0) | (df["rating"] > 5)).sum())
    if "discountPercentage" in df.columns:
        suspicious["negative_discount"] = int((df["discountPercentage"] < 0).sum())
    issues["suspicious_values"] = suspicious

    # 4. Inconsistent formatting — mixed casing within a categorical column
    inconsistent = {}
    for col in ("category", "brand", "availabilityStatus"):
        if col in df.columns:
            non_null = df[col].dropna().astype(str)
            variants = non_null.groupby(non_null.str.lower()).nunique()
            mixed = variants[variants > 1]
            if len(mixed):
                inconsistent[col] = int(mixed.sum())
    issues["inconsistent_formatting"] = inconsistent

    return issues


# ---------------------------------------------------------------------------
# Step 3: Clean the dataset based on what was found
# ---------------------------------------------------------------------------
def clean_dataset(df: pd.DataFrame, issues: dict) -> tuple[pd.DataFrame, dict]:
    cleaned = df.copy()
    summary = {}

    # Standardize casing on categorical text columns before anything else,
    # so duplicate detection isn't fooled by "Beauty" vs "beauty"
    for col in ("category", "brand", "availabilityStatus"):
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].apply(lambda v: v.strip().lower() if isinstance(v, str) else v)

    # Drop exact duplicate rows
    before = len(cleaned)
    cleaned = cleaned.drop_duplicates()
    summary["duplicate_rows_removed"] = before - len(cleaned)

    # Fill missing values with sensible defaults rather than dropping rows,
    # so we don't throw away otherwise-valid records
    fill_report = {}
    if "brand" in cleaned.columns:
        n = cleaned["brand"].isna().sum()
        cleaned["brand"] = cleaned["brand"].fillna("unknown")
        fill_report["brand"] = int(n)
    if "weight" in cleaned.columns:
        n = cleaned["weight"].isna().sum()
        cleaned["weight"] = cleaned["weight"].fillna(cleaned["weight"].median())
        fill_report["weight"] = int(n)
    if "warrantyInformation" in cleaned.columns:
        n = cleaned["warrantyInformation"].isna().sum()
        cleaned["warrantyInformation"] = cleaned["warrantyInformation"].fillna("not specified")
        fill_report["warrantyInformation"] = int(n)
    summary["missing_values_filled"] = fill_report

    # Flag (don't silently delete) suspicious numeric values, so a reviewer
    # can decide what to do with them
    cleaned["flag_suspicious"] = False
    flagged = 0
    for col, cond in (
        ("price", lambda d: d["price"] < 0),
        ("stock", lambda d: d["stock"] < 0),
        ("rating", lambda d: (d["rating"] < 0) | (d["rating"] > 5)),
        ("discountPercentage", lambda d: d["discountPercentage"] < 0),
    ):
        if col in cleaned.columns:
            mask = cond(cleaned)
            cleaned.loc[mask, "flag_suspicious"] = True
            flagged += int(mask.sum())
    summary["rows_flagged_suspicious"] = flagged

    return cleaned, summary


# ---------------------------------------------------------------------------
# Step 5: Generate the report
# ---------------------------------------------------------------------------
def build_report(df: pd.DataFrame, cleaned: pd.DataFrame, source: str,
                  issues: dict, clean_summary: dict) -> str:
    lines = []
    lines.append("# Data Quality Report\n")
    lines.append(f"**Data source:** {source}  ")
    lines.append(f"**Original record count:** {len(df)}  ")
    lines.append(f"**Columns:** {', '.join(df.columns)}\n")

    lines.append("## 1. Basic Statistics\n")
    lines.append("Column data types:\n")
    lines.append("```\n" + df.dtypes.to_string() + "\n```\n")
    numeric_desc = df.describe(include="number")
    if not numeric_desc.empty:
        lines.append("Numeric column summary:\n")
        lines.append("```\n" + numeric_desc.round(2).to_string() + "\n```\n")

    lines.append("## 2. Data Quality Issues Found\n")

    lines.append("### Missing values (count per column)")
    if issues["missing_values"]:
        for col, n in issues["missing_values"].items():
            lines.append(f"- `{col}`: {n} missing ({n/len(df):.1%})")
    else:
        lines.append("- None found.")
    lines.append("")

    lines.append("### Duplicate records")
    lines.append(f"- Full-row duplicates: {issues['duplicate_rows']}")
    if issues["duplicate_key_col"]:
        lines.append(f"- Duplicate `{issues['duplicate_key_col']}` values: {issues['duplicate_keys']}")
    lines.append("")

    lines.append("### Suspicious / out-of-range values")
    if any(issues["suspicious_values"].values()):
        for k, v in issues["suspicious_values"].items():
            if v:
                lines.append(f"- {k.replace('_', ' ')}: {v} record(s)")
    else:
        lines.append("- None found.")
    lines.append("")

    lines.append("### Inconsistent formatting (e.g. mixed casing)")
    if issues["inconsistent_formatting"]:
        for col, n in issues["inconsistent_formatting"].items():
            lines.append(f"- `{col}`: {n} value(s) affected by inconsistent casing")
    else:
        lines.append("- None found.")
    lines.append("")

    lines.append("## 3. Cleaning Summary\n")
    lines.append(f"- Duplicate rows removed: {clean_summary['duplicate_rows_removed']}")
    if clean_summary["missing_values_filled"]:
        for col, n in clean_summary["missing_values_filled"].items():
            lines.append(f"- `{col}`: {n} missing value(s) filled")
    lines.append(f"- Rows flagged as suspicious (kept, not deleted): "
                 f"{clean_summary['rows_flagged_suspicious']}")
    lines.append(f"- Final cleaned record count: {len(cleaned)} "
                 f"(columns: {len(cleaned.columns)})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    out_dir = Path(__file__).parent

    df, source = fetch_dataset()
    print(f"Loaded {len(df)} records from {source}")
    print(f"Columns: {list(df.columns)}")

    issues = detect_issues(df)
    cleaned, clean_summary = clean_dataset(df, issues)

    report_text = build_report(df, cleaned, source, issues, clean_summary)

    (out_dir / "quality_report.md").write_text(report_text)
    df.to_csv(out_dir / "raw_dataset.csv", index=False)
    cleaned.to_csv(out_dir / "cleaned_dataset.csv", index=False)

    print("\nDone. Wrote:")
    print("  - quality_report.md")
    print("  - raw_dataset.csv")
    print("  - cleaned_dataset.csv")


if __name__ == "__main__":
    main()
