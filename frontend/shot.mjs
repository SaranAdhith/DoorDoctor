import { chromium } from 'playwright-core'

const OUT = process.env.SHOT_DIR
const browser = await chromium.launch({
  executablePath: '/usr/bin/google-chrome-stable',
  headless: true,
})

const errors = []

async function session(email, routes, width = 1440, height = 900) {
  const context = await browser.newContext({ viewport: { width, height } })
  const page = await context.newPage()
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`[${email} ${page.url()}] ${msg.text()}`)
  })
  page.on('pageerror', (err) => errors.push(`[${email}] ${err.message}`))

  await page.goto('http://127.0.0.1:5173/login', { waitUntil: 'networkidle' })
  await page.fill('input[type="email"]', email)
  await page.fill('input[type="password"]', 'Demo@123')
  await page.click('button[type="submit"]')
  await page.waitForTimeout(2500)

  for (const [name, path] of routes) {
    await page.goto(`http://127.0.0.1:5173${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1200)
    const scrollW = await page.evaluate(() => document.documentElement.scrollWidth)
    const clientW = await page.evaluate(() => document.documentElement.clientWidth)
    if (scrollW > clientW + 1) errors.push(`[overflow ${width}px] ${path}: ${scrollW} > ${clientW}`)
    await page.screenshot({ path: `${OUT}/${width}-${name}.png`, fullPage: true })
    const body = await page.evaluate(() => document.body.innerText)
    if (/Something went wrong|Cannot reach the DoorDoctor API/i.test(body)) {
      errors.push(`[error state] ${path}`)
    }
  }
  await context.close()
}

const family = [
  ['family-dashboard', '/family/dashboard'],
  ['family-care', '/family/care'],
  ['family-nurse', '/family/nurse/1'],
  ['family-circle', '/family/care-circle'],
  ['family-privacy', '/family/privacy'],
  ['family-notifications', '/family/notifications'],
  ['family-medications', '/family/medications'],
]
const nurse = [
  ['nurse-myday', '/nurse/my-day'],
  ['nurse-roster', '/nurse/roster'],
]
const admin = [
  ['admin-board', '/admin/board'],
  ['admin-alerts', '/admin/alerts'],
  ['admin-nurses', '/admin/nurses'],
  ['admin-outcomes', '/admin/outcomes'],
  ['admin-zones', '/admin/zones'],
  ['admin-privacy', '/admin/privacy'],
]

for (const width of [1440, 375]) {
  await session('family@doordoctor.in', family, width)
  await session('nurse@doordoctor.in', nurse, width)
  await session('admin@doordoctor.in', admin, width)
}

await browser.close()
console.log(errors.length ? errors.join('\n') : 'CLEAN')
