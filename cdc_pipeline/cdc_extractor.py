"""
CDC Extractor to capture changes from Postgres and land them in DuckDB
"""
import os
from datetime import datetime
from typing import Dict, List, Any
import psycopg2
import duckdb
import pandas as pd


class CDCExtractor:
    """Extract CDC changes from Postgres and load into DuckDB"""

    def __init__(self, postgres_config: Dict[str, str], duckdb_path: str):
        self.postgres_config = postgres_config
        self.duckdb_path = duckdb_path
        self.pg_conn = None
        self.duck_conn = None

    def connect(self):
        """Establish connections to both databases"""
        # Connect to Postgres
        self.pg_conn = psycopg2.connect(
            host=self.postgres_config['host'],
            port=self.postgres_config['port'],
            database=self.postgres_config['database'],
            user=self.postgres_config['user'],
            password=self.postgres_config['password']
        )

        # Connect to DuckDB
        self.duck_conn = duckdb.connect(self.duckdb_path)

        # Initialize DuckDB schemas and tables
        self._init_duckdb_schema()

    def _init_duckdb_schema(self):
        """Initialize DuckDB schema and CDC tables"""
        # Create schemas
        self.duck_conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        self.duck_conn.execute("CREATE SCHEMA IF NOT EXISTS staging")
        self.duck_conn.execute("CREATE SCHEMA IF NOT EXISTS marts")

        # Create CDC tables with Iceberg-compatible structure
        # Note: DuckDB doesn't natively support Iceberg, but we'll structure data
        # in a way that's compatible with Iceberg table format (append-only with metadata)

        # Customers CDC table
        self.duck_conn.execute("""
            CREATE TABLE IF NOT EXISTS raw.customers_cdc (
                customer_id INTEGER,
                email VARCHAR,
                first_name VARCHAR,
                last_name VARCHAR,
                phone VARCHAR,
                address VARCHAR,
                city VARCHAR,
                state VARCHAR,
                zip_code VARCHAR,
                country VARCHAR,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                cdc_operation VARCHAR,  -- INSERT, UPDATE, DELETE
                cdc_timestamp TIMESTAMP,
                cdc_batch_id VARCHAR
            )
        """)

        # Orders CDC table
        self.duck_conn.execute("""
            CREATE TABLE IF NOT EXISTS raw.orders_cdc (
                order_id INTEGER,
                customer_id INTEGER,
                order_date TIMESTAMP,
                order_status VARCHAR,
                total_amount DECIMAL(10, 2),
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                cdc_operation VARCHAR,
                cdc_timestamp TIMESTAMP,
                cdc_batch_id VARCHAR
            )
        """)

        # Order Items CDC table
        self.duck_conn.execute("""
            CREATE TABLE IF NOT EXISTS raw.order_items_cdc (
                order_item_id INTEGER,
                order_id INTEGER,
                product_name VARCHAR,
                quantity INTEGER,
                unit_price DECIMAL(10, 2),
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                cdc_operation VARCHAR,
                cdc_timestamp TIMESTAMP,
                cdc_batch_id VARCHAR
            )
        """)

        # CDC metadata table
        self.duck_conn.execute("""
            CREATE TABLE IF NOT EXISTS raw.cdc_metadata (
                table_name VARCHAR PRIMARY KEY,
                last_extracted_id INTEGER,
                last_extracted_at TIMESTAMP,
                total_records_extracted BIGINT
            )
        """)

        # Initialize metadata if not exists
        for table in ['customers', 'orders', 'order_items']:
            self.duck_conn.execute(f"""
                INSERT INTO raw.cdc_metadata (table_name, last_extracted_id, last_extracted_at, total_records_extracted)
                SELECT '{table}', 0, CURRENT_TIMESTAMP, 0
                WHERE NOT EXISTS (SELECT 1 FROM raw.cdc_metadata WHERE table_name = '{table}')
            """)

        print("✓ DuckDB schema initialized")

    def extract_table_changes(self, table_name: str, id_column: str) -> pd.DataFrame:
        """Extract changes from a Postgres table using high-water mark"""
        # Get last extracted ID
        cursor = self.duck_conn.cursor()
        result = cursor.execute(f"""
            SELECT last_extracted_id
            FROM raw.cdc_metadata
            WHERE table_name = '{table_name}'
        """).fetchone()

        last_id = result[0] if result else 0

        # Extract new/updated records from Postgres
        pg_cursor = self.pg_conn.cursor()
        pg_cursor.execute(f"""
            SELECT *
            FROM {table_name}
            WHERE {id_column} > %s
            ORDER BY {id_column}
        """, (last_id,))

        # Get column names
        columns = [desc[0] for desc in pg_cursor.description]

        # Fetch all rows
        rows = pg_cursor.fetchall()
        pg_cursor.close()

        if not rows:
            return pd.DataFrame()

        # Create DataFrame
        df = pd.DataFrame(rows, columns=columns)

        # Add CDC metadata
        df['cdc_operation'] = 'INSERT'  # Simplified: treating all as inserts
        df['cdc_timestamp'] = datetime.now()
        df['cdc_batch_id'] = datetime.now().strftime('%Y%m%d_%H%M%S')

        return df

    def load_to_duckdb(self, df: pd.DataFrame, table_name: str, id_column: str):
        """Load CDC data to DuckDB"""
        if df.empty:
            print(f"  No new records for {table_name}")
            return

        # Insert into DuckDB CDC table
        target_table = f"raw.{table_name}_cdc"

        # Use DuckDB's DataFrame INSERT
        self.duck_conn.execute(f"INSERT INTO {target_table} SELECT * FROM df")

        # Update metadata
        max_id = df[id_column].max()
        record_count = len(df)

        self.duck_conn.execute(f"""
            UPDATE raw.cdc_metadata
            SET
                last_extracted_id = {max_id},
                last_extracted_at = CURRENT_TIMESTAMP,
                total_records_extracted = total_records_extracted + {record_count}
            WHERE table_name = '{table_name}'
        """)

        print(f"✓ Loaded {record_count} records to {target_table} (max ID: {max_id})")

    def export_to_parquet(self, table_name: str):
        """Export CDC data to Parquet format (Iceberg-compatible)"""
        output_dir = "/data/iceberg"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        parquet_path = f"{output_dir}/{table_name}_cdc_{timestamp}.parquet"

        self.duck_conn.execute(f"""
            COPY (SELECT * FROM raw.{table_name}_cdc)
            TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)

        print(f"✓ Exported {table_name} to {parquet_path}")

    def run_extraction(self):
        """Run full CDC extraction for all tables"""
        tables = [
            ('customers', 'customer_id'),
            ('orders', 'order_id'),
            ('order_items', 'order_item_id')
        ]

        print("\n=== Starting CDC Extraction ===")

        for table_name, id_column in tables:
            print(f"\nExtracting {table_name}...")
            try:
                df = self.extract_table_changes(table_name, id_column)
                self.load_to_duckdb(df, table_name, id_column)

                # Optionally export to Parquet for Iceberg
                # self.export_to_parquet(table_name)

            except Exception as e:
                print(f"✗ Error extracting {table_name}: {e}")

        # Show extraction summary
        self.show_summary()

    def show_summary(self):
        """Display CDC extraction summary"""
        print("\n=== CDC Extraction Summary ===")
        result = self.duck_conn.execute("""
            SELECT
                table_name,
                last_extracted_id,
                last_extracted_at,
                total_records_extracted
            FROM raw.cdc_metadata
            ORDER BY table_name
        """).fetchall()

        for row in result:
            print(f"  {row[0]}: {row[3]} total records (last ID: {row[1]})")

    def close(self):
        """Close database connections"""
        if self.pg_conn:
            self.pg_conn.close()
        if self.duck_conn:
            self.duck_conn.close()


def main():
    """Main function to run CDC extraction"""
    import os

    postgres_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'source_db'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
    }

    duckdb_path = os.getenv('DUCKDB_PATH', '/data/warehouse.duckdb')

    extractor = CDCExtractor(postgres_config, duckdb_path)

    try:
        print("Connecting to databases...")
        extractor.connect()
        print("✓ Connected to Postgres and DuckDB")

        extractor.run_extraction()

        print("\n✓ CDC extraction completed successfully!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
