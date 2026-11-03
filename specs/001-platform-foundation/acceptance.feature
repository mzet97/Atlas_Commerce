Feature: Foundation smoke is real
  Scenario: Health, trace, auth and contracts
    Given the core profile is up
    When GET /health is called on smoke-api
    Then status is ok with mongo ok, redis ok and a trace_id
    And that trace_id is searchable in Tempo
    And a customer JWT carries role customer and introspect active true
    And actionlint passes on all 3 workflows
    And the contracts check parses every yaml and enforces INV-010 fields
