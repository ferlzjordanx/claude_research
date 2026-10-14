# Orders API — Runbook

Owner: reports team · Dashboard: "Orders API / RED" · SLO: 99.5% of
requests succeed and p95 < 300 ms over 28 days.

First 5 minutes, always: (1) check what changed (deploys, flags,
traffic, dependency status), (2) look at the RED dashboard by route,
(3) mitigate before root-causing (rollback, scale, disable feature).

## Queries used below (PromQL)

```text
RATE   sum by (route) (rate(http_requests_total[5m]))
ERR    sum by (route) (rate(http_requests_total{status=~"5.."}[5m]))
       / sum by (route) (rate(http_requests_total[5m]))
P95    histogram_quantile(0.95, sum by (le, route)
         (rate(http_request_duration_seconds_bucket[5m])))
BUSY   http_requests_in_flight
```

## 1. Latency high on many routes at once

```text
SYMPTOM  P95 up on all routes; BUSY climbing; CPU may be low
QUERY    P95 by route; BUSY; traces: long gaps with no child span
CAUSES   blocking call in async def (event loop stalled);
         threadpool or DB pool exhausted; noisy neighbour / CPU
ACTIONS  py-spy dump --pid <pid>  (look for time.sleep, requests,
         sync drivers on the MainThread); roll back last deploy;
         scale out as a stopgap; fix with asyncio.to_thread / def
```

## 2. Latency high on one route only

```text
SYMPTOM  P95 up for one route; others normal
QUERY    P95{route="..."}; slowest traces for that route
CAUSES   N+1 queries (many short SELECT spans); missing index;
         slow dependency span; payload grew (more rows)
ACTIONS  count DB spans per trace; EXPLAIN the slow query;
         add eager load / aggregate query / index; add pagination
```

## 3. 504 / 502 errors on /reports/revenue-fx

```text
SYMPTOM  ERR up; problem+json "Gateway Timeout" or "Bad Gateway"
QUERY    ERR{route="/reports/revenue-fx"}; fx.get_rate span errors
CAUSES   FX provider slow or down; network/DNS; our timeout too low
ACTIONS  check provider status page; confirm with curl from the pod;
         keep the timeout (it protects us); serve cached rates or
         degrade the feature; tell the customer it is upstream
```

## 4. Requests hang, then many fail together

```text
SYMPTOM  BUSY near the worker limit; timeouts at the load balancer
CAUSES   outbound call without timeout; pool exhausted waiting on
         a hung dependency; DB lock
ACTIONS  verify every client has a timeout; check pool metrics;
         restart only as mitigation; add timeout + circuit breaker
```

## 5. Prometheus slow or memory high (metrics cardinality)

```text
SYMPTOM  scrape slow; TSDB memory up; "too many series" alerts
QUERY    topk(10, count by (__name__)({__name__=~".+"}))
         count by (route) (http_requests_total)
CAUSES   raw paths/IDs/user emails as label values
ACTIONS  label by route template; unmatched -> "<unmatched>";
         drop the label with relabeling until the fix ships
```

## 6. Can't find a user's failed request

```text
SYMPTOM  customer reports an error at 10:42, no matching log line
CHECK    ask for the X-Request-ID from the error body; search logs
         by request_id, then open the trace by trace_id
CAUSES   log sampling dropped it; error before our middleware (LB)
ACTIONS  check LB logs; never sample out errors; log 5xx always
```

## After the incident

Blameless postmortem within 5 working days: timeline, impact (SLO
budget burned), root cause (5 whys), what went well, action items
with owners. Add a test or alert that would have caught it.
