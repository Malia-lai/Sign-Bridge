# WebSocket Protocol

Endpoint: `/ws/sentence` (also `/api/ws/sentence`, `/v1/ws/sentence`)

## Authentication
If `API_KEY` is configured, pass it as `?token=<key>` or `?api_key=<key>` or `X-API-Key` header.

## Client messages
- `{"type":"ping"}` -> server responds `{"type":"pong"}`
- `{"type":"sentence","words":[...],"language":"English","timeout":30,"stream":false}`

## Server messages
- `{"type":"result","data":{...SentenceResponse...}}`
- `{"type":"partial","data":{...}}` when `stream:true`
- `{"type":"error","error":"..."}`

## Heartbeat and reconnection
Clients should send periodic `ping` messages and expect `pong`. If the connection drops, reconnect with exponential backoff and resend the last unacknowledged request. The server is stateless per request; clients should track request IDs and deduplicate results.

## Backpressure
The server disconnects clients that cannot receive messages within the send timeout.