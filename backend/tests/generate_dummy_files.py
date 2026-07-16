import os
import pandas as pd
import json

def generate():
    # Buat direktori dummy_data di folder tests
    target_dir = os.path.join(os.path.dirname(__file__), "dummy_data")
    os.makedirs(target_dir, exist_ok=True)
    
    # 1. Firewall log (CSV)
    firewall_data = {
        "tanggal": ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05", "2026-07-06", "2026-07-07"],
        "blocked_traffic": [1200, 1500, 950, 2100, 1800, 1300, 2400]
    }
    csv_path = os.path.join(target_dir, "firewall_data.csv")
    pd.DataFrame(firewall_data).to_csv(csv_path, index=False)
    print(f"Created: {csv_path}")
    
    # 2. Email Security (JSON)
    email_data = [
        {"bulan": "Januari", "phishing_detected": 15, "spam_detected": 140},
        {"bulan": "Februari", "phishing_detected": 22, "spam_detected": 185},
        {"bulan": "Maret", "phishing_detected": 12, "spam_detected": 160},
        {"bulan": "April", "phishing_detected": 35, "spam_detected": 210},
        {"bulan": "Mei", "phishing_detected": 28, "spam_detected": 195},
        {"bulan": "Juni", "phishing_detected": 40, "spam_detected": 240}
    ]
    json_path = os.path.join(target_dir, "email_data.json")
    with open(json_path, "w") as f:
        json.dump(email_data, f, indent=2)
    print(f"Created: {json_path}")
        
    # 3. VAPT Temuan (Excel)
    vapt_data = {
        "severity": ["Critical", "High", "Medium", "Low", "Informational"],
        "jumlah_temuan": [3, 12, 28, 45, 60]
    }
    xlsx_path = os.path.join(target_dir, "vapt_data.xlsx")
    pd.DataFrame(vapt_data).to_excel(xlsx_path, index=False)
    print(f"Created: {xlsx_path}")

if __name__ == "__main__":
    generate()
