export default {
  async fetch(request, env) {
    const incoming = new URL(request.url);
    if (!incoming.pathname.startsWith("/api/") && incoming.pathname !== "/health") {
      return env.ASSETS.fetch(request);
    }
    if (!env.API_ORIGIN) {
      return new Response("API is not configured", { status: 503 });
    }
    const target = new URL(env.API_ORIGIN);
    target.pathname = incoming.pathname;
    target.search = incoming.search;
    // Keep cookies, Origin, bodies and SSE streams intact; never follow a
    // redirect with the owner's credentials or cache authenticated responses.
    const upstream = new Request(target, request);
    upstream.headers.delete("host");
    try {
      const response = await fetch(upstream, { redirect: "manual", cache: "no-store" });
      const result = new Response(response.body, response);
      result.headers.set("Cache-Control", "no-store");
      return result;
    } catch {
      return new Response("API is unavailable", { status: 502 });
    }
  },
};
