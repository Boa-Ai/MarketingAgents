# Marketing Agents - Boa AI

Autonomous agents for marketing tasks with Google Sheets integration.

## Setup

### 1. Install Dependencies

```bash
# Already done:
npm install googleapis
```

### 2. Configure Environment

Your `.env` file should have:
```bash
BRAVE_API_KEY=...
OPENCLAW_MODEL=ollama/qwen3:8b   # optional, enforced at startup if set
OPENCLAW_TIMEOUT_SECONDS=1200    # optional; default 1200
OPENCLAW_THINKING=minimal        # optional; off|minimal|low|medium|high
OPENCLAW_MAX_ATTEMPTS=2          # optional; retry count if append not confirmed
SPREADSHEET_ID=your_spreadsheet_id_here  # optional
```

### 3. (Optional) Use Local Ollama + Qwen

If you want local inference instead of Anthropic:

```bash
ollama pull qwen3:8b
openclaw models set ollama/qwen3:8b
openclaw models status --plain
```

You can also pin the model for this project by setting:

```bash
OPENCLAW_MODEL=ollama/qwen3:8b
```

### 4. Add Service Account Key

**Required:** Place the Google Cloud service account JSON key here:
```
~/Boa-Ai/MarketingAgents/service-account-key.json
```

**Service Account Email:**
```
openclaw-agent@operating-tiger-456700-d6.iam.gserviceaccount.com
```

If you don't have this file:
1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Find the service account above
3. Click "Keys" → "Add Key" → "Create new key" → JSON
4. Save it as `service-account-key.json` in this directory

### 5. Share Your Spreadsheet

Share your Google Spreadsheet with the service account email (give it **Editor** permissions).

## Usage

### Spawn Agent to Read/Write Spreadsheet

```bash
# Pass spreadsheet ID directly
python main.py spreadsheet_agent YOUR_SPREADSHEET_ID

# Or set SPREADSHEET_ID in .env and run:
python main.py spreadsheet_agent
```

The agent will:
1. ✅ Launch 3 spreadsheet-agent workers in parallel
2. ✅ Each worker finds one new startup (fintech/healthtech/insurtech)
3. ✅ Each worker enriches contact info in the same run
4. ✅ Each worker appends one full row (A:N)
5. ✅ Each run saves raw agent output logs to `logs/`

### Manual Spreadsheet Operations

You can also use the helper script directly:

```bash
# Read entire sheet
node google-sheets-helper.js read SPREADSHEET_ID

# Read specific range
node google-sheets-helper.js read SPREADSHEET_ID 'Sheet1!A1:C10'

# Write to specific cells
node google-sheets-helper.js write SPREADSHEET_ID 'A1:C1' '[["Name", "Email", "Status"]]'

# Append rows to the bottom
node google-sheets-helper.js append SPREADSHEET_ID 'Sheet1' '[["John", "john@example.com", "Active"]]'
```

## Files

- **main.py** - Root launcher
- **spreadsheet_agent/run.py** - Unified startup + contact agent runner
- **spreadsheet_agent/directions.md** - Unified instructions read by the agent
- **google-sheets-helper.js** - CLI tool for Google Sheets operations
- **.env** - Environment variables (API keys, config)
- **service-account-key.json** - (you need to add this) Google Cloud credentials

## How It Works

The Python script spawns an OpenClaw agent in an isolated session. The agent:
- Has access to the `google-sheets-helper.js` CLI tool
- Executes commands to read/write sheets
- Makes autonomous decisions about what data to add
- Reports back what it did

## Next Steps

Once you've verified it works with the "hello world" test, you can modify the agent's task to do real marketing work:
- Scrape lead data and populate sheets
- Read contact lists and generate outreach campaigns
- Update status columns based on email responses
- Analyze sheet data and generate reports

---

**Need help?** See `SPREADSHEET_SETUP.md` for detailed setup instructions.
