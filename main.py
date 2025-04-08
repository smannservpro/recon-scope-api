from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

app = Flask(__name__)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import os
import json
from oauth2client.service_account import ServiceAccountCredentials

# Load JSON credentials from environment variable
creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
credentials_dict = json.loads(creds_json)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
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
            "category": row["Category"].strip().lower(),
            "selection": row["Selection"].strip().lower(),
            "description": row["Description"].strip(),
            "unit": row["Unit"].strip(),
            "description_clean": re.sub(r'[^\w\s]', '', row["Description"].lower())
        })

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
        return jsonify({
            "matched_scope_item": "Multiple matches:\n" + "\n".join(
                [f"{m['category']} {m['selection']}: {m['description']}" for m in matches]
            ),
            "related_items": []
        })

    match = matches[0]
    matched = f"({action}) {match['category'].upper()} {match['selection'].upper()} – {match['description']} – {quantity} {match['unit'].upper()}"

    related = []
    for keyword in related_keywords.get(user_input.split()[0], []):
        related += [
            f"{r['category'].upper()} {r['selection'].upper()} – {r['description']} ({r['unit']})"
            for r in data if keyword in r["description_clean"]
        ]

    return jsonify({
        "matched_scope_item": matched,
        "related_items": related
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
