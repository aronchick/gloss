# Security policy

## Report a vulnerability

Please do not open a public issue for a security vulnerability.

Use GitHub's **Report a vulnerability** flow in the repository Security tab. Include:

- the affected component and commit;
- a minimal reproduction or proof of concept;
- the expected impact;
- whether untrusted `.pptx` input is required;
- any suggested containment or fix.

If private vulnerability reporting is unavailable, contact the repository owner through the email address on their GitHub profile and ask for a private reporting channel. Do not attach a malicious deck to an unsolicited message.

## Scope

The most sensitive surfaces include ZIP/package extraction, XML parsing, LibreOffice rendering, container isolation, upload quarantine, webhook validation, authorization, and result publication.

The public `gloss.tools` launch page is static. The hosted grading service is pre-release and should not be treated as a production security boundary until a release announcement says otherwise.

## Response

Maintainers will acknowledge a complete report as soon as practical, reproduce it privately, and coordinate a fix and disclosure. Timelines depend on severity and maintainer availability.
