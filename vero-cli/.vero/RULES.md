# Vero Analytics Rules

## SQL Guidelines
- Always use explicit column names instead of `SELECT *`.
- For date filtering, prefer standard ISO dates (`YYYY-MM-DD`).
- Always provide clean aliases for aggregated metrics (e.g. `COUNT(*) AS total_orders`).
- Default to `LIMIT 50` unless otherwise specified by the user.
