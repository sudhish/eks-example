{{
    config(
        materialized='table'
    )
}}

with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select
        customer_sk,
        customer_id,
        valid_from,
        valid_to
    from {{ ref('dim_customers_scd2') }}
),

order_items as (
    select
        order_id,
        sum(quantity * unit_price) as calculated_total
    from {{ ref('stg_order_items') }}
    group by order_id
),

final as (
    select
        o.order_id,
        c.customer_sk,
        o.customer_id,
        o.order_date,
        o.order_status,
        o.total_amount,
        coalesce(oi.calculated_total, 0) as line_items_total,
        o.created_at,
        o.updated_at
    from orders o
    left join customers c
        on o.customer_id = c.customer_id
        and o.order_date >= c.valid_from
        and (o.order_date < c.valid_to or c.valid_to is null)
    left join order_items oi
        on o.order_id = oi.order_id
)

select * from final
