-- ==============================================================================
-- Customer Segmentation using RFM (Recency, Frequency, Monetary)
-- Engine: SQLite / PostgreSQL Compatible Syntax
-- File: sql/rfm_ntile.sql
-- ==============================================================================
--
-- DESCRIPTION:
-- This SQL script implements an end-to-end RFM analytical model using Common
-- Table Expressions (CTEs), Window Functions (NTILE(5)), and CASE expressions.
--
-- CORE STEPS:
-- 1. snapshot_date_cte: Dynamically sets analysis snapshot = MAX(InvoiceDate) + 1 day.
-- 2. customer_aggregates: Computes raw Recency, Frequency, Gross, Refunds, and Net Monetary.
-- 3. rfm_quintiles: Uses NTILE(5) to score R, F, and M into quintiles (1-5).
-- 4. rfm_segmented: Classifies customers into 10 business segments via CASE logic.
-- 5. validation_query: Compares SQL NTILE segments against Python reference results.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- CTE 1: Snapshot Date Definition
-- Calculates reference date = max transaction date + 1 day
-- ------------------------------------------------------------------------------
WITH snapshot_cte AS (
    SELECT 
        datetime(MAX(InvoiceDate), '+1 day') AS snapshot_date
    FROM retail_transactions
    WHERE CustomerID IS NOT NULL
),

-- ------------------------------------------------------------------------------
-- CTE 2: Customer Aggregations
-- Computes raw RFM metrics and isolates refunds:
-- - Recency: Days from customer's latest purchase date to snapshot date
-- - Frequency: Count of distinct purchase invoices (excluding cancellations)
-- - Monetary: Net revenue (Gross purchases minus refunds)
-- ------------------------------------------------------------------------------
customer_aggregates AS (
    SELECT 
        t.CustomerID,
        MAX(t.Country) AS Country,
        -- Recency: Days between last purchase and snapshot date
        ROUND(
            julianday((SELECT snapshot_date FROM snapshot_cte)) - 
            julianday(COALESCE(
                MAX(CASE WHEN t.Quantity > 0 AND t.InvoiceNo NOT LIKE 'C%' THEN t.InvoiceDate END),
                MAX(t.InvoiceDate)
            )), 
            1
        ) AS Recency,
        -- Frequency: Count of distinct purchase orders
        COUNT(DISTINCT CASE WHEN t.Quantity > 0 AND t.InvoiceNo NOT LIKE 'C%' THEN t.InvoiceNo END) AS Frequency,
        -- Gross Purchases
        ROUND(SUM(CASE WHEN t.Quantity > 0 AND t.InvoiceNo NOT LIKE 'C%' THEN t.Quantity * t.UnitPrice ELSE 0 END), 2) AS Gross_Purchases,
        -- Total Refunds
        ROUND(SUM(CASE WHEN t.Quantity < 0 OR t.InvoiceNo LIKE 'C%' THEN ABS(t.Quantity * t.UnitPrice) ELSE 0 END), 2) AS Total_Refunds,
        -- Net Monetary Spend
        ROUND(SUM(t.Quantity * t.UnitPrice), 2) AS Monetary
    FROM retail_transactions t
    WHERE t.CustomerID IS NOT NULL
    GROUP BY t.CustomerID
),

-- ------------------------------------------------------------------------------
-- CTE 3: RFM Quintile Scoring with NTILE(5)
-- Notes on NTILE:
-- - Recency: ORDER BY Recency DESC so smallest recency days -> Quintile 5 (Most recent)
-- - Frequency: ORDER BY Frequency ASC so largest order count -> Quintile 5 (Most frequent)
-- - Monetary: ORDER BY Monetary ASC so highest net spend -> Quintile 5 (Highest value)
-- - CustomerID ASC is used as a deterministic secondary tie-breaker.
-- ------------------------------------------------------------------------------
rfm_quintiles AS (
    SELECT 
        CustomerID,
        Country,
        Recency,
        Frequency,
        Monetary,
        Gross_Purchases,
        Total_Refunds,
        CASE WHEN Total_Refunds > Gross_Purchases THEN 1 ELSE 0 END AS Refund_Exceeds_Purchases,
        NTILE(5) OVER (ORDER BY Recency DESC, CustomerID ASC) AS R_Score,
        NTILE(5) OVER (ORDER BY Frequency ASC, CustomerID ASC) AS F_Score,
        NTILE(5) OVER (ORDER BY Monetary ASC, CustomerID ASC) AS M_Score
    FROM customer_aggregates
),

