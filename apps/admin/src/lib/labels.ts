/** All German UI text for enum values in one place, so French and Italian can follow. */

export const CLASS_LABEL: Record<string, string> = {
  fact: 'Faktum',
  forecast: 'Prognose',
  opinion: 'Wertung',
};

export const SIDE_LABEL: Record<string, string> = {
  proponents: 'Befürworter',
  opponents: 'Gegner',
  federal_council: 'Bundesrat',
};

export const DOCUMENT_KIND_LABEL: Record<string, string> = {
  booklet: 'Abstimmungsbüchlein',
  parliament: 'Parlamentsdebatte',
  public: 'Öffentliche Quelle',
};

export const VOTE_KIND_LABEL: Record<string, string> = {
  popular_initiative: 'Volksinitiative',
  mandatory_referendum: 'Obligatorisches Referendum',
  optional_referendum: 'Fakultatives Referendum',
  counter_proposal: 'Gegenentwurf',
};

export const STATUS_LABEL: Record<string, string> = {
  draft: 'Entwurf',
  approved: 'Freigegeben',
  rejected: 'Verworfen',
  in_review: 'In Prüfung',
  published: 'Publiziert',
};

export const ROLE_LABEL: Record<string, string> = {
  admin: 'Admin',
  reviewer: 'Reviewer',
  visualizer: 'Visualizer',
};

export const ROLE_DESCRIPTION: Record<string, string> = {
  admin: 'Vorlagen und Quellen erfassen, Extraktion starten, publizieren, Benutzer verwalten',
  reviewer: 'Aussagen prüfen, Grafiken anderer freigeben',
  visualizer: 'Grafiken zu freigegebenen Fakten erstellen',
};

export function formatDate(iso: string): string {
  return new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso).toLocaleDateString('de-CH', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('de-CH', { dateStyle: 'medium', timeStyle: 'short' });
}
