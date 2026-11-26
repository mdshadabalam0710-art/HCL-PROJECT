# Power BI Dashboard Build Guide: Customer Segmentation using RFM

This guide provides end-to-end, production-ready instructions for constructing an executive-level **Retail RFM Customer Segmentation Dashboard** in Microsoft Power BI.

---

## 1. Data Source & Preparation

1. Open **Power BI Desktop**.
2. Click **Get Data** -> **Text/CSV**.
3. Select `rfm-project/powerbi/rfm_segments.csv`.
4. Click **Transform Data** (Power Query Editor):
   - Ensure `CustomerID` is set to **Text**.
   - Ensure `Country` and `Segment` are set to **Text**.
   - Ensure `Recency`, `Frequency`, `Monetary`, `Gross_Purchases`, `Total_Refunds` are **Decimal Number** or **Whole Number**.
   - Ensure `R_Score`, `F_Score`, `M_Score` are **Whole Number**.
   - Ensure `Refund_Exceeds_Purchases` and `Net_Negative_Or_Zero` are **True/False**.
5. Click **Close & Apply**.
6. Create a dedicated **Measures Table**:
   - In Home tab, click **Enter Data**, name the table `_Measures`, and click Load.
   - Add all DAX measures from [`dax_measures.dax`](dax_measures.dax) into `_Measures`.

---

## 2. Palette & Visual Identity

To maintain consistency with the Python visualization output, apply the exact color mapping below for data segments:

| Segment | Hex Code | Purpose / Tone |
| :--- | :--- | :--- |
| **Champions** | `#2ECC71` | High vitality green |
| **Loyal** | `#27AE60` | Deep emerald green |
| **Potential Loyalists** | `#3498DB` | High engagement blue |
| **New Customers** | `#1ABC9C` | Teal freshness |
| **Promising** | `#9B59B6` | Royal purple |
| **Need Attention** | `#F39C12` | Warning amber |
| **At Risk** | `#E67E22` | Caution deep orange |
| **Can't Lose Them** | `#E74C3C` | Urgent crimson red |
| **Hibernating** | `#95A5A6` | Cool grey |
| **Lost** | `#7F8C8D` | Churned charcoal |

- **Canvas Background**: `#F8F9FA` (Soft modern grey)
- **Card Background**: `#FFFFFF` with 2px corner radius and subtle drop shadow (`#00000010`)
- **Primary Font**: `Segoe UI` or `Segoe UI Semibold`

---

## 3. Dashboard Layout & Grid Structure (16:9 Canvas)

Canvas Dimensions: **1280 x 720 px** (or 1920 x 1080 px scaled).

```
+---------------------------------------------------------------------------------------------------+
|  HEADER: Retail RFM Customer Segmentation Dashboard                 [ Country Slicer: All ▼ ]     |
+---------------------------------------------------------------------------------------------------+
|  [ Total Customers ]  [ Total Net Revenue ]  [ Avg Recency ]  [ Avg Frequency ]  [ Avg Monetary ] |
|       2,003                $367,871             127.5 days       4.5 orders          $183.66      |
+---------------------------------------------------+-----------------------------------------------+
|  VISUAL 1: Segment Breakdown (Treemap / Bar)       |  VISUAL 2: Net Revenue Contribution by Segment|
|  - Champions (24.1%)                              |  - Champions ($233K, 63.4%)                   |
|  - Loyal (19.3%)                                  |  - Loyal ($59K, 16.1%)                        |
|  - Hibernating (17.4%)                            |  - Potential Loyalists ($31K, 8.5%)           |
+---------------------------------------------------+-----------------------------------------------+
|  VISUAL 3: Customer Scatter (Frequency vs Monetary)|  VISUAL 4: Customer Drilldown Table          |
|  - X: Frequency (Orders)                          |  - Columns: CustomerID, Country, RFM_Score,   |
|  - Y: Monetary ($ Net Spend)                      |    Recency, Frequency, Monetary, Segment      |
|  - Legend: Segment                                |  - Conditional Formatting on Segment & Spend  |
+---------------------------------------------------------------------------------------------------+
```

---

## 4. Visual-by-Visual Configuration

### Visual A: Country Slicer (Top Right)
- **Visual Type**: Slicer
- **Field**: `rfm_segments[Country]`
- **Slicer Settings**: Dropdown (Single or Multi-select with "Select All" enabled).
- **Position**: `X=980, Y=20, W=260, H=45`

