# Data Quality Report

**Data source:** LIVE API (https://dummyjson.com/products, 194 records)  
**Fetched at:** 2026-10-01 20:51:57 India Standard Time  
**Original record count:** 194  
**Columns (22):** id, title, description, category, price, discountPercentage, rating, stock, tags, brand, sku, weight, dimensions, warrantyInformation, shippingInformation, availabilityStatus, reviews, returnPolicy, minimumOrderQuantity, meta, images, thumbnail

## 1. Basic Statistics

Column data types:

```
id                        int64
title                    object
description              object
category                 object
price                   float64
discountPercentage      float64
rating                  float64
stock                     int64
tags                     object
brand                    object
sku                      object
weight                    int64
dimensions               object
warrantyInformation      object
shippingInformation      object
availabilityStatus       object
reviews                  object
returnPolicy             object
minimumOrderQuantity      int64
meta                     object
images                   object
thumbnail                object
```

Numeric column summary:

```
           id     price  discountPercentage  rating   stock  weight  minimumOrderQuantity
count  194.00    194.00              194.00  194.00  194.00  194.00                194.00
mean    97.50   1570.10               10.56    3.80   50.41    5.38                 13.30
std     56.15   5509.49                5.53    0.73   30.63    3.01                 14.18
min      1.00      0.79                0.04    2.51    0.00    1.00                  1.00
25%     49.25     11.99                6.34    3.18   25.00    3.00                  3.00
50%     97.50     34.99               10.76    3.86   52.00    5.00                  8.00
75%    145.75    249.99               14.91    4.42   79.00    8.00                 18.75
max    194.00  36999.99               19.61    4.99  100.00   10.00                 50.00
```

Top `category` values:

```
category
kitchen-accessories    30
groceries              27
sports-accessories     17
smartphones            16
mobile-accessories     14
mens-watches            6
fragrances              5
beauty                  5
```

Top `brand` values:

```
brand
NaN               92
Apple             14
Rolex              6
Samsung            5
Fashion Shades     4
Realme             3
Oppo               3
Vivo               3
```

## 2. Data Quality Issues Found

### Missing values (NaN or blank)
- `brand`: 92 (47.4%)

### Duplicate records
- Full-row duplicates: 0
- Duplicate `id`: 0
- Duplicate `sku`: 0
- Duplicate titles (case-insensitive): 1

### Suspicious / out-of-range values
- non positive price: 0
- price outliers iqr: 30
- negative stock: 0
- zero stock: 4
- rating out of 0 to 5: 0
- discount outside 0 to 100: 0
- non positive min order qty: 0
- availabilityStatus vs stock mismatch: 0

### Inconsistent formatting
- category leading trailing whitespace: 0
- category mixed casing groups: 0
- brand leading trailing whitespace: 0
- brand mixed casing groups: 0
- availabilityStatus leading trailing whitespace: 0
- availabilityStatus mixed casing groups: 0
- title leading trailing whitespace: 0
- title mixed casing groups: 0

## 3. Cleaning Summary

- Duplicate rows removed: 0
- `brand`: 92 missing value(s) filled
- Rows flagged suspicious (kept, not deleted): 0
- Nested fields (dimensions, meta, reviews, tags, images) flattened for CSV
- Final cleaned record count: 194 (columns: 28)