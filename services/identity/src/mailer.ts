import nodemailer from 'nodemailer';
import { CODE_TTL_MINUTES } from './codes.ts';
import { log } from './log.ts';

export interface Mailer {
  sendLoginCode(to: string, code: string): Promise<void>;
}

function body(code: string): { subject: string; text: string } {
  return {
    subject: `Ihr Stimmig-Anmeldecode: ${code}`,
    text: [
      'Guten Tag',
      '',
      `Ihr Code für die Anmeldung bei Stimmig lautet: ${code}`,
      '',
      `Er ist ${CODE_TTL_MINUTES} Minuten gültig und funktioniert nur in dem Browserfenster, in dem Sie ihn angefordert haben.`,
      'Falls Sie keinen Code angefordert haben, können Sie diese E-Mail ignorieren.',
    ].join('\n'),
  };
}

export function smtpMailer(url: string, from: string): Mailer {
  const transport = nodemailer.createTransport(url);
  return {
    async sendLoginCode(to, code) {
      await transport.sendMail({ from, to, ...body(code) });
    },
  };
}

/** Development only: prints the code instead of sending it. */
export function consoleMailer(): Mailer {
  return {
    async sendLoginCode(to, code) {
      log.info('login code (not sent, development mailer)', { to, code });
    },
  };
}
