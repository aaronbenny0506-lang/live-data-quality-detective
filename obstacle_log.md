# Obstacle Log : Live Data Quality Detective

## 1. First submission used synthetic data instead of the live API
My build environment had no outbound network access, and a test call to
`https://dummyjson.com/products` returned `403 Forbidden`. The first version of
the script handled this by silently falling back to a bundled synthetic
`sample_products.json`, so the report and CSVs I submitted were not based on
live data. The mentor correctly flagged this.

**Fix:** the fallback is now opt-in. By default the script retries the API
(3 attempts, with backoff) and, if it still fails, exits with a clear error
rather than producing output. Synthetic data is only used with the `--demo`
flag, and any output from it is labelled "NOT LIVE DATA". I then re-ran the
script on a machine with normal internet access, and the report's
`**Data source:**` line confirms it used the live API. The fallback files
were removed from the submission.

## 2. Nested JSON fields broke duplicate detection
The real API returns nested fields (`tags`, `images`, `reviews` as lists, and
`dimensions`, `meta` as dicts). pandas cannot hash lists or dicts, so
`df.duplicated()` and `drop_duplicates()` raise an "unhashable type" error on
live data. This never showed up with my flat synthetic data.

**Fix:** duplicate detection now runs on a JSON-serialised copy of the nested
columns. For the CSV outputs, `dimensions` and `meta` are flattened into
separate columns, `tags` and `images` are joined with `|`, and `reviews` is
replaced by a `review_count` column.

## 3. Real data is cleaner than expected
The live dataset has far fewer obvious defects than the synthetic one (few or
no exact duplicates, consistent casing), so the original checks alone risked
finding almost nothing.

**Fix:** added checks suited to real data: price outliers (IQR method), zero
stock, leading/trailing whitespace, blank strings counted as missing,
duplicate titles, and `availabilityStatus` vs `stock` mismatches. The report
states what was actually found, including "none" where applicable.

## 4. Mixed-casing values look like new categories
Values like `"Beauty"`, `"beauty"` and `"BEAUTY"` would be counted as
separate categories and make `drop_duplicates()` miss rows that differ only
by casing.

**Fix:** the script measures this explicitly and normalises casing and
whitespace as the first cleaning step, before removing duplicates.

## 5. Deciding how to "clean" suspicious values
Deleting rows with odd numbers (negative price, out-of-range rating) would
silently throw away information that might just be typos worth reviewing.

**Fix:** suspicious rows are kept and marked with a `flag_suspicious` boolean
column so a reviewer can decide case by case.

## 6. Missing values needed different strategies per column
Dropping every row with any missing value would discard many otherwise-good
records.

**Fix:** text columns get explicit labels (`"unknown"` / `"not specified"`),
and numeric columns are filled with the column median rather than a
placeholder like 0.
