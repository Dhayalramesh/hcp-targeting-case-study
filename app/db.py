"""
Database access layer for the HCP Targeting & Call Planning System.
One function per data need, per TDD §7. All queries parameterized.

Uses NullPool: Neon's free tier auto-suspends the database on idle, which
kills pooled connections silently. NullPool opens a fresh connection per
query instead of reusing a potentially-dead one from a pool.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

def get_engine():
    db_url = os.environ.get("DATABASE_URL") or st_secret_fallback()
    return create_engine(db_url, pool_pre_ping=True, poolclass=NullPool)

def st_secret_fallback():
    # allows the app to also read from Streamlit's secrets.toml when deployed
    import streamlit as st
    return st.secrets["DATABASE_URL"]

engine = None

def _engine():
    global engine
    if engine is None:
        engine = get_engine()
    return engine


def get_territories() -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql(text("SELECT territory_id, territory_name FROM territories ORDER BY territory_name"), conn)


def get_reps(territory_id=None) -> pd.DataFrame:
    q = "SELECT rep_id, rep_name, territory_id FROM reps"
    params = {}
    if territory_id:
        q += " WHERE territory_id = :tid"
        params["tid"] = territory_id
    q += " ORDER BY rep_name"
    with _engine().connect() as conn:
        return pd.read_sql(text(q), conn, params=params)


def get_hcp_scores(territory_id=None, tier=None) -> pd.DataFrame:
    q = "SELECT * FROM hcp_scores WHERE 1=1"
    params = {}
    if territory_id:
        q += " AND territory_name = (SELECT territory_name FROM territories WHERE territory_id = :tid)"
        params["tid"] = territory_id
    if tier:
        q += " AND tier = :tier"
        params["tier"] = tier
    q += " ORDER BY composite_score DESC"
    with _engine().connect() as conn:
        return pd.read_sql(text(q), conn, params=params)


def get_rep_hcp_list(rep_id) -> pd.DataFrame:
    q = """
        SELECT DISTINCT sc.*
        FROM hcp_scores sc
        JOIN calls c ON c.hcp_id = sc.hcp_id
        WHERE c.rep_id = :rep_id
        ORDER BY sc.composite_score DESC
    """
    with _engine().connect() as conn:
        return pd.read_sql(text(q), conn, params={"rep_id": rep_id})


def get_coverage_summary(territory_id=None) -> pd.DataFrame:
    q = "SELECT * FROM hcp_coverage WHERE 1=1"
    params = {}
    if territory_id:
        q += " AND territory_name = (SELECT territory_name FROM territories WHERE territory_id = :tid)"
        params["tid"] = territory_id
    q += " ORDER BY coverage_pct ASC"
    with _engine().connect() as conn:
        return pd.read_sql(text(q), conn, params=params)


def get_coverage_by_tier() -> pd.DataFrame:
    q = """
        SELECT tier,
               COUNT(*) AS hcp_count,
               ROUND(AVG(coverage_pct), 1) AS avg_coverage_pct
        FROM hcp_coverage
        GROUP BY tier
        ORDER BY tier
    """
    with _engine().connect() as conn:
        return pd.read_sql(text(q), conn)


def get_decline_alerts() -> pd.DataFrame:
    q = "SELECT * FROM hcp_decline_alerts ORDER BY tier, hcp_name"
    with _engine().connect() as conn:
        return pd.read_sql(text(q), conn)


def get_territory_summary() -> pd.DataFrame:
    q = """
        SELECT t.territory_name,
               COUNT(DISTINCT h.hcp_id) AS total_hcps,
               COUNT(DISTINCT h.hcp_id) FILTER (WHERE sc.tier = 'A') AS tier_a_count,
               ROUND(AVG(cov.coverage_pct), 1) AS avg_coverage_pct
        FROM territories t
        LEFT JOIN hcps h ON h.territory_id = t.territory_id
        LEFT JOIN hcp_scores sc ON sc.hcp_id = h.hcp_id
        LEFT JOIN hcp_coverage cov ON cov.hcp_id = h.hcp_id
        GROUP BY t.territory_name
        ORDER BY t.territory_name
    """
    with _engine().connect() as conn:
        return pd.read_sql(text(q), conn)