"""
RFM Scoring & Customer Segmentation Engine
Author: Antigravity
Dataset: Online Retail (UCI E-Commerce / Synthetic Benchmark)

Steps:
1. Data Cleaning: Drop null CustomerIDs, deduplicate, compute line revenue.
2. Refund Handling: Identify negative quantities and 'C' invoices, calculate net purchases,
   flag customers whose refunds exceed their purchases.
3. RFM Metrics:
   - Recency: Days from customer's last purchase to snapshot date (max date + 1 day).
   - Frequency: Number of distinct purchase invoices.
   - Monetary: Total net revenue (gross purchases minus refunds).
4. Quintile Scoring:
   - Score 1-5 using pandas rank(method='first') and qcut to handle ties cleanly.
   - Recency reversed (recent = 5).
5. Segmentation:
   - 10 segments mapped from R & F scores.
6. Visualizations & Exports:
   - Segment size distribution, revenue by segment, Recency vs Frequency heatmap.
   - Exports rfm_results.csv, cleaned data, and prepares SQLite database for SQL validation.
"""

import os
import sys
import sqlite3
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configure visual styling
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "figure.titlesize": 14
})

# Segment Mapping Definition (25 cells)
SEGMENT_MAP = {
    (5, 5): "Champions", (5, 4): "Champions", (4, 5): "Champions", (4, 4): "Champions",
    (5, 3): "Potential Loyalists", (5, 2): "Potential Loyalists",
    (4, 3): "Potential Loyalists", (4, 2): "Potential Loyalists",
    (5, 1): "New Customers",
    (4, 1): "Promising", (3, 1): "Promising",
    (3, 5): "Loyal", (3, 4): "Loyal", (3, 3): "Loyal",
    (3, 2): "Need Attention", (2, 3): "Need Attention",
    (2, 5): "At Risk", (2, 4): "At Risk", (1, 3): "At Risk",
    (1, 5): "Can't Lose Them", (1, 4): "Can't Lose Them",
    (2, 2): "Hibernating", (1, 2): "Hibernating",
    (2, 1): "Lost", (1, 1): "Lost"
}

ALL_SEGMENTS = [
    "Champions", "Loyal", "Potential Loyalists", "New Customers", "Promising",
    "Need Attention", "At Risk", "Can't Lose Them", "Hibernating", "Lost"
]

SEGMENT_COLORS = {
    "Champions": "#2ecc71",
    "Loyal": "#27ae60",
    "Potential Loyalists": "#3498db",
    "New Customers": "#1abc9c",
    "Promising": "#9b59b6",
    "Need Attention": "#f39c12",
    "At Risk": "#e67e22",
    "Can't Lose Them": "#e74c3c",
    "Hibernating": "#95a5a6",
    "Lost": "#7f8c8d"
}

def load_and_clean_data(raw_data_path):
    """Loads raw retail data, cleans nulls, removes duplicates, and computes revenue."""
    print("=" * 60)
    print("STEP 1: DATA INGESTION & CLEANING")
    print("=" * 60)
    
    if not os.path.exists(raw_data_path):
        raise FileNotFoundError(f"Input data file not found at: {raw_data_path}")
        
    print(f"Loading data from: {raw_data_path}")
    if raw_data_path.endswith(".xlsx") or raw_data_path.endswith(".xls"):
        df = pd.read_excel(raw_data_path)
    else:
        df = pd.read_csv(raw_data_path)
        
    initial_rows = len(df)
    print(f"Initial raw transactions: {initial_rows:,}")
    
    # Standardize column names
    col_mapping = {c: c.strip() for c in df.columns}
    df.rename(columns=col_mapping, inplace=True)
    
    # 1. Null CustomerID handling
    null_cust = df['CustomerID'].isna().sum()
    print(f"Null CustomerIDs found: {null_cust:,} ({null_cust / initial_rows * 100:.2f}%)")
    df_cleaned = df.dropna(subset=['CustomerID']).copy()
    
    # Standardize CustomerID as integer string
    df_cleaned['CustomerID'] = df_cleaned['CustomerID'].astype(int).astype(str)
    
    # 2. Duplicate handling
    duplicates = df_cleaned.duplicated().sum()
    print(f"Exact duplicate records found: {duplicates:,}")
    df_cleaned = df_cleaned.drop_duplicates().copy()
    
    # 3. Data type and date parsing
    df_cleaned['InvoiceDate'] = pd.to_datetime(df_cleaned['InvoiceDate'])
    df_cleaned['Quantity'] = pd.to_numeric(df_cleaned['Quantity'], errors='coerce').fillna(0).astype(int)
    df_cleaned['UnitPrice'] = pd.to_numeric(df_cleaned['UnitPrice'], errors='coerce').fillna(0.0).astype(float)
    
    # 4. Revenue calculation
    df_cleaned['Revenue'] = df_cleaned['Quantity'] * df_cleaned['UnitPrice']
    
    cleaned_rows = len(df_cleaned)
    print(f"Cleaned transactions: {cleaned_rows:,} (Removed {initial_rows - cleaned_rows:,} rows)")
    print(f"Unique active customers: {df_cleaned['CustomerID'].nunique():,}")
    print(f"Date range: {df_cleaned['InvoiceDate'].min()} to {df_cleaned['InvoiceDate'].max()}")
    
    return df_cleaned


