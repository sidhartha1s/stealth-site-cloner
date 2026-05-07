# Technology Coverage Goal

This project is a rendered-page cloner. It does not need language-specific
parsers for every website stack, but it does need stack-aware replay handling
for the browser features that break local clones.

## Terms

| Term | What it is | Clone risk |
|---|---|---|
| JavaScript / TypeScript | Programming languages used by most modern frontends | Runtime bundles, dynamic chunks, hydration |
| WebGL | Browser JavaScript API for GPU-rendered 2D/3D in `<canvas>` | Canvas pixels are not serialized into HTML; workers/WASM/assets must replay |
| GLSL | Shader language used by WebGL/WebGPU pipelines | Shader files or inline shader strings may need capture |
| Three.js | JavaScript 3D library, usually using WebGL underneath | Hidden model/texture/decoder assets |
| React / Vue / Svelte / Angular | Frontend frameworks | Hydration, route payloads, lazy chunks |
| Next.js / Nuxt / Gatsby / Astro | App/site frameworks | Static data payloads, image proxy URLs, build manifests |
| GSAP / Motion / Anime.js | Animation libraries | Scroll/time-driven state must settle before saving |
| PixiJS / P5.js / Matter.js / D3 | Canvas/SVG/visual libraries | Runtime-created canvas/SVG state and assets |
| Unity / Unreal | Game/3D engines exported to web | Compressed WASM/data bundles and server headers |
| Webflow / Framer / Readymag / Wix / Tilda | No-code/site builders | Runtime vendor scripts, forms, assets on builder CDNs |
| WordPress / Shopify / Magento / Drupal | CMS/e-commerce platforms | Theme assets, lazy images, cart/search/session endpoints |

## 2026 Priority

Awwwards' current technology filters include creative-web stacks such as WebGL,
Three.js, GSAP, Framer, Webflow, React, Next.js, Nuxt.js, Svelte, Vue.js, Vite,
PixiJS, P5.js, Unity, Unreal Engine, Canvas API, GLSL, Lottie, D3, Shopify,
WordPress, and many more. The filters also include non-runtime tools such as
Figma, Blender, Photoshop, and Cinema 4D; those are useful for design analysis
but do not require clone runtime support.

Prioritize by replay risk, not by whether the item is called a language.

## Coverage Matrix

| Priority | Stack group | Current status | Goal |
|---|---|---|---|
| P0 | WebGL / Three.js / Unity / Canvas API | Partially supported by asset capture and Unity replay fixes | Add repeatable fixtures and headers-aware replay guidance |
| P0 | Next.js / Nuxt / Vite SPAs | Partially supported; n8n Nuxt homepage replay works locally | Capture route payloads, image optimizer URLs, and build manifests reliably |
| P1 | GSAP / Motion / Anime.js / Locomotive / Rellax / Barba / Highway | Basic rendered snapshot only | Add settle strategies for scroll/time animation pages |
| P1 | PixiJS / P5.js / Matter.js / D3 / SVG | Basic asset capture only | Add visual replay tests for canvas/SVG-heavy pages |
| P1 | Webflow / Framer / Readymag / Wix / Tilda | Unknown/partial | Add vendor-specific smoke fixtures and analytics/form stripping |
| P2 | WordPress / Shopify / Magento / Drupal / WooCommerce | Likely works for static pages | Add lazy image, CDN, and query-string collision tests |
| P2 | Contentful / Sanity / Prismic / DatoCMS / Directus / Craft CMS | Framework-dependent | Ensure JSON/API payloads are captured when same-origin |
| P3 | Server/backend labels: Node.js, PHP, Python, Ruby, Go, Laravel, Express, Nginx, AWS, Vercel, Netlify | Not directly cloneable as languages | Detect only for reporting; runtime support belongs to frontend output |
| P3 | Design tools: Figma, Blender, Cinema 4D, After Effects, Photoshop, Illustrator, Sketch | Not website runtimes | Include in design extraction only |

## PR Plan

Create one branch and PR per stack group. Each PR must include:

- A representative homepage fixture command.
- A local replay check that records failed requests, HTTP 400+ responses, title,
  and console warnings/errors.
- At least one deterministic unit test for URL/path/asset-candidate logic when
  code changes are made.
- Docs update when a user-facing flag, caveat, or replay instruction changes.

Suggested branches:

| Branch | Scope |
|---|---|
| `coverage-webgl-three-unity` | WebGL, Three.js, Unity, GLSL, compressed assets |
| `coverage-next-nuxt-vite` | Next.js, Nuxt, Vite, React/Vue/Svelte hydration assets |
| `coverage-animation-scroll` | GSAP, Motion, Anime.js, Locomotive, Barba, Highway |
| `coverage-canvas-svg` | PixiJS, P5.js, Matter.js, D3, SVG |
| `coverage-builders-cms` | Webflow, Framer, Shopify, WordPress, Wix, Tilda |

## Definition Of Done

A stack group is covered when a homepage clone can be replayed locally with:

- `0` failed first-party asset requests.
- `0` first-party HTTP 400+ responses.
- Expected page title.
- No missing critical runtime files in the manifest.
- Known third-party analytics failures either stripped or documented as non-critical.

