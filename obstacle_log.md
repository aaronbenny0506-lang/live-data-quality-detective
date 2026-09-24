# Obstacle Log — Live Data Quality Detective

## 1. API blocked the request in this sandbox
The build/test environment I used to write and verify this script does not
have outbound network access, and a direct test call to
`https://dummyjson.com/products` came back with `403 Forbidden` (likely an
edge/WAF block on the sandbox's egress, not an issue with dummyjson itself).

**Fix:** rather than let the script crash, `fetch_dataset()` retries the
request a few times with a short backoff, and if the API still can't be
reached it falls back to a small bundled `sample_products.json` file
(modeled on the real API's schema and known quirks, e.g. missing `brand`
for beauty/skincare items) so the rest of the pipeline — detection,
cleaning, reporting — can still be exercised end-to-end. On a machine with
normal internet access, the script pulls live data on the first try and the
fallback path never triggers. The report clearly labels which source was
actually used (`**Data source:**` line at the top).

## 2. Mixed-casing values look like new categories, not duplicates
Early on, `df["category"].value_counts()` showed `"Beauty"`, `"beauty"`,
and `"BEAUTY"` as three separate categories, which would have thrown off
any grouping/aggregation and made duplicate detection miss near-duplicate
rows that only differed by casing.

**Fix:** added an explicit "inconsistent formatting" check (case-insensitive
grouping to count how many values are affected) as one of the required
data-quality issue types, and normalize casing on the text columns as the
*first* cleaning step, before dropping duplicates — otherwise
`drop_duplicates()` wouldn't catch rows that are identical except for
casing.

## 3. Deciding how to "clean" suspicious values
Simply deleting rows with a negative price or an out-of-range rating felt
too aggressive — those numbers might be typos worth reviewing rather than
noise worth discarding, and dropping them silently would just be a
different way of losing information.

**Fix:** suspicious rows are kept in the cleaned dataset but marked with a
new `flag_suspicious` boolean column, so a human reviewer can filter and
decide case by case instead of the script making that call for them.

## 4. Missing values needed different strategies per column
A single blanket "drop rows with any NaN" would have thrown away a lot of
otherwise-good records (`warrantyInformation` was missing on over a third
of rows in testing).

**Fix:** used column-appropriate fills instead of dropping: categorical
text columns get an explicit `"unknown"` / `"not specified"` label, and the
one numeric column with missing values (`weight`) gets filled with the
column median rather than a fixed placeholder like 0.
