# Architecture notes

## Bounded contexts

- `research`: sessions, plans, events, reports, and agent orchestration
- `companies`: company identity, profile, and market metadata
- `intelligence`: news, SEC filings, source provenance, and memory retrieval
- `portfolio`: saved holdings and alerts

The API is versioned under `/api/v1`. Agent execution will expose durable events, allowing the web client to stream task progress without revealing private model reasoning.

## Design principles

1. Agents produce structured artifacts, not unbounded text.
2. External facts must retain a source, timestamp, and tool provenance.
3. Long-running research is asynchronous and resumable.
4. Recommendation output is decision support, not investment advice.
