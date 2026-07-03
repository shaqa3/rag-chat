# Nimbus API and Rate Limits

The Nimbus HTTP API lets you read and write notes programmatically. All requests
go to `https://api.nimbus.app/v1` and must include a personal access token in an
`Authorization: Bearer <token>` header. Tokens are created in Settings → API and
can be scoped to read-only or read-write.

Rate limits depend on your plan. Free tokens are limited to **60 requests per
minute**; Pro tokens to **600 requests per minute**; Team tokens to **1,000
requests per minute** per token. Every response includes `X-RateLimit-Remaining`
and `X-RateLimit-Reset` headers. When you exceed the limit the API returns HTTP
status **429** with a `Retry-After` header telling you how many seconds to wait.

The API paginates list endpoints with a `cursor` query parameter; a page returns
up to 100 items plus a `next_cursor` field, which is null on the last page.
Webhooks can be registered to receive `note.created`, `note.updated`, and
`note.deleted` events; Nimbus retries a failing webhook up to 5 times with
exponential backoff before marking the endpoint as unhealthy.

Uploads are capped at 100 MB per attachment on Pro and Team, and 25 MB on Free.
Requests larger than the cap return HTTP status 413.
