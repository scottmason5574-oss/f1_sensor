const { test, expect } = require('@playwright/test');

async function mount(page, options, missingMap = false) {
  await page.goto('/frontend-tests/modular.html');
  await page.waitForFunction(() => window.modularReady);
  return page.evaluate(({ options, missingMap }) => {
    const config = window.mountModular({
      config: { modules: [{ type: 'map', fields: ['track_map', 'map_drivers'], ...(options ? { options } : {}) }] },
    });
    if (missingMap) window.fixtureCard.previewData = { ...window.fixtureDemo.preview, map: undefined };
    return config.modules[0].options.view_mode;
  }, { options, missingMap });
}

test('defaults to the physical map and preserves driver selection across keyboard switching', async ({ page }) => {
  expect(await mount(page)).toBe('physical');
  const view = page.locator('f1-track-map-view');
  await expect(view.locator('path.track')).toBeVisible();
  const driver = view.locator('.driver-list button').first();
  await driver.click();
  const physical = view.getByRole('button', { name: 'Physical', exact: true });
  const circular = view.getByRole('button', { name: 'Circular', exact: true });
  await expect(physical).toHaveAttribute('aria-pressed', 'true');
  await physical.focus();
  await page.keyboard.press('Tab');
  await expect(circular).toBeFocused();
  await expect(circular).toHaveCSS('outline-style', 'solid');
  await page.keyboard.press('Enter');
  await expect(circular).toBeFocused();
  await expect(circular).toHaveAttribute('aria-pressed', 'true');
  await expect(view.getByRole('heading', { name: 'Circle of Doom' })).toBeVisible();
  await expect(view.locator('.marker')).toHaveCount(0);
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Space');
  await expect(physical).toBeFocused();
  await expect(view.locator('path.track')).toBeVisible();
  await expect(driver).toHaveAttribute('aria-pressed', 'true');
});