def process_refunds(df):
    """
    Separates refunds/cancellations (Quantity < 0 or InvoiceNo starting with 'C').
    Computes gross purchases, refund totals, and flags customers with net <= 0.
    """
    print("\n" + "=" * 60)
    print("STEP 2: REFUNDS & CANCELLATIONS ANALYSIS")
    print("=" * 60)
    
    is_refund = (df['Quantity'] < 0) | (df['InvoiceNo'].astype(str).str.startswith('C', na=False))
    df_refunds = df[is_refund].copy()
    df_purchases = df[~is_refund].copy()
    
    total_refund_items = len(df_refunds)
    total_refund_amount = df_refunds['Revenue'].sum() # negative value
    print(f"Refund transactions: {total_refund_items:,}")
    print(f"Total refund value: ${abs(total_refund_amount):,.2f}")
    
    # Per-customer purchase and refund aggregations
    cust_purchases = df_purchases.groupby('CustomerID').agg(
        Gross_Purchases=('Revenue', 'sum'),
        Purchase_Invoices=('InvoiceNo', 'nunique'),
        Last_Purchase_Date=('InvoiceDate', 'max')
    )
    
    cust_refunds = df_refunds.groupby('CustomerID').agg(
        Total_Refunds=('Revenue', lambda x: abs(x.sum())),
        Refund_Invoices=('InvoiceNo', 'nunique'),
        Last_Refund_Date=('InvoiceDate', 'max')
    )
    
    # Combine customer financial summary
    all_custs = pd.Series(df['CustomerID'].unique(), name='CustomerID')
    cust_summary = pd.DataFrame(index=all_custs)
    cust_summary = cust_summary.join(cust_purchases).join(cust_refunds).fillna({
        'Gross_Purchases': 0.0,
        'Purchase_Invoices': 0,
        'Total_Refunds': 0.0,
        'Refund_Invoices': 0
    })
    
    cust_summary['Net_Monetary'] = cust_summary['Gross_Purchases'] - cust_summary['Total_Refunds']
    cust_summary['Refund_Exceeds_Purchases'] = cust_summary['Total_Refunds'] > cust_summary['Gross_Purchases']
    cust_summary['Net_Negative_Or_Zero'] = cust_summary['Net_Monetary'] <= 0
    
    flagged_refund_custs = cust_summary[cust_summary['Refund_Exceeds_Purchases']]
    print(f"Customers flagged where refunds exceed purchases: {len(flagged_refund_custs):,}")
    for cid, row in flagged_refund_custs.head(5).iterrows():
        print(f"  - Customer {cid}: Gross ${row['Gross_Purchases']:.2f}, Refunds ${row['Total_Refunds']:.2f}, Net ${row['Net_Monetary']:.2f}")
        
    return df_purchases, df_refunds, cust_summary


