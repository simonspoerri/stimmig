/**
 * User administration from the shell, e.g. to create the first admin:
 *
 *   npm run users -w @stimmig/identity -- add --email simon@example.ch --name "Simon" --roles admin,reviewer
 *   npm run users -w @stimmig/identity -- list
 *   npm run users -w @stimmig/identity -- roles --email simon@example.ch --roles admin
 */
import { parseArgs } from 'node:util';
import { loadConfig } from './config.ts';
import { createPool, migrate } from './db.ts';
import { UserError, Users } from './users.ts';

const [command, ...rest] = process.argv.slice(2);
const { values } = parseArgs({
  args: rest,
  options: { email: { type: 'string' }, name: { type: 'string' }, roles: { type: 'string', default: '' } },
});
const roles = (values.roles ?? '').split(',').map((r) => r.trim()).filter(Boolean);

const db = createPool(loadConfig().databaseUrl);
await migrate(db);
const users = new Users(db);

try {
  if (command === 'add') {
    const user = await users.create({ email: values.email ?? '', name: values.name ?? values.email ?? '', roles });
    console.log(`created ${user.email} (${user.roles.join(', ') || 'no roles'})`);
  } else if (command === 'roles') {
    const user = await users.byEmail(values.email ?? '');
    if (!user) throw new UserError(`no user ${values.email}`);
    const updated = await users.update(user.id, { roles });
    console.log(`${updated.email}: ${updated.roles.join(', ') || 'no roles'}`);
  } else if (command === 'list') {
    for (const u of await users.list()) console.log(`${u.email}\t${u.roles.join(',')}\t${u.disabled ? 'disabled' : ''}`);
  } else {
    console.error('usage: users add|roles|list [--email] [--name] [--roles admin,reviewer,visualizer]');
    process.exitCode = 2;
  }
} catch (error) {
  console.error(error instanceof UserError ? error.message : error);
  process.exitCode = 1;
} finally {
  await db.end();
}
