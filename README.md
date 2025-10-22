# DBT CDC Demo Application

A comprehensive demonstration of Change Data Capture (CDC) and Slowly Changing Dimensions (SCD) using DBT, Postgres, DuckDB, and Iceberg-compatible formats.

## Overview

This project demonstrates a modern data pipeline that:

- **Simulates CDC events** in a Postgres source database
- **Captures changes** using a high-water mark CDC pattern
- **Lands data** in DuckDB with Iceberg-compatible structure (Parquet format)
- **Transforms data** using DBT with SCD Type 2 dimensions
- **Orchestrates** the entire pipeline using Python and Docker

## Architecture

```
┌─────────────────┐
│    Postgres     │  Source Database
│  (Source Data)  │  - Customers
│                 │  - Orders
└────────┬────────┘  - Order Items
         │
         │ CDC Extraction
         │ (Python)
         ▼
┌─────────────────┐
│     DuckDB      │  Data Warehouse
│   (Raw Layer)   │  - CDC Tables
│                 │  - Parquet Files
└────────┬────────┘
         │
         │ DBT Transformations
         │
         ▼
┌─────────────────┐
│  DBT Models     │
│  - Staging      │  Latest state views
│  - Marts        │  SCD Type 2 dimensions
│                 │  Fact tables
└─────────────────┘
```

## Features

### CDC Simulation
- High-water mark based change capture
- Simulated INSERT, UPDATE, DELETE operations
- Batch tracking with timestamps
- Incremental extraction

### SCD Type 2 Implementation
- Customer dimension with full history
- Valid from/to timestamps
- Current record flags
- Automatic versioning on changes

### Data Quality
- DBT data tests
- Schema validation
- Referential integrity checks
- Source freshness monitoring

## Tech Stack

- **Python 3.11** - Pipeline orchestration
- **UV** - Fast Python package manager
- **DBT** - Data transformation framework
- **Postgres 16** - Source database
- **DuckDB** - Data warehouse
- **Docker** - Containerization
- **Faker** - Realistic test data generation

## Project Structure

```
.
├── cdc_pipeline/              # CDC extraction pipeline
│   ├── data_generator.py      # Generates sample data in Postgres
│   ├── cdc_extractor.py       # Extracts changes to DuckDB
│   └── orchestrator.py        # Main pipeline orchestrator
│
├── dbt_project/               # DBT project
│   ├── models/
│   │   ├── staging/           # Staging layer (views)
│   │   │   ├── stg_customers.sql
│   │   │   ├── stg_orders.sql
│   │   │   └── stg_order_items.sql
│   │   └── marts/             # Analytics layer (tables)
│   │       ├── dim_customers_scd2.sql    # SCD Type 2 dimension
│   │       ├── fact_orders.sql
│   │       └── customer_order_summary.sql
│   ├── dbt_project.yml
│   └── profiles.yml
│
├── sql_scripts/               # Database initialization
│   └── 01_init_source.sql
│
├── docker-compose.yml         # Service orchestration
├── Dockerfile.pipeline        # Pipeline container
├── pyproject.toml            # Python dependencies
├── Makefile                  # Command shortcuts
└── README.md                 # This file
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Make (optional, for convenience commands)

### 1. Setup

```bash
# Clone and enter directory
cd eks-example

# Setup environment
make setup

# Or manually copy .env file
cp .env.example .env
```

### 2. Run Complete Demo

```bash
# One command to rule them all!
make demo
```

This will:
1. Build Docker images
2. Start Postgres
3. Initialize schema
4. Generate sample data
5. Extract CDC changes
6. Run DBT transformations
7. Show sample query results

### 3. Explore Results

```bash
# Run sample queries
make query

# View all logs
make logs

# Run DBT tests
make dbt-test

# Generate DBT documentation
make dbt-docs
```

## Usage

### Running the Pipeline

#### One-time Execution
```bash
make run-once
```

#### Continuous Mode
```bash
make run-continuous
```

This runs the pipeline every 30 seconds (configurable via `CDC_POLL_INTERVAL`).

### Individual Components

```bash
# Generate data in Postgres
make generate-data

# Extract CDC changes
make extract-cdc

# Run DBT models
make dbt-run

# Run DBT tests
make dbt-test
```

### Interactive Development

```bash
# Open bash shell in pipeline container
make shell

# Open DBT shell for SQL queries
make dbt-shell
```

### Manual Docker Commands

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d postgres

# Run pipeline once
docker-compose run --rm pipeline python /app/cdc_pipeline/orchestrator.py

# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Clean up volumes and data
docker-compose down -v
rm -rf data/
```

## Pipeline Details

### CDC Process

1. **Data Generation**
   - Uses Faker library to generate realistic data
   - Creates customers, orders, and order items
   - Simulates updates and status changes

2. **Change Extraction**
   - Queries Postgres for records with ID > last extracted ID
   - Adds CDC metadata (operation type, timestamp, batch ID)
   - Loads to DuckDB raw layer

3. **DBT Transformations**
   - **Staging**: Deduplicates CDC records, keeps latest state
   - **Marts**: Applies SCD Type 2 logic, creates fact tables
   - **Tests**: Validates data quality

### SCD Type 2 Implementation

The `dim_customers_scd2` model implements slowly changing dimensions:

- **Surrogate Key**: Generated using customer_id + timestamp
- **Natural Key**: customer_id from source
- **Valid From/To**: Temporal validity of each record
- **Is Current**: Flag for current version
- **Change Detection**: Compares all attributes to detect changes
- **Versioning**: Creates new version on change, expires old version

Example:
```sql
customer_id | email           | city    | valid_from | valid_to   | is_current
1           | john@email.com  | NYC     | 2024-01-01 | 2024-02-01 | false
1           | john@email.com  | Boston  | 2024-02-01 | NULL       | true
```

