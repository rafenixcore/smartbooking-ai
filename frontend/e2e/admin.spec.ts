import { expect, test } from '@playwright/test'

async function mockAdminAPI(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('platform_access_token', 'test-platform-access')
    localStorage.setItem('platform_refresh_token', 'test-platform-refresh')
  })
  await page.route('**/api/platform/auth/me', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ id: 1, email: 'admin@example.test' }),
  }))
  await page.route('**/api/platform/businesses**', (route) => {
    const url = new URL(route.request().url())
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, offset: Number(url.searchParams.get('offset') || 0), limit: Number(url.searchParams.get('limit') || 25) }),
    })
  })
  await page.route('**/api/platform/invitations**', (route) => {
    const url = new URL(route.request().url())
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, offset: Number(url.searchParams.get('offset') || 0), limit: Number(url.searchParams.get('limit') || 25) }),
    })
  })
  await page.route('**/api/platform/audit**', (route) => {
    const url = new URL(route.request().url())
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, offset: Number(url.searchParams.get('offset') || 0), limit: Number(url.searchParams.get('limit') || 25) }),
    })
  })
}

test('admin navega por resumen y lista en escritorio', async ({ page }) => {
  await mockAdminAPI(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: 'Resumen' })).toBeVisible()
  await page.getByRole('link', { name: 'Negocios' }).first().click()
  await expect(page.getByRole('heading', { name: 'Negocios', exact: true })).toBeVisible()
  await expect(page.getByText('No encontramos negocios')).toBeVisible()
})

test('admin muestra navegación usable sin desbordamiento en móvil', async ({ page }) => {
  await mockAdminAPI(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: 'Resumen' })).toBeVisible()
  await page.getByRole('navigation', { name: 'Navegación móvil' }).getByRole('link', { name: 'Invitaciones' }).click()
  await expect(page.getByRole('heading', { name: 'Invitaciones', exact: true })).toBeVisible()
  const noHorizontalPageOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  expect(noHorizontalPageOverflow).toBe(true)
})
