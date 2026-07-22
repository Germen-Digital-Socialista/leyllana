# 0009 — License: AGPL-3.0

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** Felipe Carvajal Brown

## Context

The repository needs a license from the first commit. The choice carries the
org's stance on software freedom. Note: this decision is about project fit, not
legal advice; a qualified lawyer should confirm licensing questions that matter.

## Decision

License leyllana under **AGPL-3.0** (GNU Affero General Public License v3.0).

AGPL-3.0 is strong copyleft and additionally closes the "SaaS loophole": anyone
who runs a modified version as a network service must share their source. For a
socialist, anti-enclosure org, this is the closest fit — the tool and its forks
stay free and open even when hosted.

## Consequences

- Forks and network-hosted derivatives must remain open under the same license.
- Contributors and users know the tool cannot be quietly enclosed in a
  proprietary product or SaaS.
- Some organizations avoid AGPL dependencies by policy; accepted, given leyllana
  is an end-user desktop app, not a library meant for wide embedding.

## Alternatives considered

- **GPL-3.0** — strong copyleft for desktop, but no network/SaaS clause.
- **MIT** — maximal adoption, but permits proprietary enclosure; weak fit for the
  org's ethos.
