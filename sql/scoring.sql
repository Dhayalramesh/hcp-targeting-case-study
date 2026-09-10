-- HCP Targeting & Call Planning System
-- Segmentation scoring logic — TDD §5.2, §5.4
-- Kept as standalone, re-runnable SQL (not baked into app code) so the
-- analytics team can review/modify the formula independently (FR-08, FR-09).

-- ============================================================
-- 1. Trailing 3-month volume + growth per HCP (per product totalled)
-- ============================================================
CREATE OR REPLACE VIEW hcp_trailing_volume AS
WITH monthly_totals AS (
    SELECT
        hcp_id,
        rx_month,
        SUM(rx_volume) AS month_volume
    FROM prescriptions
    GROUP BY hcp_id, rx_month
),
windowed AS (
    SELECT
        hcp_id,
        rx_month,
        month_volume,
        LAG(month_volume, 2) OVER (PARTITION BY hcp_id ORDER BY rx_month) AS volume_3mo_ago,
        LAG(month_volume, 1) OVER (PARTITION BY hcp_id ORDER BY rx_month) AS volume_prior_month
    FROM monthly_totals
)
SELECT
    w.hcp_id,
    h.territory_id,
    w.rx_month AS latest_month,
    w.month_volume AS latest_volume,
    w.volume_3mo_ago,
    CASE
        WHEN w.volume_3mo_ago IS NULL OR w.volume_3mo_ago = 0 THEN NULL
        ELSE ROUND(((w.month_volume - w.volume_3mo_ago)::NUMERIC / w.volume_3mo_ago) * 100, 1)
    END AS growth_pct_3mo
FROM windowed w
JOIN hcps h ON h.hcp_id = w.hcp_id
-- keep only each HCP's most recent month
WHERE w.rx_month = (SELECT MAX(rx_month) FROM monthly_totals mt WHERE mt.hcp_id = w.hcp_id);

-- ============================================================
-- 2. Composite score + tier (TDD §5.2)
--    volume_score / growth_score = quartile (1=lowest, 4=highest) within territory
--    composite = 0.7 * volume_score + 0.3 * growth_score
--    tier A = top quartile of composite, down to D = bottom quartile
-- ============================================================
CREATE OR REPLACE VIEW hcp_scores AS
WITH ranked AS (
    SELECT
        hcp_id,
        territory_id,
        latest_volume,
        growth_pct_3mo,
        NTILE(4) OVER (PARTITION BY territory_id ORDER BY latest_volume ASC)           AS volume_score,
        NTILE(4) OVER (PARTITION BY territory_id ORDER BY COALESCE(growth_pct_3mo, 0) ASC) AS growth_score
    FROM hcp_trailing_volume
),
scored AS (
    SELECT
        *,
        ROUND((0.7 * volume_score) + (0.3 * growth_score), 2) AS composite_score
    FROM ranked
)
SELECT
    s.hcp_id,
    h.hcp_name,
    h.specialty,
    t.territory_name,
    s.latest_volume,
    s.growth_pct_3mo,
    s.volume_score,
    s.growth_score,
    s.composite_score,
    CASE
        WHEN s.composite_score >= 3.3 THEN 'A'
        WHEN s.composite_score >= 2.6 THEN 'B'
        WHEN s.composite_score >= 1.9 THEN 'C'
        ELSE 'D'
    END AS tier,
    CASE
        WHEN s.composite_score >= 3.3 THEN 7   -- Tier A: weekly
        WHEN s.composite_score >= 2.6 THEN 14  -- Tier B: biweekly
        WHEN s.composite_score >= 1.9 THEN 30  -- Tier C: monthly
        ELSE 90                                 -- Tier D: quarterly
    END AS recommended_call_interval_days
FROM scored s
JOIN hcps h ON h.hcp_id = s.hcp_id
JOIN territories t ON t.territory_id = s.territory_id;

-- ============================================================
-- 3. Coverage: actual calls vs. recommended, per HCP
--    LEFT JOIN so zero-call HCPs still appear at 0% (TDD §5.4)
-- ============================================================
CREATE OR REPLACE VIEW hcp_coverage AS
SELECT
    sc.hcp_id,
    sc.hcp_name,
    sc.territory_name,
    sc.tier,
    sc.recommended_call_interval_days,
    COUNT(c.call_id) AS calls_last_90_days,
    -- how many calls "should" have happened in 90 days at the recommended interval
    GREATEST(1, ROUND(90.0 / sc.recommended_call_interval_days)) AS recommended_calls_90_days,
    ROUND(
        100.0 * COUNT(c.call_id) / GREATEST(1, ROUND(90.0 / sc.recommended_call_interval_days)),
        1
    ) AS coverage_pct
FROM hcp_scores sc
LEFT JOIN calls c
    ON c.hcp_id = sc.hcp_id
    AND c.call_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY sc.hcp_id, sc.hcp_name, sc.territory_name, sc.tier, sc.recommended_call_interval_days;

-- ============================================================
-- 4. Decline alerts: 2 consecutive months of falling volume (TDD §5.4)
-- ============================================================
CREATE OR REPLACE VIEW hcp_decline_alerts AS
WITH monthly_totals AS (
    SELECT hcp_id, rx_month, SUM(rx_volume) AS month_volume
    FROM prescriptions
    GROUP BY hcp_id, rx_month
),
with_lags AS (
    SELECT
        hcp_id,
        rx_month,
        month_volume,
        LAG(month_volume, 1) OVER (PARTITION BY hcp_id ORDER BY rx_month) AS prev_1,
        LAG(month_volume, 2) OVER (PARTITION BY hcp_id ORDER BY rx_month) AS prev_2
    FROM monthly_totals
),
latest_per_hcp AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY hcp_id ORDER BY rx_month DESC) AS rn
    FROM with_lags
)
SELECT
    l.hcp_id,
    h.hcp_name,
    t.territory_name,
    sc.tier,
    l.prev_2 AS two_months_ago_volume,
    l.prev_1 AS last_month_volume,
    l.month_volume AS current_month_volume
FROM latest_per_hcp l
JOIN hcps h ON h.hcp_id = l.hcp_id
JOIN territories t ON t.territory_id = h.territory_id
JOIN hcp_scores sc ON sc.hcp_id = l.hcp_id
WHERE l.rn = 1
  AND l.prev_2 IS NOT NULL
  AND l.month_volume < l.prev_1
  AND l.prev_1 < l.prev_2
  AND sc.tier IN ('A', 'B');