# Project Skills

This directory keeps project-local skills and imported skill packs together.

## Layout

- `CODEX.md`
  - Project-specific operating skill for this recipe chatbot.
  - Read this first when working in this repository.
  - Includes Google Cloud cost guardrails for staying in the free tier or under about 500 JPY/month.

- `ui-ux-pro-max-skill/`
  - Source: `https://github.com/nextlevelbuilder/ui-ux-pro-max-skill`
  - Imported commit: `d7e37dd3598de748a4ec789efc42cff0409a9ac0`
  - Local skill path: `ui-ux-pro-max-skill/skills/`
  - Use for UI/UX, design systems, visual styling, branding, slides, banners, and product interface decisions.

- `agent-skills/`
  - Source: `https://github.com/addyosmani/agent-skills`
  - Imported commit: `aba7c4e9695c363e65cb59effe926c7f1d1abe3d`
  - Local skill path: `agent-skills/skills/`
  - Use for engineering workflows such as specs, planning, incremental implementation, TDD, debugging, review, security, performance, CI/CD, and shipping.

## Usage

When starting work:

1. Read `SKILLS/CODEX.md`.
2. If the task is UI/design-heavy, read the relevant `SKILLS/ui-ux-pro-max-skill/skills/<name>/SKILL.md`.
3. If the task is engineering-process-heavy, read the relevant `SKILLS/agent-skills/skills/<name>/SKILL.md`.
4. Keep cloud-cost-sensitive work aligned with `SKILLS/CODEX.md`.

These files are vendored into this repository. They are not automatically synced with upstream.

## Updating Vendored Skills

To update a source pack, clone the upstream repository into `/private/tmp`, replace only the corresponding local subtree, and update the imported commit SHA above. Do not overwrite `SKILLS/CODEX.md` when refreshing third-party skills.

