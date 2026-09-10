"""
Seed data generator for the HCP Targeting & Call Planning System.

Generates realistic-ish sample data:
- 5 territories
- ~15 reps
- ~150 HCPs (long-tail volume distribution, not uniform — a handful of
  high-volume prescribers and a long tail of low-volume ones, matching
  real pharma Rx distributions per TDD §5.2)
- 3 products
- 6 months of monthly prescription volume per HCP/product
- ~4 months of randomized call history

Run with:
    DATABASE_URL="postgresql://..." python seed_data.py
"""

import os
import random
from datetime import date, timedelta
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("Set DATABASE_URL environment variable first.")

random.seed(42)

TERRITORIES = [
    ("North Metro", "East"),
    ("South Valley", "East"),
    ("West Coast", "West"),
    ("Central Plains", "Midwest"),
    ("Mountain West", "West"),
]

REP_FIRST = ["Aisha", "Rohan", "Maria", "James", "Priya", "Daniel", "Wei", "Fatima",
             "Carlos", "Emma", "Arjun", "Sophia", "Noah", "Ananya", "Lucas"]
REP_LAST = ["Khan", "Mehta", "Garcia", "Smith", "Patel", "Brown", "Chen", "Ali",
            "Rodriguez", "Wilson", "Nair", "Kim", "Davis", "Sharma", "Martin"]

HCP_FIRST = ["Sarah", "Michael", "Linda", "Robert", "Jennifer", "David", "Emily",
             "William", "Ashley", "Kevin", "Nisha", "Thomas", "Rachel", "Sanjay",
             "Grace", "Benjamin", "Olivia", "Henry", "Natasha", "Peter"]
HCP_LAST = ["Patel", "Thompson", "Nguyen", "Anderson", "Lee", "Moore", "Iyer",
            "Clark", "Reddy", "White", "Kumar", "Hall", "Desai", "Young",
            "Gupta", "King", "Rao", "Wright", "Menon", "Scott"]

SPECIALTIES = ["Cardiology", "Internal Medicine", "Endocrinology", "Family Medicine"]

PRODUCTS = ["Cardivex", "Cardivex XR", "Lipidrol"]

