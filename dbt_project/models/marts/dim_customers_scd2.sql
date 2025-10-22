{{
    config(
        materialized='incremental',
        unique_key='customer_sk'
    )
}}

with source_data as (
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
        cdc_timestamp
    from {{ ref('stg_customers') }}
),

{% if is_incremental() %}

existing_records as (
    select
        customer_sk,
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
        valid_from,
        valid_to,
        is_current
    from {{ this }}
),

changed_records as (
    select
        s.customer_id,
        s.email,
        s.first_name,
        s.last_name,
        s.phone,
        s.address,
        s.city,
        s.state,
        s.zip_code,
        s.country,
        s.cdc_timestamp,
        e.customer_sk,
        e.valid_from
    from source_data s
    inner join existing_records e
        on s.customer_id = e.customer_id
        and e.is_current = true
    where
        s.email != e.email
        or s.first_name != e.first_name
        or s.last_name != e.last_name
        or s.phone != e.phone
        or s.address != e.address
        or s.city != e.city
        or s.state != e.state
        or s.zip_code != e.zip_code
        or s.country != e.country
),

-- Close out changed records
expired_records as (
    select
        customer_sk,
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
        valid_from,
        current_timestamp as valid_to,
        false as is_current
    from existing_records
    where customer_id in (select customer_id from changed_records)
        and is_current = true
),

-- Create new versions for changed records
new_versions as (
    select
        {{ dbt_utils.generate_surrogate_key(['customer_id', 'cdc_timestamp']) }} as customer_sk,
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
        cdc_timestamp as valid_from,
        null::timestamp as valid_to,
        true as is_current
    from changed_records
),

-- New customers
new_customers as (
    select
        {{ dbt_utils.generate_surrogate_key(['s.customer_id', 's.created_at']) }} as customer_sk,
        s.customer_id,
        s.email,
        s.first_name,
        s.last_name,
        s.phone,
        s.address,
        s.city,
        s.state,
        s.zip_code,
        s.country,
        s.created_at as valid_from,
        null::timestamp as valid_to,
        true as is_current
    from source_data s
    left join existing_records e
        on s.customer_id = e.customer_id
    where e.customer_id is null
),

-- Unchanged current records
unchanged_records as (
    select
        customer_sk,
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
        valid_from,
        valid_to,
        is_current
    from existing_records
    where customer_id not in (select customer_id from changed_records)
        and is_current = true
),

final as (
    select * from expired_records
    union all
    select * from new_versions
    union all
    select * from new_customers
    union all
    select * from unchanged_records
)

{% else %}

-- Initial load
final as (
    select
        {{ dbt_utils.generate_surrogate_key(['customer_id', 'created_at']) }} as customer_sk,
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
        created_at as valid_from,
        null::timestamp as valid_to,
        true as is_current
    from source_data
)

{% endif %}

select * from final
