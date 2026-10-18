# Webhook delivery and integrations

## Delivery contract
Nimbus sends a signed webhook when a workflow completes. A destination must return a 2xx response within five seconds. Deliveries are retried after one minute, five minutes, and thirty minutes. Each payload has an event_id that remains constant across retries. Consumers should deduplicate by event_id.

## Signature verification
Verify the X-Nimbus-Signature HMAC-SHA256 signature using the webhook signing secret and the exact raw request body. Reject invalid signatures. Do not verify a parsed and reserialized JSON body because its bytes can differ from the signed body. Signing secrets must not be added to support tickets.

## Failed deliveries
Use Integrations, then Delivery Logs to inspect the response code and attempt timestamps. After fixing the endpoint, a workspace administrator can replay a failed event from the delivery log. A support copilot can explain this procedure or draft an escalation; it cannot replay events itself.
