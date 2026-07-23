# DeskFlow: product write-up

DeskFlow is a small coworking operations product for quoting, confirming and cancelling workspace reservations while reporting revenue by the operator’s local calendar day.

I built it because booking systems become difficult at their boundaries: overlapping reservations, browser and workspace time zones, bookings crossing midnight, occupancy-based pricing and money that must remain exact.

The main decisions were mine: storing prices as integer VND, separating quotes from confirmed bookings, normalising offset-aware timestamps, allocating midnight-crossing revenue without inventing or losing a dong, and using PostgreSQL row locking to reduce concurrent booking conflicts.

I deliberately kept authentication, payments and multi-tenancy outside the MVP so I could test the booking rules deeply. Nineteen automated tests cover pricing, validation, overlap boundaries, cancellation, time zones and revenue conservation.

The deployed stack is FastAPI, SQLAlchemy, TypeScript/Vite, Neon PostgreSQL and Vercel.