test('configured circular mode fits a narrow viewport without timing evidence', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' });
  expect(await mount(page, { view_mode: 'circular' }, true)).toBe('circular');
  const view = page.locator('f1-track-map-view');
  await expect(view.getByRole('button', { name: 'Circular', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(view.getByRole('status')).toHaveText('Verified timing positioning is not yet available.');
  await expect(view.getByText('Start/finish line at 12 o’clock')).toBeVisible();
  await expect(view.getByText(/leader zero/i)).toHaveCount(0);
  expect(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);
  await expect(view.locator('circle.track')).toBeVisible();
  await expect(view.locator('.circle-reference')).toBeVisible();
  expect(await finishLineGeometry(view)).toBe(true);
  await expect(view.locator('.marker')).toHaveCount(0);
  const shell = view.getByRole('region', { name: 'Circle of Doom' });
  expect(await shell.evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true);
  const bounds = await shell.boundingBox();
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(320);
  const mode = view.getByRole('button', { name: 'Circular', exact: true });
  await expect(mode).toHaveCSS('border-block-end-width', '3px');
  expect((await mode.boundingBox()).height).toBeGreaterThanOrEqual(44);
});

async function finishLineGeometry(view) {
  return view.locator('.circle-reference').evaluate(tick => {
    const ring = tick.ownerSVGElement.querySelector('circle.track');
    const { x, y, width, height } = tick.getBBox();
    const top = ring.cy.baseVal.value - ring.r.baseVal.value;
    const halfStroke = Number.parseFloat(getComputedStyle(ring).strokeWidth) / 2;
    return height > width && x + width / 2 === ring.cx.baseVal.value &&
      y < top - halfStroke && y + height > top + halfStroke;
  });
}

test('timing-shaped snapshots leave the finish line fixed and placement unavailable', async ({ page }) => {
  await mount(page, { view_mode: 'circular' });
  const view = page.locator('f1-track-map-view');
  const tick = view.locator('.circle-reference');
  await expect(tick).toBeVisible();
  const tickCoordinates = () => tick.evaluate(node => {
    const { x, y, width, height } = node.getBBox();
    return { x, y, width, height };
  });
  const original = await tickCoordinates();
  const roster = view.getByRole('region', { name: 'Driver roster' });
  for (const context of [
    { source: 'live' },
    { source: 'replay', replay_state: 'seeking' },
    { source: 'replay', replay_state: 'paused' },
  ]) {
    await page.evaluate(context => {
      const preview = window.fixtureDemo.preview;
      window.fixtureCard.previewData = { ...preview, map: {
        ...preview.map, ...context,
        session: { session_key: context.source },
        reference_lap: { duration_seconds: 90, eligible: true },
        drivers: preview.map.drivers.map(row => ({
          ...row, tla: context.source.toUpperCase(), gap_seconds: 9, crossing_elapsed_seconds: 45, angle: 144,
        })),
      } };
    }, context);
    if (context.replay_state === 'seeking') {
      await expect(roster).toContainText('temporarily unavailable while replay seeks');
    } else {
      await expect(roster.getByRole('button', { name: new RegExp(context.source, 'i') }).first()).toBeVisible();
    }
    await expect(view.getByRole('status')).toHaveText('Verified timing positioning is not yet available.');
    await expect(view.locator('svg circle')).toHaveCount(1);
    await expect(view.locator('.marker')).toHaveCount(0);
    expect(await finishLineGeometry(view)).toBe(true);
    expect(await tickCoordinates()).toEqual(original);
  }
});

test('circular roster shares driver selection with physical and clears it on session change and seek', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await mount(page, { view_mode: 'circular' });
  const view = page.locator('f1-track-map-view');
  const roster = view.getByRole('region', { name: 'Driver roster' });
  const driver = roster.getByRole('button', { name: /4 · NOR/ });
  await expect(driver).toContainText('McLaren');
  await expect(driver).toContainText('Circular placement unavailable');
  await expect(driver).toHaveCSS('border-inline-start-color', 'rgb(255, 128, 0)');
  await driver.focus();
  await page.keyboard.press('Space');
  await expect(driver).toHaveCSS('outline-style', 'solid');
  await expect(driver).toHaveAttribute('aria-pressed', 'true');
  await page.emulateMedia({ forcedColors: 'active' });
  await expect(driver).toHaveCSS('border-block-end-width', '3px');
  expect((await driver.boundingBox()).height).toBeGreaterThanOrEqual(44);
  expect(await roster.evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true);
  await view.getByRole('button', { name: 'Physical', exact: true }).click();
  await expect(view.locator('.driver-list').getByRole('button', { name: /4 · NOR/ })).toHaveAttribute('aria-pressed', 'true');
  await expect(view.locator('.marker.selected')).toHaveCount(1);
  await view.getByRole('button', { name: 'Circular', exact: true }).click();
  await expect(driver).toHaveAttribute('aria-pressed', 'true');

  const patchSnapshot = patch => page.evaluate(patch => {
    const preview = window.fixtureDemo.preview;
    window.fixtureCard.previewData = { ...preview, map: { ...preview.map, ...patch } };
  }, patch);
  await patchSnapshot({ session: { session_key: 'next' }, stale: true });
  await expect(driver).toHaveAttribute('aria-pressed', 'false');
  await expect(driver).toContainText('Saved driver data');
  await patchSnapshot({
    session: { session_key: 'next' },
    drivers: [{ racing_number: '4', tla: 'NOR', team_name: 'McLaren', status: 'OffTrack' }],
  });
  await expect(driver).toContainText('Off track');
  await expect(driver).toContainText('Circular placement unavailable');
  await driver.click();
  await patchSnapshot({ session: { session_key: 'next' }, source: 'replay', replay_state: 'seeking' });
  await expect(roster).toContainText('temporarily unavailable while replay seeks');
  await expect(roster.getByRole('button')).toHaveCount(0);
  await patchSnapshot({ session: { session_key: 'next' }, source: 'replay', replay_state: 'paused' });
  await expect(driver).toHaveAttribute('aria-pressed', 'false');
  await patchSnapshot({ session: { session_key: 'next' }, drivers: [] });
  await expect(roster).toContainText('No driver data is available.');
});

test('circular roster reports a disconnected feed and keeps team names with accents disabled', async ({ page }) => {
  await mount(page, { view_mode: 'circular' });
  await page.evaluate(() => {
    const card = window.fixtureCard, demo = window.fixtureDemo;
    card.setConfig({ appearance: { team_colors: false, full_names: true }, modules: [{ type: 'map', options: { view_mode: 'circular' } }] });
    card.previewData = null;
    const connection = {
      connected: true,
      subscribeEvents: async () => () => {},
      subscribeMessage: async (callback, message) => {
        if (message.type === 'f1_sensor/track_map/subscribe') {
          callback({ protocol_version: 2, type: 'snapshot', entry_id: 'demo', sequence: 1, geometry_revision: 1, snapshot: demo.preview.map });
        }
        return () => {};
      },
    };
    card.hass = { ...demo.hass, connection, callWS: async () => demo.preview.entries };
  });
  const roster = page.getByRole('region', { name: 'Driver roster' });
  const driver = roster.getByRole('button', { name: /4 · Lando Norris/ });
  await expect(driver).toContainText('McLaren');
  await expect(driver).toHaveCSS('border-inline-start-color', 'rgba(0, 0, 0, 0)');
  await driver.tap();
  await expect(driver).toHaveAttribute('aria-pressed', 'true');
  await page.evaluate(() => {
    const card = window.fixtureCard;
    card.hass.connection.connected = false;
    card.hass = { ...card.hass };
  });
  await expect(roster.getByText(/Home Assistant is disconnected/)).toBeVisible();
  await expect(page.locator('f1-track-map-view .marker')).toHaveCount(0);
  await page.evaluate(() => window.fixtureCard.setConfig({
    modules: [{ type: 'map', unavailable: 'hide', options: { view_mode: 'circular' } }],
  }));
  await expect(roster).toHaveCount(0);
});


test('saved circular mode honors a roster-only Track Map configuration', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => window.fixtureCard.setConfig({
    modules: [{ type: 'map', fields: ['map_drivers'], options: { view_mode: 'circular' } }],
  }));
  const view = page.locator('f1-track-map-view');
  await expect(view.getByRole('region', { name: 'Driver roster' })).toBeVisible();
  await expect(view.locator('svg')).toHaveCount(0);
  await view.getByRole('button', { name: 'Physical', exact: true }).click();
  await expect(view.getByText('Driver positions and status', { exact: false })).toBeVisible();
  expect(await page.evaluate(() => window.fixtureCard.config.modules[0].options.view_mode)).toBe('circular');
});

test('physical map clears a local selection when the driver becomes inactive', async ({ page }) => {
  await mount(page);
  const view = page.locator('f1-track-map-view');
  const driver = view.getByRole('button', { name: /4 · NOR/ });
  await driver.click();
  await expect(driver).toHaveAttribute('aria-pressed', 'true');
  const setRetired = retired => page.evaluate(retired => {
    const card = window.fixtureCard, demo = window.fixtureDemo;
    const entity = demo.preview.entries[0].entities.driver_positions;
    const state = demo.hass.states[entity];
    card.hass = { ...demo.hass, states: { ...demo.hass.states, [entity]: {
      ...state, attributes: { ...state.attributes, drivers: state.attributes.drivers.map(row =>
        String(row.racing_number) === '4' ? { ...row, retired } : row) },
    } } };
  }, retired);
  await setRetired(true);
  await expect(driver).toHaveCount(0);
  await setRetired(false);
  await expect(driver).toHaveAttribute('aria-pressed', 'false');
});
