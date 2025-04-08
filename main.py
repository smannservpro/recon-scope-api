from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import os
import json

app = Flask(__name__)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
credentials_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)

client = gspread.authorize(creds)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1_ZUG0tYgooafAtuXjZSVdt3XMFUHail67ts5Wy31A_U"
sheet = client.open_by_url(SHEET_URL)
worksheet = sheet.worksheet("Data Pull")
rows = worksheet.get_all_records()

data = []
for row in rows:
    if row["Category"] and row["Selection"] and row["Description"] and row["Unit"]:
        description_clean = re.sub(r'[^a-z0-9\s]', '', str(row["Description"]).lower().replace('"', '').replace("'", ''))
        data.append({
            "category": str(row["Category"]).strip().lower(),
            "selection": str(row["Selection"]).strip().lower(),
            "description": str(row["Description"]).strip(),
            "unit": str(row["Unit"]).strip(),
            "description_clean": description_clean
        })

# Typical related item keywords
related_keywords = {
    "sink": ["p-trap", "supply line", "stop valve"],
    "cabinet": ["toe kick"],
    "ceiling": ["register", "light fixture", "junction box"],
    "wall": ["insulation"],
    "floor": ["floor sample", "floor prep"]
}

@app.route("/scope", methods=["POST"])
def scope():
    req = request.get_json()
    user_input = req.get("input", "").lower()
    quantity = req.get("quantity", "1")
    action = req.get("action", "+")

    # Normalize user input
    user_input_clean = re.sub(r'[^a-z0-9\s]', '', user_input)
    user_keywords = user_input_clean.lower().split()

    normalized_keywords = []
    for kw in user_keywords:
        if kw in {"base", "baseboard", "trim"}:
            normalized_keywords.append("baseboard")
        elif kw in {"3.25", "3 1/4", "three and a quarter", "3-1/4", "three-quarter"}:
            normalized_keywords.append("3 1/4")
        else:
            normalized_keywords.append(kw)

    matches = [
        row for row in data
        if any(kw in row["description_clean"] for kw in normalized_keywords)
    ]

    if not matches:
        return jsonify({
            "matched_scope_item": "I couldn’t find a matching line item in the Xactimate master sheet. Please clarify the material, size, or description.",
            "related_items": []
        })

    if len(matches) > 1:
        options = matches[:5]
        return jsonify({
            "matched_scope_item": "Multiple matches found. Please clarify material, size, or description. Top 5 possible matches:",
            "related_items": [
                f"({action}) {m['category'].upper()} {m['selection'].upper()} – {m['description']} – {quantity} {m['unit'].upper()}"
                for m in options
            ]
        })

    match = matches[0]
    matched_line = f"({action}) {match['category'].upper()} {match['selection'].upper()} – {match['description']} – {quantity} {match['unit'].upper()}"

    keyword = user_input.split()[0]
    related = []
    for kw in related_keywords.get(keyword, []):
        related += [
            f"(+) {r['category'].upper()} {r['selection'].upper()} – {r['description']} – 1 {r['unit'].upper()}"
            for r in data if kw in r["description_clean"]
        ]
    related = related[:5]

    return jsonify({
        "matched_scope_item": matched_line,
        "related_items": related
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
