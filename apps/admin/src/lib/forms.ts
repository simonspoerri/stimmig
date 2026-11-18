import type { AstroGlobal } from 'astro';
import { ApiError } from './api.ts';

export interface FormResult {
  error?: string;
  problems?: string[];
}

/** Notices shown after a successful post (Post/Redirect/Get), keyed by a short code in `?ok=`. */
export const NOTICES: Record<string, string> = {
  'vote-created': 'Vorlage erfasst.',
  'document-added': 'Dokument hinzugefügt.',
  extracted: 'Extraktion abgeschlossen. Die Aussagen warten auf die Prüfung.',
  'claim-reviewed': 'Aussage geprüft.',
  published: 'Vorlage publiziert.',
  unpublished: 'Publikation zurückgezogen.',
  saved: 'Gespeichert.',
  submitted: 'Zur Prüfung eingereicht.',
  'viz-reviewed': 'Grafik geprüft.',
  'user-created': 'Benutzer erfasst.',
  'user-updated': 'Benutzer aktualisiert.',
};

export function notice(Astro: AstroGlobal): string | undefined {
  const code = Astro.url.searchParams.get('ok');
  return code ? NOTICES[code] : undefined;
}

/**
 * Runs a page's POST handler: on success it redirects (PRG), on an API error
 * it returns the message to show next to the form.
 */
export async function handlePost(
  Astro: AstroGlobal,
  handler: (form: FormData) => Promise<string>,
): Promise<{ redirect?: Response; result: FormResult }> {
  if (Astro.request.method !== 'POST') return { result: {} };
  try {
    const target = await handler(await Astro.request.formData());
    return { redirect: Astro.redirect(target, 303), result: {} };
  } catch (error) {
    if (error instanceof ApiError) {
      Astro.response.status = error.status >= 500 ? 502 : 400;
      return { result: { error: errorText(error), problems: error.problems } };
    }
    if (error instanceof FormError) {
      Astro.response.status = 400;
      return { result: { error: error.message } };
    }
    throw error;
  }
}

/** A problem with the submitted form itself, before it reaches an API. */
export class FormError extends Error {}

function errorText(error: ApiError): string {
  if (error.status === 403) return `Keine Berechtigung: ${error.detail}`;
  if (error.status === 409 && error.problems.length) return 'Die Vorlage kann noch nicht publiziert werden:';
  return error.detail;
}

export function text(form: FormData, name: string): string {
  return String(form.get(name) ?? '').trim();
}

export function optional(form: FormData, name: string): string | null {
  return text(form, name) || null;
}

export function json(form: FormData, name: string, label: string): unknown {
  try {
    return JSON.parse(text(form, name));
  } catch {
    throw new FormError(`${label} ist kein gültiges JSON.`);
  }
}
