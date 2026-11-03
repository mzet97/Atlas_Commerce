# atlas-platform-contracts

Versioned public contracts + shared scaffolding templates. NOT a domain
system: sharing a model across bounded contexts is forbidden except for
deliberately stable value objects. Consumers pin a version; N/N-1 compat.

```text
atlas-platform-contracts/
├── contracts/
│   ├── asyncapi/     # domain event envelopes (this increment)
│   ├── openapi/      # edge HTTP APIs (M1-next)
│   ├── proto/        # internal gRPC (M1-next, buf breaking checks)
│   └── jsonschema/   # projection/validation schemas (as needed)
├── templates/        # Copier fastapi-service / modular-monolith (M1-next)
├── infrastructure/   # base compose, IAM realm, telemetry (M1-next)
└── ci/               # contract-test harness (M1-next)
```

See [domain-event-envelope](contracts/asyncapi/domain-event-envelope.yaml).
