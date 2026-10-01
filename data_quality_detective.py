#!/usr/bin/env python3
"""
Live Data Quality Detective
============================
Fetches the real JSON dataset from https://dummyjson.com/products, analyzes it
with pandas, writes a cleaned dataset and a Markdown quality report.

Usage:
    python data_quality_detective.py            # live API only (use for submission)
    python data_quality_detective.py --demo     # allow synthetic fallback (testing only)

By default the script EXITS WITH AN ERROR if the live API cannot be reached,
so it can never silently produce a report from synthetic data.

Outputs (next to this script):
    quality_report.md, raw_dataset.csv, cleaned_dataset.csv
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

API_URL = "https://dummyjson.com/products"
MIN_RECORDS = 100
TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
FALLBACK_FILE = Path(__file__).parent / "sample_products.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (data-quality-detective)"}


# ---------------------------------------------------------------------------
# Step 1 + 4: Fetch with error handling
# ---------------------------------------------------------------------------
def fetch_dataset(allow_fallback: bool) -> tuple[pd.DataFrame, str, bool]:
    """Returns (dataframe, source_description, is_live)."""
    last_error = None
    # limit=0 asks dummyjson for ALL products (194 at time of writing)
    params = {"limit": 0, "skip": 0}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(API_URL, params=params, headers=HEADERS,
                                timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict) or "products" not in payload:
                raise ValueError("Unexpected payload shape (no 'products' key)")
            records = payload["products"]
            if not isinstance(records, list) or not records:
                raise ValueError("API returned an empty 'products' list")

            df = pd.DataFrame(records)
            if len(df) < MIN_RECORDS:
                raise ValueError(f"Only {len(df)} records returned; need >= {MIN_RECORDS}")
            return df, f"LIVE API ({API_URL}, {len(df)} records)", True

        except requests.exceptions.Timeout as e:
            last_error = e
            print(f"[attempt {attempt}/{MAX_RETRIES}] Timeout. Retrying...")
        except requests.exceptions.ConnectionError as e:
            last_error = e
            print(f"[attempt {attempt}/{MAX_RETRIES}] Connection error. Retrying...")
        except requests.exceptions.HTTPError as e:
            last_error = e
            print(f"[attempt {attempt}/{MAX_RETRIES}] HTTP error: {e}. Retrying...")
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            print(f"[attempt {attempt}/{MAX_RETRIES}] Bad response: {e}. Retrying...")
        time.sleep(1.5 * attempt)

    print(f"[error] Live API unreachable after {MAX_RETRIES} attempts: {last_error!r}")

    if allow_fallback and FALLBACK_FILE.exists():
        print("[demo] Using SYNTHETIC fallback data. Do NOT submit these outputs.")
        with open(FALLBACK_FILE) as f:
            payload = json.load(f)
        df = pd.DataFrame(payload.get("products", payload))
        return df, f"SYNTHETIC FALLBACK ({FALLBACK_FILE.name}) - NOT LIVE DATA", False

    print("[fatal] No live data. Check your internet connection and re-run.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers: real API has nested lists/dicts (tags, images, reviews, dimensions,
# meta). These are unhashable, so duplicated()/drop_duplicates() would crash.
# ---------------------------------------------------------------------------
def hashable_view(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].map(lambda v: isinstance(v, (list, dict))).any():
            out[col] = out[col].map(
                lambda v: json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v)
    return out


def flatten_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten nested fields into CSV-friendly columns."""
    out = df.copy()
    if "dimensions" in out.columns:
        dims = pd.json_normalize(out["dimensions"].map(lambda v: v if isinstance(v, dict) else {}))
        dims.columns = [f"dimensions_{c}" for c in dims.columns]
        dims.index = out.index
        out = pd.concat([out.drop(columns=["dimensions"]), dims], axis=1)
    if "meta" in out.columns:
        meta = pd.json_normalize(out["meta"].map(lambda v: v if isinstance(v, dict) else {}))
        meta.columns = [f"meta_{c}" for c in meta.columns]
        meta.index = out.index
        out = pd.concat([out.drop(columns=["meta"]), meta], axis=1)
    if "reviews" in out.columns:
        out["review_count"] = out["reviews"].map(lambda v: len(v) if isinstance(v, list) else 0)
        out = out.drop(columns=["reviews"])
    for col in ("tags", "images"):
        if col in out.columns:
            out[col] = out[col].map(lambda v: "|".join(map(str, v)) if isinstance(v, list) else v)
    return out


