import { deleteExpired } from './adapter.ts';
import { createProvider } from './app.ts';
import { loadConfig } from './config.ts';
import { createPool, migrate } from './db.ts';
import { log } from './log.ts';
import { consoleMailer, smtpMailer } from './mailer.ts';

const config = loadConfig();
const db = createPool(config.databaseUrl);
await migrate(db);

const mailer = config.smtpUrl ? smtpMailer(config.smtpUrl, config.mailFrom) : consoleMailer();
const provider = createProvider(config, { db, mailer });
const server = provider.listen(config.port, () => log.info('identity started', { issuer: config.issuer, port: config.port }));

const cleanup = setInterval(() => {
  deleteExpired(db).catch((error: unknown) => log.error('cleanup failed', { error: String(error) }));
}, 60 * 60 * 1000);

for (const signal of ['SIGTERM', 'SIGINT'] as const) {
  process.on(signal, () => {
    clearInterval(cleanup);
    server.close(() => void db.end().then(() => process.exit(0)));
  });
}
