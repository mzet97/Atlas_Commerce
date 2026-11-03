Feature: Reservation is authoritative under contention
  Scenario: UC003-T01 two buyers race for the final physical unit
    Given SKU "SKU-001" has on_hand 1, reserved 0 and safety_stock 0
    When both customers request reservation concurrently
    Then exactly one reservation becomes ACTIVE
    And the other returns an explicit OUT_OF_STOCK result
    And on_hand equals 1 and reserved equals 1
    And no confirmed order exists without valid reservation and payment

Feature: Financial operations are idempotent
  Scenario: UC003-T02 PSP sends the same approval webhook twice
    Given a payment intent exists with a valid idempotency key
    When the PSP sends the same signed approval webhook twice
    Then at most one corresponding capture is recognized
    And the order reaches a single terminal commercial outcome

Feature: Saga reconciles after outage
  Scenario: UC003-T03 payment approved but order service down
    Given payment approved and order service unavailable
    When the worker resumes
    Then the saga reconciles to confirmation or compensation
    And no silent loss occurs

Feature: Stale read never decides stock
  Scenario: UC003-T04 PostgreSQL projection is lagging
    Given the PostgreSQL projection is stale
    When checkout starts
    Then availability is revalidated at the authoritative Inventory

Feature: Out-of-order webhooks are safe
  Scenario: UC003-T05 duplicate and out-of-order PSP webhook
    Given a signed webhook arrives duplicated and out of order
    When processed
    Then invalid transitions are rejected
    And no duplicate refund or capture occurs

Feature: Catalog publication respects ownership and CQRS
  Scenario: ADM publishes product, storefront receives projection
    Given a catalog operator is allowed to publish in market BR
    And the new SKU has an approved offer and nonzero available inventory
    When the operator publishes via the Angular administrative portal
    Then the Control monolith dispatches the command to the catalog owner
    And the owner persists aggregate and outbox in one local transaction
    And a versioned Kafka event eventually updates the PostgreSQL read model
    And the Next.js storefront displays the correct published product

Feature: Administrative segregation of duties
  Scenario: ADM-05 requester tries to approve their own adjustment
    Given an operator requested stock adjustment on warehouse W1
    When the same operator attempts approval
    Then the action is denied and audited
    And the inventory aggregate is unchanged

Feature: Shopping AI cannot charge without confirmation
  Scenario: AI-06 untrusted description tries to bypass human approval
    Given a product description includes prompt-injection instructions
    When the customer asks the assistant to compare that product
    Then the assistant may cite authorized product information
    But cannot execute payment, grant permissions or mutate stock
    And any cart mutation requires explicit customer confirmation
