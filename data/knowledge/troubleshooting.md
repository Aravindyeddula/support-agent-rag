# Workflow troubleshooting runbook

## Failed workflows
For a failed workflow, open the execution log and identify the first failing step. Check input validation errors and the downstream service's response code. Collect the workflow ID, execution ID, request ID, and UTC timestamp. Remove secrets before sharing log excerpts.

## HTTP 5xx errors
Repeated HTTP 5xx errors can indicate an upstream or Nimbus service problem. Retry idempotent requests with exponential backoff and jitter. Do not automatically retry a non-idempotent operation unless it uses an idempotency key. If errors continue for more than ten minutes, prepare a high-priority engineering escalation with request IDs and the affected workflow IDs.

## Escalation priority
Use urgent priority for suspected unauthorized access or a total administrator lockout. Use high priority for a confirmed duplicate charge or persistent service errors affecting production workflows. Use normal priority for configuration questions and isolated failures. A person must review the draft before a ticket is created.
