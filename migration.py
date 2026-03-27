"""
One-time migration of mora earnings from Firebase to PostgreSQL.

Usage:
    python migration.py              # Run full migration
    python migration.py --dry-run    # Test without writing to database

This script:
1. Reads all /Mora data from Firebase
2. Creates minigame_mora table in PostgreSQL
3. Batch inserts all entries
4. Validates data integrity
"""
import asyncio
import asyncpg
import firebase_admin
from firebase_admin import credentials, db
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from assets.secret import DATABASE_PATH, DATABASE_URL, DATABASE_USER, DATABASE_PASSWORD

async def init_mora_schema(pool: asyncpg.Pool) -> None:
    """Create the minigame_mora table if it doesn't exist."""
    async with pool.acquire() as conn:
        # Main table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS minigame_mora (
                gid BIGINT NOT NULL,
                uid BIGINT NOT NULL,
                cid BIGINT NOT NULL,
                timestamp BIGINT NOT NULL,
                count INT NOT NULL,
                PRIMARY KEY (gid, uid, cid, timestamp)
            )
        """)

        # Index for per-guild user lookups (leaderboard, profile)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_minigame_mora_gid_uid 
            ON minigame_mora (gid, uid)
        """)

        # Index for global rankings
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_minigame_mora_uid 
            ON minigame_mora (uid)
        """)

        # Index for time-range queries (graph generation)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_minigame_mora_timestamp 
            ON minigame_mora (timestamp)
        """)

        # Index for guild daily aggregates
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_minigame_mora_gid_timestamp 
            ON minigame_mora (gid, timestamp)
        """)


async def batch_insert_mora(
    pool: asyncpg.Pool,
    entries: list
) -> int:
    """
    Batch insert mora entries for efficiency.
    entries: list of tuples (uid, gid, cid, timestamp, count)
    Returns: number of rows inserted.
    """
    if not entries:
        return 0

    async with pool.acquire() as conn:
        # Use executemany for bulk inserts
        result = await conn.executemany("""
            INSERT INTO minigame_mora (uid, gid, cid, timestamp, count)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (gid, uid, cid, timestamp)
            DO UPDATE SET count = $5
        """, entries)

    return len(entries)


async def get_mora_table_stats(pool: asyncpg.Pool) -> dict:
    """
    Get statistics about the mora table.
    Used for validation and migration verification.
    """
    async with pool.acquire() as conn:
        stats = {}
        stats['total_rows'] = await conn.fetchval("SELECT COUNT(*) FROM minigame_mora")
        stats['unique_users'] = await conn.fetchval("SELECT COUNT(DISTINCT uid) FROM minigame_mora")
        stats['unique_guilds'] = await conn.fetchval("SELECT COUNT(DISTINCT gid) FROM minigame_mora")
        stats['total_mora'] = await conn.fetchval("SELECT COALESCE(SUM(count), 0) FROM minigame_mora")
        stats['min_timestamp'] = await conn.fetchval("SELECT MIN(timestamp) FROM minigame_mora")
        stats['max_timestamp'] = await conn.fetchval("SELECT MAX(timestamp) FROM minigame_mora")

    return stats


async def check_duplicates(pool: asyncpg.Pool) -> list:
    """
    Check for duplicate (gid, uid, cid, timestamp) entries.
    Should return empty list if table is clean.
    """
    async with pool.acquire() as conn:
        duplicates = await conn.fetch("""
            SELECT gid, uid, cid, timestamp, COUNT(*) as count
            FROM minigame_mora
            GROUP BY gid, uid, cid, timestamp
            HAVING COUNT(*) > 1
        """)
    return duplicates


# ============================================================================
# Logging & Formatting
# ============================================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log_section(title: str):
    """Log a major section header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}\n")

def log_step(num: int, title: str):
    """Log a numbered step."""
    print(f"{Colors.BOLD}{Colors.BLUE}[Step {num}]{Colors.RESET} {title}")

def log_success(msg: str, indent=1):
    """Log a success message."""
    prefix = "  " * indent
    print(f"{prefix}{Colors.GREEN}✓{Colors.RESET} {msg}")

def log_warning(msg: str, indent=1):
    """Log a warning message."""
    prefix = "  " * indent
    print(f"{prefix}{Colors.YELLOW}⚠{Colors.RESET} {msg}")

