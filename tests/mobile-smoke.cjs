// Read-only browser smoke checks against the configured API. No records are changed.
// TEST_ADMIN_PASSWORD and TEST_USER_PASSWORD are supplied locally, never committed.
const { chromium, webkit } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'artifacts');
fs.mkdirSync(out, {recursive: true});
const api = process.env.TEST_API_URL || 'https://safetrack-api-live.vercel.app';
const adminBase = process.env.TEST_ADMIN_URL || 'http://127.0.0.1:5511/Tamper_admin/frontend/';
const userBase = process.env.TEST_USER_URL || 'http://127.0.0.1:5511/Tamper_user/frontend/';
async function login(username, password) {
  assert(password, 'Supply test passwords through environment variables');
  const response = await fetch(api + '/api/auth/login', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({username,password})});
  assert.equal(response.status, 200, 'Test account login');
  return response.json();
}
(async () => {
  const accounts = {
    admin: await login(process.env.TEST_ADMIN_USER || 'admin', process.env.TEST_ADMIN_PASSWORD),
    user: await login(process.env.TEST_USER_USER || 'Rahul Sharma', process.env.TEST_USER_PASSWORD)
  };
  const browser = process.env.TEST_BROWSER === 'webkit'
    ? await webkit.launch({headless:true}) : await chromium.launch({channel:'chrome',headless:true});
  const results = [];
  const failures = [];
  try {
    for (const role of (process.env.TEST_ROLE ? [process.env.TEST_ROLE] : ['admin','user'])) {
      const context = await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
      await context.addInitScript(account => {
        for(const [key,value] of Object.entries({safetrack_access_token:account.access_token,safetrack_role:account.role,safetrack_username:account.username,safetrack_assigned_shipments:JSON.stringify(account.assigned_shipments)})) sessionStorage.setItem(key,value);
      },accounts[role]);
      const page = await context.newPage();
      page.on('pageerror', error => failures.push({role,error:error.message}));
      const pages = role==='admin' ? ['index.html','shipments.html','vehicle-details.html?id=TRK-MH-001','alerts.html','reports.html','users.html','settings.html','live.html'] : ['index.html','live.html'];
      const sizes = process.env.TEST_SIZES ? JSON.parse(process.env.TEST_SIZES) : process.env.TEST_QUICK ? [[390,844]] : [[320,740],[390,844],[412,915],[768,1024],[844,390],[1280,800]];
      for (const [width,height] of sizes) {
        await page.setViewportSize({width,height});
        for (const file of pages) {
          if(process.env.TEST_PAGE && !file.startsWith(process.env.TEST_PAGE)) continue;
          await page.goto((role==='admin'?adminBase:userBase)+file,{waitUntil:'networkidle'});
          if(file==='live.html') await page.locator('#history tr').first().waitFor({timeout:70000});
          if(role==='user' && file==='index.html') await page.locator('#appShell').waitFor();
          const layout = await page.evaluate(() => ({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
          const good = layout.scroll <= width+1 && layout.body <= width+1;
          if(!good) {
            const overflow = await page.evaluate(limit => [...document.querySelectorAll('main *, header *')].filter(el => {
              const r=el.getBoundingClientRect(); return r.width>0 && r.right>limit+1 && !el.closest('.overflow-x-auto,.table-responsive,.wide,#sidebar');
            }).slice(0,15).map(el=>({tag:el.tagName,id:el.id,classes:el.className,right:el.getBoundingClientRect().right})),width);
            failures.push({role,file,width,layout,overflow});
          }
          if(role==='admin' && file!=='live.html' && width<1024) {
            await page.getByRole('button',{name:'☰ Menu',exact:true}).click();
            assert.equal(await page.locator('#sidebar').evaluate(el=>el.inert),false);
            await page.getByRole('button',{name:'Close menu ×',exact:true}).click();
            assert.equal(await page.locator('#sidebar').evaluate(el=>el.inert),true);
          }
          if(width===390) {
            await page.screenshot({path:path.join(out,`${role}-${file.split('.')[0]}-${process.env.TEST_BROWSER||'chrome'}.png`),fullPage:true});
            if(role==='admin' && file==='shipments.html') {
              await page.locator('[data-action="inspectShipment"]').first().click();
              await page.locator('#inspectShipmentModal').waitFor();
              await page.screenshot({path:path.join(out,'admin-shipment-inspector.png'),fullPage:true});
              await page.locator('#inspectShipmentModal').getByRole('button',{name:'Close',exact:true}).click();
            }
          }
          if(role==='user' && file==='index.html') {
            for(const tab of ['shipment','environment','alerts','history']) {
              await page.locator(`[data-tab="${tab}"]`).click();
              const widthAfter = await page.evaluate(()=>document.documentElement.scrollWidth);
              if(widthAfter>width+1) failures.push({role,file,tab,width,widthAfter});
            }
          }
          results.push({role,file,width,height,passed:good});
          console.log(`${good?'PASS':'FAIL'} ${role} ${file} ${width}x${height}`);
        }
      }
      await context.close();
    }
  } finally { await browser.close(); }
  fs.writeFileSync(path.join(out,`mobile-results-${process.env.TEST_BROWSER||'chrome'}.json`),JSON.stringify({results,failures},null,2));
  if(failures.length) {console.error(JSON.stringify(failures,null,2));process.exitCode=1;}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