---

### Visual B: Executive KPI Cards (Row 1)
Create 5 Single Card Visuals across `Y=80, H=90`:

1. **Card 1: Total Customers**
   - **Measure**: `[Total Customers]`
   - **Callout Value**: 28pt, Bold, Color `#2C3E50`
   - **Category Label**: 10pt, "Active Customers"
   - **Position**: `X=40, Y=80, W=220, H=90`

2. **Card 2: Total Revenue**
   - **Measure**: `[Total Revenue]`
   - **Display Units**: Auto (e.g. `$368K`)
   - **Position**: `X=285, Y=80, W=220, H=90`

3. **Card 3: Avg Recency**
   - **Measure**: `[Avg Recency]`
   - **Value Format**: `0.0 "days"`
   - **Position**: `X=530, Y=80, W=220, H=90`

4. **Card 4: Avg Frequency**
   - **Measure**: `[Avg Frequency]`
   - **Value Format**: `0.0 "orders"`
   - **Position**: `X=775, Y=80, W=220, H=90`

5. **Card 5: Avg Monetary**
   - **Measure**: `[Avg Monetary]`
   - **Value Format**: `"$#,##0"`
   - **Position**: `X=1020, Y=80, W=220, H=90`

---

### Visual C: Segment Size Distribution (Treemap or Horizontal Bar)
- **Visual Type**: Treemap (or Horizontal Clustered Bar Chart)
- **Category**: `rfm_segments[Segment]`
- **Values**: `[Total Customers]`
- **Tooltips**: `[% of Customers by Segment]`, `[Total Revenue]`, `[Avg Monetary]`
- **Data Colors**: Apply segment hex colors defined in Section 2.
- **Data Labels**: On (display Count and `% of Total`).
- **Position**: `X=40, Y=190, W=580, H=240`

---

### Visual D: Net Revenue by Segment (Clustered Column Chart)
- **Visual Type**: Clustered Column Chart
- **X-Axis**: `rfm_segments[Segment]` (Sorted descending by `[Total Revenue]`)
- **Y-Axis**: `[Total Revenue]`
- **Tooltips**: `[% of Revenue by Segment]`, `[Avg Monetary]`
- **Data Labels**: On (Display `$#,##0` and `%`).
- **Position**: `X=660, Y=190, W=580, H=240`

---

### Visual E: Customer Scatter Plot (Frequency vs Monetary)
- **Visual Type**: Scatter Chart
- **X-Axis**: `rfm_segments[Frequency]` (Min: 0, Max: Auto)
- **Y-Axis**: `rfm_segments[Monetary]` (Min: -50, Max: Auto)
- **Legend**: `rfm_segments[Segment]`
- **Values / Details**: `rfm_segments[CustomerID]`
- **Tooltips**: `rfm_segments[Country]`, `rfm_segments[Recency]`, `rfm_segments[RFM_Score]`
- **Position**: `X=40, Y=450, W=580, H=240`

---

### Visual F: Customer Drill-Down Table (Bottom Right)
- **Visual Type**: Table
- **Columns**:
  1. `CustomerID`
  2. `Country`
  3. `RFM_Score`
  4. `Recency`
  5. `Frequency`
  6. `Monetary`
  7. `Segment`
  8. `Refund_Exceeds_Purchases`
- **Formatting**:
  - Currency format on `Monetary` (`$#,##0.00`).
  - Conditional formatting on `Segment`: Background color based on Field Value (`Segment Color` measure) or custom rules.
  - Flag indicator on `Refund_Exceeds_Purchases` (Red warning icon if True).
- **Position**: `X=660, Y=450, W=580, H=240`

---

## 5. Cross-Filtering & Interaction Behavior

1. **Select Segment**: Clicking **Champions** in the Treemap highlights Champions across the Revenue bar, isolates Champions in the Scatter plot, and updates KPI cards to show Champion metrics ($233K revenue, 63.4% of total).
2. **Slicer Interaction**: Filtering by **Germany** or **France** updates customer counts and segment proportions dynamically via the `ALLSELECTED()` DAX context.
3. **Empty Segments Safety**: If a filtered country has 0 customers for a particular segment, `DIVIDE(..., ..., 0)` and `COALESCE` guard all cards and charts from showing `NaN` or `#ERROR`.
