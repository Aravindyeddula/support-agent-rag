# API rate limits

## Limits by plan
Nimbus API requests are limited per workspace: Starter allows 60 requests per minute, Team allows 300 requests per minute, and Enterprise allows 1,000 requests per minute. These are fictional product limits for this demo. The limit is shared across all API keys in the same workspace.

## Handling HTTP 429
HTTP 429 means the workspace request rate limit was exceeded. Honor the Retry-After response header before retrying. Use exponential backoff with jitter and cap retries at five attempts. Queue bursts instead of repeatedly sending the same request. Retrying immediately can extend the throttling period.

## Escalation details
If HTTP 429 persists below the documented workspace limit, collect the workspace ID, request IDs, UTC timestamps, and approximate request rate. Prepare an escalation with normal priority. Never include API keys or Authorization headers in the ticket.
