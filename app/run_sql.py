import os
import sys
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("Set DATABASE_URL environment variable first.")

if len(sys.argv) < 2:
    raise SystemExit("Usage: python run_sql.py <path_to_sql_file>")

sql_file = sys.argv[1]
with open(sql_file, "r", encoding="utf-8") as f:
    sql = f.read()

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()
cur.execute(sql)
cur.close()
conn.close()
print(f"Ran {sql_file} successfully.")