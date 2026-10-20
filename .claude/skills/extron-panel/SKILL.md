---
name: extron-panel
description: Use when creating, modifying or reviewing an Extron GUI Designer touch-panel (.gdl/.glt) — building a panel from a Claude Design canvas link or from a description, editing an existing client panel, checking a design against Extron's standards, or previewing what a panel will look like before it is built.
---

# Extron touch panels

The procedure lives in this repository's `SKILL.md`, at its root. Read it now
and follow it:

- **A Claude Design canvas** (a claude.ai link to a design made with the
  template's design system): `docs/claude-design.md` §1 *Build: in Claude Code*
  - read the canvas, translate it, build and verify every panel it lists, and
  put each artboard beside its built page for sign-off.
- **A description, or a spec**: `SKILL.md` workflow A.
- **An existing panel**: `SKILL.md` workflow B.

What needs GUI Designer installed, and what runs anywhere, is in `CLAUDE.md`
*Environment*.

This file's name and description are the root `SKILL.md`'s, word for word;
`tests/test_skill.py` fails when they differ, so change both together.
