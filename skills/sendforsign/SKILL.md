---
name: sendforsign
description: Create contracts from templates, fill their fields, add signers and collect e-signatures with Sendforsign, through its MCP server (tools like list_templates, create_contract, send_for_signature) or its REST API (api.sendforsign.com). Use when the user asks to draft, prepare, send, track or download a contract, NDA, agreement or offer for signature, to embed signing links in a product, or to integrate Sendforsign in code.
---

# Sendforsign

Sendforsign turns contract templates into signed agreements: pick a template, fill the owner's fields, add recipients
(signers, approvers, viewers), send or hand out signing links, and get notified when everyone has signed.

Docs: https://about.sendforsign.com (append `.md` to any page for Markdown; full reference in
https://about.sendforsign.com/llms-full.txt).

## Choose the interface

- **MCP tools available** (names like `list_templates`, `create_contract`, `send_for_signature`): use them. The server
  enforces the user's mode and allowlist; call `get_connection_info` first if unsure what is allowed.
- **Writing code** for an integration: use the REST API, `POST https://api.sendforsign.com/api/<resource>` with body
  `{"data": {"action": "...", "clientKey": "...", ...}}` and header `X-Sendforsign-Key`. Never hardcode the key; read
  it from the environment.
- **Neither configured**: tell the user how to connect the MCP server
  (`claude mcp add --transport http sendforsign https://api.sendforsign.com/mcp --header "X-Sendforsign-Key: ..." --header "X-Sendforsign-Client-Key: ..."`)
  instead of guessing credentials.

## Rules

1. **Never email anyone without explicit approval.** Before `send_for_signature` (or REST `recipient` `send`, or
   `contract` `create` with recipients), show the contract name, the filled values, every recipient's name, email and
   role, and ask. Pass `confirm: true` only after the user says yes in this conversation. Approval for one contract is
   not approval for the next.
2. **Prefer templates.** For a standard document, `list_templates` first; draft from scratch only if nothing fits or
   the user asks. Do not invent legal terms the user did not ask for.
3. **Fill only the owner's fields.** Fields have `filledBy`: `owner` (you fill), `any_recipient` / `specific_recipient`
   (the signer fills, leave empty), `none` (fixed). Ask the user for owner values you don't know; don't make them up.
4. **Archive only on request**, with `confirm: true` after approval.
5. If a tool returns `Blocked by policy`, do not retry or work around it. Explain the limit (mode, allowed domains) and
   offer the next step: share the signing links, or ask the account owner.
6. Signing links identify a recipient. Give each link only to that recipient.

## Recipe: template → fill → send (MCP)

1. `list_templates` → choose → `get_template {templateKey}`; note which fields are `owner`.
2. `create_contract {name, templateKey, fields:[{name|placeholderKey, value}], recipients:[{fullname, email, action:"sign"}]}`.
   This creates a **draft** and emails nobody. `fields` may use the template's `placeholderKey` or the field name. It
   returns `contractKey`, `recipients[].signingUrl`, `filled` (check for `ok: false`), `unfilledFields`.
3. Fill anything left in `unfilledFields` with `fill_placeholders {contractKey, fields:[...]}` (ask the user for values).
4. Summarise and ask for approval (rule 1).
5. `send_for_signature {contractKey, confirm: true}`.
6. Later: `get_contract_timeline {contractKey}`, `download_contract_pdf {contractKey}` when status is `Fully signed`.

## Recipe: embedded signing, no email

Use when the product shows the signing step itself. Create the draft and add recipients (`create_contract` with
`recipients`, or `add_recipients`), then give each signer their `signingUrl`
(`https://app.sendforsign.com/sharing/{recipientKey}`). Do not call `send_for_signature`.

## Recipe: multi-tenant product

Each customer is a client (`clientKey`) and optionally has users (`userKey`). Over MCP the tenant comes from the
`X-Sendforsign-Client-Key` / `X-Sendforsign-User-Key` headers; tools also accept `userKey`. `list_users` /
`create_user` manage users. Over REST, pass `clientKey` (and `userKey`) in `data`.

## Recipe: react to signatures (code)

Register a webhook per client: `POST /api/webhook` `{"data":{"action":"create","clientKey":"...","webhooks":[{"url":"...","fullySigned":true}]}}`.
On `status: "contract.fully_signed"`, download the PDF with `GET /api/download_pdf?clientKey=...&contractKey=...`.

## REST gotchas

- **`contract` `create` with a `recipients` array SENDS email immediately** (create-and-send). To prepare without
  emailing: `contract` `create` without recipients, then `recipient` `create`. `recipient` `send` emails.
- A contract from a template: `contract` `create` with `contract.templateKey`, then `placeholder` `list` on the new
  contract and `placeholder` `update` by the **contract's** `placeholderKey` (a new contract gets new field keys; match
  template fields by name). Don't rely on `placeholders` by name inside `contract` `create`.
- `recipient` `send`: give every recipient a `position` (1-based signing order).
- `placeholder` `update` only changes the fields you send. To unassign a recipient from a field, send
  `"externalRecipientKey": null` explicitly with the new `fillingType` (1 none, 2 owner, 3 any recipient, 4 specific
  recipient).
- Contract bodies are HTML. Placeholders appear in the body as tags like `<placeholder7 ...>value</placeholder7>`;
  change values through the placeholder API, never by editing the tags in the HTML.
- Responses carry `code` and `message`; check `code`, not only the HTTP status.
- Test with `@example.com` recipients and a `[TEST]` name prefix, and archive test contracts afterwards.

## Status values

`Created` → `Sent` → `Seen` → `Approved` / `Signed` → `Fully signed`; `Archived` when archived.
