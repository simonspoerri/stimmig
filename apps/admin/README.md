# Admin

Internal tool for the three roles (Astro, server-rendered). German UI.

| Page | Who | |
|---|---|---|
| `/` | all | votes; admins create new ones |
| `/votes/:id` | all | source documents and extraction (admin), claim review (reviewer), publishing (admin), audit log |
| `/claims/:id/visualize`, `/visualizations/:id` | visualizer, reviewer | chart editor with live preview, submit, four-eyes review |
| `/users` | admin | users and roles, via the identity service's management API |

Login is the OIDC authorization code flow with PKCE ([`src/lib/oidc.ts`](src/lib/oidc.ts)).
Tokens live in an encrypted httpOnly cookie ([`src/lib/session.ts`](src/lib/session.ts)).
The app only hides what a role may not do; the APIs enforce it.

Environment: `PUBLIC_URL`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`,
`PIPELINE_URL`, `PUBLIC_SITE_URL`, `SESSION_SECRET` (32+ bytes, base64url).
Development defaults match `scripts/dev.sh`.
