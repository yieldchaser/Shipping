#!/usr/bin/env bash
# Push the bot's commit to main, rebasing over concurrent bot pushes.
#
# Several workflows regenerate the same cadence-audit / register files whole on every run, so two runs that
# overlap always conflict there (report_ingest failed this way on 2026-10-16, and the old loop never aborted the
# half-done rebase, so every retry failed on "unmerged files"). A conflict confined to those generated files takes
# this run's copy (the next run regenerates them anyway); a conflict anywhere else aborts the rebase and fails.
set -u
GEN='^(corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT\.md|docs/CORPUS_CADENCE_AND_AUDIT\.md|corpus/CORPUS_PUBLICATION_CADENCE_AND_AUDIT\.xlsx|data/extracted/series/corpus_publication_cadence_and_audit\.xlsx|corpus/_inventory_untracked\.json|data/extracted/EXTRACTION_REGISTER\.json|docs/EXTRACTION_REGISTER\.md)$'

rebase_in_progress() {
  [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]
}

for attempt in 1 2 3 4 5; do
  git fetch -q origin main
  if ! git rebase --autostash origin/main; then
    while rebase_in_progress; do
      conflicted=$(git diff --name-only --diff-filter=U)
      other=$(printf '%s\n' "$conflicted" | grep -Ev "$GEN" | grep -v '^$' || true)
      if [ -z "$conflicted" ] || [ -n "$other" ]; then
        echo "Rebase conflict outside the regenerated audit files:"
        printf '%s\n' "${other:-<none listed>}"
        git rebase --abort
        exit 1
      fi
      echo "Regenerated files in conflict, keeping this run's copy: $conflicted"
      printf '%s\n' "$conflicted" | xargs git checkout --theirs --
      printf '%s\n' "$conflicted" | xargs git add --
      GIT_EDITOR=true git rebase --continue || true
    done
  fi
  if git push origin HEAD:main; then
    echo "Push succeeded on attempt $attempt."
    exit 0
  fi
  echo "Push race on attempt $attempt. Retrying in $((attempt * 10))s..."
  sleep $((attempt * 10))
done
echo "Failed to push after 5 attempts."
exit 1
