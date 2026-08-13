# Hinweise für Claude

## Was nie ins Repository darf

Diese Dateien und Inhalte werden **niemals** committet, auch nicht auf
ausdrückliche Bitte hin, ohne vorher nachzufragen:

* `post_daily.conf` und jede Sicherungskopie davon (`post_daily.conf.*`) —
  enthält Zugriffstoken, App-Geheimcode und Konto-ID
* Zugriffstoken jeder Art (`IGAA…`, `EAA…`) im Klartext, auch in Dokumentation
  oder Commit-Nachrichten
* der Instagram-App-Geheimcode

Vor jedem `git commit` erst `git status --short` und `git diff --cached`
ansehen. Ein `git add -A` nach einer längeren Sitzung nimmt leicht etwas mit,
das nicht gemeint war — genau so wäre am 11. August 2026 beinahe eine
Sicherungskopie der Konfiguration mitgegangen.

Ein Haken unter `hooks/pre-commit` blockiert das zusätzlich. Er ist über
`git config core.hooksPath hooks` aktiviert. Wird er ausgelöst, ist das kein
Werkzeugfehler, sondern ein Fund: die Datei gehört aus dem Index genommen,
nicht der Haken übergangen.

## Vor git-Aktionen fragen

`commit`, `push` und `pull` nie ungefragt ausführen. Änderungen im
Arbeitsverzeichnis liegen lassen und den Commit anbieten, mit Vorschlag für
die Nachricht. Eine Erlaubnis aus einer früheren Nachricht überträgt sich
nicht auf den nächsten Fall.

## Veröffentlichen nur auf Ansage

`post_daily.py --publish` und `instagram_post.py --publish` nur, wenn der
Nutzer es für genau diesen Beitrag ausdrücklich verlangt. Ein einmal
ausgeführter Veröffentlichungsauftrag ist verbraucht; nach jeder Änderung an
Bild oder Text neu fragen. `--upload-only` legt das Bild nur in der Bildablage
ab und braucht keine Rückfrage.

Die Instagram-API kennt kein Löschen — ein Beitrag lässt sich nur von Hand in
der App entfernen.

## Sprache

Code-Kommentare, Begleittexte und Commit-Nachrichten auf Deutsch. Commit-
Nachrichten ohne Umlaute, weil die Historie sonst uneinheitlich wird.
