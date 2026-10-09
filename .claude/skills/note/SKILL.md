---
name: "note"
description: "Use whenever the user asks to note down, write down, remember, keep in mind or not forget something, or asks what was noted or remembered: stores and reads notes with the shrubbery-notes CLI instead of memory files."
---

# Notes

Notes replace memory files. They live encrypted in `data/notes.data` and are
only reachable through `uv run shrubbery-notes`.

To store a note:
1. Run `uv run shrubbery-notes list` and reuse an existing type where one fits,
   otherwise pick a new single lowercase word (`numerai`, `financial`,
   `feedback`, ...). If a note already covers the subject, `delete` it and add
   the corrected one instead of adding a duplicate.
2. Write a one line summary that is enough to decide relevance from `list`.
3. Pass the body on stdin with a quoted heredoc
   (`uv run shrubbery-notes add TYPE "SUMMARY" <<'EOF' ... EOF`). For
   corrections and preferences include **Why:** and **How to apply:** lines.
   Convert relative dates to absolute ones.
4. Reply with the type, summary and returned timestamp.

To recall: `list`, then `show TIMESTAMP` for the relevant entries.

Never print, log or store `SHRUBBERY_KEY`, and never write decrypted notes to
a file.
