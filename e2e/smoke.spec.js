import { test, expect } from '@playwright/test';

const BASE = 'http://127.0.0.1:8000';

test('bosh sahifa ochiladi va filmlar ko\'rinadi', async ({ page }) => {
  await page.goto(BASE + '/');
  await expect(page).toHaveTitle(/CINEMA/);
  await expect(page.locator('.grid .card').first()).toBeVisible();
});

test('film sahifasida treyler tugmasi bor va videoplyer ishlaydi', async ({ page }) => {
  await page.goto(BASE + '/film/gladiator/');
  await expect(page.locator('[data-open-video]')).toBeVisible();

  await page.locator('[data-open-video]').click();
  const modal = page.locator('#video-modal');
  await expect(modal).toBeVisible();
  await expect(page.locator('#video-el')).toHaveAttribute('src', /\.mp4/);

  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
});

test('qidiruv lotin va kirillcha ishlaydi', async ({ page }) => {
  await page.goto(BASE + '/search/?q=' + encodeURIComponent('Гладиатор'));
  await expect(page.locator('.grid .card').first()).toBeVisible();
});

test('admin sahifasi noindex header bilan javob beradi', async ({ page }) => {
  const response = await page.goto(BASE + '/admin/login/');
  expect(response.headers()['x-robots-tag']).toContain('noindex');
});