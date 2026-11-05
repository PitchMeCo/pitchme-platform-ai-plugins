---
name: reveal-contacts-safely
description: Reveal one person's contacts in PitchMe after checking the Sonar balance and getting an explicit yes. Use only when the person asks to reveal a contact.
---

# Reveal contacts safely

Use this skill only when the person asks to reveal a contact.

## Inputs

- The person to reveal. They must already be on a project shortlist.
- An explicit yes after the credit cost is stated. Silence is not a yes.

## Steps

1. Call `read_contract_and_credits`.
2. Tell the person the current Sonar balance.
3. Say that revealing this one person spends one Sonar credit.
4. Wait for an explicit yes that names the person. Do not reveal a list on your own. Do not reveal when they did not ask.
5. Call `reveal_contacts` once for that person.
6. If they name another person, repeat from step 3. One call reveals one person.

## Outputs

The credit balance before the reveal, and the contact result the server returned for each person they approved.

## Errors

If the balance call or the reveal returns an error, show the code, the message, and the trace id. Do not retry a reveal unless they ask. A failed reveal may already have spent a credit, so say that and ask before trying again. Do not invent an email address or a phone number.
