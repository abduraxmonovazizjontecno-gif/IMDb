import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.js',
  timeout: 30000,
  retries: 1,
  use: {
    headless: true,
  },
  webServer: {
    command: 'python manage.py migrate && python manage.py seed_smoke && python manage.py runserver 127.0.0.1:8000',
    url: 'http://127.0.0.1:8000/',
    reuseExistingServer: true,
    timeout: 120000,
  },
  reporter: [['list']],
});