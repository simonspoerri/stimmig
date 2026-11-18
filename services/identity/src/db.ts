import pg from 'pg';

/**
 * Schema migrations, applied in order on startup. Append new ones; never
 * edit one that has been released.
 */
const MIGRATIONS: { id: string; sql: string }[] = [
  {
    id: '0001_initial',
    sql: `
      CREATE TABLE users (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        email text NOT NULL UNIQUE CHECK (email = lower(email)),
        name text NOT NULL,
        roles text[] NOT NULL DEFAULT '{}',
        disabled boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now(),
        last_login_at timestamptz
      );

      -- One row per oidc-provider model instance (sessions, grants, codes, tokens, ...).
      CREATE TABLE oidc_payloads (
        id text NOT NULL,
        type text NOT NULL,
        payload jsonb NOT NULL,
        grant_id text,
        user_code text,
        uid text,
        expires_at timestamptz,
        consumed_at timestamptz,
        PRIMARY KEY (id, type)
      );
      CREATE INDEX oidc_payloads_grant_id ON oidc_payloads (grant_id);
      CREATE INDEX oidc_payloads_uid ON oidc_payloads (uid);
      CREATE INDEX oidc_payloads_user_code ON oidc_payloads (user_code);
      CREATE INDEX oidc_payloads_expires_at ON oidc_payloads (expires_at);

      -- Login codes, bound to one login interaction (one browser), stored as HMACs.
      CREATE TABLE login_codes (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        interaction_uid text NOT NULL,
        email text NOT NULL,
        code_hmac text NOT NULL,
        attempts integer NOT NULL DEFAULT 0,
        expires_at timestamptz NOT NULL,
        consumed_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE INDEX login_codes_interaction ON login_codes (interaction_uid);
      CREATE INDEX login_codes_email_created ON login_codes (email, created_at);
    `,
  },
];

export type Db = pg.Pool;

export function createPool(databaseUrl: string): Db {
  return new pg.Pool({ connectionString: databaseUrl, max: 10 });
}

export async function migrate(db: Db): Promise<void> {
  const client = await db.connect();
  try {
    await client.query('SELECT pg_advisory_lock(4711)');
    await client.query('CREATE TABLE IF NOT EXISTS schema_migrations (id text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())');
    const { rows } = await client.query<{ id: string }>('SELECT id FROM schema_migrations');
    const applied = new Set(rows.map((r) => r.id));
    for (const migration of MIGRATIONS) {
      if (applied.has(migration.id)) continue;
      await client.query('BEGIN');
      await client.query(migration.sql);
      await client.query('INSERT INTO schema_migrations (id) VALUES ($1)', [migration.id]);
      await client.query('COMMIT');
    }
  } catch (error) {
    await client.query('ROLLBACK').catch(() => undefined);
    throw error;
  } finally {
    await client.query('SELECT pg_advisory_unlock(4711)').catch(() => undefined);
    client.release();
  }
}
