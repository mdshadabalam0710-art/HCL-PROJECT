"""
SQL RFM Validation and Comparison Script
Runs the SQL model from sql/rfm_ntile.sql against data/retail_rfm.db,
compares SQL NTILE segments against Python results, and reports tie behavior.
"""

import os
import sqlite3
import pandas as pd

def run_sql_validation():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "retail_rfm.db")
    sql_file = os.path.join(base_dir, "sql", "rfm_ntile.sql")
    output_report_csv = os.path.join(base_dir, "validation", "sql_python_mismatches.csv")
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}. Run python/rfm_scoring.py first.")
        
    conn = sqlite3.connect(db_path)
    
    # Core CTE model definition
    cte_query = """
    WITH snapshot_cte AS (
        SELECT 
            datetime(MAX(InvoiceDate), '+1 day') AS snapshot_date
        FROM retail_transactions
        WHERE CustomerID IS NOT NULL
    ),
    customer_aggregates AS (
        SELECT 
            t.CustomerID,
            MAX(t.Country) AS Country,
            ROUND(
                julianday((SELECT snapshot_date FROM snapshot_cte)) - 
                julianday(COALESCE(
                    MAX(CASE WHEN t.Quantity > 0 AND t.InvoiceNo NOT LIKE 'C%' THEN t.InvoiceDate END),
                    MAX(t.InvoiceDate)
                )), 
                1
            ) AS Recency,
            COUNT(DISTINCT CASE WHEN t.Quantity > 0 AND t.InvoiceNo NOT LIKE 'C%' THEN t.InvoiceNo END) AS Frequency,
            ROUND(SUM(CASE WHEN t.Quantity > 0 AND t.InvoiceNo NOT LIKE 'C%' THEN t.Quantity * t.UnitPrice ELSE 0 END), 2) AS Gross_Purchases,
            ROUND(SUM(CASE WHEN t.Quantity < 0 OR t.InvoiceNo LIKE 'C%' THEN ABS(t.Quantity * t.UnitPrice) ELSE 0 END), 2) AS Total_Refunds,
            ROUND(SUM(t.Quantity * t.UnitPrice), 2) AS Monetary
        FROM retail_transactions t
        WHERE t.CustomerID IS NOT NULL
        GROUP BY t.CustomerID
    ),
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
    """
    
    # 1. Summary comparison query
    summary_sql = cte_query + """
    SELECT 
        COUNT(*) AS Total_Customers,
        SUM(CASE WHEN s.Segment = p.Segment THEN 1 ELSE 0 END) AS Segment_Matches,
        SUM(CASE WHEN s.Segment != p.Segment THEN 1 ELSE 0 END) AS Segment_Mismatches,
        ROUND(SUM(CASE WHEN s.Segment = p.Segment THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS Match_Percentage,
        SUM(CASE WHEN s.R_Score = p.R_Score THEN 1 ELSE 0 END) AS R_Score_Matches,
        SUM(CASE WHEN s.F_Score = p.F_Score THEN 1 ELSE 0 END) AS F_Score_Matches,
        SUM(CASE WHEN s.M_Score = p.M_Score THEN 1 ELSE 0 END) AS M_Score_Matches
    FROM rfm_segmented s
    JOIN rfm_python_reference p ON s.CustomerID = p.CustomerID;
    """
    
    summary_df = pd.read_sql_query(summary_sql, conn)
    print("=" * 70)
    print("SQL (NTILE) vs PYTHON (QCUT/RANK) CONCORDANCE REPORT")
    print("=" * 70)
    print(summary_df.to_string(index=False))
    
    # 2. Detailed mismatch query
    mismatch_sql = cte_query + """
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
        CASE 
            WHEN s.F_Score != p.F_Score THEN 'Tie Boundary in Frequency (F=' || CAST(s.Frequency AS TEXT) || ')'
            WHEN s.R_Score != p.R_Score THEN 'Tie Boundary in Recency (R=' || CAST(s.Recency AS TEXT) || ')'
            WHEN s.M_Score != p.M_Score THEN 'Tie Boundary in Monetary (M=' || CAST(s.Monetary AS TEXT) || ')'
            ELSE 'Other'
        END AS Variance_Driver
    FROM rfm_segmented s
    JOIN rfm_python_reference p ON s.CustomerID = p.CustomerID
    WHERE s.Segment != p.Segment
    ORDER BY s.CustomerID;
    """
    
    mismatch_df = pd.read_sql_query(mismatch_sql, conn)
    os.makedirs(os.path.dirname(output_report_csv), exist_ok=True)
    mismatch_df.to_csv(output_report_csv, index=False)
    
    print(f"\nTotal Segment Mismatches: {len(mismatch_df)}")
    if len(mismatch_df) > 0:
        print("\nPrimary Variance Drivers:")
        print(mismatch_df['Variance_Driver'].value_counts())
        print("\nSample Mismatches (First 5 Rows):")
        print(mismatch_df.head(5)[['CustomerID', 'Frequency', 'SQL_F', 'PY_F', 'SQL_Segment', 'PY_Segment', 'Variance_Driver']].to_string(index=False))
    
    conn.close()
    print(f"\nFull mismatch audit log saved to: {output_report_csv}")
    print("=" * 70)

if __name__ == "__main__":
    run_sql_validation()
