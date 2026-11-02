# AGENTS.md

<!-- ai-rulebook:start -->
<!-- Managed by the AI Rulebook extension. Text between the ai-rulebook markers is regenerated on install; toggle rules from the AI Rulebook sidebar instead of editing here. -->

<!-- ai-rulebook:rule code enabled -->

## Code

- Before adding a helper, search for an existing one. Reuse or extend it instead of adding a near-duplicate.
- Where code reads user input, network data, files, or environment variables, validate the data there.
- Never log or commit secrets.
- When an error crosses a module or process boundary, add context saying what failed and keep the original cause. Never swallow a failure.
- Prefer the standard library or an existing dependency to a new one. Name any new dependency in your report.
- Before adding a dependency, confirm it is maintained, supports the project's runtime, and has no known unmitigated vulnerability. Never add a prerelease, archived, or deprecated package, or one that needs an end-of-life runtime. An old release date calls for a closer look, not rejection.
- Report dependency problems you run into; don't migrate them unasked.

<!-- ai-rulebook:end-rule code -->

<!-- ai-rulebook:rule docs enabled -->

## Docs

- When your change makes documentation inaccurate (usage, configuration, requirements, architecture, development commands), update it in the same change.
- Write densely for a reader who will act on it, human or agent: commands, paths, settings, constraints, and the reason behind non-obvious choices. Cut filler, restated code, and marketing. Prefer lists and tables to long prose.
- Keep each fact in one place and link to it elsewhere.
- Keep agent-instruction files (`AGENTS.md`, `CLAUDE.md`, rule files) shortest of all: every line is loaded into every session.
- Add a release note for user-visible changes in the existing changelog format. Describe behavior; skip internal refactors.
- Add new documents only when asked or when the change cannot be explained in existing ones. Without an existing layout, put them under `docs/`, linked from `README.md`. Don't introduce a documentation framework unasked.

<!-- ai-rulebook:end-rule docs -->

<!-- ai-rulebook:rule git enabled -->

## Git

- Don't commit, push, or create branches unless asked.
- Never force-push, rebase, amend, or reset away pushed history unless the user names that operation.
- Inspect the working tree before editing. Preserve changes you did not make.
- When committing, stage only your changes (the task and its **Also fixed** items), using selective hunks in files with unrelated edits. Never `git add -A` blindly.
- Inspect the staged diff before committing. Write an imperative subject line and a body that says why.

<!-- ai-rulebook:end-rule git -->

<!-- ai-rulebook:rule markdown enabled -->

## Markdown

When editing `.md` files:

- One H1; never skip heading levels.
- `-` for bullets; language tag on every fence.
- Inline code for paths, commands, and filenames.
- Relative links for in-repo targets.

<!-- ai-rulebook:end-rule markdown -->

<!-- ai-rulebook:rule review enabled -->

## Review

Apply this section only when the user explicitly asks for a full or thorough code review. Never start one on your own.

- Scope: every change not yet pushed — uncommitted changes plus local commits missing from the upstream branch (from the default branch when there is no upstream). Use the range the user names instead when they give one. Read the callers and callees you need to judge a change.
- Work through these passes and fix what you find as you go; the other rules still apply:
  1. Bugs: logic errors, edge cases, error handling, races, and leaks. Add a regression test for each fix where feasible.
  2. Security: trust-boundary input, injection, path handling, auth, secrets, and vulnerable dependencies.
  3. Dead code: unused code, files, exports, config, and dependencies. Confirm nothing still references it, including config, scripts, and docs.
  4. Duplication and structure: consolidate real duplicates and refactor where it clearly helps maintainability, keeping public interfaces and intended behavior.
  5. Improvements: low-risk gains in correctness, performance, or clarity.
  6. Tests: cover changed behavior and fix weak or wrong assertions.
  7. Docs: fix anything the review shows is inaccurate.
  8. Licensing: report, don't fix — dependency licenses that may conflict with the project's, copied code without attribution, and missing required notices.
- Run the project's test command and the project's lint and type checks after the fixes; all must pass before you commit.
- Report with the Scope rule's headings, grouping **Changed** by pass with each change's path and a one-line reason. Put licensing concerns and unfixed findings, with the reason, under **Not done**.
- Then commit and push; asking for the review is the request to do so unless the user says otherwise. Follow the Git rule, split the work into focused commits, and push to the current branch's upstream. If the push is rejected, stop and report; never force-push.

<!-- ai-rulebook:end-rule review -->

<!-- ai-rulebook:rule scope enabled -->

## Scope

- Change what the task requires plus the defect fixes below. No drive-by refactors, renames, reformatting, or version bumps.
- Before editing, read the relevant code, its tests, and the project's commands.
- Make the smallest complete change, verify it, and keep going until it is done or blocked by something concrete.
- Decide routine, reversible choices yourself by following project conventions. Ask only when the choice changes behavior, scope, compatibility, or cannot be undone.
- Tests and docs for your change are part of the task.
- Follow local naming, formatting, and structure, except where they conflict with safety, correctness, or verification.
- Fix defects you find while working, even outside the task (bugs, dead code, stale docs, wrong or broken tests), when the fix is small, local, and verified by the project's checks.
- Report a defect without fixing it when the fix would change a public interface or intended behavior, needs a migration or dependency change, is large, or needs a product decision.
- End with a report under these headings, omitting empty ones: **Changed**, **Also fixed**, **Checks** (each command run and its result), **Not done** (failing or unrun checks, blockers, defects reported but not fixed).

<!-- ai-rulebook:end-rule scope -->

<!-- ai-rulebook:rule tests enabled -->

## Tests

- Never describe an unrun check as passing. Report every failing test and every relevant check you did not run, and keep observed results apart from assumptions.
- Never weaken, skip, or disable a check to get a pass. When a requirement intentionally changes, update the obsolete expectation, say why, and keep coverage of behavior that is still required.
- For a behavior change, add or update a test at the level that exercises the requirement. Test observable behavior, not implementation details.
- For a bug fix, first reproduce the failure with a regression test when feasible.
- Put tests where the project already does, named the same way. Without a convention, colocate them using the ecosystem's suffix (`foo.test.ts`, `foo_test.go`).
- After a behavior change, run the project's test command. Before reporting done, run the existing lint and type checks and fix what you introduced.
- If no linter is configured, recommend one that suits the project and say why. Add it only when asked or approved.
- Before reporting done, read the final diff for unintended changes, debug code, secrets, and missing generated files.

<!-- ai-rulebook:end-rule tests -->
<!-- ai-rulebook:end -->
