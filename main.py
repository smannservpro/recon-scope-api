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
        data.append({
            "category": str(row["Category"]).strip().lower(),
            "selection": str(row["Selection"]).strip().lower(),
            "description": str(row["Description"]).strip(),
            "unit": str(row["Unit"]).strip(),
            "description_clean": re.sub(r'[^\w\s]', '', str(row["Description"]).lower())
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

    words = re.sub(r"[^\w\s]", "", user_input).split()
    matches = [row for row in data if any(word in row["description_clean"] for word in words)]

    if not matches:
        return jsonify({
            "matched_scope_item": "I couldn’t find a matching line item in the Xactimate master sheet. Please clarify the material, size, or description.",
            "related_items": []
        })

    if len(matches) > 1:
        options = matches[:5]  # Limit to top 5 matches
        return jsonify({
            "matched_scope_item": "Multiple matches found. Please clarify material, size, or description. Top 5 possible matches:",
            "related_items": [
                f"({action}) {m['category'].upper()} {m['selection'].upper()} – {m['description']} – {quantity} {m['unit'].upper()}"
                for m in options
            ]
        })

    match = matches[0]
    matched_line = f"({action}) {match['category'].upper()} {match['selection'].upper()} – {match['description']} – {quantity} {match['unit'].upper()}"

    # Related items — capped at 5 for safety
    keyword = user_input.split()[0]
    related = []
    for kw in related_keywords.get(keyword, []):
        related += [
            f"(+) {r['category'].upper()} {r['selection'].upper()} – {r['description']} – 1 {r['unit'].upper()}"
            for r in data if kw in r["description_clean"]
        ]
    related = related[:5]  # Limit to 5 suggestions

    return jsonify({
        "matched_scope_item": matched_line,
        "related_items": related
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
