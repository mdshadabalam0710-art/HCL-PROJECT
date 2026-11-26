"""
Dataset Generator for RFM Project
Generates a realistic synthetic Online Retail dataset mimicking the UCI Online Retail dataset structure:
Columns: InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country
Includes cancellations (starting with 'C' and negative Quantity), null CustomerIDs, duplicate rows,
single-purchase customers (ties in Frequency), refund-heavy customers (net negative monetary), and edge cases.
"""

import os
import random
import datetime
import numpy as np
import pandas as pd

def generate_synthetic_retail(output_csv_path, output_excel_path=None, num_records=25000, seed=42):
    random.seed(seed)
    np.random.seed(seed)

    products = [
        ("85123A", "WHITE HANGING HEART T-LIGHT HOLDER", 2.55),
        ("71053", "WHITE METAL LANTERN", 3.39),
        ("84406B", "CREAM CUPID HEARTS COAT HANGER", 2.75),
        ("84029G", "KNITTED UNION FLAG HOT WATER BOTTLE", 3.75),
        ("84029E", "RED WOOLLY HOTTIE WHITE HEART.", 3.75),
        ("22752", "SET 7 BABUSHKA NESTING BOXES", 8.50),
        ("21730", "GLASS STAR FROSTED T-LIGHT HOLDER", 4.25),
        ("22633", "HAND WARMER UNION JACK", 1.85),
        ("22632", "HAND WARMER RED POLKADOT", 1.85),
        ("84879", "ASSORTED COLOUR BIRD ORNAMENT", 1.69),
        ("22745", "POPPY'S PLAYHOUSE BEDROOM", 2.10),
        ("22748", "POPPY'S PLAYHOUSE KITCHEN", 2.10),
        ("22749", "POPPY'S PLAYHOUSE BATHROOM", 2.10),
        ("22310", "IVORY KNITTED MUG COSY", 1.65),
        ("84969", "BOX OF 6 ASSORTED COLOUR TEASPOONS", 4.25),
        ("20725", "LUNCH BAG RED RETROSPOT", 1.65),
        ("20727", "LUNCH BAG BLACK SKULL", 1.65),
        ("20728", "LUNCH BAG CARS BLUE", 1.65),
        ("22382", "LUNCH BAG SPACEBOY DESIGN", 1.65),
        ("22383", "LUNCH BAG SUKI DESIGN", 1.65),
        ("22384", "LUNCH BAG PINK POLKADOT", 1.65),
        ("20726", "LUNCH BAG WOODLAND", 1.65),
        ("22423", "REGENCY CAKESTAND 3 TIER", 12.75),
        ("22554", "PLASTERS IN TIN WOODLAND ANIMALS", 1.65),
        ("22556", "PLASTERS IN TIN CIRCUS PARADE", 1.65),
        ("22551", "PLASTERS IN TIN SPACEBOY", 1.65),
        ("22457", "NATURAL SLATE HEART CHALKBOARD", 2.95),
        ("22469", "HEART OF WICKER SMALL", 1.45),
        ("22470", "HEART OF WICKER LARGE", 2.55),
        ("21622", "VINTAGE UNION JACK CUSHION COVER", 4.95),
        ("21621", "VINTAGE UNION JACK DOORSTOP", 5.95),
        ("22197", "SMALL POPCORN HOLDER", 0.85),
        ("85099B", "JUMBO BAG RED RETROSPOT", 1.95),
        ("85099C", "JUMBO BAG STRAWBERRY", 1.95),
        ("85099F", "JUMBO BAG VINTAGE LEAF", 1.95),
        ("21931", "JUMBO STORAGE BAG SUKI", 1.95),
        ("22386", "JUMBO BAG PINK POLKADOT", 1.95),
        ("22960", "JAM MAKING SET WITH JARS", 3.75),
        ("22961", "JAM MAKING SET PRINTED", 1.45),
        ("47566", "PARTY BUNTING", 4.65)
    ]

    countries = [
        ("United Kingdom", 0.85),
        ("Germany", 0.04),
        ("France", 0.03),
        ("EIRE", 0.02),
        ("Spain", 0.015),
        ("Netherlands", 0.015),
        ("Belgium", 0.01),
        ("Switzerland", 0.008),
        ("Portugal", 0.006),
        ("Australia", 0.006)
    ]
    country_names = [c[0] for c in countries]
    country_probs = [c[1] for c in countries]

    start_date = datetime.datetime(2025, 1, 1, 8, 30)
    end_date = datetime.datetime(2025, 12, 9, 18, 0)
    date_range_seconds = int((end_date - start_date).total_seconds())

    # Create a customer base of ~2,000 customers
    # Segment definitions for synthetic generation to ensure realistic RFM spread:
    # 1. Loyal / Champions: 15% (freq 6-25, recency 1-45 days, higher quantities)
    # 2. Potential Loyalists / Promising: 20% (freq 3-8, recency 10-90 days)
    # 3. New Customers: 15% (freq 1-2, recency 1-30 days)
    # 4. Need Attention / At Risk: 20% (freq 3-10, recency 90-250 days)
    # 5. Hibernating / Lost: 25% (freq 1-3, recency 180-340 days)
    # 6. Edge cases:
    #    - Customer with negative net monetary (refunds > purchases)
    #    - Customer with zero net monetary (exact refund match)
    #    - High volume single purchase customers (ties in F=1)
    
    num_customers = 2000
    customer_ids = [10000 + i for i in range(num_customers)]
    customer_profiles = {}

    for cid in customer_ids:
        c_country = np.random.choice(country_names, p=country_probs)
        rand_type = random.random()
        if rand_type < 0.15:
            # Champion / Loyal
            prof = {"type": "champion", "invoices": random.randint(6, 20), "recency_window": (1, 40), "qty_mult": random.uniform(1.2, 3.0)}
        elif rand_type < 0.35:
            # Potential / Promising
            prof = {"type": "potential", "invoices": random.randint(3, 7), "recency_window": (15, 90), "qty_mult": random.uniform(0.8, 1.8)}
        elif rand_type < 0.50:
            # New Customers (recency 1-30 days, F = 1-2)
            prof = {"type": "new", "invoices": random.randint(1, 2), "recency_window": (1, 35), "qty_mult": random.uniform(0.8, 1.5)}
        elif rand_type < 0.70:
            # At Risk / Need Attention
            prof = {"type": "at_risk", "invoices": random.randint(2, 6), "recency_window": (90, 220), "qty_mult": random.uniform(0.8, 1.6)}
        else:
            # Hibernating / Lost (mostly F=1 or F=2, older recency)
            prof = {"type": "lost", "invoices": random.randint(1, 2), "recency_window": (180, 340), "qty_mult": random.uniform(0.5, 1.2)}
        prof["country"] = c_country
        customer_profiles[cid] = prof

    # Specific Edge Case Customers:
    # Edge case 1: Customer 19991 - Negative net monetary (Refund exceeds purchases)
    customer_profiles[19991] = {"type": "edge_negative_spend", "invoices": 2, "recency_window": (20, 60), "qty_mult": 1.0, "country": "United Kingdom"}
    # Edge case 2: Customer 19992 - Zero net monetary (Exact full refund of sole purchase)
    customer_profiles[19992] = {"type": "edge_zero_spend", "invoices": 1, "recency_window": (30, 45), "qty_mult": 1.0, "country": "United Kingdom"}
    # Edge case 3: Customer 19993 - Sole purchase of huge quantity (F=1, High M)
    customer_profiles[19993] = {"type": "edge_whale_single", "invoices": 1, "recency_window": (5, 15), "qty_mult": 25.0, "country": "Germany"}

    rows = []
    invoice_seq = 536365

    # Generate transactions per customer
    for cid, prof in customer_profiles.items():
        if prof["type"] == "edge_negative_spend":
            # 1 normal purchase: 2 items, total ~$20
            # 1 cancellation: -5 items, refund ~$50 -> net negative
            dt_base = end_date - datetime.timedelta(days=random.randint(40, 60))
            inv_no = str(invoice_seq)
            invoice_seq += 1
            rows.append({
                "InvoiceNo": inv_no, "StockCode": "22423", "Description": "REGENCY CAKESTAND 3 TIER",
                "Quantity": 2, "InvoiceDate": dt_base.strftime("%Y-%m-%d %H:%M:%S"),
                "UnitPrice": 12.75, "CustomerID": float(cid), "Country": prof["country"]
            })
            # Refund
            dt_cancel = dt_base + datetime.timedelta(days=5)
            rows.append({
                "InvoiceNo": f"C{invoice_seq}", "StockCode": "22423", "Description": "REGENCY CAKESTAND 3 TIER",
                "Quantity": -5, "InvoiceDate": dt_cancel.strftime("%Y-%m-%d %H:%M:%S"),
                "UnitPrice": 12.75, "CustomerID": float(cid), "Country": prof["country"]
            })
            invoice_seq += 1
            continue

        if prof["type"] == "edge_zero_spend":
            # 1 purchase, exactly 1 cancellation of same quantity
            dt_base = end_date - datetime.timedelta(days=35)
            inv_no = str(invoice_seq)
            invoice_seq += 1
            rows.append({
                "InvoiceNo": inv_no, "StockCode": "85123A", "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
                "Quantity": 10, "InvoiceDate": dt_base.strftime("%Y-%m-%d %H:%M:%S"),
                "UnitPrice": 2.55, "CustomerID": float(cid), "Country": prof["country"]
            })
            dt_cancel = dt_base + datetime.timedelta(days=2)
            rows.append({
                "InvoiceNo": f"C{invoice_seq}", "StockCode": "85123A", "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
                "Quantity": -10, "InvoiceDate": dt_cancel.strftime("%Y-%m-%d %H:%M:%S"),
                "UnitPrice": 2.55, "CustomerID": float(cid), "Country": prof["country"]
            })
            invoice_seq += 1
            continue

        # Standard customer invoice generation
        num_inv = prof["invoices"]
        min_rec, max_rec = prof["recency_window"]
        
        # Generate timestamps for invoices
        # Most recent purchase is within (min_rec, max_rec)
        last_dt = end_date - datetime.timedelta(days=random.randint(min_rec, max_rec), hours=random.randint(0, 10))
        dates = [last_dt]
        for _ in range(num_inv - 1):
            prior_offset_days = random.randint(10, 50)
            prior_dt = dates[-1] - datetime.timedelta(days=prior_offset_days, hours=random.randint(0, 8))
            if prior_dt < start_date:
                prior_dt = start_date + datetime.timedelta(days=random.randint(0, 30))
            dates.append(prior_dt)
        dates.sort()

        for inv_dt in dates:
            inv_no = str(invoice_seq)
            invoice_seq += 1
            # Each invoice has 1 to 6 line items
            num_items = random.choices([1, 2, 3, 4, 6], weights=[0.45, 0.25, 0.15, 0.1, 0.05])[0]
            chosen_prods = random.sample(products, num_items)
            
            for p_code, p_desc, p_price in chosen_prods:
                base_qty = random.choices([1, 2, 4, 6, 12, 24], weights=[0.35, 0.25, 0.15, 0.12, 0.08, 0.05])[0]
                qty = max(1, int(round(base_qty * prof["qty_mult"])))
                rows.append({
                    "InvoiceNo": inv_no,
                    "StockCode": p_code,
                    "Description": p_desc,
                    "Quantity": qty,
                    "InvoiceDate": inv_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "UnitPrice": p_price,
                    "CustomerID": float(cid),
                    "Country": prof["country"]
                })

            # ~4% chance of a subsequent cancellation/refund for this invoice
            if random.random() < 0.04:
                cancel_dt = inv_dt + datetime.timedelta(days=random.randint(1, 7), hours=random.randint(1, 4))
                if cancel_dt <= end_date:
                    canc_prod = random.choice(chosen_prods)
                    canc_qty = -random.randint(1, max(1, int(round(base_qty * prof["qty_mult"]))))
                    rows.append({
                        "InvoiceNo": f"C{invoice_seq}",
                        "StockCode": canc_prod[0],
                        "Description": canc_prod[1],
                        "Quantity": canc_qty,
                        "InvoiceDate": cancel_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "UnitPrice": canc_prod[2],
                        "CustomerID": float(cid),
                        "Country": prof["country"]
                    })
                    invoice_seq += 1

    # Add Guest Checkout / Null CustomerID records (~8% of total volume)
    num_guest_invoices = int(len(rows) * 0.08 / 2)
    for _ in range(num_guest_invoices):
        inv_no = str(invoice_seq)
        invoice_seq += 1
        guest_dt = start_date + datetime.timedelta(seconds=random.randint(0, date_range_seconds))
        guest_country = np.random.choice(country_names, p=country_probs)
        chosen_prods = random.sample(products, random.randint(1, 3))
        for p_code, p_desc, p_price in chosen_prods:
            qty = random.randint(1, 6)
            rows.append({
                "InvoiceNo": inv_no,
                "StockCode": p_code,
                "Description": p_desc if random.random() > 0.02 else None, # occasional null description
                "Quantity": qty,
                "InvoiceDate": guest_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "UnitPrice": p_price if random.random() > 0.01 else 0.0, # occasional 0 price
                "CustomerID": np.nan,
                "Country": guest_country
            })

    # Add duplicate rows (exact duplicates to test deduplication)
    duplicate_sample = random.sample(rows, min(50, len(rows)))
    rows.extend(duplicate_sample)

    df = pd.DataFrame(rows)
    # Shuffle slightly while keeping general chronological spread
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    df.sort_values(by="InvoiceDate", inplace=True)
    df.reset_index(drop=True, inplace=True)

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    df.to_csv(output_csv_path, index=False)
    print(f"Dataset generated successfully at: {output_csv_path}")
    print(f"Total Rows: {len(df):,}")
    print(f"Unique Invoices: {df['InvoiceNo'].nunique():,}")
    print(f"Unique Customers: {df['CustomerID'].dropna().nunique():,}")
    print(f"Null CustomerIDs: {df['CustomerID'].isna().sum():,}")
    cancellations = df[df['InvoiceNo'].str.startswith('C', na=False) | (df['Quantity'] < 0)]
    print(f"Cancellations / Refunds: {len(cancellations):,}")

    if output_excel_path:
        # Sample or full for excel if requested
        print(f"Saving Excel copy at {output_excel_path}...")
        df.head(10000).to_excel(output_excel_path, index=False)
        print("Excel copy saved.")

    return df

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_dest = os.path.join(base_dir, "data", "online_retail_raw.csv")
    csv_alias = os.path.join(base_dir, "data", "online_retail.csv")
    generate_synthetic_retail(csv_dest)
    # Also save as online_retail.csv for standard name compatibility
    import shutil
    shutil.copy(csv_dest, csv_alias)
