// Publish both role-specific views on one origin, preserving sessionStorage.
const fs = require('node:fs');
const path = require('node:path');
const source = path.resolve(__dirname, '../../Tamper_user/frontend');
const output = path.join(__dirname, 'user');
fs.mkdirSync(output, { recursive: true });
// Shared logic has ONE source; keep the parcel-aware bundled HTML/CSS intact.
if (fs.existsSync(source)) {
  for (const name of ['dashboard.js','common.js']) fs.copyFileSync(path.join(source,name),path.join(output,name));
  fs.copyFileSync(path.join(source,'evidence.js'),path.join(__dirname,'evidence.js'));
}
// A standalone frontend deployment contains the committed generated bundle.
if (fs.existsSync(path.join(output, "parcel.js")) || !fs.existsSync(source)) {
  if (!fs.existsSync(path.join(__dirname, 'evidence.js'))) throw new Error('Missing shared evidence verifier');
  for (const name of ['dashboard.html', 'dashboard.css', 'dashboard.js', 'common.js']) {
    if (!fs.existsSync(path.join(output, name))) throw new Error(`Missing user bundle: ${name}. Run npm run sync-user from the full repository.`);
  }
  console.log('Using bundled user dashboard');
  return;
}
for (const name of ['dashboard.html', 'dashboard.css', 'dashboard.js', 'common.js']) {
  let content = fs.readFileSync(path.join(source, name), 'utf8');
  if (name === 'dashboard.html') {
    content = content.replace('<html lang="en">', '<html lang="en" data-shared-login="../login.html">');
    // Only the shared cinematic login is shown in the combined website.
    content = content.replace('id="loginScreen"', 'id="loginScreen" hidden');
    content = content.replace('src="evidence.js?', 'src="../evidence.js?');
  }
  fs.writeFileSync(path.join(output, name), content);
}
console.log('User dashboard prepared at /user/dashboard.html');
