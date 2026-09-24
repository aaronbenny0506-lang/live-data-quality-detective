"""
Generates sample_products.json — a local fallback dataset styled after the
dummyjson.com/products API response. This is ONLY used by data_quality_detective.py
when the live API cannot be reached (e.g. no network access), so the pipeline can
still be demonstrated end-to-end. It intentionally contains the same kinds of
messiness the live API is known to have (missing brand values, a few duplicate
records, out-of-range numeric values, and inconsistent category casing) so the
detection logic has something real to find.
"""
import json
import random

random.seed(42)

categories = ["smartphones", "laptops", "fragrances", "skincare", "groceries",
              "home-decoration", "furniture", "tops", "womens-dresses", "beauty"]
brands = ["Apple", "Samsung", "OPPO", "Huawei", "Microsoft Surface", "Dell",
          "HP Pavilion", "Impression of Acqua Di Gio", "Calvin Klein", None]

records = []
for i in range(1, 121):  # 120 records -> comfortably over the 100-record minimum
    category = random.choice(categories)
    # inconsistent casing injected on purpose (data-quality issue #4: formatting)
    if random.random() < 0.15:
        category = category.upper() if random.random() < 0.5 else category.capitalize()

    brand = random.choice(brands)
    # beauty/skincare/fragrances genuinely lack a brand field on the real API
    if category.lower() in ("beauty", "skincare", "fragrances") and random.random() < 0.6:
        brand = None

    price = round(random.uniform(5, 2000), 2)
    if random.random() < 0.03:
        price = round(random.uniform(-50, -1), 2)  # suspicious: negative price

    rating = round(random.uniform(0, 5), 2)
    if random.random() < 0.03:
        rating = round(random.uniform(5.1, 9.9), 2)  # suspicious: out-of-range rating

    stock = random.randint(0, 500)
    if random.random() < 0.03:
        stock = -random.randint(1, 20)  # suspicious: negative stock

    discount = round(random.uniform(0, 30), 2)
    if random.random() < 0.03:
        discount = round(random.uniform(-20, -1), 2)  # suspicious: negative discount

    sku = f"SKU-{1000+i}"

    record = {
        "id": i,
        "title": f"Product {i}",
        "category": category,
        "brand": brand,
        "price": price,
        "discountPercentage": discount,
        "rating": rating,
        "stock": stock,
        "sku": sku,
        "weight": round(random.uniform(0.1, 20), 2) if random.random() > 0.05 else None,
        "warrantyInformation": random.choice(["1 week warranty", "1 month warranty",
                                               "No warranty", None]),
        "availabilityStatus": random.choice(["In Stock", "Low Stock", "Out of Stock"]),
    }
    records.append(record)

# Inject a handful of exact duplicate records (data-quality issue #2: duplicates)
for dup_source in random.sample(records[:100], 5):
    dup = dict(dup_source)
    records.append(dup)

random.shuffle(records)

with open("sample_products.json", "w") as f:
    json.dump({"products": records, "total": len(records)}, f, indent=2)

print(f"Wrote sample_products.json with {len(records)} records")
