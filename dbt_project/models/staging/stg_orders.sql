{{
    config(
        materialized='view'
    )
}}

with source as (
    select * from {{ source('raw', 'orders_cdc') }}
),

latest_records as (
    select
        order_id,
        customer_id,
        order_date,
        order_status,
        total_amount,
        created_at,
        updated_at,
        cdc_operation,
        cdc_timestamp,
        row_number() over (
            partition by order_id
            order by cdc_timestamp desc
        ) as rn
    from source
),

final as (
    select
        order_id,
        customer_id,
        order_date,
        order_status,
        total_amount,
        created_at,
        updated_at,
        cdc_operation,
        cdc_timestamp
    from latest_records
    where rn = 1
        and cdc_operation != 'DELETE'
)

select * from final
