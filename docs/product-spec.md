# Product brief

Coworking operators lose revenue when availability is unclear, bookings overlap, or every hour is priced identically. DeskFlow explores a compact booking flow that can explain its pricing and remain correct across timezone boundaries.

## MVP user stories

- An operator can create a space with a local timezone and integer VND hourly rate.
- A customer can request a quote for an offset-aware time interval.
- The system prevents overlapping confirmed bookings and permits back-to-back boundaries.
- A customer or operator can cancel a booking and release the interval.
- An operator can view bookings, booked hours and revenue for a chosen local calendar day.

## Current pricing experiment

- Under 50% occupancy: base price.
- From 50% to under 80%: 1.15x.
- At or above 80%: 1.35x.
- Saturday and Sunday in the workspace timezone: additional 0.90x multiplier.

The weekend discount is intentionally debatable. It assumes demand is lower outside the working week. A real product should make the rule configurable and test conversion rather than treating it as universal truth.

## Questions to investigate

- Does occupancy-based pricing increase revenue without reducing conversion?
- Which rules should be visible or editable by operators?
- Should the API hold a short-lived quote before checkout?
- How should opening hours and public holidays interact with timezone rules?
- Should cancellation release inventory immediately or follow a refund policy state machine?
