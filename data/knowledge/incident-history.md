# Historical incident: delayed webhooks

## Incident summary
This is a fictional historical incident, not a live status feed. On September 14, 2026, webhook delivery in the US East region was delayed between 13:10 and 14:35 UTC. The incident was resolved at 14:35 UTC after workers were restarted and the delivery queue drained. Workflow execution itself was unaffected.

## Customer follow-up
For this historical incident, administrators were advised to inspect delivery logs and confirm that each event_id had arrived. Events still marked failed could be replayed after checking that the receiving endpoint was healthy. The customer should deduplicate replays by event_id. Do not infer current service health from this incident record.
