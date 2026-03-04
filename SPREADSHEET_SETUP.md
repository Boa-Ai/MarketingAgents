# Google Sheets Agent Setup

## Quick Start

You're ready to spawn agents that can read/write Google Sheets! Just need one more file:

## 1. Add Service Account Key

You need the JSON key file for the service account:
- `openclaw-agent@operating-tiger-456700-d6.iam.gserviceaccount.com`

Place it at: `~/Boa-Ai/MarketingAgents/service-account-key.json`

If you don't have this file yet, download it from Google Cloud Console:
1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Find the service account `openclaw-agent@...`
3. Click "Keys" → "Add Key" → "Create new key" → JSON
4. Save as `service-account-key.json` in the workspace

## 2. Share Your Spreadsheet

Share your Google Spreadsheet with:
```
openclaw-agent@operating-tiger-456700-d6.iam.gserviceaccount.com
```
(Give it **Editor** permissions)

## 3. Run the Agent

```bash
# Method 1: Pass spreadsheet ID as argument
python main.py spreadsheet_agent YOUR_SPREADSHEET_ID

# Method 2: Set in .env
echo 'SPREADSHEET_ID=YOUR_SPREADSHEET_ID' >> .env
python main.py spreadsheet_agent
```

The agent will:
1. Launch 3 spreadsheet workers in parallel
2. Each worker finds one startup and its decision-maker contact details
3. Each worker appends one full enriched row (A:N) in a single run
4. Each run writes raw session logs under `logs/`

## Files Created

- **google-sheets-helper.js** - Node.js CLI for reading/writing sheets
- **spreadsheet_agent/run.py** - Spreadsheet discovery/append agent
- **SPREADSHEET_SETUP.md** - This file

## Example

```bash
# Get your spreadsheet ID from the URL:
# https://docs.google.com/spreadsheets/d/1ABC123xyz/edit
# ID = 1ABC123xyz

python main.py spreadsheet_agent 1ABC123xyz
```

The agent will autonomously:
- Call `node google-sheets-helper.js read 1ABC123xyz`
- Find a new startup and contact details
- Append a full enriched row to the sheet
- Report success

---

**Need help?** The agent understands the helper script and can use it flexibly. Just describe what you want done with the spreadsheet!
