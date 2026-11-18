# Identity service

OpenID Connect provider for Stimmig, built on the OpenID-certified
[`oidc-provider`](https://github.com/panva/node-oidc-provider) library
([why](../../docs/adr/0003-own-oidc-provider.md)).

- **Login** by a one-time code sent by email ([`interactions.ts`](src/interactions.ts),
  [`codes.ts`](src/codes.ts)): no passwords, no self sign-up, codes bound to the
  browser, stored as HMACs, 10 minutes, five attempts, rate-limited per address.
- **Roles** `admin`, `reviewer`, `visualizer` per user ([`users.ts`](src/users.ts)),
  sent as the `roles` claim in access and ID tokens.
- **Access tokens** are ES256 JWTs bound to one resource: `urn:stimmig:api`
  (pipeline) or `urn:stimmig:identity` (user management).
- **User management API** under `/manage`, admins only ([`manage.ts`](src/manage.ts)).
- State (sessions, grants, codes, tokens) in Postgres ([`adapter.ts`](src/adapter.ts)).

```sh
npm run dev -w @stimmig/identity     # http://localhost:4000, login codes printed to the log
npm test -w @stimmig/identity        # full login and token flows against a test database
npm run users -w @stimmig/identity -- add --email you@example.ch --name "You" --roles admin
```

In production (`NODE_ENV=production`) these must be set: `ISSUER`,
`DATABASE_URL`, `IDENTITY_CLIENTS` (JSON client list), `IDENTITY_JWKS`
(private JWKS with an ES256 key), `COOKIE_KEYS`, `CODE_KEY`, `SMTP_URL`,
`MAIL_FROM`, and `TRUST_PROXY=true` behind a reverse proxy. In development
keys are generated once into `.local/`.