-- ------------------------------------------------------------------------------
-- CTE 4: RFM Segmentation Logic
-- Maps all 25 (R, F) combinations into 10 industry-standard customer segments
-- ------------------------------------------------------------------------------
rfm_segmented AS (
    SELECT 
        CustomerID,
        Country,
        Recency,
        Frequency,
        Monetary,
        Gross_Purchases,
        Total_Refunds,
        Refund_Exceeds_Purchases,
        R_Score,
        F_Score,
        M_Score,
        CAST(R_Score AS TEXT) || CAST(F_Score AS TEXT) || CAST(M_Score AS TEXT) AS RFM_Score,
        CASE 
            WHEN R_Score >= 4 AND F_Score >= 4 THEN 'Champions'
            WHEN R_Score >= 4 AND F_Score IN (2, 3) THEN 'Potential Loyalists'
            WHEN R_Score = 5 AND F_Score = 1 THEN 'New Customers'
            WHEN R_Score IN (3, 4) AND F_Score = 1 THEN 'Promising'
            WHEN R_Score = 3 AND F_Score >= 3 THEN 'Loyal'
            WHEN (R_Score = 3 AND F_Score = 2) OR (R_Score = 2 AND F_Score = 3) THEN 'Need Attention'
            WHEN (R_Score = 2 AND F_Score >= 4) OR (R_Score = 1 AND F_Score = 3) THEN 'At Risk'
            WHEN R_Score = 1 AND F_Score >= 4 THEN 'Can''t Lose Them'
            WHEN (R_Score = 2 AND F_Score = 2) OR (R_Score = 1 AND F_Score = 2) THEN 'Hibernating'
            WHEN (R_Score = 2 AND F_Score = 1) OR (R_Score = 1 AND F_Score = 1) THEN 'Lost'
            ELSE 'Need Attention'
        END AS Segment
    FROM rfm_quintiles
)

-- ------------------------------------------------------------------------------
-- PRIMARY OUTPUT QUERY: View Top 20 Customer RFM Profiles
-- ------------------------------------------------------------------------------
SELECT 
    CustomerID,
    Country,
    Recency,
    Frequency,
    Monetary,
    R_Score,
    F_Score,
    M_Score,
    RFM_Score,
    Segment,
    Refund_Exceeds_Purchases
FROM rfm_segmented
ORDER BY Monetary DESC
LIMIT 20;


-- ==============================================================================
-- VALIDATION QUERY: SQL vs Python Results Comparison & Tie Behavior Analysis
-- ==============================================================================
-- EXPLANATION OF TIE BEHAVIOR (NTILE vs qcut / rank):
-- 1. SQL NTILE(5):
--    Partitions the sorted dataset into 5 equal buckets of N/5 rows.
--    When many rows have tied values (e.g. ~40% of customers having Frequency = 1),
--    NTILE arbitrarily places a portion of the tied values into bucket 1 and the
--    remainder into bucket 2 based purely on the physical scan/sort order.
-- 2. Python rank(method='first') + pd.qcut():
--    Ranks rows sequentially by DataFrame index order when values are identical.
-- 3. Mismatches occur along the boundary cutoffs when the underlying sorting order
--    of tied rows differs between SQL and Python.
-- ==============================================================================

/*
-- To run validation against rfm_python_reference table:

SELECT 
    COUNT(*) AS Total_Customers,
    SUM(CASE WHEN s.Segment = p.Segment THEN 1 ELSE 0 END) AS Segment_Exact_Matches,
    SUM(CASE WHEN s.Segment != p.Segment THEN 1 ELSE 0 END) AS Segment_Mismatches,
    ROUND(SUM(CASE WHEN s.Segment = p.Segment THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS Match_Percentage,
    SUM(CASE WHEN s.R_Score = p.R_Score THEN 1 ELSE 0 END) AS R_Score_Matches,
    SUM(CASE WHEN s.F_Score = p.F_Score THEN 1 ELSE 0 END) AS F_Score_Matches,
    SUM(CASE WHEN s.M_Score = p.M_Score THEN 1 ELSE 0 END) AS M_Score_Matches
FROM rfm_segmented s
JOIN rfm_python_reference p ON s.CustomerID = p.CustomerID;

-- Query to list individual mismatches with detailed score comparison:
SELECT 
    s.CustomerID,
    s.Recency,
    s.Frequency,
    s.Monetary,
    s.R_Score AS SQL_R,
    p.R_Score AS PY_R,
    s.F_Score AS SQL_F,
    p.F_Score AS PY_F,
    s.M_Score AS SQL_M,
    p.M_Score AS PY_M,
    s.Segment AS SQL_Segment,
    p.Segment AS PY_Segment,
    'Tie boundary variance in ' || 
    CASE WHEN s.F_Score != p.F_Score THEN 'Frequency'
         WHEN s.R_Score != p.R_Score THEN 'Recency'
         ELSE 'Monetary' END AS Variance_Reason
FROM rfm_segmented s
JOIN rfm_python_reference p ON s.CustomerID = p.CustomerID
WHERE s.Segment != p.Segment
ORDER BY s.CustomerID
LIMIT 20;
*/
