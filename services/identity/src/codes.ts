import { createHmac, randomInt, timingSafeEqual } from 'node:crypto';
import type { Db } from './db.ts';
import { normalizeEmail } from './users.ts';

export const CODE_TTL_MINUTES = 10;
export const MAX_ATTEMPTS = 5;
/** Codes one email address may request per 15 minutes. */
export const MAX_CODES_PER_WINDOW = 5;

export type VerifyResult = { ok: true; email: string } | { ok: false; reason: 'invalid' | 'expired' | 'locked' };

/**
 * One-time login codes. A code is bound to the login interaction (and so to
 * the browser) it was requested in, stored only as an HMAC, valid for 10
 * minutes and for at most five attempts.
 */
export class LoginCodes {
  constructor(
    private readonly db: Db,
    private readonly key: string,
  ) {}

  private hmac(interactionUid: string, code: string): string {
    return createHmac('sha256', this.key).update(`${interactionUid}:${code}`).digest('hex');
  }

  /** Returns the code to send, or undefined when the address hit the rate limit. */
  async issue(interactionUid: string, email: string): Promise<string | undefined> {
    const address = normalizeEmail(email);
    const { rows } = await this.db.query<{ n: string }>(
      "SELECT count(*) AS n FROM login_codes WHERE email = $1 AND created_at > now() - interval '15 minutes'",
      [address],
    );
    if (Number(rows[0]?.n ?? 0) >= MAX_CODES_PER_WINDOW) return undefined;

    const code = String(randomInt(0, 1_000_000)).padStart(6, '0');
    // A new code replaces any earlier one for this interaction.
    await this.db.query('UPDATE login_codes SET consumed_at = now() WHERE interaction_uid = $1 AND consumed_at IS NULL', [
      interactionUid,
    ]);
    await this.db.query(
      `INSERT INTO login_codes (interaction_uid, email, code_hmac, expires_at)
       VALUES ($1, $2, $3, now() + make_interval(mins => $4))`,
      [interactionUid, address, this.hmac(interactionUid, code), CODE_TTL_MINUTES],
    );
    return code;
  }

  async verify(interactionUid: string, code: string): Promise<VerifyResult> {
    const { rows } = await this.db.query<{ id: string; email: string; code_hmac: string; attempts: number; expired: boolean }>(
      `SELECT id, email, code_hmac, attempts, expires_at < now() AS expired FROM login_codes
       WHERE interaction_uid = $1 AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1`,
      [interactionUid],
    );
    const row = rows[0];
    if (!row) return { ok: false, reason: 'invalid' };
    if (row.expired) return { ok: false, reason: 'expired' };
    if (row.attempts >= MAX_ATTEMPTS) return { ok: false, reason: 'locked' };

    const expected = Buffer.from(row.code_hmac, 'hex');
    const actual = Buffer.from(this.hmac(interactionUid, code.replace(/\s+/g, '')), 'hex');
    if (!timingSafeEqual(expected, actual)) {
      await this.db.query('UPDATE login_codes SET attempts = attempts + 1 WHERE id = $1', [row.id]);
      return { ok: false, reason: row.attempts + 1 >= MAX_ATTEMPTS ? 'locked' : 'invalid' };
    }
    await this.db.query('UPDATE login_codes SET consumed_at = now() WHERE id = $1', [row.id]);
    return { ok: true, email: row.email };
  }
}
