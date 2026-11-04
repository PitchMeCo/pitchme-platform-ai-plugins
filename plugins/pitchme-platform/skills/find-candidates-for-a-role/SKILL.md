---
name: find-candidates-for-a-role
description: Find candidates for a role in PitchMe. Use when the person has a job brief and wants an estimate, a search, and an optional shortlist.
---

# Find candidates for a role

Use this skill when the person wants candidates for a role.

## Inputs

- Whether to open an existing hiring project or create a new one.
- A description of the person, or a job description, before a new project or a new search.

## Steps

1. Ask the person to open an existing hiring project or create a new one. Do not choose the project for them.
2. For a new project, get the description first. Then create the project only after they confirm the name and the description.
3. Call `expand_brief` with that description.
4. Call `estimate_search`. Tell the person both numbers: the external pool and the internal talent pool.
5. Call `start_search` only after they have seen both numbers and asked to start.
6. Call `list_search_candidates`. For each person, show location, current position, current company, whether they are already in the account, and the match summary.
7. Call `shortlist_person` only when the person asks to shortlist someone. Shortlisting does not spend a credit.

## Outputs

The estimate, the search, and the candidate list. A shortlist entry only when they asked for one.

## Errors

If a call returns an error, show the code, the message, and the trace id. Ask whether to retry or open a support ticket. Do not invent a project id, a search id, or a person. Do not call `reveal_contacts` from this skill.