def compute_rfm_metrics(df_cleaned, cust_summary):
    """
    Computes RFM:
    - Snapshot date = max InvoiceDate + 1 day
    - Recency = days since last purchase date
    - Frequency = count of distinct purchase invoices
    - Monetary = total net revenue (gross purchases - refunds)
    """
    print("\n" + "=" * 60)
    print("STEP 3: COMPUTING RFM CORE METRICS")
    print("=" * 60)
    
    # Reference snapshot date
    max_date = df_cleaned['InvoiceDate'].max()
    snapshot_date = max_date + datetime.timedelta(days=1)
    print(f"Max transaction date: {max_date}")
    print(f"Snapshot analysis date: {snapshot_date}")
    
    rfm = cust_summary.copy()
    
    # Recency: days from last purchase date to snapshot date
    # If no purchase exists (refund-only customer), fallback to last refund date
    rfm['Effective_Last_Date'] = rfm['Last_Purchase_Date'].fillna(rfm['Last_Refund_Date'])
    rfm['Recency'] = (snapshot_date - pd.to_datetime(rfm['Effective_Last_Date'])).dt.total_seconds() / (24 * 3600)
    rfm['Recency'] = rfm['Recency'].round(1)
    
    # Frequency: count of distinct purchase invoices
    rfm['Frequency'] = rfm['Purchase_Invoices'].astype(int)
    
    # Monetary: net revenue
    rfm['Monetary'] = rfm['Net_Monetary'].round(2)
    
    # Pull Primary Country for each customer
    country_map = df_cleaned.groupby('CustomerID')['Country'].agg(lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0])
    rfm['Country'] = rfm.index.map(country_map).fillna("Unknown")
    
    print(f"Computed RFM metrics for {len(rfm):,} customers.")
    print("Summary statistics of raw RFM:")
    print(rfm[['Recency', 'Frequency', 'Monetary']].describe().T[['mean', 'std', 'min', '50%', 'max']])
    
    return rfm, snapshot_date


