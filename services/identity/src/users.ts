import { ROLES, type Role } from './config.ts';
import type { Db } from './db.ts';

export interface User {
  id: string;
  email: string;
  name: string;
  roles: Role[];
  disabled: boolean;
  created_at: Date;
  last_login_at: Date | null;
}

export class UserError extends Error {}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

function checkRoles(roles: string[]): Role[] {
  const unknown = roles.filter((r) => !(ROLES as readonly string[]).includes(r));
  if (unknown.length > 0) throw new UserError(`unknown role(s): ${unknown.join(', ')}`);
  return [...new Set(roles as Role[])].sort();
}

function checkEmail(email: string): string {
  const normalized = normalizeEmail(email);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) throw new UserError('invalid email address');
  return normalized;
}

export class Users {
  constructor(private readonly db: Db) {}

  async list(): Promise<User[]> {
    const { rows } = await this.db.query<User>('SELECT * FROM users ORDER BY email');
    return rows;
  }

  async byId(id: string): Promise<User | undefined> {
    if (!/^[0-9a-f-]{36}$/i.test(id)) return undefined;
    const { rows } = await this.db.query<User>('SELECT * FROM users WHERE id = $1', [id]);
    return rows[0];
  }

  async byEmail(email: string): Promise<User | undefined> {
    const { rows } = await this.db.query<User>('SELECT * FROM users WHERE email = $1', [normalizeEmail(email)]);
    return rows[0];
  }

  /** Users that can log in: existing and not disabled. */
  async active(id: string): Promise<User | undefined> {
    const user = await this.byId(id);
    return user && !user.disabled ? user : undefined;
  }

  async create(input: { email: string; name: string; roles: string[] }): Promise<User> {
    const email = checkEmail(input.email);
    if (!input.name.trim()) throw new UserError('name is required');
    if (await this.byEmail(email)) throw new UserError(`a user with ${email} already exists`);
    const { rows } = await this.db.query<User>(
      'INSERT INTO users (email, name, roles) VALUES ($1, $2, $3) RETURNING *',
      [email, input.name.trim(), checkRoles(input.roles)],
    );
    return rows[0]!;
  }

  async update(id: string, changes: { name?: string; roles?: string[]; disabled?: boolean }): Promise<User> {
    const user = await this.byId(id);
    if (!user) throw new UserError('user not found');
    const { rows } = await this.db.query<User>(
      'UPDATE users SET name = $2, roles = $3, disabled = $4 WHERE id = $1 RETURNING *',
      [
        id,
        changes.name?.trim() || user.name,
        changes.roles ? checkRoles(changes.roles) : user.roles,
        changes.disabled ?? user.disabled,
      ],
    );
    return rows[0]!;
  }

  async recordLogin(id: string): Promise<void> {
    await this.db.query('UPDATE users SET last_login_at = now() WHERE id = $1', [id]);
  }
}
