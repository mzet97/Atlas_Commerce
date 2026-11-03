Feature: Catalog slice respects ownership and CQRS
  Scenario: Admin publishes, storefront shows, out-of-scope is denied
    Given cara.catalog has role catalog_editor and alice.customer does not
    When cara creates a product via the Control command channel
    Then the owner persists aggregate and outbox in one transaction
    When cara publishes version 1
    Then the owner confirms PUBLISHED version 2
    And the relay drains the outbox and the projector upserts the read model
    And the Next.js storefront lists the published title
    When alice tries the same create
    Then she gets 403 and an audit row with result denied

Feature: Concurrent writers do not duplicate
  Scenario: UC003-T01 adapted — 20 concurrent creates, one key
    Given one idempotency key and 20 concurrent POSTs
    When all requests race
    Then all return 201 with the same product id
    And exactly one product row exists for that key

Feature: Duplicate delivery never duplicates the view
  Scenario: Relayed event applied twice
    Given a published outbox event
    When the projector applies it twice
    Then one catalog_product_search row and one processed_events row exist
