# Methodik

Diese Regeln sind das Neutralitätsversprechen von Stimmig. Sie gelten für jede
Vorlage gleich und werden nur mit einer öffentlichen, begründeten Änderung im
[Quellcode](https://github.com/simonspoerri/stimmig/blob/main/docs/methodology.md)
angepasst.

## 1. Welche Aussagen aufgenommen werden

Quellen, in dieser Reihenfolge:

1. **Abstimmungsbüchlein** (Erläuterungen des Bundesrates), inklusive der
   Argumente des Initiativ- bzw. Referendumskomitees.
2. **Parlamentsdebatte** zur Vorlage (Amtliches Bulletin).
3. **Fixe Liste öffentlicher Quellen**, pro Vorlage festgelegt, bevor die
   Auswertung beginnt (z. B. die Websites der offiziellen Komitees).

Aus diesen Quellen werden **alle** überprüfbaren Aussagen erfasst, nicht eine
Auswahl. Lässt sich eine Faktenaussage nicht mit offiziellen Daten darstellen,
wird sie mit Begründung als «nicht visualisiert» aufgeführt. So entsteht keine
Schlagseite durch Auswahl.

## 2. Einordnung

Jede Aussage erhält genau eine Klasse:

| Klasse | Bedeutung | Behandlung |
|---|---|---|
| Faktum | Aussage über einen vergangenen oder gegenwärtigen, messbaren Sachverhalt | wird mit offiziellen Daten als Grafik gezeigt |
| Prognose | Aussage über künftige Entwicklungen, Kosten oder Wirkungen, inklusive Schätzungen und Wenn-dann-Aussagen | keine Grafik, kein eigenes Modell; aufgeführt als «Schätzung von X» mit Quelle |
| Wertung | Werturteil, Forderung oder Interpretation ohne messbaren Kern | wird nicht behandelt |

Sätze mit mehreren Aussagen werden aufgeteilt. Im Zweifel gilt die
zurückhaltendere Klasse: Prognose vor Faktum, Wertung vor Prognose.

## 3. Was Stimmig nicht tut

- Keine Prognosen, Hochrechnungen oder Modellrechnungen.
- Keine Umfragen.
- Keine Abstimmungsempfehlung und keine Zusammenfassung von Parolen.
- Nach dem Abstimmungssonntag höchstens die amtlichen Resultate, ohne
  Interpretation.

## 4. Datenquellen

Grafiken verwenden nur Daten aus offiziellen Quellen, zum Beispiel des
Bundesamts für Statistik, von opendata.swiss, der Eidgenössischen
Steuerverwaltung, des SECO, des Bundesamts für Sozialversicherungen oder
kantonaler statistischer Ämter. Zu jedem Datenpunkt sind Herausgeber, Link,
Tabellen- bzw. Datensatznummer und Abrufdatum angegeben.

## 5. Neutrale Darstellung

- Keine Partei- oder Ja/Nein-Farben (kein Rot/Grün).
- Wertachsen beginnen bei null, wo das sinnvoll ist; Ausnahmen werden vermerkt.
- Gleiche Zeitfenster für Aussagen beider Seiten zum gleichen Sachverhalt.
- Neben jeder Grafik steht der Originalwortlaut der Aussage.

## 6. Ablauf und Freigabe

1. Ein Sprachmodell erfasst die Aussagen und ordnet sie ein. Jede Aussage muss
   wörtlich im Quelltext vorkommen, sonst wird sie automatisch verworfen.
2. Eine Person aus dem Review-Team prüft jede Aussage: freigeben, korrigieren
   oder verwerfen.
3. Zu jedem freigegebenen Faktum erstellt eine Person eine Grafik aus
   offiziellen Daten. Die Daten werden aus der Quelle übernommen, nie vom
   Modell geschrieben.
4. Eine zweite Person, die nicht an der Grafik gearbeitet hat, gibt sie frei
   oder weist sie zurück.
5. Nur Freigegebenes einer publizierten Vorlage erscheint auf dieser Website.

Wie oft das Review-Team das Modell korrigieren musste, wird öffentlich in den
[Evals](https://github.com/simonspoerri/stimmig/tree/main/services/pipeline/evals)
festgehalten.
