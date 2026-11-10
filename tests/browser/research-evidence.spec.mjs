import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const capture = JSON.parse(readFileSync(new URL('../../evals/examples/yulia/actual_agent.json', import.meta.url)));

async function showFixture(page, transform = value => value) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const data = transform(structuredClone(capture.actual));
  // Serve the actual production HTML over HTTP and mock only the chat response.
  // No request to Google, a model, or an external host is allowed in these tests.
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:8765') return route.abort();
    if (url.pathname === '/chat') return route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ response: data.response, session_id: 'synthetic-ui-qa', tool_calls: data.tool_calls }),
    });
    return route.continue();
  });
  await page.goto('/');
  await page.getByLabel('Message CommonGround', { exact: true }).fill('Synthetic QA: show the missing-hours example.');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Cafe evidence and verification' })).toBeVisible();
  return errors;
}

test('missing hours, exact routes, citations and responsive layout', async ({ page }, testInfo) => {
  const errors = await showFixture(page);
  const evidence = page.getByRole('region', { name: 'Cafe evidence and verification' });
  await expect(evidence).toContainText('Evidence insufficient');
  await expect(evidence).toContainText('Opening at meeting time: unknown');
  await expect(evidence).toContainText('Exact cafe commute · Columbia University: 20 min / 35 min limit');
  await expect(evidence).toContainText('Verify meeting-time opening directly with the venue');
  await expect(evidence).toContainText('Cafe Researcher · Round 1 / Transit Researcher · Round 2');
  await expect(evidence.locator('img')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await evidence.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  const topScreenshot = testInfo.outputPath(`missing-hours-${testInfo.project.name}-top.png`);
  await evidence.getByText('Evidence insufficient', { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: topScreenshot });
  await testInfo.attach('Synthetic evidence viewport, top', { path: topScreenshot, contentType: 'image/png' });
  const gap = evidence.locator('.evidence-gap').first();
  await gap.scrollIntoViewIfNeeded();
  // A textContent assertion alone cannot prove a mobile user can scroll to a gap.
  const visible = await gap.evaluate(el => {
    const row=el.getBoundingClientRect(), log=document.querySelector('#messages').getBoundingClientRect();
    const composer=document.querySelector('.composer').getBoundingClientRect();
    return row.top>=log.top-1 && row.bottom<=log.bottom+1 && row.bottom<=composer.top+1;
  });
  expect(visible).toBe(true);
  const bottomScreenshot = testInfo.outputPath(`missing-hours-${testInfo.project.name}-verification.png`);
  await page.screenshot({ path: bottomScreenshot });
  await testInfo.attach('Synthetic evidence viewport, verification', { path: bottomScreenshot, contentType: 'image/png' });
  await evidence.getByText('Evidence and sources', { exact: true }).click();
  const links = await evidence.locator('a').evaluateAll(items => items.map(link => ({ href: link.href, rel: link.rel })));
  expect(links.length).toBeGreaterThan(0);
  expect(links.every(link => link.href.startsWith('https://') && link.rel.includes('noopener'))).toBe(true);
  expect(errors).toEqual([]);
});

test('center estimates never appear as exact venue routes', async ({ page }) => {
  const errors = await showFixture(page, data => {
    for (const event of data.tool_calls) {
      if (event.agent === 'transit_researcher' && event.round === 2) {
        const result = JSON.parse(event.result); result.facts = []; event.result = JSON.stringify(result);
      }
      if (event.name === 'evaluate_feasibility') event.result = '[]';
    }
    return data;
  });
  const evidence = page.getByRole('region', { name: 'Cafe evidence and verification' });
  await expect(evidence).toContainText('Not yet evaluated');
  await expect(evidence).toContainText('Exact cafe commute · Columbia University: not verified');
  await evidence.getByText('Area-center estimates — not exact cafe routes', { exact: true }).click();
  await expect(evidence).toContainText('Columbia University · Union Square: 20 min');
  expect(errors).toEqual([]);
});
