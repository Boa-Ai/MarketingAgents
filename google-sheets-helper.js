#!/usr/bin/env node
/**
 * google-sheets-helper.js
 * Simple CLI for reading/writing Google Sheets via service account
 * Usage:
 *   node google-sheets-helper.js read <spreadsheetId> [range]
 *   node google-sheets-helper.js write <spreadsheetId> <range> <jsonData>
 *   node google-sheets-helper.js append <spreadsheetId> <range> <jsonData>
 */

const { google } = require('googleapis');
const fs = require('fs');
const path = require('path');

// Service account key path
const KEY_PATH = path.join(__dirname, 'service-account-key.json');

async function getAuthClient() {
  if (!fs.existsSync(KEY_PATH)) {
    throw new Error(`Service account key not found at: ${KEY_PATH}`);
  }
  
  const auth = new google.auth.GoogleAuth({
    keyFile: KEY_PATH,
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
  });
  
  return auth.getClient();
}

async function readSheet(spreadsheetId, range = 'Sheet1') {
  const auth = await getAuthClient();
  const sheets = google.sheets({ version: 'v4', auth });
  
  const response = await sheets.spreadsheets.values.get({
    spreadsheetId,
    range,
  });
  
  return response.data.values || [];
}

async function writeSheet(spreadsheetId, range, values) {
  const auth = await getAuthClient();
  const sheets = google.sheets({ version: 'v4', auth });
  
  await sheets.spreadsheets.values.update({
    spreadsheetId,
    range,
    valueInputOption: 'RAW',
    resource: { values },
  });
}

async function appendSheet(spreadsheetId, range, values) {
  const auth = await getAuthClient();
  const sheets = google.sheets({ version: 'v4', auth });
  
  const response = await sheets.spreadsheets.values.append({
    spreadsheetId,
    range,
    valueInputOption: 'RAW',
    insertDataOption: 'INSERT_ROWS',
    resource: { values },
  });

  return response.data || {};
}

function normalizeRows(values, action) {
  if (!Array.isArray(values)) {
    throw new Error(`${action} jsonData must be a JSON array`);
  }
  if (values.length === 0) {
    return [];
  }

  // Accept either:
  // - 2D rows: [[...], [...]]
  // - single row: [...]
  if (Array.isArray(values[0])) {
    return values;
  }
  return [values];
}

async function main() {
  const args = process.argv.slice(2);
  
  if (args.length < 2) {
    console.error('Usage:');
    console.error('  read <spreadsheetId> [range]');
    console.error('  write <spreadsheetId> <range> <jsonData>');
    console.error('  append <spreadsheetId> <range> <jsonData>');
    process.exit(1);
  }
  
  const [action, spreadsheetId, ...rest] = args;
  
  try {
    switch (action) {
      case 'read': {
        const range = rest[0] || 'Sheet1';
        const data = await readSheet(spreadsheetId, range);
        console.log(JSON.stringify(data, null, 2));
        break;
      }
      
      case 'write': {
        const range = rest[0];
        const jsonData = rest[1];
        if (!range || !jsonData) {
          throw new Error('write requires <range> and <jsonData>');
        }
        const values = normalizeRows(JSON.parse(jsonData), 'write');
        await writeSheet(spreadsheetId, range, values);
        console.log('✓ Written to sheet');
        break;
      }
      
      case 'append': {
        const range = rest[0];
        const jsonData = rest[1];
        if (!range || !jsonData) {
          throw new Error('append requires <range> and <jsonData>');
        }
        const values = normalizeRows(JSON.parse(jsonData), 'append');
        const result = await appendSheet(spreadsheetId, range, values);
        const updates = result.updates || {};
        console.log(JSON.stringify({
          ok: true,
          updatedRange: updates.updatedRange || null,
          updatedRows: updates.updatedRows || null,
          updatedColumns: updates.updatedColumns || null,
          updatedCells: updates.updatedCells || null,
        }, null, 2));
        break;
      }
      
      default:
        throw new Error(`Unknown action: ${action}`);
    }
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

main();
