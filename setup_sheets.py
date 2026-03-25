#!/usr/bin/env python3
"""One-time setup: add headers to Google Sheet."""
import os, json

_env = os.path.expanduser("~/.alpaca/options-paper.env")
if os.path.exists(_env):
    for line in open(_env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_CREDENTIALS"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
service = build("sheets", "v4", credentials=creds, cache_discovery=False)

service.spreadsheets().values().update(
    spreadsheetId=os.environ["GOOGLE_SHEET_ID"],
    range="Sheet1!A1:F1",
    valueInputOption="USER_ENTERED",
    body={"values": [["Date", "Time", "Symbol", "Sentiment", "Score %", "Headline"]]}
).execute()

print("✅ Headers added to Google Sheet!")
