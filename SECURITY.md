<!-- Adapted from ELI_Legal: SECURITY.md @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes. -->
# Security policy

ELI Creation Station runs models on people's machines, reads files they choose and, when allowed,
their screen, so a weakness in it matters. Please report one privately, and please do not open a
public issue for it.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository:
**[Report a vulnerability](https://github.com/ShadowESC95/ELI_Creation_Station/security/advisories/new)**
(the Security tab, then *Report a vulnerability*). Only the maintainer sees the report.

Please include the version (`eli-creation --version`), how it was installed, what an attacker could
do and what they need first, and the steps to reproduce it. Never send personal data or
credentials in a report.

## What happens next

| Step | When |
|---|---|
| Acknowledgement | within 5 working days |
| First assessment: confirmed or not, and how severe | within 10 working days |
| A fix, or a mitigation you can apply, for a confirmed high or critical issue | as soon as it is ready, normally within 30 days |
| Public advisory and credit (if you want it) | when the fix is released, or after 90 days, whichever is first |

A vulnerability that is being **actively exploited** is notified as the EU Cyber Resilience Act
requires (Regulation (EU) 2024/2847, Art. 14): an early warning within 24 hours of becoming aware.

## Supported versions

Security fixes are made in the latest release. Upgrade to the latest.
