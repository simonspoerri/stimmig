// End-to-end walkthrough of all four components and three roles, in a real browser.
//
//   scripts/dev.sh &                                  # all components, replay mode
//   node scripts/walkthrough.mjs [screenshot-dir]
//
// Uses the synthetic example document whose model answer is recorded in
// services/pipeline/evals/recordings, so it needs no API key. Login codes are
// read from the identity service's development log. Run it against an empty
// pipeline database: the example vote id is fixed by the recording.
import { mkdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

// Playwright is not a dependency of the repo; use the one installed on the machine.
const { chromium } = createRequire(import.meta.url)('playwright');

const ADMIN = 'http://localhost:4321';
const WEB = 'http://localhost:4322';
const LOG = new URL('../.local/logs/identity.log', import.meta.url);
const shots = process.argv[2];
if (shots) mkdirSync(shots, { recursive: true });

const dataset = JSON.parse(
  readFileSync(new URL('../services/pipeline/evals/datasets/synthetic-smoke.json', import.meta.url), 'utf8'),
);
const item = dataset.items[0].input;
const VOTE = item.vote_id;

function lastCode(email) {
  const lines = readFileSync(LOG, 'utf8').trim().split('\n').reverse();
  for (const line of lines) {
    try {
      const entry = JSON.parse(line);
      if (entry.msg?.startsWith('login code') && entry.to === email) return entry.code;
    } catch {
      // not a JSON log line (tsx watch output)
    }
  }
  throw new Error(`no login code for ${email} in ${LOG.pathname}`);
}

const browser = await chromium.launch();
const errors = [];

async function as(role, steps) {
  const email = `${role}@stimmig.local`;
  const context = await browser.newContext({ locale: 'de-CH', viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(`${role}: ${e.message}`));
  await page.goto(ADMIN);
  await page.fill('input[name=email]', email);
  if (shots && role === 'admin') await page.screenshot({ path: `${shots}/1-login.png` });
  await page.click('button[type=submit]');
  await page.waitForSelector('input[name=code]');
  await page.fill('input[name=code]', lastCode(email));
  await page.click('button[type=submit]');
  await page.waitForURL(`${ADMIN}/**`);
  await steps(page);
  await context.close();
  console.log(`✓ ${role}`);
}

const shot = async (page, name) => shots && page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });

// 1. Admin: vote, source document, extraction.
await as('admin', async (page) => {
  await page.fill('#date', '2099-01-01');
  await page.fill('#id', VOTE);
  await page.fill('#title', 'Musterinitiative (synthetisches Beispiel)');
  await page.fill('#official_url', 'https://www.admin.ch/gov/de/start/dokumentation/abstimmungen.html');
  await page.click('text=Vorlage erfassen');
  await page.waitForURL(`**/votes/${VOTE}?ok=vote-created`);

  await page.selectOption('#side', item.side);
  await page.fill('#title', item.document_title);
  await page.fill('#url', 'https://example.org/abstimmungsbuechlein');
  await page.fill('#locator', 'S. 12');
  await page.fill('#text', item.text);
  await page.click('button:has-text("Hinzufügen")');
  await page.waitForURL('**?ok=document-added');
  await page.click('text=Aussagen extrahieren');
  await page.waitForURL('**?ok=extracted*');
  const claims = await page.locator('article.claim').count();
  if (claims !== 4) throw new Error(`expected 4 claims, got ${claims}`);
  // Admins can't review claims.
  if (await page.locator('text=Freigeben').count()) throw new Error('admin sees review buttons');
});

// 2. Reviewer: approve facts and forecast, reject the opinion.
await as('reviewer', async (page) => {
  await page.goto(`${ADMIN}/votes/${VOTE}`);
  await shot(page, '2-review');
  const review = async (quoteStart, decision, fields = {}) => {
    const card = page.locator('article.claim', { hasText: quoteStart });
    for (const [name, value] of Object.entries(fields)) await card.locator(`[name=${name}]`).fill(value);
    await card.locator(`button[value=${decision}]`).click();
    await page.waitForURL('**?ok=claim-reviewed*');
  };
  await review('Die Zahl der Musterbetriebe', 'approved');
  await review('Heute arbeiten', 'approved', { not_visualized_reason: 'Keine amtliche Zeitreihe zur Musterbranche.' });
  await review('Mit der Initiative', 'approved', { estimate_by: 'Initiativkomitee' });
  await review('Das ist schlicht unfair', 'rejected');
});

// 3. Visualizer: a chart for the first fact, submitted for review.
let vizUrl;
await as('visualizer', async (page) => {
  await page.goto(`${ADMIN}/votes/${VOTE}`);
  await page.locator('article.claim', { hasText: 'Die Zahl der Musterbetriebe' }).locator('text=Grafik erstellen').click();
  await page.fill('#title', 'Musterbetriebe, 2010 bis 2024');
  await page.fill('#description', 'Anzahl Musterbetriebe pro Jahr (synthetische Daten).');
  const spec = {
    mark: 'bar',
    data: { values: [2010, 2013, 2016, 2019, 2022, 2024].map((jahr, i) => ({ jahr: String(jahr), betriebe: 500 + i * 40 })) },
    encoding: {
      x: { field: 'jahr', type: 'ordinal', title: 'Jahr' },
      y: { field: 'betriebe', type: 'quantitative', title: 'Betriebe' },
    },
  };
  await page.fill('#spec', JSON.stringify(spec, null, 2));
  await page.waitForSelector('[data-preview] svg');
  await shot(page, '3-editor');
  await page.click('text=Als Entwurf speichern');
  await page.waitForURL('**/visualizations/**?ok=saved');
  vizUrl = page.url().split('?')[0];
  await page.click('text=Zur Prüfung einreichen');
  await page.waitForURL('**?ok=submitted');
});

// 4. Reviewer approves the chart (a different person than its author).
await as('reviewer', async (page) => {
  await page.goto(vizUrl);
  await page.click('button[value=approve]');
  await page.waitForURL('**?ok=viz-reviewed');
});

// 5. Admin publishes; the public site shows it.
await as('admin', async (page) => {
  await page.goto(`${ADMIN}/votes/${VOTE}`);
  await page.click('button:has-text("Publizieren")');
  await page.waitForURL('**?ok=published');
  await page.goto(`${ADMIN}/users`);
  await shot(page, '4-users');
});

const context = await browser.newContext({ locale: 'de-CH', viewport: { width: 1000, height: 900 }, deviceScaleFactor: 2 });
const page = await context.newPage();
page.on('pageerror', (e) => errors.push(`web: ${e.message}`));
await page.goto(`${WEB}/vorlagen/${VOTE}/`);
await page.waitForSelector('.chart svg');
const body = await page.textContent('main');
for (const expected of ['Die Zahl der Musterbetriebe', 'Initiativkomitee', 'Keine amtliche Zeitreihe']) {
  if (!body.includes(expected)) throw new Error(`public page misses "${expected}"`);
}
if (body.includes('schlicht unfair')) throw new Error('public page shows a rejected opinion');
await shot(page, '5-public');
console.log('✓ public site');

await browser.close();
if (errors.length) throw new Error(`page errors:\n${errors.join('\n')}`);
console.log('walkthrough passed');