# ---------------------------------------------------------------------------
# Step 2: Detect issues
# ---------------------------------------------------------------------------
def detect_issues(df: pd.DataFrame) -> dict:
    issues = {}
    hv = hashable_view(df)

    # Missing values (NaN, plus empty / whitespace-only strings)
    missing = df.isna().sum()
    for col in df.columns:
        if df[col].dtype == object or str(df[col].dtype) == "str":
            blanks = df[col].map(lambda v: isinstance(v, str) and v.strip() == "").sum()
            missing[col] += blanks
    issues["missing_values"] = missing[missing > 0].to_dict()

    # Duplicates
    issues["duplicate_rows"] = int(hv.duplicated().sum())
    issues["duplicate_ids"] = int(df["id"].duplicated().sum()) if "id" in df else None
    issues["duplicate_skus"] = int(df["sku"].duplicated().sum()) if "sku" in df else None
    issues["duplicate_titles"] = (
        int(df["title"].str.strip().str.lower().duplicated().sum()) if "title" in df else None)

    # Suspicious / out-of-range values
    sus = {}
    if "price" in df:
        sus["non_positive_price"] = int((df["price"] <= 0).sum())
        q1, q3 = df["price"].quantile([0.25, 0.75])
        iqr = q3 - q1
        sus["price_outliers_iqr"] = int(((df["price"] < q1 - 1.5 * iqr) |
                                         (df["price"] > q3 + 1.5 * iqr)).sum())
    if "stock" in df:
        sus["negative_stock"] = int((df["stock"] < 0).sum())
        sus["zero_stock"] = int((df["stock"] == 0).sum())
    if "rating" in df:
        sus["rating_out_of_0_to_5"] = int(((df["rating"] < 0) | (df["rating"] > 5)).sum())
    if "discountPercentage" in df:
        sus["discount_outside_0_to_100"] = int(
            ((df["discountPercentage"] < 0) | (df["discountPercentage"] > 100)).sum())
    if "minimumOrderQuantity" in df:
        sus["non_positive_min_order_qty"] = int((df["minimumOrderQuantity"] <= 0).sum())
    issues["suspicious_values"] = sus

    # Inconsistent formatting: mixed casing + stray whitespace
    fmt = {}
    for col in ("category", "brand", "availabilityStatus", "title"):
        if col in df:
            s = df[col].dropna().astype(str)
            fmt[f"{col}_leading_trailing_whitespace"] = int((s != s.str.strip()).sum())
            variants = s.groupby(s.str.strip().str.lower()).nunique()
            fmt[f"{col}_mixed_casing_groups"] = int((variants > 1).sum())
    issues["inconsistent_formatting"] = fmt

    # Consistency: price/stock vs availabilityStatus
    if {"stock", "availabilityStatus"} <= set(df.columns):
        s = df["availabilityStatus"].astype(str).str.lower()
        issues["status_stock_mismatch"] = int(
            (((s == "out of stock") & (df["stock"] > 0)) |
             ((s == "in stock") & (df["stock"] == 0))).sum())
    return issues


# ---------------------------------------------------------------------------
# Step 3: Clean
# ---------------------------------------------------------------------------
def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    summary = {}
    cleaned = flatten_for_csv(df)

    # Normalize whitespace/casing on categorical text first
    for col in ("category", "brand", "availabilityStatus"):
        if col in cleaned:
            cleaned[col] = cleaned[col].map(
                lambda v: v.strip().lower() if isinstance(v, str) else v)
    for col in cleaned.columns:
        if cleaned[col].map(lambda v: isinstance(v, str) and v.strip() == "").any():
            cleaned[col] = cleaned[col].map(
                lambda v: pd.NA if isinstance(v, str) and v.strip() == "" else v)

    before = len(cleaned)
    cleaned = cleaned.drop_duplicates()
    if "id" in cleaned:
        cleaned = cleaned.drop_duplicates(subset=["id"])
    summary["duplicate_rows_removed"] = before - len(cleaned)

    fills = {}
    for col, value in (("brand", "unknown"), ("warrantyInformation", "not specified"),
                       ("shippingInformation", "not specified"),
                       ("returnPolicy", "not specified")):
        if col in cleaned:
            n = int(cleaned[col].isna().sum())
            if n:
                cleaned[col] = cleaned[col].fillna(value)
                fills[col] = n
    for col in cleaned.select_dtypes("number").columns:
        n = int(cleaned[col].isna().sum())
        if n:
            cleaned[col] = cleaned[col].fillna(cleaned[col].median())
            fills[col] = n
    summary["missing_values_filled"] = fills

    # Flag (don't delete) suspicious rows
    cleaned["flag_suspicious"] = False
    rules = []
    if "price" in cleaned:
        rules.append(cleaned["price"] <= 0)
    if "stock" in cleaned:
        rules.append(cleaned["stock"] < 0)
    if "rating" in cleaned:
        rules.append((cleaned["rating"] < 0) | (cleaned["rating"] > 5))
    if "discountPercentage" in cleaned:
        rules.append((cleaned["discountPercentage"] < 0) | (cleaned["discountPercentage"] > 100))
    for mask in rules:
        cleaned.loc[mask, "flag_suspicious"] = True
    summary["rows_flagged_suspicious"] = int(cleaned["flag_suspicious"].sum())
    return cleaned, summary


