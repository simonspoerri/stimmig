import type { Adapter, AdapterPayload } from 'oidc-provider';
import type { Db } from './db.ts';

/** Models that are tied to a grant and must go away when it is revoked. */
const GRANTABLE = new Set([
  'AccessToken',
  'AuthorizationCode',
  'RefreshToken',
  'DeviceCode',
  'ClientCredentials',
  'BackchannelAuthenticationRequest',
]);

/** Persists oidc-provider's models in Postgres (table oidc_payloads). */
export function postgresAdapter(db: Db): new (name: string) => Adapter {
  return class PostgresAdapter implements Adapter {
    constructor(private readonly type: string) {}

    async upsert(id: string, payload: AdapterPayload, expiresIn?: number): Promise<void> {
      const expiresAt = expiresIn ? new Date(Date.now() + expiresIn * 1000) : null;
      await db.query(
        `INSERT INTO oidc_payloads (id, type, payload, grant_id, user_code, uid, expires_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         ON CONFLICT (id, type) DO UPDATE
         SET payload = excluded.payload, grant_id = excluded.grant_id, user_code = excluded.user_code,
             uid = excluded.uid, expires_at = excluded.expires_at`,
        [
          id,
          this.type,
          payload,
          GRANTABLE.has(this.type) ? (payload.grantId ?? null) : null,
          payload.userCode ?? null,
          payload.uid ?? null,
          expiresAt,
        ],
      );
    }

    private async findWhere(column: 'id' | 'user_code' | 'uid', value: string): Promise<AdapterPayload | undefined> {
      const { rows } = await db.query<{ payload: AdapterPayload; consumed_at: Date | null }>(
        `SELECT payload, consumed_at FROM oidc_payloads
         WHERE type = $1 AND ${column} = $2 AND (expires_at IS NULL OR expires_at > now())`,
        [this.type, value],
      );
      const row = rows[0];
      if (!row) return undefined;
      return row.consumed_at ? { ...row.payload, consumed: Math.floor(row.consumed_at.getTime() / 1000) } : row.payload;
    }

    find(id: string) {
      return this.findWhere('id', id);
    }

    findByUserCode(userCode: string) {
      return this.findWhere('user_code', userCode);
    }

    findByUid(uid: string) {
      return this.findWhere('uid', uid);
    }

    async consume(id: string): Promise<void> {
      await db.query('UPDATE oidc_payloads SET consumed_at = now() WHERE id = $1 AND type = $2', [id, this.type]);
    }

    async destroy(id: string): Promise<void> {
      await db.query('DELETE FROM oidc_payloads WHERE id = $1 AND type = $2', [id, this.type]);
    }

    async revokeByGrantId(grantId: string): Promise<void> {
      await db.query('DELETE FROM oidc_payloads WHERE grant_id = $1', [grantId]);
    }
  };
}

export async function deleteExpired(db: Db): Promise<number> {
  const { rowCount: payloads } = await db.query('DELETE FROM oidc_payloads WHERE expires_at < now()');
  const { rowCount: codes } = await db.query("DELETE FROM login_codes WHERE expires_at < now() - interval '1 day'");
  return (payloads ?? 0) + (codes ?? 0);
}
