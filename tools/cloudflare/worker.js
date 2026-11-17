// planplate-media: PlanPlate's photos and videos in the R2 bucket "planplate-media".
// Deployed by tools/cloudflare/deploy.py (wrangler). Address: https://planplate-media.<subdomain>.workers.dev/
//
// Why a Worker and not the bucket's own address: a custom domain on R2 needs the domain's DNS on Cloudflare
// (planplate.com stays at Namecheap), and the bucket's r2.dev address is rate-limited and not meant for live sites.
//
//   GET/HEAD /<key>          anyone: the file (byte ranges for video, cached a year: keys are never reused)
//   GET      /<key>?meta     anyone: {ok, size, type} (the app checks an upload arrived)
//   PUT      /<key>?...      the browser uploads one file with a link the app signed (media_ticket)
//   POST     /<key>?...      copy: the Worker fetches ?from=<https URL> into <key> (moving photos off Cloudinary)
//   DELETE   /<key>?...      remove a file (signed by the app)
//
// Signing: sig = hex HMAC-SHA256(SIGNING_KEY, METHOD \n key \n exp \n extra), where extra is
//   PUT:    max \n kind        (kind = image | video: the Content-Type must be one of that kind's types)
//   POST:   max \n from
//   DELETE: (empty)
// and exp is a unix time the link stops working. SIGNING_KEY is a Worker secret; the Anvil app has the same value in
// its app secret "cloudflare_media" (https://<SIGNING_KEY>@planplate-media.<subdomain>.workers.dev).

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, PUT, OPTIONS',
  'Access-Control-Allow-Headers': 'Range, Content-Type',
  'Access-Control-Expose-Headers': 'Content-Length, Content-Range, Accept-Ranges, ETag, Content-Type',
};
const KEY_RE = /^[a-z0-9][a-z0-9/_-]{0,200}$/;
const TYPES = {
  image: ['image/jpeg', 'image/png', 'image/webp', 'image/gif'],
  video: ['video/mp4', 'video/webm', 'video/quicktime'],
};
const IMMUTABLE = 'public, max-age=31536000, immutable';

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json' } });
}

async function hmac(secret, text) {
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(text));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function same(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

async function signed(env, method, key, q, extra) {
  const exp = Number(q.get('exp') || 0);
  if (!env.SIGNING_KEY || !exp || exp < Date.now() / 1000) return false;
  return same(await hmac(env.SIGNING_KEY, [method, key, String(exp), extra].join('\n')), q.get('sig') || '');
}

async function readCapped(body, max) {
  // the whole body, or null when it is bigger than max (Content-Length can be missing or wrong)
  const reader = body.getReader();
  const parts = [];
  let n = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    n += value.length;
    if (n > max) { try { await reader.cancel(); } catch (e) { /* ignore */ } return null; }
    parts.push(value);
  }
  const out = new Uint8Array(n);
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
}

async function serve(request, env, key) {
  const ranged = request.method === 'GET' && request.headers.has('Range');
  const obj = request.method === 'HEAD'
    ? await env.MEDIA.head(key)
    : await env.MEDIA.get(key, ranged ? { range: request.headers } : undefined);
  if (!obj) return new Response('Not found', { status: 404, headers: CORS });
  const headers = new Headers(CORS);
  obj.writeHttpMetadata(headers);
  headers.set('ETag', obj.httpEtag);
  headers.set('Accept-Ranges', 'bytes');
  if (!headers.has('Cache-Control')) headers.set('Cache-Control', IMMUTABLE);
  if (request.method === 'HEAD') {
    headers.set('Content-Length', String(obj.size));
    return new Response(null, { status: 200, headers });
  }
  if (ranged && obj.range) {
    const r = obj.range;
    const offset = 'suffix' in r ? obj.size - r.suffix : (r.offset || 0);
    const length = 'suffix' in r ? r.suffix : (r.length ?? obj.size - offset);
    headers.set('Content-Range', `bytes ${offset}-${offset + length - 1}/${obj.size}`);
    headers.set('Content-Length', String(length));
    return new Response(obj.body, { status: 206, headers });
  }
  headers.set('Content-Length', String(obj.size));
  return new Response(obj.body, { status: 200, headers });
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: { ...CORS, 'Access-Control-Max-Age': '86400' } });
    }
    const url = new URL(request.url);
    const key = decodeURIComponent(url.pathname.slice(1));
    if (!KEY_RE.test(key)) return new Response('Not found', { status: 404, headers: CORS });
    const q = url.searchParams;

    if (request.method === 'GET' && q.has('meta')) {  // the app checks an upload arrived (Anvil can't read headers)
      const obj = await env.MEDIA.head(key);
      return obj ? json(200, { ok: true, size: obj.size, type: (obj.httpMetadata || {}).contentType || '' })
                 : json(404, { ok: false });
    }
    if (request.method === 'GET' || request.method === 'HEAD') return serve(request, env, key);

    if (request.method === 'PUT') {
      const max = Number(q.get('max') || 0), kind = q.get('kind') || '';
      if (!(await signed(env, 'PUT', key, q, `${max}\n${kind}`))) return json(403, { ok: false, error: 'This upload link has expired. Please try again.' });
      const type = (request.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
      if (!(TYPES[kind] || []).includes(type)) return json(415, { ok: false, error: 'That file type isn\'t supported.' });
      if (Number(request.headers.get('Content-Length') || 0) > max) return json(413, { ok: false, error: 'That file is too big.' });
      const body = await readCapped(request.body, max);
      if (body === null) return json(413, { ok: false, error: 'That file is too big.' });
      await env.MEDIA.put(key, body, { httpMetadata: { contentType: type, cacheControl: IMMUTABLE } });
      return json(200, { ok: true, key, size: body.length, type });
    }

    if (request.method === 'POST') {
      const max = Number(q.get('max') || 0), from = q.get('from') || '';
      if (!(await signed(env, 'POST', key, q, `${max}\n${from}`))) return json(403, { ok: false, error: 'This copy link has expired.' });
      if (!/^https:\/\//.test(from)) return json(400, { ok: false, error: 'Only https addresses can be copied.' });
      const res = await fetch(from, { headers: { Accept: 'image/webp,image/*,video/*,*/*;q=0.5' } });
      if (!res.ok) return json(502, { ok: false, error: `The source answered ${res.status}.` });
      const type = (res.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
      if (![...TYPES.image, ...TYPES.video].includes(type)) return json(415, { ok: false, error: `Not a photo or video (${type}).` });
      const body = await readCapped(res.body, max);
      if (body === null) return json(413, { ok: false, error: 'The source file is too big.' });
      await env.MEDIA.put(key, body, { httpMetadata: { contentType: type, cacheControl: IMMUTABLE } });
      return json(200, { ok: true, key, size: body.length, type });
    }

    if (request.method === 'DELETE') {
      if (!(await signed(env, 'DELETE', key, q, ''))) return json(403, { ok: false, error: 'This link has expired.' });
      await env.MEDIA.delete(key);
      return json(200, { ok: true });
    }
    return new Response('Method not allowed', { status: 405, headers: CORS });
  },
};
