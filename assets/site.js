const esc = s => String(s ?? '').replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const fmtDate = d => new Date(d + 'T12:00:00').toLocaleDateString(undefined,
  { year: 'numeric', month: 'long', day: 'numeric' });

async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function loadSite() {
  const site = await getJSON('site.json');
  document.querySelectorAll('[data-site]').forEach(el => { el.textContent = site[el.dataset.site] || ''; });
  document.getElementById('year').textContent = new Date().getFullYear();
  return site;
}

const metaLine = p => [fmtDate(p.date), p.location].filter(Boolean).map(esc).join(' &middot; ');

function card(p, lead) {
  const cover = p.cover
    ? `<img src="${esc(p.cover)}" alt="" loading="lazy">`
    : '<div class="no-cover"></div>';
  return `
    <a class="card${lead ? ' lead' : ''}" href="post.html?p=${encodeURIComponent(p.slug)}">
      <div class="cover">${cover}</div>
      <div class="card-text">
        <p class="meta">${metaLine(p)}</p>
        <h2>${esc(p.title)}</h2>
        <p class="excerpt">${esc(p.excerpt)}</p>
      </div>
    </a>`;
}

async function renderHome() {
  const site = await loadSite();
  document.title = site.title;
  const posts = await getJSON('posts/index.json');
  document.getElementById('posts').innerHTML = posts.length
    ? posts.map((p, i) => card(p, i === 0)).join('')
    : '<p class="empty">No posts yet.</p>';
}

async function renderPost() {
  const site = await loadSite();
  const slug = new URLSearchParams(location.search).get('p');
  const posts = await getJSON('posts/index.json');
  const p = posts.find(x => x.slug === slug);
  const el = document.getElementById('post');
  if (!p) { el.innerHTML = '<p class="empty">This post could not be found.</p>'; return; }

  document.title = `${p.title} — ${site.title}`;
  const md = await fetch(`posts/${encodeURIComponent(p.slug)}.md`, { cache: 'no-cache' }).then(r => r.text());
  el.innerHTML = `
    <p class="meta">${metaLine(p)}</p>
    <h1>${esc(p.title)}</h1>
    <div class="body">${marked.parse(md)}</div>`;

  // A photo's description becomes its caption.
  el.querySelectorAll('.body img').forEach(img => {
    const fig = document.createElement('figure');
    img.replaceWith(fig);
    fig.append(img);
    if (img.alt) {
      const cap = document.createElement('figcaption');
      cap.textContent = img.alt;
      fig.append(cap);
    }
  });
}
