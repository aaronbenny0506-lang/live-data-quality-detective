# Data Quality Report

**Data source:** local fallback file (sample_products.json, 125 records, API unreachable)  
**Original record count:** 125  
**Columns:** id, title, category, brand, price, discountPercentage, rating, stock, sku, weight, warrantyInformation, availabilityStatus

## 1. Basic Statistics

Column data types:

```
id                       int64
title                      str
category                   str
brand                      str
price                  float64
discountPercentage     float64
rating                 float64
stock                    int64
sku                        str
weight                 float64
warrantyInformation        str
availabilityStatus         str
```

Numeric column summary:

```
           id    price  discountPercentage  rating   stock  weight
count  125.00   125.00              125.00  125.00  125.00  111.00
mean    60.54   968.15               14.20    2.64  265.02   10.04
std     34.12   599.66                9.36    1.80  149.20    5.68
min      1.00   -49.27              -13.30    0.03   -9.00    0.51
25%     32.00   501.07                6.45    1.00  142.00    5.38
50%     62.00   922.89               13.19    2.67  282.00    9.44
75%     89.00  1471.70               22.80    3.88  393.00   15.16
max    120.00  1989.08               29.91    9.52  497.00   19.68
```

## 2. Data Quality Issues Found

### Missing values (count per column)
- `brand`: 36 missing (28.8%)
- `weight`: 14 missing (11.2%)
- `warrantyInformation`: 45 missing (36.0%)

### Duplicate records
- Full-row duplicates: 5
- Duplicate `sku` values: 5

### Suspicious / out-of-range values
- negative price: 3 record(s)
- negative stock: 3 record(s)
- rating out of 0 to 5: 5 record(s)
- negative discount: 1 record(s)

### Inconsistent formatting (eg: mixed casing)
- `category`: 21 value(s) affected by inconsistent casing

## 3. Cleaning Summary

- Duplicate rows removed: 5
- `brand`: 35 missing value(s) filled
- `weight`: 13 missing value(s) filled
- `warrantyInformation`: 42 missing value(s) filled
- Rows flagged as suspicious (kept, not deleted): 12
- Final cleaned record count: 120 (columns: 13)
