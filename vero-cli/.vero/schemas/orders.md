# Table: `orders`

## Columns

| Column Name | Data Type | Nullable | Default |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | True | None |
| `customer_id` | `INTEGER` | True | None |
| `amount` | `REAL` | True | None |
| `status` | `TEXT` | True | None |
| `created_at` | `TEXT` | True | None |

## Relationships & Foreign Keys

- `['customer_id']` -> `customers(['id'])`
