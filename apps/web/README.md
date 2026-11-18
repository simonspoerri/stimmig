# Public site

What voters see (Astro, server-rendered, German). Reads only the pipeline's
public API (`PIPELINE_PUBLIC_URL`), which serves approved content of
published votes. No login, no AI at view time, cacheable responses.

All text is in [`src/lib/i18n.ts`](src/lib/i18n.ts) and the German methodology
in [`src/content/methodik.md`](src/content/methodik.md) (keep it in sync with
[`docs/methodology.md`](../../docs/methodology.md)). Charts use a neutral
palette that follows the light/dark theme ([`src/components/Chart.astro`](src/components/Chart.astro)).
