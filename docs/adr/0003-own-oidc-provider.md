# 0003 – Own OIDC provider on a certified library

Status: accepted, 2026-11-18

## Context

The admin needs logins and three roles. Options: a hosted identity product,
running an off-the-shelf server (Zitadel, Keycloak), or a small service of
our own.

## Decision

A small Node service built on [`oidc-provider`](https://github.com/panva/node-oidc-provider),
which is OpenID Certified. The library implements the protocol (authorization
code with PKCE, refresh tokens, JWT access tokens via resource indicators,
discovery, JWKS). We only write the login interaction (one-time code by
email), the user and role store, the persistence adapter and a small
management API.

## Consequences

- Light to run and fully visible in the repository, including the role model.
- Protocol security comes from the library; our own security-relevant code is
  the login interaction and user management, and has dedicated tests.
- No passwords. Passkeys can be added later as a second login method.
- We maintain it ourselves; if requirements grow (federation, SAML, many
  tenants), revisit in favour of an off-the-shelf server.
