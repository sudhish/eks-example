{{
    config(
        materialized='view'
    )
}}

with source as (
    select * from {{ source('raw', 'customers_cdc') }}
),

latest_records as (
    select
        customer_id,
        email,
        first_name,
        last_name,
        phone,
        address,
        city,
        state,
        zip_code,
        country,
        created_at,
        updated_at,
        cdc_operation,
        cdc_timestamp,
        row_number() over (
            partition by customer_id
            order by cdc_timestamp desc
        ) as rn
    from source
),

final as (
    select
        customer_id,
        email,
        first_name,
        last_name,
        phone,
        address,
        city,
        state,
        zip_code,
        country,
        created_at,
        updated_at,
        cdc_operation,
        cdc_timestamp
    from latest_records
    where rn = 1
        and cdc_operation != 'DELETE'
)

select * from final
