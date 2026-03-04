Read the Google Spreadsheet with ID: {{SPREADSHEET_ID}}.

You are in a NON-INTERACTIVE batch run.
- Do NOT ask clarifying questions.
- Do NOT propose options.
- Execute the task fully now.

Task:
Find one startup in fintech, healthtech, or insurtech that is not already listed in the sheet,
enrich it with contact data, append it, then confirm.

Required steps:
1. Read the current data:
   node google-sheets-helper.js read {{SPREADSHEET_ID}}
2. Extract existing company names to avoid duplicates.
3. Research one new startup (fintech/healthtech/insurtech only; no security companies).
4. Find one strong decision-maker contact (prefer CEO/founder).
5. Build one full row in this exact column order:
   - A Company Name
   - B Website
   - C Vertical
   - D Contact Name
   - E Title
   - F Email
   - G LinkedIn
   - H Company Stage
   - I Recent Funding
   - J Outreach Status = "Not Contacted"
   - K First Contact = ""
   - L Last Contact = ""
   - M Priority = Low/Medium/High
   - N Notes
6. If a field cannot be verified, leave it blank (do not invent).
7. Append exactly one row to `Sheet1` using REAL values from your research (never use literal placeholders like "Company" or "https://company.com"):
   node google-sheets-helper.js append {{SPREADSHEET_ID}} 'Sheet1' '["<Company Name>","<Website>","<Vertical>","<Contact Name>","<Title>","<Email>","<LinkedIn>","<Company Stage>","<Recent Funding>","Not Contacted","","","<Priority>","<Notes>"]'
8. Re-read the sheet to verify the append:
   node google-sheets-helper.js read {{SPREADSHEET_ID}}

Final response format (required):
STATUS: APPEND_CONFIRMED
COMPANY: <company name>
ROW_JSON: <single JSON array with exactly 14 fields in A:N order>

If append fails, return:
STATUS: APPEND_FAILED
REASON: <short reason>