def score_rfm_quintiles(rfm):
    """
    Scores R, F, and M from 1 to 5 using quintiles.
    Uses rank(method='first') before qcut to handle ties cleanly (e.g. F=1 ties).
    Recency is reversed: lower days -> rank higher -> score 5.
    Frequency and Monetary: higher values -> score 5.
    """
    print("\n" + "=" * 60)
    print("STEP 4: QUINTILE SCORING WITH RANK(METHOD='FIRST')")
    print("=" * 60)
    
    # Recency: lowest days gets highest rank -> score 5
    # rank(ascending=False, method='first') assigns rank 1 to the largest recency, rank N to smallest
    # pd.qcut on ascending rank with labels [1, 2, 3, 4, 5]:
    #   smallest recency -> highest rank -> quintile 5
    r_rank = rfm['Recency'].rank(ascending=False, method='first')
    rfm['R_Score'] = pd.qcut(r_rank, q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    
    # Frequency: highest frequency gets highest score
    f_rank = rfm['Frequency'].rank(ascending=True, method='first')
    rfm['F_Score'] = pd.qcut(f_rank, q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    
    # Monetary: highest net monetary gets highest score
    m_rank = rfm['Monetary'].rank(ascending=True, method='first')
    rfm['M_Score'] = pd.qcut(m_rank, q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    
    # Construct combined RFM Score string
    rfm['RFM_Score'] = (
        rfm['R_Score'].astype(str) +
        rfm['F_Score'].astype(str) +
        rfm['M_Score'].astype(str)
    )
    
    # Map to Segments
    rfm['Segment'] = [
        SEGMENT_MAP.get((r, f), "Need Attention")
        for r, f in zip(rfm['R_Score'], rfm['F_Score'])
    ]
    
    print("Quintile scoring completed successfully.")
    print("Segment distribution:")
    seg_counts = rfm['Segment'].value_counts()
    for seg, count in seg_counts.items():
        pct = count / len(rfm) * 100
        print(f"  - {seg:20s}: {count:5,d} ({pct:5.2f}%)")
        
    return rfm


def generate_visualizations(rfm, output_dir):
    """Generates charts for segment size, revenue by segment, and R vs F heatmap."""
    print("\n" + "=" * 60)
    print("STEP 5: GENERATING CHARTS & DASHBOARD GRAPHICS")
    print("=" * 60)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Segment Size Distribution
    plt.figure(figsize=(12, 6))
    seg_size = rfm['Segment'].value_counts().reindex(ALL_SEGMENTS).fillna(0)
    colors = [SEGMENT_COLORS.get(s, "#34495e") for s in seg_size.index]
    
    ax1 = seg_size.plot(kind='bar', color=colors, edgecolor='black', alpha=0.85)
    plt.title("Customer Count by RFM Segment", fontweight='bold', pad=15)
    plt.xlabel("RFM Segment", fontweight='bold')
    plt.ylabel("Number of Customers", fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    
    for p in ax1.patches:
        h = p.get_height()
        if h > 0:
            pct = h / len(rfm) * 100
            ax1.annotate(f"{int(h):,}\n({pct:.1f}%)",
                         (p.get_x() + p.get_width() / 2., h / 2),
                         ha='center', va='center', color='white', fontweight='bold', fontsize=9)
    plt.tight_layout()
    chart1_path = os.path.join(output_dir, "segment_size_bar.png")
    plt.savefig(chart1_path, dpi=300)
    plt.close()
    print(f"Saved: {chart1_path}")
    
    # 2. Revenue Contribution by Segment
    plt.figure(figsize=(12, 6))
    # Aggregate net monetary per segment
    seg_rev = rfm.groupby('Segment')['Monetary'].sum().reindex(ALL_SEGMENTS).fillna(0)
    total_rev = rfm['Monetary'].sum()
    
    ax2 = seg_rev.plot(kind='bar', color=colors, edgecolor='black', alpha=0.85)
    plt.title("Total Net Revenue by RFM Segment", fontweight='bold', pad=15)
    plt.xlabel("RFM Segment", fontweight='bold')
    plt.ylabel("Net Revenue ($)", fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    
    for p in ax2.patches:
        h = p.get_height()
        if h > 0:
            pct = h / total_rev * 100
            ax2.annotate(f"${h:,.0f}\n({pct:.1f}%)",
                         (p.get_x() + p.get_width() / 2., h / 2),
                         ha='center', va='center', color='white', fontweight='bold', fontsize=9)
    plt.tight_layout()
    chart2_path = os.path.join(output_dir, "revenue_by_segment_bar.png")
    plt.savefig(chart2_path, dpi=300)
    plt.close()
    print(f"Saved: {chart2_path}")
    
    # 3. Recency vs Frequency Heatmap (5x5 matrix)
    plt.figure(figsize=(9, 7))
    matrix_counts = pd.crosstab(
        index=rfm['R_Score'],
        columns=rfm['F_Score'],
        values=rfm.index,
        aggfunc='count'
    ).reindex(index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5]).fillna(0)
    
    matrix_avg_m = pd.crosstab(
        index=rfm['R_Score'],
        columns=rfm['F_Score'],
        values=rfm['Monetary'],
        aggfunc='mean'
    ).reindex(index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5]).fillna(0)
    
    # Build text annotations: Segment name, Count, Avg Monetary
    annotations = np.empty((5, 5), dtype=object)
    for r_idx, r_val in enumerate([5, 4, 3, 2, 1]):
        for f_idx, f_val in enumerate([1, 2, 3, 4, 5]):
            seg = SEGMENT_MAP.get((r_val, f_val), "")
            cnt = int(matrix_counts.loc[r_val, f_val])
            avg_m = matrix_avg_m.loc[r_val, f_val]
            annotations[r_idx, f_idx] = f"{seg}\nN={cnt}\n${avg_m:,.0f}"
            
    sns.heatmap(
        matrix_counts,
        annot=annotations,
        fmt="",
        cmap="YlGnBu",
        cbar_kws={'label': 'Customer Volume'},
        linewidths=1,
        linecolor='white'
    )
    plt.title("RFM Matrix: Recency vs Frequency\n(Annotated with Segment, Count, and Avg Monetary)", fontweight='bold', pad=15)
    plt.xlabel("Frequency Score (1: Infrequent -> 5: Most Frequent)", fontweight='bold')
    plt.ylabel("Recency Score (1: Churned/Old -> 5: Active/Recent)", fontweight='bold')
    plt.tight_layout()
    chart3_path = os.path.join(output_dir, "rf_heatmap.png")
    plt.savefig(chart3_path, dpi=300)
    plt.close()
    print(f"Saved: {chart3_path}")
    
    # 4. Frequency vs Monetary Scatter
    plt.figure(figsize=(10, 6))
    for seg in ALL_SEGMENTS:
        sub = rfm[rfm['Segment'] == seg]
        if len(sub) > 0:
            plt.scatter(
                sub['Frequency'],
                sub['Monetary'],
                label=seg,
                alpha=0.65,
                s=40,
                color=SEGMENT_COLORS.get(seg, "#333333"),
                edgecolors='none'
            )
    plt.yscale('symlog')
    plt.title("Customer Frequency vs Net Monetary by Segment (Log Scale)", fontweight='bold')
    plt.xlabel("Frequency (Distinct Purchase Orders)", fontweight='bold')
    plt.ylabel("Net Monetary ($ - Symlog Scale)", fontweight='bold')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', frameon=True)
    plt.tight_layout()
    chart4_path = os.path.join(output_dir, "freq_vs_monetary_scatter.png")
    plt.savefig(chart4_path, dpi=300)
    plt.close()
    print(f"Saved: {chart4_path}")


def populate_sqlite_database(db_path, df_cleaned, rfm):
    """
    Creates an embedded SQLite database containing:
    1. retail_transactions (cleaned line-item table)
    2. rfm_python_reference (Python computed RFM scores for cross-validation)
    """
    print("\n" + "=" * 60)
    print("STEP 6: CREATING EMBEDDED SQLITE DATABASE FOR SQL STEP")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    
    # Save cleaned transactions
    df_sql = df_cleaned.copy()
    df_sql['InvoiceDate'] = df_sql['InvoiceDate'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df_sql.to_sql("retail_transactions", conn, if_exists="replace", index=False)
    
    # Save Python RFM results for direct SQL cross-verification
    rfm_ref = rfm.reset_index().rename(columns={'index': 'CustomerID'})
    rfm_ref.to_sql("rfm_python_reference", conn, if_exists="replace", index=False)
    
    conn.commit()
    conn.close()
    print(f"SQLite database created at: {db_path}")


def run_pipeline():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_csv = os.path.join(base_dir, "data", "online_retail_raw.csv")
    cleaned_csv = os.path.join(base_dir, "data", "online_retail_cleaned.csv")
    rfm_csv = os.path.join(base_dir, "data", "rfm_results.csv")
    powerbi_csv = os.path.join(base_dir, "powerbi", "rfm_segments.csv")
    refunds_csv = os.path.join(base_dir, "data", "refunds_report.csv")
    docs_img_dir = os.path.join(base_dir, "docs", "images")
    pbi_img_dir = os.path.join(base_dir, "powerbi", "images")
    db_path = os.path.join(base_dir, "data", "retail_rfm.db")
    
    # Ensure all target directories exist
    os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "powerbi"), exist_ok=True)
    os.makedirs(docs_img_dir, exist_ok=True)
    os.makedirs(pbi_img_dir, exist_ok=True)
    os.makedirs(os.path.join(base_dir, "validation"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "docs"), exist_ok=True)
    
    # 1. Clean data
    df_cleaned = load_and_clean_data(raw_csv)
    df_cleaned.to_csv(cleaned_csv, index=False)
    
    # 2. Refunds
    df_purchases, df_refunds, cust_summary = process_refunds(df_cleaned)
    df_refunds.to_csv(refunds_csv, index=False)
    
    # 3. RFM
    rfm, snapshot_date = compute_rfm_metrics(df_cleaned, cust_summary)
    
    # 4. Scoring
    rfm_scored = score_rfm_quintiles(rfm)
    
    # Export RFM results
    rfm_export = rfm_scored.reset_index().rename(columns={'index': 'CustomerID'})
    rfm_export.to_csv(rfm_csv, index=False)
    rfm_export.to_csv(powerbi_csv, index=False)
    print(f"\nExported RFM results to:")
    print(f"  - {rfm_csv}")
    print(f"  - {powerbi_csv}")
    
    # 5. Visualizations
    generate_visualizations(rfm_scored, docs_img_dir)
    generate_visualizations(rfm_scored, pbi_img_dir)
    
    # 6. SQLite DB setup for Step 2 SQL execution
    populate_sqlite_database(db_path, df_cleaned, rfm_scored)
    
    print("\n" + "=" * 60)
    print("PYTHON PIPELINE EXECUTION COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    run_pipeline()