def log_error(msg: str, indent=1):
    """Log an error message."""
    prefix = "  " * indent
    print(f"{prefix}{Colors.RED}✗{Colors.RESET} {msg}")

def log_info(msg: str, indent=1):
    """Log an info message."""
    prefix = "  " * indent
    print(f"{prefix}{Colors.CYAN}»{Colors.RESET} {msg}")

# ============================================================================
# Firebase Setup
# ============================================================================

def init_firebase():
    """Initialize Firebase if not already initialized."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(DATABASE_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
    return db


# ============================================================================
# Data Extraction & Validation
# ============================================================================

def extract_mora_from_firebase() -> list:
    """
    Extract all mora entries from Firebase /Mora tree.
    
    Structure: /Mora/{uid}/{gid}/{cid}/{timestamp} = count
    
    Returns: list of tuples (uid, gid, cid, timestamp, count)
    """
    log_step(1, "Extracting mora data from Firebase")
    db_ref = db.reference("/Mora")
    mora_data = db_ref.get() or {}
    
    entries = []
    error_count = 0
    
    for uid_str, user_data in mora_data.items():
        if not isinstance(user_data, dict):
            error_count += 1
            log_warning(f"Invalid user data structure for uid={uid_str}", indent=2)
            continue
            
        try:
            uid = int(uid_str)
        except (ValueError, TypeError):
            error_count += 1
            log_warning(f"Invalid UID format: {uid_str}", indent=2)
            continue
        
        for gid_str, guild_data in user_data.items():
            if not isinstance(guild_data, dict):
                error_count += 1
                continue
                
            try:
                gid = int(gid_str)
            except (ValueError, TypeError):
                error_count += 1
                continue
            
            for cid_str, channel_data in guild_data.items():
                if not isinstance(channel_data, dict):
                    error_count += 1
                    continue
                    
                try:
                    cid = int(cid_str)
                except (ValueError, TypeError):
                    error_count += 1
                    continue
                
                for ts_str, count in channel_data.items():
                    try:
                        timestamp = int(ts_str)
                        # Validate count is an integer
                        if not isinstance(count, int):
                            error_count += 1
                            continue
                        
                        entries.append((uid, gid, cid, timestamp, count))
                    except (ValueError, TypeError):
                        error_count += 1
                        continue
    
    log_success(f"Extracted {len(entries):,} valid entries", indent=2)
    if error_count > 0:
        log_warning(f"Skipped {error_count} invalid entries", indent=2)
    
    return entries


# ============================================================================
# PostgreSQL Migration
# ============================================================================

async def migrate_mora_to_postgres(entries: list, dry_run: bool = False) -> None:
    """
    Migrate extracted entries to PostgreSQL.
    
    Creates table, initializes schema, and batch inserts all entries.
    
    Args:
        entries: List of (uid, gid, cid, timestamp, count) tuples from Firebase
        dry_run: If True, simulate migration without writing to database
    """
    log_step(2, "Connecting to PostgreSQL" + (" (DRY RUN - No writes)" if dry_run else ""))
    
    # Create connection pool
    pool = await asyncpg.create_pool(
        database="db",
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host="localhost",
        min_size=2,
        max_size=10,
    )
    
    try:
        log_success("Connected to PostgreSQL", indent=2)
        
        # Initialize schema
        if not dry_run:
            log_step(3, "Creating minigame_mora table and indexes")
            await init_mora_schema(pool)
            log_success("Schema initialized", indent=2)
        else:
            log_step(3, "Schema initialization (DRY RUN - skipped)")
        
        # Batch insert entries
        log_step(4, f"Inserting {len(entries):,} mora entries" + (" (DRY RUN - simulating)" if dry_run else ""))
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i+batch_size]
            if not dry_run:
                inserted = await batch_insert_mora(pool, batch)
                total_inserted += inserted
            else:
                total_inserted += len(batch)
            
            progress = min(i + batch_size, len(entries))
            pct = (progress / len(entries)) * 100
            log_info(f"Progress: {progress:,}/{len(entries):,} ({pct:.1f}%)", indent=2)
        
        log_success(f"Inserted {total_inserted:,} entries" + (" (simulated)" if dry_run else ""), indent=2)
        
        # Validate data integrity
        log_step(5, "Validating data integrity" + (" (DRY RUN - simulating)" if dry_run else ""))
        
        if not dry_run:
            stats = await get_mora_table_stats(pool)
            
            log_info(f"Total rows: {stats['total_rows']:,}", indent=2)
            log_info(f"Unique users: {stats['unique_users']:,}", indent=2)
            log_info(f"Unique guilds: {stats['unique_guilds']:,}", indent=2)
            log_info(f"Total mora: {stats['total_mora']:,}", indent=2)
            if stats['min_timestamp']:
                log_info(f"Date range: {stats['min_timestamp']} to {stats['max_timestamp']}", indent=2)
            
            # Check for duplicates
            duplicates = await check_duplicates(pool)
            if duplicates:
                log_warning(f"Found {len(duplicates)} duplicate (gid, uid, cid, timestamp) entries", indent=2)
                for dup in duplicates[:5]:
                    log_info(f"uid={dup['uid']}, gid={dup['gid']}, cid={dup['cid']}, ts={dup['timestamp']}, count={dup['count']}", indent=3)
            else:
                log_success(f"No duplicates found", indent=2)
            
            # Final validation
            log_step(6, "Final validation")
            if stats['total_rows'] == len(entries):
                log_success(f"Row count matches: {len(entries):,} entries", indent=2)
            else:
                log_warning(f"Row count mismatch", indent=2)
                log_info(f"Expected: {len(entries):,}", indent=3)
                log_info(f"Actual: {stats['total_rows']:,}", indent=3)
        else:
            # Dry run stats calculation
            log_info(f"Total rows: {len(entries):,} (simulated)", indent=2)
            unique_users = len(set(e[0] for e in entries))
            unique_guilds = len(set(e[1] for e in entries))
            total_mora = sum(e[4] for e in entries)
            log_info(f"Unique users: {unique_users:,} (simulated)", indent=2)
            log_info(f"Unique guilds: {unique_guilds:,} (simulated)", indent=2)
            log_info(f"Total mora: {total_mora:,} (simulated)", indent=2)
        
    finally:
        await pool.close()


# ============================================================================
# Main Execution
# ============================================================================

async def main():
    """Main migration flow."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Migrate mora data from Firebase to PostgreSQL"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test migration without writing to database"
    )
    args = parser.parse_args()
    
    # Display header
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}MORA DATA MIGRATION: Firebase → PostgreSQL{Colors.RESET}")
    if args.dry_run:
        print(f"{Colors.YELLOW}[DRY RUN MODE - No database changes]{Colors.RESET}")
    print("=" * 70)
    
    print(f"\n{Colors.YELLOW}⚠️  WARNING: Ensure the Discord bot is STOPPED before running this!{Colors.RESET}")
    print("    Concurrent writes will cause data corruption.\n")
    
    if not args.dry_run:
        input("Press ENTER to continue, or Ctrl+C to cancel...")
    else:
        print(f"{Colors.CYAN}→ Running in dry-run mode (no database writes){Colors.RESET}\n")
    
    log_section("EXTRACTION PHASE")
    
    try:
        # Initialize Firebase
        init_firebase()
        
        # Extract from Firebase
        entries = extract_mora_from_firebase()
        
        if not entries:
            log_error("No mora entries found in Firebase. Aborting.", indent=1)
            return
        
        # Migrate to PostgreSQL
        log_section("MIGRATION PHASE")
        await migrate_mora_to_postgres(entries, dry_run=args.dry_run)
        
        print("\n" + "=" * 70)
        log_success("MIGRATION COMPLETE", indent=0)
        print("=" * 70)
        
        print(f"\n{Colors.CYAN}Next steps:{Colors.RESET}")
        print("  1. Review the stats above")
        if not args.dry_run:
            print("  2. Backup Firebase /Mora tree (optional)")
            print("  3. Deploy updated bot code")
            print("  4. Monitor logs for errors")
            print("  5. Archive/delete Firebase /Mora if migration successful")
        else:
            print("  2. Without --dry-run to perform actual migration")
        
    except Exception as e:
        log_error(f"MIGRATION FAILED: {e}", indent=1)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
