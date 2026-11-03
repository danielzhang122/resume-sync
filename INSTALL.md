# Installing the résumé sync for someone else

**This file is written for Claude** (or any coding agent). A person who wants the pipeline points
their agent here, for example:

> Set up the résumé sync from https://github.com/danielzhang122/resume for me. Follow its INSTALL.md.

What they get: a weekly agent that diffs their GitHub repos since last week, drafts résumé edits that
cite the commit behind each claim, has CI build the PDF and fail if it runs past one page, and opens
a pull request. It never merges anything. See [docs/PIPELINE.md](docs/PIPELINE.md) for the design.

Work through the steps in order. Ask the person only for what you can't find yourself, and confirm
before anything outward-facing (creating a repo, pushing to `main`, scheduling the task).

## 1. Gather the settings

| Setting | How to find it | Example |
|---|---|---|
| Full name | Their résumé header | `Jane Doe` |
| GitHub username | `git remote -v`, the GitHub tools, or ask | `janedoe` |
| Résumé repo | Where their LaTeX résumé lives. If none, create a **private** repo (ask first) | `janedoe/resume` |
| LaTeX file | `*.tex` at that repo's root with `\documentclass` | `resume.tex` |
| PDF name | Default `First_Last_Resume.pdf`; keep an existing committed PDF's name | `Jane_Doe_Resume.pdf` |
| Portfolio site (optional) | URL on the résumé or GitHub profile | `https://janedoe.dev` |
| Website repo (optional) | Only if the site **serves the résumé PDF from a repo** | `janedoe.github.io` |
| Website commit identity (optional) | Name and email they commit to the website repo with | `janedoe`, `…@users.noreply.github.com` |

## 2. Make sure the résumé is LaTeX at the repo root

The build uses `xu-cheng/latex-action` (full TeX Live) and checks the page count, so the résumé must
be a `.tex` file at the root of the repo that compiles to **one page**. If they only have a PDF,
Word file or Google Doc, offer to convert it into LaTeX first, keeping the content exactly; show
them the converted PDF and get their OK before going further.

## 3. Run the installer

Clone this repo and theirs side by side, then from this repo:

```bash
python3 scripts/install.py --target ../<their-resume-repo> --name "Jane Doe" --github-user janedoe
```

Add `--tex`, `--pdf-name`, `--site-url`, `--website-repo`, `--website-git-name` and
`--website-git-email` when they apply. The installer copies `scripts/check.py`, its tests and the two
workflows; writes `SYNC.md` (the agent's instructions, filled in from `template/SYNC.md`) and a fresh
`sync-state.json`; adds build artifacts to `.gitignore`; and adds one line after `\documentclass`
so rebuilding unchanged source gives a byte-identical PDF. It refuses to overwrite existing files
unless given `--force`.

Then, in their repo:

1. Read the generated `SYNC.md` and adjust anything that doesn't fit them (rule 10 assumes they
   reword drafts; drop it if they don't). Keep the rules about accuracy, one page and never merging.
2. `python3 -m unittest discover tests` must pass.
3. Commit everything and push to `main` (ask first if `main` is protected or shared; otherwise use
   a branch and PR).
4. Set `repos.<résumé repo>` in `sync-state.json` to the new `HEAD` SHA and commit just that file.
   `sync-state.json` is an excluded path, so the pipeline treats its own install as already seen.
5. Check the **Build résumé** Action ran green on GitHub (push a no-op `.tex` change or use
   *Run workflow* if it didn't trigger). In the repo's *Settings → Actions → General*, workflow
   permissions must allow **Read and write** so it can commit the PDF back.

## 4. Schedule the weekly agent

Create a weekly scheduled task (a Claude Code routine) with:

- **Repository:** their résumé repo, plus the website repo if they have one. The environment must
  be able to clone their other public repos (GitHub access/network to `github.com`).
- **Schedule:** weekly, at a quiet hour in their time zone (Daniel's runs Sundays 06:00 Eastern).
- **Prompt** (fill in the names):

  > You are the weekly résumé sync agent for Jane Doe. Open the résumé repo and follow its SYNC.md
  > exactly, step 0 first. If step 0 prints NOTHING TO SYNC, send Jane a one-line push notification
  > ("Résumé sync: nothing changed this week."), end with "Nothing to sync." and do nothing else.
  > Otherwise finish with a one- or two-line push notification summarising what happened. Keep token
  > use low. Never merge PRs, never edit the résumé on main directly, never edit project repos other
  > than the website PDF PR in SYNC.md, never invent metrics or present planned work as done, and
  > don't revert Jane's own rewording of résumé bullets.

If you have a tool for creating scheduled tasks (for example `create_trigger` in a Claude Code cloud
session), use it after the person confirms. Otherwise give them the prompt above and tell them to
create it with `/schedule` in Claude Code or under Routines on claude.ai/code. Use a smaller model
for the task if they want it cheap: step 0 is a script, and quiet weeks end there.

## 5. First run

Offer to run the task once now. With only the résumé repo in `repos`, every other public repo shows
up as `new`, so the first run audits the whole résumé against their GitHub and usually opens the
most useful PR the pipeline ever makes. Tell them to review it like any PR: every change cites its
source, and nothing lands until they merge.

## What to tell them when you're done

- Where the pieces are: `SYNC.md` (rules), `sync-state.json` (what's been reviewed; add repos to
  `ignore` to skip them), `scripts/check.py` (change detection), `.github/workflows/build.yml`.
- That they review and merge every PR, and should reword drafted bullets in their own voice.
- How to pause it: disable the scheduled task.
