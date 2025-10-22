"""
Main orchestrator for the DBT CDC pipeline
Coordinates data generation, CDC extraction, and DBT transformations
"""
import os
import sys
import time
import subprocess
from datetime import datetime
from data_generator import DataGenerator
from cdc_extractor import CDCExtractor


def wait_for_postgres(db_config, max_retries=30):
    """Wait for Postgres to be ready"""
    import psycopg2

    print("Waiting for Postgres to be ready...")
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                database=db_config['database'],
                user=db_config['user'],
                password=db_config['password']
            )
            conn.close()
            print("✓ Postgres is ready!")
            return True
        except psycopg2.OperationalError:
            if i < max_retries - 1:
                print(f"  Waiting... ({i+1}/{max_retries})")
                time.sleep(2)
            else:
                print("✗ Postgres not available")
                return False
    return False


def run_dbt_command(command: str, project_dir: str = "/app/dbt_project"):
    """Run a DBT command"""
    print(f"\n=== Running DBT: {command} ===")
    try:
        result = subprocess.run(
            f"cd {project_dir} && dbt {command} --profiles-dir .",
            shell=True,
            capture_output=True,
            text=True
        )

        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:", result.stderr)

        if result.returncode == 0:
            print(f"✓ DBT {command} completed successfully")
            return True
        else:
            print(f"✗ DBT {command} failed with return code {result.returncode}")
            return False

    except Exception as e:
        print(f"✗ Error running DBT {command}: {e}")
        return False


def run_pipeline_once(db_config, duckdb_path):
    """Run one iteration of the pipeline"""
    print("\n" + "="*60)
    print(f"Pipeline Iteration - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Step 1: Generate/Update data in Postgres
    print("\n[1/4] Generating data in Postgres...")
    generator = DataGenerator(db_config)
    try:
        generator.connect()

        # Get existing IDs
        customer_ids = generator.get_all_customer_ids()
        order_ids = generator.get_all_order_ids()

        if not customer_ids:
            # Initial load
            print("  Performing initial data load...")
            customer_ids = generator.generate_customers(20)
            order_ids = generator.generate_orders(customer_ids, 50)
            generator.generate_order_items(order_ids)
        else:
            # Incremental updates
            print("  Performing incremental updates...")
            new_customers = generator.generate_customers(5)
            customer_ids.extend(new_customers)

            generator.update_customers(customer_ids, 3)

            new_orders = generator.generate_orders(customer_ids, 10)
            order_ids.extend(new_orders)
            generator.generate_order_items(new_orders)

            generator.update_order_status(order_ids, 5)

        print("✓ Data generation complete")
    finally:
        generator.close()

    # Step 2: Extract CDC changes to DuckDB
    print("\n[2/4] Extracting CDC changes to DuckDB...")
    extractor = CDCExtractor(db_config, duckdb_path)
    try:
        extractor.connect()
        extractor.run_extraction()
        print("✓ CDC extraction complete")
    finally:
        extractor.close()

    # Step 3: Run DBT transformations
    print("\n[3/4] Running DBT transformations...")

    # Install DBT packages (first time only)
    if not os.path.exists("/app/dbt_project/dbt_packages"):
        run_dbt_command("deps")

    # Run DBT models
    success = run_dbt_command("run")

    if success:
        print("✓ DBT transformations complete")
    else:
        print("✗ DBT transformations failed")
        return False

    # Step 4: Run DBT tests
    print("\n[4/4] Running DBT tests...")
    run_dbt_command("test")

    print("\n" + "="*60)
    print("✓ Pipeline iteration complete!")
    print("="*60)

    return True


def run_continuous_pipeline(db_config, duckdb_path, interval_seconds=30):
    """Run pipeline continuously with specified interval"""
    print("\n" + "="*60)
    print("Starting Continuous CDC Pipeline")
    print("="*60)
    print(f"Interval: {interval_seconds} seconds")
    print("Press Ctrl+C to stop")
    print("="*60)

    iteration = 0
    try:
        while True:
            iteration += 1
            print(f"\n\nIteration #{iteration}")

            success = run_pipeline_once(db_config, duckdb_path)

            if not success:
                print("Pipeline iteration failed, but continuing...")

            print(f"\nWaiting {interval_seconds} seconds until next iteration...")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\n✓ Pipeline stopped by user")
        print(f"Total iterations completed: {iteration}")


def show_results(duckdb_path):
    """Show some results from the data warehouse"""
    import duckdb

    print("\n" + "="*60)
    print("Sample Query Results")
    print("="*60)

    conn = duckdb.connect(duckdb_path)

    # Show customer summary
    print("\n--- Top 10 Customers by Revenue ---")
    result = conn.execute("""
        SELECT
            customer_id,
            email,
            first_name || ' ' || last_name as name,
            total_orders,
            total_revenue,
            avg_order_value
        FROM main_marts.customer_order_summary
        ORDER BY total_revenue DESC
        LIMIT 10
    """).fetchall()

    for row in result:
        print(f"  {row[1]}: ${row[4]:.2f} ({row[3]} orders, avg ${row[5]:.2f})")

    # Show SCD2 example
    print("\n--- Customers with History (SCD2) ---")
    result = conn.execute("""
        SELECT
            customer_id,
            email,
            city,
            state,
            valid_from,
            valid_to,
            is_current
        FROM main_marts.dim_customers_scd2
        WHERE customer_id IN (
            SELECT customer_id
            FROM main_marts.dim_customers_scd2
            GROUP BY customer_id
            HAVING COUNT(*) > 1
        )
        ORDER BY customer_id, valid_from
        LIMIT 10
    """).fetchall()

    for row in result:
        current = "CURRENT" if row[6] else "EXPIRED"
        print(f"  Customer {row[0]}: {row[2]}, {row[3]} [{current}]")

    conn.close()


def main():
    """Main entry point"""
    # Configuration
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'source_db'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
    }

    duckdb_path = os.getenv('DUCKDB_PATH', '/data/warehouse.duckdb')
    mode = os.getenv('PIPELINE_MODE', 'once')  # 'once' or 'continuous'
    interval = int(os.getenv('CDC_POLL_INTERVAL', '30'))

    # Wait for Postgres to be ready
    if not wait_for_postgres(db_config):
        print("✗ Failed to connect to Postgres")
        sys.exit(1)

    # Create data directory
    os.makedirs('/data', exist_ok=True)

    try:
        if mode == 'continuous':
            run_continuous_pipeline(db_config, duckdb_path, interval)
        else:
            # Run once
            run_pipeline_once(db_config, duckdb_path)

            # Show results
            show_results(duckdb_path)

            print("\n✓ Pipeline completed successfully!")

    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
