import assert from "node:assert/strict";
import { test } from "node:test";
import worker from "../public/_worker.js";

test("API proxy preserves session credentials and streams without caching or following redirects", async (t) => {
  t.mock.method(globalThis, "fetch", async (request, options) => {
    assert.equal(request.url, "https://backend.example/api/projects/id/session?doc=/docs/");
    assert.equal(request.method, "POST");
    assert.equal(request.headers.get("Origin"), "https://brief.example");
    assert.equal(request.headers.get("Cookie"), "brief_id=private");
    assert.equal(await request.text(), '{"token":"private"}');
    assert.equal(options.redirect, "manual");
    assert.equal(options.cache, "no-store");
    return new Response("data: ready\n\n", {
      headers: { "Content-Type": "text/event-stream", "Set-Cookie": "brief_id=private; Secure; HttpOnly" },
    });
  });
  const response = await worker.fetch(new Request("https://brief.example/api/projects/id/session?doc=/docs/", {
    method: "POST",
    headers: { Origin: "https://brief.example", Cookie: "brief_id=private" },
    body: '{"token":"private"}',
  }), { API_ORIGIN: "https://backend.example" });
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.match(response.headers.get("Set-Cookie"), /Secure; HttpOnly/);
  assert.equal(response.headers.get("Content-Type"), "text/event-stream");
  assert.equal(await response.text(), "data: ready\n\n");
});

test("missing API configuration fails closed while workspace paths use static assets", async () => {
  assert.equal((await worker.fetch(new Request("https://brief.example/api/projects"), {})).status, 503);
  const response = await worker.fetch(new Request("https://brief.example/s/site-id"), {
    ASSETS: { fetch: () => new Response("app") },
  });
  assert.equal(await response.text(), "app");
});
