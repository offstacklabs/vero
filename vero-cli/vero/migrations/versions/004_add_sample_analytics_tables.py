"""Add sample analytics warehouse tables (customers, products, orders, order_items)

Revision ID: 004_add_sample_analytics
Revises: 003_add_users_and_auth
Create Date: 2026-10-11 14:00:00

"""
from typing import Sequence, Union
from datetime import datetime, date, timezone
from alembic import op
import sqlalchemy as sa

revision: str = '004_add_sample_analytics'
down_revision: Union[str, None] = '003_add_users_and_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Customers Table
    if 'customers' not in existing_tables:
        customers_table = op.create_table(
            'customers',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=150), nullable=False, unique=True),
            sa.Column('plan', sa.String(length=50), nullable=False, server_default='Starter'),
            sa.Column('country', sa.String(length=50), nullable=False, server_default='United States'),
            sa.Column('created_at', sa.DateTime(), nullable=True)
        )

        op.bulk_insert(
            customers_table,
            [
                {'id': 1, 'name': 'Acme Corp', 'email': 'contact@acme.com', 'plan': 'Enterprise', 'country': 'United States', 'created_at': datetime(2025, 1, 15, 10, 0)},
                {'id': 2, 'name': 'Globex Industries', 'email': 'billing@globex.de', 'plan': 'Enterprise', 'country': 'Germany', 'created_at': datetime(2025, 2, 1, 11, 30)},
                {'id': 3, 'name': 'Soylent Media', 'email': 'ops@soylent.com', 'plan': 'Pro', 'country': 'United States', 'created_at': datetime(2025, 2, 20, 9, 15)},
                {'id': 4, 'name': 'Initech Software', 'email': 'peter@initech.com', 'plan': 'Pro', 'country': 'United States', 'created_at': datetime(2025, 3, 5, 14, 20)},
                {'id': 5, 'name': 'Umbrella Labs', 'email': 'procurement@umbrella.co.uk', 'plan': 'Enterprise', 'country': 'United Kingdom', 'created_at': datetime(2025, 3, 12, 16, 45)},
                {'id': 6, 'name': 'Hooli Cloud', 'email': 'gavin@hooli.com', 'plan': 'Enterprise', 'country': 'United States', 'created_at': datetime(2025, 4, 1, 8, 0)},
                {'id': 7, 'name': 'Massive Dynamic', 'email': 'walter@massivedynamic.com', 'plan': 'Enterprise', 'country': 'United States', 'created_at': datetime(2025, 4, 18, 13, 10)},
                {'id': 8, 'name': 'Stark Logistics', 'email': 'tony@stark.com', 'plan': 'Enterprise', 'country': 'United States', 'created_at': datetime(2025, 5, 2, 17, 0)},
                {'id': 9, 'name': 'Wayne Tech', 'email': 'bruce@wayne.com', 'plan': 'Enterprise', 'country': 'United States', 'created_at': datetime(2025, 5, 19, 19, 30)},
                {'id': 10, 'name': 'Cyberdyne Systems', 'email': 'miles@cyberdyne.jp', 'plan': 'Starter', 'country': 'Japan', 'created_at': datetime(2025, 6, 1, 10, 15)}
            ]
        )

    # 2. Products Table
    if 'products' not in existing_tables:
        products_table = op.create_table(
            'products',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('price', sa.Numeric(10, 2), nullable=False),
            sa.Column('cost', sa.Numeric(10, 2), nullable=False)
        )

        op.bulk_insert(
            products_table,
            [
                {'id': 1, 'name': 'Vero Enterprise Server', 'category': 'Software', 'price': 4999.00, 'cost': 500.00},
                {'id': 2, 'name': 'Vero Cloud Agent (Annual)', 'category': 'SaaS', 'price': 1200.00, 'cost': 150.00},
                {'id': 3, 'name': 'Dedicated BigQuery Connector', 'category': 'Connector', 'price': 450.00, 'cost': 50.00},
                {'id': 4, 'name': 'Snowflake Compute Bridge', 'category': 'Connector', 'price': 450.00, 'cost': 50.00},
                {'id': 5, 'name': 'Autonomous RCA Diagnostic Engine', 'category': 'Add-on', 'price': 850.00, 'cost': 100.00},
                {'id': 6, 'name': 'Data Governance & PII Masker', 'category': 'Security', 'price': 950.00, 'cost': 80.00},
                {'id': 7, 'name': 'Priority 24/7 Support SLA', 'category': 'Support', 'price': 2500.00, 'cost': 600.00},
                {'id': 8, 'name': 'Embedded Analytics SDK License', 'category': 'Developer', 'price': 3500.00, 'cost': 300.00},
                {'id': 9, 'name': 'Custom LookML Semantic Migration', 'category': 'Services', 'price': 1800.00, 'cost': 700.00},
                {'id': 10, 'name': 'Single Sign-On (Okta / Azure AD)', 'category': 'Security', 'price': 600.00, 'cost': 40.00}
            ]
        )

    # 3. Orders Table
    if 'orders' not in existing_tables:
        orders_table = op.create_table(
            'orders',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=False),
            sa.Column('order_date', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='Completed'),
            sa.Column('amount', sa.Numeric(10, 2), nullable=False)
        )

        op.bulk_insert(
            orders_table,
            [
                {'id': 101, 'customer_id': 1, 'order_date': date(2026, 1, 10), 'status': 'Completed', 'amount': 5449.00},
                {'id': 102, 'customer_id': 2, 'order_date': date(2026, 1, 14), 'status': 'Completed', 'amount': 6449.00},
                {'id': 103, 'customer_id': 3, 'order_date': date(2026, 1, 20), 'status': 'Completed', 'amount': 1200.00},
                {'id': 104, 'customer_id': 4, 'order_date': date(2026, 2, 1), 'status': 'Completed', 'amount': 2050.00},
                {'id': 105, 'customer_id': 5, 'order_date': date(2026, 2, 12), 'status': 'Completed', 'amount': 8449.00},
                {'id': 106, 'customer_id': 6, 'order_date': date(2026, 2, 28), 'status': 'Completed', 'amount': 4999.00},
                {'id': 107, 'customer_id': 7, 'order_date': date(2026, 3, 5), 'status': 'Completed', 'amount': 11949.00},
                {'id': 108, 'customer_id': 8, 'order_date': date(2026, 3, 15), 'status': 'Completed', 'amount': 4999.00},
                {'id': 109, 'customer_id': 9, 'order_date': date(2026, 3, 22), 'status': 'Completed', 'amount': 7499.00},
                {'id': 110, 'customer_id': 10, 'order_date': date(2026, 4, 1), 'status': 'Completed', 'amount': 1200.00},
                {'id': 111, 'customer_id': 1, 'order_date': date(2026, 4, 10), 'status': 'Completed', 'amount': 4350.00},
                {'id': 112, 'customer_id': 2, 'order_date': date(2026, 4, 18), 'status': 'Completed', 'amount': 950.00},
                {'id': 113, 'customer_id': 3, 'order_date': date(2026, 5, 2), 'status': 'Completed', 'amount': 1650.00},
                {'id': 114, 'customer_id': 5, 'order_date': date(2026, 5, 15), 'status': 'Completed', 'amount': 4999.00},
                {'id': 115, 'customer_id': 6, 'order_date': date(2026, 6, 1), 'status': 'Completed', 'amount': 3500.00},
                {'id': 116, 'customer_id': 7, 'order_date': date(2026, 6, 12), 'status': 'Shipped', 'amount': 4999.00},
                {'id': 117, 'customer_id': 8, 'order_date': date(2026, 6, 25), 'status': 'Shipped', 'amount': 850.00},
                {'id': 118, 'customer_id': 9, 'order_date': date(2026, 7, 4), 'status': 'Shipped', 'amount': 1800.00},
                {'id': 119, 'customer_id': 4, 'order_date': date(2026, 7, 15), 'status': 'Pending', 'amount': 1200.00},
                {'id': 120, 'customer_id': 10, 'order_date': date(2026, 7, 28), 'status': 'Pending', 'amount': 450.00}
            ]
        )

    # 4. Order Items Table
    if 'order_items' not in existing_tables:
        order_items_table = op.create_table(
            'order_items',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('sale_price', sa.Numeric(10, 2), nullable=False)
        )

        op.bulk_insert(
            order_items_table,
            [
                {'id': 1, 'order_id': 101, 'product_id': 1, 'quantity': 1, 'sale_price': 4999.00},
                {'id': 2, 'order_id': 101, 'product_id': 3, 'quantity': 1, 'sale_price': 450.00},
                {'id': 3, 'order_id': 102, 'product_id': 1, 'quantity': 1, 'sale_price': 4999.00},
                {'id': 4, 'order_id': 102, 'product_id': 6, 'quantity': 1, 'sale_price': 950.00},
                {'id': 5, 'order_id': 103, 'product_id': 2, 'quantity': 1, 'sale_price': 1200.00},
                {'id': 6, 'order_id': 104, 'product_id': 5, 'quantity': 1, 'sale_price': 850.00},
                {'id': 7, 'order_id': 105, 'product_id': 1, 'quantity': 1, 'sale_price': 4999.00},
                {'id': 8, 'order_id': 105, 'product_id': 7, 'quantity': 1, 'sale_price': 2500.00},
                {'id': 9, 'order_id': 106, 'product_id': 1, 'quantity': 1, 'sale_price': 4999.00},
                {'id': 10, 'order_id': 107, 'product_id': 8, 'quantity': 1, 'sale_price': 3500.00}
            ]
        )

def downgrade() -> None:
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('products')
    op.drop_table('customers')
