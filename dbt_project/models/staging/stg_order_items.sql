{{
    config(
        materialized='view'
    )
}}

with source as (
    select * from {{ source('raw', 'order_items_cdc') }}
),

latest_records as (
    select
        order_item_id,
        order_id,
        product_name,
        quantity,
        unit_price,
        created_at,
        updated_at,
        cdc_operation,
        cdc_timestamp,
        row_number() over (
            partition by order_item_id
            order by cdc_timestamp desc
        ) as rn
    from source
),

final as (
    select
        order_item_id,
        order_id,
        product_name,
        quantity,
        unit_price,
        created_at,
        updated_at,
        cdc_operation,
        cdc_timestamp
    from latest_records
    where rn = 1
        and cdc_operation != 'DELETE'
)

select * from final
