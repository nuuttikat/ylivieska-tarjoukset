/**
 * Ylivieskan tarjoukset: email price alerts.
 *
 * Runs as a Google Apps Script web app inside a Google Sheet owned by the page's maintainer.
 * - The page POSTs {email, q, max}. A new alert stays "pending" until its owner clicks the
 *   confirmation link we email them, so nobody can sign someone else up for alerts.
 * - checkAlerts() (daily trigger) reads the published offers and emails each confirmed alert's
 *   new matches once. Every email has links to stop one alert or all of them.
 * Emails and alerts live only in this Sheet, never in the public repository.
 *
 * Setup: see README.md, section "Setting up the email alerts".
 */
const PAGE = 'https://nuuttikat.github.io/ylivieska-tarjoukset/';
const DATA_URL = PAGE + 'offers.json';
const MAX_ALERTS_PER_EMAIL = 15;   // active + pending
const MAX_NEW_PER_EMAIL_PER_DAY = 5;
const MAX_NEW_TOTAL_PER_DAY = 30;   // confirmation emails per day, for everyone together
const QUOTA_RESERVE = 50;           // keep this much of Google's daily email quota for the alert emails
const PENDING_DAYS = 3;             // an unconfirmed alert's link stops working after this
const ALERT_COLS = ['id', 'email', 'q', 'max', 'status', 'token', 'created', 'confirmed'];

function setup() {
  sheet_('alerts', ALERT_COLS);
  sheet_('sent', ['alertId', 'offerKey', 'sentAt']);
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('checkAlerts').timeBased().everyDays(1).atHour(7).inTimezone('Europe/Helsinki').create();
}

// Works both as a standalone script (creates its own "Hintavahdit" Sheet) and inside a Sheet.
function ss_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('SHEET_ID');
  if (id) return SpreadsheetApp.openById(id);
  const ss = SpreadsheetApp.getActive() || SpreadsheetApp.create('Hintavahdit');
  props.setProperty('SHEET_ID', ss.getId());
  return ss;
}

function sheet_(name, header) {
  const ss = ss_();
  let sh = ss.getSheetByName(name);
  if (!sh) { sh = ss.insertSheet(name); sh.appendRow(header); }
  return sh;
}

function rows_() {
  const sh = sheet_('alerts', ALERT_COLS);
  const values = sh.getDataRange().getValues();
  return values.slice(1).map((r, i) => ({row: i + 2, id: r[0], email: String(r[1]), q: String(r[2]), max: r[3] === '' ? null : Number(r[3]),
                                        status: r[4], token: r[5], created: r[6] ? new Date(r[6]) : null}));
}

function norm_(s) {
  return String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');
}

function matches_(a, o) {
  const words = norm_(a.q).split(/\s+/).filter(Boolean);
  const text = norm_(o[2] + ' ' + o[0]);
  return words.length > 0 && words.every(w => text.indexOf(w) >= 0) && (!a.max || (o[3] && o[3] <= a.max));
}

function eur_(x) { return x.toFixed(2).replace('.', ',') + ' €'; }

