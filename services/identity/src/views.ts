/** Server-rendered login pages. User-facing text is German (see AGENTS.md). */

const escapeMap: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escape(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (c) => escapeMap[c]!);
}

const STYLE = `
:root { --bg:#f6f5f2; --surface:#fff; --text:#1d232b; --muted:#5b6573; --line:#dedad3; --accent:#1f3a5f; --error:#8a1c1c;
  color-scheme: light dark; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
@media (prefers-color-scheme: dark) { :root { --bg:#14171b; --surface:#1d2127; --text:#e6e3de; --muted:#9aa3ae;
  --line:#2f353d; --accent:#9db8dc; --error:#f0a0a0; } }
* { box-sizing: border-box; }
body { margin:0; min-height:100vh; display:grid; place-items:center; background:var(--bg); color:var(--text); padding:16px; }
main { width:100%; max-width:380px; background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:28px; }
.brand { font-weight:700; letter-spacing:.01em; margin:0 0 20px; }
h1 { font-size:1.25rem; margin:0 0 8px; }
p { color:var(--muted); line-height:1.5; margin:0 0 16px; }
label { display:block; font-size:.9rem; margin-bottom:6px; }
input { width:100%; font:inherit; padding:10px 12px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--text); }
input.code { font-size:1.4rem; letter-spacing:.3em; text-align:center; }
button { width:100%; margin-top:16px; font:inherit; font-weight:600; padding:10px 12px; border:0; border-radius:8px;
  background:var(--accent); color:var(--surface); cursor:pointer; }
.error { color:var(--error); margin:12px 0 0; }
.secondary { display:block; text-align:center; margin-top:14px; color:var(--muted); font-size:.9rem; }
`;

function page(title: string, content: string): string {
  return `<!doctype html>
<html lang="de-CH">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${escape(title)} · Stimmig</title>
<style>${STYLE}</style>
</head>
<body><main><p class="brand">Stimmig</p>${content}</main></body>
</html>`;
}

export function emailForm(uid: string, error?: string): string {
  return page(
    'Anmelden',
    `<h1>Anmelden</h1>
<p>Wir senden Ihnen einen Code per E-Mail. Ein Passwort gibt es nicht.</p>
<form method="post" action="/interaction/${escape(uid)}/email">
  <label for="email">E-Mail-Adresse</label>
  <input id="email" name="email" type="email" autocomplete="email" required autofocus>
  <button type="submit">Code senden</button>
  ${error ? `<p class="error" role="alert">${escape(error)}</p>` : ''}
</form>`,
  );
}

export function codeForm(uid: string, email: string, error?: string): string {
  return page(
    'Code eingeben',
    `<h1>Code eingeben</h1>
<p>Falls für <strong>${escape(email)}</strong> ein Zugang besteht, haben wir einen sechsstelligen Code gesendet.
Er ist 10 Minuten gültig.</p>
<form method="post" action="/interaction/${escape(uid)}/code">
  <label for="code">Code</label>
  <input id="code" class="code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9 ]{6,7}" maxlength="7" required autofocus>
  <button type="submit">Anmelden</button>
  ${error ? `<p class="error" role="alert">${escape(error)}</p>` : ''}
</form>
<a class="secondary" href="/interaction/${escape(uid)}">Andere E-Mail-Adresse verwenden</a>`,
  );
}

export function errorPage(message: string): string {
  return page('Fehler', `<h1>Das hat nicht geklappt</h1><p>${escape(message)}</p>`);
}

export function logoutPage(form: string): string {
  return page(
    'Abmelden',
    `<h1>Abmelden?</h1><p>Sie werden bei Stimmig abgemeldet.</p>
${form}
<button type="submit" form="op.logoutForm" name="logout" value="yes">Abmelden</button>`,
  );
}

export function loggedOutPage(): string {
  return page('Abgemeldet', '<h1>Sie sind abgemeldet</h1><p>Sie können dieses Fenster schliessen.</p>');
}
