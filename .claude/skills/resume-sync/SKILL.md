---
name: resume-sync
description: Run the résumé sync bot (the "Weekly résumé sync" scheduled task) right now instead of waiting for Monday. Only when Daniel types /resume-sync.
argument-hint: "[full] [extra notes for this run]"
disable-model-invocation: true
---

Daniel wants the résumé sync bot to do its vet now. The bot is the claude.ai scheduled task
**Weekly résumé sync**, trigger ID `trig_01CL6rNXRC54CaHcJ6zoBgAG`. It follows `SYNC.md` in the
`resume-sync` repo and opens PRs; it never merges.

Arguments given: `$ARGUMENTS`

1. Build the extra message for this run (leave it empty if there are no arguments):
   - If the arguments start with `full`, include: "On-demand full vet requested by Daniel: do not
     stop at step 0 even if it prints NOTHING TO SYNC. Re-check every bullet in resume.tex against
     the current READMEs, code and zhangdz.ca, and follow SYNC.md steps 3–7 for anything wrong,
     overstated or missing. If everything checks out, change nothing and say so in the notification."
   - Pass any remaining words through as: "Notes from Daniel for this run: <words>".
2. Fire the scheduled task once, with that message:
   - In a cloud session: `mcp__claude-code-remote__fire_trigger` with `trigger_id` and `text`.
   - On a PC: the `RemoteTrigger` tool, action `run`, same trigger ID (load it with ToolSearch if
     it's deferred).
   - If neither tool exists, or the ID is not found, don't run SYNC.md here. Tell Daniel to press
     **Run now** on the task at https://claude.ai/code/routines (and, if the ID was not found, to
     update the ID in this skill).
3. Do not touch the task's schedule, prompt or model, and don't fire it more than once.
4. Reply in one or two lines: that it's started, that results arrive as a push notification and
   PRs on `danielzhang122/resume-sync`, and the run's session link if the tool returned one.
