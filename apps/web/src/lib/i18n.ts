/**
 * All user-facing text of the public site. German for now; add `fr` and `it`
 * with the same keys when translations are ready.
 */
export const de = {
  siteDescription: 'Aussagen aus dem Abstimmungsbüchlein und der Debatte, mit offiziellen Daten visualisiert.',
  navVotes: 'Vorlagen',
  navMethod: 'Methodik',
  navCode: 'Code',
  footer:
    'Stimmig zeigt Daten zu Aussagen beider Seiten. Keine Prognosen, keine Abstimmungsempfehlung. Jede Zahl ist mit ihrer offiziellen Quelle verlinkt.',
  footerMethod: 'So arbeiten wir.',
  homeTitle: 'Was sagen die Daten zu den Aussagen?',
  homeLead:
    'Im Abstimmungsbüchlein und in der Debatte werden viele Zahlen genannt. Stimmig stellt die überprüfbaren Faktenaussagen beider Seiten den offiziellen Daten gegenüber, als Grafik und mit Originalwortlaut.',
  homeEmpty: 'Noch keine Vorlage veröffentlicht. Die erste Auswertung ist für den Abstimmungstermin vom 28. Februar 2027 geplant.',
  voteOn: 'Abstimmung vom',
  officialInfo: 'Offizielle Informationen',
  factsTitle: 'Faktenaussagen und Daten',
  factsEmpty: 'Keine Faktenaussagen erfasst.',
  notVisualized: 'Nicht visualisiert:',
  source: 'Quelle:',
  accessedOn: 'abgerufen am',
  estimatesTitle: 'Schätzungen',
  estimatesLead: 'Aussagen über die Zukunft visualisiert Stimmig nicht. Sie werden hier mit ihrer Herkunft aufgeführt.',
  estimateBy: 'Schätzung von',
  claim: 'Aussage',
  side: 'Seite',
  chartError: 'Die Grafik konnte nicht geladen werden.',
  counts: (facts: number, charts: number) => `${facts} Faktenaussagen · ${charts} Grafiken`,
  sides: { proponents: 'Befürworter', opponents: 'Gegner', federal_council: 'Bundesrat' } as Record<string, string>,
  kinds: {
    popular_initiative: 'Volksinitiative',
    mandatory_referendum: 'Obligatorisches Referendum',
    optional_referendum: 'Fakultatives Referendum',
    counter_proposal: 'Gegenentwurf',
  } as Record<string, string>,
  notFoundTitle: 'Seite nicht gefunden',
  notFound: 'Diese Vorlage gibt es nicht oder sie ist (noch) nicht veröffentlicht.',
};

export const t = de;

export function formatDate(iso: string): string {
  return new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso).toLocaleDateString('de-CH', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}
