/** JSON log lines on stdout: `time`, `level`, `msg` plus fields. */
type Fields = Record<string, unknown>;

function write(level: 'info' | 'warn' | 'error', msg: string, fields: Fields = {}): void {
  if (process.env.LOG_SILENT === 'true') return;
  process.stdout.write(`${JSON.stringify({ time: new Date().toISOString(), level, msg, ...fields })}\n`);
}

export const log = {
  info: (msg: string, fields?: Fields) => write('info', msg, fields),
  warn: (msg: string, fields?: Fields) => write('warn', msg, fields),
  error: (msg: string, fields?: Fields) => write('error', msg, fields),
};