# ---------------------------------------------------------------------------
# Step 5: Report
# ---------------------------------------------------------------------------
def build_report(df, cleaned, source, issues, cs) -> str:
    L = ["# Data Quality Report\n",
         f"**Data source:** {source}  ",
         f"**Fetched at:** {time.strftime('%Y-%m-%d %H:%M:%S %Z')}  ",
         f"**Original record count:** {len(df)}  ",
         f"**Columns ({len(df.columns)}):** {', '.join(df.columns)}\n",
         "## 1. Basic Statistics\n", "Column data types:\n",
         "```\n" + df.dtypes.astype(str).to_string() + "\n```\n"]
    desc = df.describe(include="number")
    if not desc.empty:
        L += ["Numeric column summary:\n", "```\n" + desc.round(2).to_string() + "\n```\n"]
    for col in ("category", "brand"):
        if col in df:
            L += [f"Top `{col}` values:\n",
                  "```\n" + df[col].value_counts(dropna=False).head(8).to_string() + "\n```\n"]

    L.append("## 2. Data Quality Issues Found\n")
    L.append("### Missing values (NaN or blank)")
    mv = issues["missing_values"]
    L += [f"- `{c}`: {n} ({n/len(df):.1%})" for c, n in mv.items()] or ["- None found."]
    L.append("")
    L.append("### Duplicate records")
    L += [f"- Full-row duplicates: {issues['duplicate_rows']}",
          f"- Duplicate `id`: {issues['duplicate_ids']}",
          f"- Duplicate `sku`: {issues['duplicate_skus']}",
          f"- Duplicate titles (case-insensitive): {issues['duplicate_titles']}", ""]
    L.append("### Suspicious / out-of-range values")
    for k, v in issues["suspicious_values"].items():
        L.append(f"- {k.replace('_', ' ')}: {v}")
    if "status_stock_mismatch" in issues:
        L.append(f"- availabilityStatus vs stock mismatch: {issues['status_stock_mismatch']}")
    L.append("")
    L.append("### Inconsistent formatting")
    for k, v in issues["inconsistent_formatting"].items():
        L.append(f"- {k.replace('_', ' ')}: {v}")
    L.append("")
    L.append("## 3. Cleaning Summary\n")
    L.append(f"- Duplicate rows removed: {cs['duplicate_rows_removed']}")
    for c, n in cs["missing_values_filled"].items():
        L.append(f"- `{c}`: {n} missing value(s) filled")
    L += [f"- Rows flagged suspicious (kept, not deleted): {cs['rows_flagged_suspicious']}",
          f"- Nested fields (dimensions, meta, reviews, tags, images) flattened for CSV",
          f"- Final cleaned record count: {len(cleaned)} (columns: {len(cleaned.columns)})"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true",
                    help="allow synthetic fallback data (testing only)")
    args = ap.parse_args()
    out = Path(__file__).parent

    df, source, is_live = fetch_dataset(allow_fallback=args.demo)
    print(f"Loaded {len(df)} records from {source}")
    print(f"Columns: {list(df.columns)}")

    issues = detect_issues(df)
    cleaned, cs = clean_dataset(df)

    (out / "quality_report.md").write_text(build_report(df, cleaned, source, issues, cs))
    flatten_for_csv(df).to_csv(out / "raw_dataset.csv", index=False)
    cleaned.to_csv(out / "cleaned_dataset.csv", index=False)
    print("\nDone. Wrote quality_report.md, raw_dataset.csv, cleaned_dataset.csv")
    if not is_live:
        print("WARNING: outputs are from SYNTHETIC data and must not be submitted.")


if __name__ == "__main__":
    main()