function esc_(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const p = (e && e.parameter) || {};
    const email = String(p.email || '').trim().toLowerCase();
    // Product words only: letters, digits and a little punctuation. This keeps links, addresses and
    // spreadsheet formulas (=..., +..., @...) out of the Sheet and out of the confirmation email,
    // so nobody can use the form to send their own message to someone else.
    const q = String(p.q || '').replace(/\s+/g, ' ').trim().slice(0, 60);
    if (!/^[\p{L}\p{N}][\p{L}\p{N} .,%/()-]*$/u.test(q) || /https?|www|\.[a-z]{2,}\b/i.test(q)) return json_({ok: false, error: 'q'});
    const max = p.max ? Math.round(Number(String(p.max).replace(',', '.')) * 100) / 100 : null;
    if (!/^[a-z0-9][a-z0-9._%+-]*@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$/.test(email) || email.length > 120) return json_({ok: false, error: 'email'});
    if (q.length < 2) return json_({ok: false, error: 'q'});
    if (max !== null && !(max > 0 && max < 100000)) return json_({ok: false, error: 'max'});
    const all = rows_();
    const dayAgo = Date.now() - 24 * 3600 * 1000;
    const mine = all.filter(r => r.email === email && r.status !== 'stopped');
    if (mine.length >= MAX_ALERTS_PER_EMAIL) return json_({ok: false, error: 'limit'});
    if (all.filter(r => r.email === email && r.created && r.created.getTime() > dayAgo).length >= MAX_NEW_PER_EMAIL_PER_DAY) return json_({ok: false, error: 'limit'});
    if (all.filter(r => r.created && r.created.getTime() > dayAgo).length >= MAX_NEW_TOTAL_PER_DAY) return json_({ok: false, error: 'busy'});
    if (MailApp.getRemainingDailyQuota() < QUOTA_RESERVE) return json_({ok: false, error: 'busy'});
    const token = Utilities.getUuid();
    const id = Utilities.getUuid().slice(0, 8);
    sheet_('alerts', ALERT_COLS).appendRow([id, email, q, max === null ? '' : max, 'pending', token, new Date(), '']);
    const url = ScriptApp.getService().getUrl();
    MailApp.sendEmail({
      to: email,
      subject: 'Vahvista hintavahti: ' + q,
      body: 'Joku (toivottavasti sinä) lisäsi hintavahdin Ylivieskan tarjoukset -sivulla:\n\n  ' + q + (max ? ' alle ' + eur_(max) : '') +
            '\n\nVahvista vahti tästä:\n' + url + '?a=confirm&t=' + token +
            '\n\nJos et lisännyt vahtia, älä tee mitään. Ilman vahvistusta et saa viestejä.\n\n' + PAGE,
      name: 'Ylivieskan tarjoukset'
    });
    return json_({ok: true});
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  const p = (e && e.parameter) || {};
  const sh = sheet_('alerts', ALERT_COLS);
  const all = rows_();
  const hit = all.find(r => p.t && r.token === p.t);
  let msg = 'Linkki ei ole voimassa.';
  const fresh = hit && hit.created && Date.now() - hit.created.getTime() < PENDING_DAYS * 24 * 3600 * 1000;
  if (hit && p.a === 'confirm' && (hit.status === 'active' || (hit.status === 'pending' && fresh))) {
    sh.getRange(hit.row, 5).setValue('active');
    sh.getRange(hit.row, 8).setValue(new Date());
    msg = 'Hintavahti "' + hit.q + '" on nyt päällä. Saat sähköpostia, kun sopiva tarjous löytyy.';
  } else if (hit && p.a === 'stop') {
    sh.getRange(hit.row, 5).setValue('stopped');
    msg = 'Hintavahti "' + hit.q + '" on poistettu.';
  } else if (hit && p.a === 'stopall') {
    all.filter(r => r.email === hit.email).forEach(r => sh.getRange(r.row, 5).setValue('stopped'));
    msg = 'Kaikki hintavahtisi on poistettu.';
  }
  return HtmlService.createHtmlOutput('<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<div style="font:16px/1.5 system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 16px">' +
    '<h1 style="font-size:1.4rem">Ylivieskan tarjoukset</h1><p>' + esc_(msg) + '</p>' +
    '<p><a href="' + PAGE + '">Takaisin tarjouksiin</a></p></div>').setTitle('Hintavahti');
}

function checkAlerts() {
  const data = JSON.parse(UrlFetchApp.fetch(DATA_URL, {muteHttpExceptions: false}).getContentText());
  const offers = data.offers || [];
  const alerts = rows_().filter(r => r.status === 'active');
  const sentSh = sheet_('sent', ['alertId', 'offerKey', 'sentAt']);
  const sent = new Set(sentSh.getDataRange().getValues().slice(1).map(r => r[0] + '|' + r[1]));
  const url = ScriptApp.getService().getUrl();
  const byEmail = {};
  alerts.forEach(a => {
    offers.forEach(o => {
      if (!matches_(a, o)) return;
      const key = [o[0], o[2], o[3], o[8]].join('|');
      if (sent.has(a.id + '|' + key)) return;
      (byEmail[a.email] = byEmail[a.email] || []).push({a: a, o: o, key: key});
    });
  });
  Object.keys(byEmail).forEach(email => {
    if (MailApp.getRemainingDailyQuota() < 1) return;  // the rest are sent on the next run
    const items = byEmail[email];
    const lines = items.slice(0, 40).map(x => '- ' + x.o[0] + ': ' + x.o[2] + ' ' + eur_(x.o[3]) +
      (x.o[5] ? ' (ennen ' + eur_(x.o[5]) + ')' : '') + (x.o[8] ? ', ' + x.o[8] : '') + '\n  ' + (x.o[9] || PAGE));
    const stops = {};
    items.forEach(x => stops[x.a.id] = x.a);
    const stopLines = Object.keys(stops).map(id => 'Poista vahti "' + stops[id].q + '": ' + url + '?a=stop&t=' + stops[id].token);
    MailApp.sendEmail({
      to: email,
      subject: 'Hintavahti: ' + items.length + ' uutta tarjousta',
      body: 'Hintavahtisi löysivät uusia tarjouksia:\n\n' + lines.join('\n') + (items.length > 40 ? '\n...ja ' + (items.length - 40) + ' muuta.' : '') +
            '\n\nKaikki tarjoukset: ' + PAGE + '\n\n' + stopLines.join('\n') +
            '\nPoista kaikki vahtisi: ' + url + '?a=stopall&t=' + items[0].a.token + '\n',
      name: 'Ylivieskan tarjoukset'
    });
    const now = new Date();
    sentSh.getRange(sentSh.getLastRow() + 1, 1, items.length, 3).setValues(items.map(x => [x.a.id, x.key, now]));
  });
}
