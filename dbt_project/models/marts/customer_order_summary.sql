{{
    config(
        materialized='table'
    )
}}

with orders as (
    select * from {{ ref('fact_orders') }}
),

customers as (
    select * from {{ ref('dim_customers_scd2') }}
    where is_current = true
),

final as (
    select
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.city,
        c.state,
        count(distinct o.order_id) as total_orders,
        sum(o.total_amount) as total_revenue,
        avg(o.total_amount) as avg_order_value,
        min(o.order_date) as first_order_date,
        max(o.order_date) as last_order_date,
        sum(case when o.order_status = 'completed' then 1 else 0 end) as completed_orders,
        sum(case when o.order_status = 'cancelled' then 1 else 0 end) as cancelled_orders
    from customers c
    left join orders o
        on c.customer_id = o.customer_id
    group by
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.city,
        c.state
)

select * from final
