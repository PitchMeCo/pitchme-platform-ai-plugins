---
name: get-started
description: Show who is signed in to PitchMe and what this session can do. Use after install and when the person asks who is signed in.
---

# Get started

Use this skill when the plugin is installed, or when the person asks who is signed in.

## Inputs

No extra input. The PitchMe sign-in is already on the session.

## Steps

1. Call `who_is_signed_in`.
2. Tell the person the account and the group from that result.
3. Say that this session stays in that account and group. Another account or group needs a new sign-in.
4. Say what they can do next: search talent, run a hiring project, read the contract and Sonar balance, or open a support ticket.

## Outputs

The signed-in account and group, and the short list of next steps.

## Errors

If `who_is_signed_in` returns an error, show the code, the message, and the trace id from the result. Ask whether to retry or open a support ticket. Do not invent an account id.
