# Security and data retention

## Demonstration policy
This document describes the fictional Nimbus product. It is source material for retrieval experiments, not a statement about the Atlas application's security controls. Nimbus policy specifies encryption in transit using TLS and encryption at rest for stored workspace data.

## Retention and deletion
Workflow execution logs are retained for 30 days on Starter and Team plans. Enterprise retention is set by the workspace agreement. Workspace deletion requests require verification by the account team and have a 30-day processing window. Support must not promise immediate deletion or claim a deletion has completed without confirmation.

## Incident reporting
Suspected unauthorized access should be escalated urgently to the security team. Collect the workspace ID, relevant UTC timestamps, and a description of observed activity. Never request passwords, API keys, session cookies, or full payment details. Do not attach sensitive customer documents to an escalation without an approved process.
