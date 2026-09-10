-- HCP Targeting & Call Planning System
-- Schema per Technical Design Document §4

CREATE TABLE territories (
    territory_id   SERIAL PRIMARY KEY,
    territory_name TEXT NOT NULL,
    region         TEXT NOT NULL
);

CREATE TABLE reps (
    rep_id        SERIAL PRIMARY KEY,
    rep_name      TEXT NOT NULL,
    territory_id  INT NOT NULL REFERENCES territories(territory_id)
);

CREATE TABLE hcps (
    hcp_id        SERIAL PRIMARY KEY,
    hcp_name      TEXT NOT NULL,
    specialty     TEXT NOT NULL,
    territory_id  INT NOT NULL REFERENCES territories(territory_id)
);

CREATE TABLE products (
    product_id    SERIAL PRIMARY KEY,
    product_name  TEXT NOT NULL
);

CREATE TABLE prescriptions (
    rx_id        SERIAL PRIMARY KEY,
    hcp_id       INT NOT NULL REFERENCES hcps(hcp_id),
    product_id   INT NOT NULL REFERENCES products(product_id),
    rx_month     DATE NOT NULL,
    rx_volume    INT NOT NULL CHECK (rx_volume >= 0),
    UNIQUE (hcp_id, product_id, rx_month)
);

CREATE TABLE calls (
    call_id     SERIAL PRIMARY KEY,
    rep_id      INT NOT NULL REFERENCES reps(rep_id),
    hcp_id      INT NOT NULL REFERENCES hcps(hcp_id),
    call_date   DATE NOT NULL,
    outcome     TEXT NOT NULL DEFAULT 'Completed'
);

-- Indexes to support territory-scoped queries (NFR-01)
CREATE INDEX idx_reps_territory ON reps(territory_id);
CREATE INDEX idx_hcps_territory ON hcps(territory_id);
CREATE INDEX idx_rx_hcp_month ON prescriptions(hcp_id, rx_month);
CREATE INDEX idx_calls_hcp ON calls(hcp_id);
CREATE INDEX idx_calls_rep ON calls(rep_id);