### Data Model

```
Source Tables (Postgres):
- customers: Customer master data
- orders: Order transactions
- order_items: Order line items
- cdc_metadata: Tracking table for CDC

Raw Layer (DuckDB):
- customers_cdc: All customer changes
- orders_cdc: All order changes
- order_items_cdc: All order item changes

Staging Layer (Views):
- stg_customers: Latest customer state
- stg_orders: Latest order state
- stg_order_items: Latest order item state

Marts Layer (Tables):
- dim_customers_scd2: Customer dimension with history
- fact_orders: Order fact table
- customer_order_summary: Aggregated metrics
```

## Configuration

### Environment Variables

Edit `.env` file to configure:

```bash
# Postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=source_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# DuckDB
DUCKDB_PATH=/data/warehouse.duckdb

# Pipeline
CDC_BATCH_SIZE=100
CDC_POLL_INTERVAL=30
PIPELINE_MODE=once  # or 'continuous'
```

### DBT Configuration

Edit `dbt_project/profiles.yml` for DuckDB settings:
- Path to warehouse file
- Number of threads
- Extensions to load

## Querying the Data Warehouse

### Using Python

```python
import duckdb

conn = duckdb.connect('/data/warehouse.duckdb')

# Query customer summary
df = conn.execute("""
    SELECT * FROM marts.customer_order_summary
    ORDER BY total_revenue DESC
    LIMIT 10
""").df()

print(df)
```

### Using DBT Shell

```bash
make shell
cd dbt_project
dbt run --profiles-dir .

# Then query interactively
python
>>> import duckdb
>>> conn = duckdb.connect('/data/warehouse.duckdb')
>>> conn.execute("SELECT * FROM marts.customer_order_summary LIMIT 5").df()
```

### Sample Queries

```sql
-- Top customers by revenue
SELECT
    customer_id,
    email,
    total_orders,
    total_revenue,
    avg_order_value
FROM marts.customer_order_summary
ORDER BY total_revenue DESC
LIMIT 10;

-- Customer change history (SCD Type 2)
SELECT
    customer_id,
    email,
    city,
    state,
    valid_from,
    valid_to,
    is_current
FROM marts.dim_customers_scd2
WHERE customer_id = 1
ORDER BY valid_from;

-- Orders with customer info at time of order
SELECT
    o.order_id,
    o.order_date,
    c.email,
    c.city,
    o.total_amount
FROM marts.fact_orders o
JOIN marts.dim_customers_scd2 c
    ON o.customer_sk = c.customer_sk
WHERE o.order_date >= '2024-01-01'
LIMIT 10;
```

## Iceberg Integration

While DuckDB doesn't natively support Apache Iceberg, this project uses Iceberg-compatible patterns:

- **Parquet Format**: CDC data can be exported to Parquet
- **Schema Evolution**: Tables support column additions
- **Time Travel**: SCD Type 2 provides historical queries
- **Partition Awareness**: Batch IDs enable partition pruning

To export to Iceberg-compatible Parquet:

```python
# In cdc_extractor.py
extractor.export_to_parquet('customers')
```

Files are saved to `/data/iceberg/` in Parquet format with Snappy compression.

## Development

### Adding New Tables

1. Add table to Postgres schema in `sql_scripts/01_init_source.sql`
2. Create CDC table in `cdc_extractor.py`
3. Add extraction logic in `cdc_extractor.py`
4. Create staging model in `dbt_project/models/staging/`
5. Create marts model in `dbt_project/models/marts/`

### Customizing Data Generation

Edit `cdc_pipeline/data_generator.py`:
- Add new products to the list
- Adjust probability distributions
- Add new customer attributes
- Customize update patterns

### Extending DBT Models

- Add new transformations in `dbt_project/models/marts/`
- Create custom macros in `dbt_project/macros/`
- Add data tests in model schema files

## Troubleshooting

### Postgres Connection Issues
```bash
# Check if Postgres is running
docker-compose ps

# View Postgres logs
docker-compose logs postgres

# Restart Postgres
docker-compose restart postgres
```

### DuckDB Errors
```bash
# Remove DuckDB file and start fresh
rm -f data/warehouse.duckdb
make run-once
```

### DBT Issues
```bash
# Install dependencies
docker-compose run --rm pipeline sh -c "cd /app/dbt_project && dbt deps"

# Debug mode
docker-compose run --rm pipeline sh -c "cd /app/dbt_project && dbt run --debug"
```

### Reset Everything
```bash
make clean
make demo
```

## Performance Considerations

- **Batch Size**: Adjust `CDC_BATCH_SIZE` for larger datasets
- **Polling Interval**: Tune `CDC_POLL_INTERVAL` based on data velocity
- **DBT Threads**: Increase threads in `profiles.yml` for faster builds
- **Indexes**: Add indexes in Postgres for large tables
- **Partitioning**: Consider partitioning DuckDB tables by date

## Testing

```bash
# Run all DBT tests
make dbt-test

# Run specific test
docker-compose run --rm pipeline sh -c "cd /app/dbt_project && dbt test --select stg_customers"
```

## Cleanup

```bash
# Stop services
make down

# Remove all data and volumes
make clean
```

## License

MIT

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Resources

- [DBT Documentation](https://docs.getdbt.com/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Apache Iceberg](https://iceberg.apache.org/)
- [CDC Patterns](https://www.confluent.io/learn/change-data-capture/)
- [SCD Type 2](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/)

## Next Steps

- Add real-time CDC with Debezium
- Implement Apache Iceberg tables
- Add data quality monitoring
- Create dashboards with visualization tools
- Add incremental snapshots
- Implement data lineage tracking
- Add CI/CD for DBT models
