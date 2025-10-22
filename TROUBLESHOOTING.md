## Troubleshooting Guide

### Permission Denied on data/ directory (macOS/Linux)

If you see:
```
Error response from daemon: error while creating mount source path '/path/to/data': chown /path/to/data: permission denied
```

**Solution:**
```bash
# Create data directory with proper permissions
mkdir -p data
chmod 777 data

# Or run setup again
make setup

# Then try again
make run-once
```

**Why this happens:**
Docker on macOS/Linux needs proper permissions to mount volumes. The Makefile now automatically creates this directory with correct permissions.

### Docker Compose Version Warning

If you see:
```
WARN[0000] the attribute `version` is obsolete
```

This is just a warning and can be safely ignored. Docker Compose v2 no longer requires the version field.

### Postgres Connection Issues

```bash
# Check if Postgres is running
docker-compose ps

# View Postgres logs
docker-compose logs postgres

# Restart Postgres
docker-compose restart postgres

# Wait longer for Postgres to be ready
make up
sleep 10
make run-once
```

### DuckDB Lock Errors

If you see "database is locked" errors:

```bash
# Stop all containers
make down

# Remove DuckDB file
rm -f data/warehouse.duckdb*

# Start fresh
make run-once
```

### Build Errors

```bash
# Clean rebuild
docker-compose build --no-cache

# Or clean everything
make clean
make demo
```

### macOS Specific Issues

**1. Docker Desktop not running:**
```bash
# Start Docker Desktop first
open -a Docker

# Wait for it to be ready, then:
make demo
```

**2. Port 5432 already in use:**
```bash
# Find what's using the port
lsof -i :5432

# Stop local Postgres if running
brew services stop postgresql

# Or change the port in docker-compose.yml
```

### Import Errors

If you see Python import errors:

```bash
# Rebuild the container
docker-compose build --no-cache

# The Dockerfile should install all dependencies
```

### DBT Errors

**"Compilation Error" or "Relation does not exist":**

This usually means DBT is trying to run before the CDC extraction has completed.

```bash
# Run steps individually:
make up                  # Start Postgres
make generate-data       # Generate source data
make extract-cdc         # Extract to DuckDB
make dbt-run            # Run DBT models
```

**"Package not found":**

```bash
# Install DBT packages
docker-compose run --rm pipeline sh -c "cd /app/dbt_project && dbt deps --profiles-dir ."
```

### Data Volume Issues

**Clean slate:**
```bash
# Remove everything
make clean

# This removes:
# - All containers
# - All volumes (including Postgres data)
# - Local data/ directory

# Start fresh
make demo
```

### Still Having Issues?

1. **Check Docker resources:**
   - Docker Desktop → Settings → Resources
   - Ensure at least 4GB RAM allocated

2. **Check logs:**
   ```bash
   # All services
   make logs

   # Just Postgres
   docker-compose logs postgres

   # Pipeline container
   docker-compose logs pipeline
   ```

3. **Run with debug:**
   ```bash
   # Verbose output
   docker-compose run --rm pipeline python /app/cdc_pipeline/orchestrator.py
   ```

4. **Check file permissions:**
   ```bash
   # Your user should own these directories
   ls -la

   # Fix ownership if needed (Linux)
   sudo chown -R $USER:$USER .
   ```

### Quick Reset Commands

```bash
# Soft reset (keep Postgres data)
docker-compose down
rm -rf data/
make run-once

# Hard reset (everything)
make clean
make demo

# Nuclear option (remove all Docker resources)
docker-compose down -v
docker system prune -af
make demo
```

### Getting Help

If you're still stuck:

1. Check the logs: `make logs`
2. Try the nuclear option above
3. Ensure Docker Desktop is running and healthy
4. Check disk space: `df -h`
5. Check Docker status: `docker info`

### Common Error Messages Explained

| Error | Meaning | Solution |
|-------|---------|----------|
| `permission denied` | File/directory permissions issue | `chmod 777 data/` |
| `connection refused` | Postgres not ready | Wait longer or check `make logs` |
| `database is locked` | Multiple DuckDB connections | Stop all containers, remove .duckdb files |
| `relation does not exist` | DBT running before data loaded | Run extraction first |
| `port already allocated` | Port 5432 in use | Stop local Postgres or change port |
| `no such image` | Docker image not built | Run `make build` |