print("Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
print("Connected.")

# ---- territories ----
territory_ids = []
for name, region in TERRITORIES:
    cur.execute(
        "INSERT INTO territories (territory_name, region) VALUES (%s, %s) RETURNING territory_id",
        (name, region),
    )
    territory_ids.append(cur.fetchone()[0])
conn.commit()
print(f"Inserted {len(territory_ids)} territories.")

# ---- reps (2-4 per territory) ----
rep_ids_by_territory = {tid: [] for tid in territory_ids}
name_pool = list(zip(REP_FIRST, REP_LAST))
random.shuffle(name_pool)
idx = 0
for tid in territory_ids:
    n_reps = random.randint(2, 4)
    for _ in range(n_reps):
        first, last = name_pool[idx % len(name_pool)]
        idx += 1
        cur.execute(
            "INSERT INTO reps (rep_name, territory_id) VALUES (%s, %s) RETURNING rep_id",
            (f"{first} {last}", tid),
        )
        rep_ids_by_territory[tid].append(cur.fetchone()[0])
conn.commit()
total_reps = sum(len(v) for v in rep_ids_by_territory.values())
print(f"Inserted {total_reps} reps.")

# ---- products ----
product_ids = []
for p in PRODUCTS:
    cur.execute("INSERT INTO products (product_name) VALUES (%s) RETURNING product_id", (p,))
    product_ids.append(cur.fetchone()[0])
conn.commit()
print(f"Inserted {len(product_ids)} products.")

# ---- HCPs (~30 per territory, long-tail volume via a power-law-ish draw) ----
hcp_records = []  # (hcp_id, territory_id, base_volume_tier, trend)
hcp_name_pool = [(f, l) for f in HCP_FIRST for l in HCP_LAST]
random.shuffle(hcp_name_pool)
name_idx = 0

for tid in territory_ids:
    n_hcps = random.randint(25, 32)
    for _ in range(n_hcps):
        first, last = hcp_name_pool[name_idx % len(hcp_name_pool)]
        name_idx += 1
        specialty = random.choice(SPECIALTIES)
        cur.execute(
            "INSERT INTO hcps (hcp_name, specialty, territory_id) VALUES (%s, %s, %s) RETURNING hcp_id",
            (f"Dr. {first} {last}", specialty, tid),
        )
        hcp_id = cur.fetchone()[0]
        # long-tail base volume: most HCPs low volume, few very high
        roll = random.random()
        if roll < 0.08:
            base_volume = random.randint(180, 320)      # whales
        elif roll < 0.25:
            base_volume = random.randint(80, 180)        # strong
        elif roll < 0.60:
            base_volume = random.randint(20, 80)          # mid
        else:
            base_volume = random.randint(0, 20)            # long tail
        # assign a trend: growing / flat / declining
        trend = random.choices(["growing", "flat", "declining"], weights=[0.25, 0.55, 0.20])[0]
        hcp_records.append((hcp_id, tid, base_volume, trend))
conn.commit()
print(f"Inserted {len(hcp_records)} HCPs.")

# ---- prescriptions: 6 months, per HCP, for their "primary" product (+ some secondary) ----
today = date.today().replace(day=1)
months = [today - timedelta(days=30 * i) for i in range(5, -1, -1)]  # 6 months, oldest first
months = [m.replace(day=1) for m in months]

print("Seeding prescriptions (this is the slow part, ~1-2 min)...")
for i, (hcp_id, tid, base_volume, trend) in enumerate(hcp_records):
    if i % 20 == 0:
        print(f"  ...{i}/{len(hcp_records)} HCPs done")
    primary_product = random.choice(product_ids)
    vol = base_volume
    for m in months:
        if trend == "growing":
            vol = int(vol * random.uniform(1.03, 1.12))
        elif trend == "declining":
            vol = max(0, int(vol * random.uniform(0.82, 0.96)))
        else:
            vol = max(0, int(vol * random.uniform(0.93, 1.07)))
        noisy_vol = max(0, vol + random.randint(-3, 3))
        cur.execute(
            """INSERT INTO prescriptions (hcp_id, product_id, rx_month, rx_volume)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (hcp_id, product_id, rx_month) DO NOTHING""",
            (hcp_id, primary_product, m, noisy_vol),
        )
        # occasional secondary product activity
        if random.random() < 0.3:
            secondary = random.choice([p for p in product_ids if p != primary_product])
            cur.execute(
                """INSERT INTO prescriptions (hcp_id, product_id, rx_month, rx_volume)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (hcp_id, product_id, rx_month) DO NOTHING""",
                (hcp_id, secondary, m, max(0, int(noisy_vol * random.uniform(0.1, 0.4)))),
            )

conn.commit()
print("Prescriptions done.")

# ---- calls: last 90 days, biased so high-volume HCPs get called more (but imperfectly) ----
outcomes = ["Completed", "Completed", "Completed", "Rescheduled", "Declined"]
call_window_start = date.today() - timedelta(days=90)

print("Seeding call history...")
for i, (hcp_id, tid, base_volume, trend) in enumerate(hcp_records):
    if i % 20 == 0:
        print(f"  ...{i}/{len(hcp_records)} HCPs done")
    reps_here = rep_ids_by_territory[tid]
    if not reps_here:
        continue
    rep_id = random.choice(reps_here)
    # rough call count target, intentionally imperfect vs. what the tier would recommend
    if base_volume > 150:
        n_calls = random.randint(3, 9)
    elif base_volume > 60:
        n_calls = random.randint(1, 6)
    else:
        n_calls = random.randint(0, 3)
    for _ in range(n_calls):
        offset = random.randint(0, 89)
        call_date = call_window_start + timedelta(days=offset)
        cur.execute(
            "INSERT INTO calls (rep_id, hcp_id, call_date, outcome) VALUES (%s, %s, %s, %s)",
            (rep_id, hcp_id, call_date, random.choice(outcomes)),
        )

conn.commit()
cur.close()
conn.close()

print(f"\nDone. Seeded {len(territory_ids)} territories, "
      f"{total_reps} reps, "
      f"{len(hcp_records)} HCPs, {len(product_ids)} products, "
      f"6 months of prescriptions, ~90 days of call history.")