# Coin Analyzer Public / Private IP Boundary

## Goal

Keep the public repository useful as a portfolio, engineering record, and collaboration surface without assuming that every future commercial or technically sensitive asset should be public.

## Public repository

Appropriate public material includes:

- application code intentionally released under the repository licence;
- architecture and design documents intended for public review;
- tests and CI configuration;
- portfolio-facing release evidence;
- synthetic fixtures that contain no private collector data;
- public API integration code that contains no credentials or restricted data.

Anything committed publicly should be treated as disclosed. Do not classify already-public source as a trade secret.

## Private "crown jewels"

Keep the following private unless there is a deliberate release decision:

- proprietary or licensed datasets that cannot be redistributed;
- collector/customer data and private images;
- credentials, API keys, tokens, private endpoints, or secrets;
- unpublished recognition heuristics whose secrecy provides commercial value;
- proprietary evaluation/golden datasets;
- unreleased model weights, prompt/configuration systems, or tuning recipes with commercial value;
- security-sensitive operational details beyond what is appropriate for responsible disclosure;
- commercial strategy, pricing, partner terms, and confidential due-diligence material;
- patent-sensitive inventions before patent strategy has been considered.

## Development rule

Before adding a new asset, ask:

1. Do we own it or have permission to use it?
2. Can it legally be redistributed?
3. Does making it public destroy useful confidentiality?
4. Does it contain personal, customer, security, or credential information?
5. Is it needed in the public repository at all?

If any answer creates uncertainty, keep the material out of the public repository until reviewed.

## Architecture rule

Prefer interfaces that allow private components to plug into the public application without requiring their implementation, datasets, credentials, or model assets to live in the public repository.

## Human authority

Moving material from private to public is a deliberate release decision. Automated agents may recommend disclosure or packaging changes but must not publish confidential assets, change repository visibility, or alter licensing without repository-owner approval.
