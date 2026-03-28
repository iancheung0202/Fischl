"""
One-time migration script: Firebase → PostgreSQL minigame_progression
Migrates three Firebase nodes into a single minigame_progression table.

Firebase Source Nodes:
  - /Kingdom/{gid}/{uid}/buildings/{key} → kingdom_{key}
  - /Progression/{gid}/{uid} → xp, prestige, bonus_tier
  - /User Events Stats/{gid}/{uid} → mora_boost, chest_upgrades, gift_tax, minigame_summons, realm_* → kingdom_*

PostgreSQL Table: minigame_progression
  Columns: gid, uid, kingdom_schloss, kingdom_theater, kingdom_bibliothek, kingdom_garten,
           xp, prestige, bonus_tier, mora_boost, chest_upgrades, gift_tax, minigame_summons,
           kingdom_chest_summon_chance, kingdom_refund_summon_chance, kingdom_xp_boost
  PK: (gid, uid)

Usage:
  python migration.py  # Interactive - will prompt before migrating
  python migration.py --no-prompt  # Non-interactive
"""

import asyncio
import asyncpg
import firebase_admin
from firebase_admin import credentials, db
from assets.secret import DATABASE_PATH, DATABASE_USER, DATABASE_PASSWORD, DATABASE_URL

# Initialize Firebase
cred = credentials.Certificate(DATABASE_PATH)
firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})


async def create_table(pool):
    """Create minigame_progression table if it doesn't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS minigame_progression (
                gid BIGINT NOT NULL,
                uid BIGINT NOT NULL,
                kingdom_schloss INT DEFAULT 0,
                kingdom_theater INT DEFAULT 0,
                kingdom_bibliothek INT DEFAULT 0,
                kingdom_garten INT DEFAULT 0,
                xp INT DEFAULT 0,
                prestige INT DEFAULT 0,
                bonus_tier INT DEFAULT 0,
                mora_boost INT DEFAULT 0,
                chest_upgrades INT DEFAULT 4,
                gift_tax INT,
                minigame_summons INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (gid, uid)
            );
        """)
    print("✅ Table minigame_progression created/verified")


async def migrate_data(pool):
    """Fetch from Firebase, merge, and insert into PostgreSQL."""
    
    print("\n📥 Fetching Firebase data...")
    
    # Fetch all three Firebase nodes
    kingdom_ref = db.reference("/Kingdom")
    progression_ref = db.reference("/Progression")
    stats_ref = db.reference("/User Events Stats")
    
    kingdom_data = kingdom_ref.get() or {}
    progression_data = progression_ref.get() or {}
    stats_data = stats_ref.get() or {}
    
    print(f"  Kingdom nodes: {sum(len(v) for v in kingdom_data.values())}")
    print(f"  Progression nodes: {sum(len(v) for v in progression_data.values())}")
    print(f"  Stats nodes: {sum(len(v) for v in stats_data.values())}")
    
    # Merge all data into dict keyed by (gid, uid)
    merged = {}
    
    # Process Kingdom buildings
    for gid_str, guild_data in kingdom_data.items():
        try:
            gid = int(gid_str)
        except (ValueError, TypeError):
            continue
        
        for uid_str, user_data in guild_data.items():
            try:
                uid = int(uid_str)
            except (ValueError, TypeError):
                continue
            
            key = (gid, uid)
            if key not in merged:
                merged[key] = {}
            
            buildings = user_data.get("buildings", {})
            merged[key]["kingdom_schloss"] = buildings.get("schloss", 0)
            merged[key]["kingdom_theater"] = buildings.get("theater", 0)
            merged[key]["kingdom_bibliothek"] = buildings.get("bibliothek", 0)
            merged[key]["kingdom_garten"] = buildings.get("garten", 0)
    
    # Process Progression (xp, prestige, bonus_tier)
    for gid_str, guild_data in progression_data.items():
        try:
            gid = int(gid_str)
        except (ValueError, TypeError):
            continue
        
        for uid_str, user_data in guild_data.items():
            try:
                uid = int(uid_str)
            except (ValueError, TypeError):
                continue
            
            key = (gid, uid)
            if key not in merged:
                merged[key] = {}
            
            merged[key]["xp"] = user_data.get("xp", 0)
            merged[key]["prestige"] = user_data.get("prestige", 0)
            merged[key]["bonus_tier"] = user_data.get("bonus_tier", 0)
    
    # Process User Events Stats
    for gid_str, guild_data in stats_data.items():
        try:
            gid = int(gid_str)
        except (ValueError, TypeError):
            continue
        
        for uid_str, user_stats in guild_data.items():
            try:
                uid = int(uid_str)
            except (ValueError, TypeError):
                continue
            
            key = (gid, uid)
            if key not in merged:
                merged[key] = {}
            
            merged[key]["mora_boost"] = user_stats.get("mora_boost", 0)
            merged[key]["chest_upgrades"] = user_stats.get("chest_upgrades", 4)
            merged[key]["gift_tax"] = user_stats.get("gift_tax", None)
            merged[key]["minigame_summons"] = user_stats.get("minigame_summons", 0)
            # Note: realm_* fields (realm_chest_bonus_chance, realm_encore_chance, realm_xp_boost)
            # are now derived from building levels, so we don't store them separately
    
    print(f"\n🔀 Merged {len(merged)} unique (gid, uid) pairs")
    
    # Batch insert into PostgreSQL
    print("\n⬆️  Inserting into PostgreSQL...")
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            for (gid, uid), data in merged.items():
                # Set defaults for any missing fields
                data.setdefault("kingdom_schloss", 0)
                data.setdefault("kingdom_theater", 0)
                data.setdefault("kingdom_bibliothek", 0)
                data.setdefault("kingdom_garten", 0)
                data.setdefault("xp", 0)
                data.setdefault("prestige", 0)
                data.setdefault("bonus_tier", 0)
                data.setdefault("mora_boost", 0)
                data.setdefault("chest_upgrades", 4)
                data.setdefault("gift_tax", None)
                data.setdefault("minigame_summons", 0)
                
                await conn.execute("""
                    INSERT INTO minigame_progression 
                    (gid, uid, kingdom_schloss, kingdom_theater, kingdom_bibliothek, kingdom_garten,
                     xp, prestige, bonus_tier, mora_boost, chest_upgrades, gift_tax, minigame_summons)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT (gid, uid) DO UPDATE SET
                        kingdom_schloss = $3, kingdom_theater = $4, kingdom_bibliothek = $5, kingdom_garten = $6,
                        xp = $7, prestige = $8, bonus_tier = $9, mora_boost = $10, chest_upgrades = $11,
                        gift_tax = $12, minigame_summons = $13,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    gid, uid,
                    data["kingdom_schloss"], data["kingdom_theater"], data["kingdom_bibliothek"], data["kingdom_garten"],
                    data["xp"], data["prestige"], data["bonus_tier"],
                    data["mora_boost"], data["chest_upgrades"], data["gift_tax"], data["minigame_summons"]
                )
    
    print(f"✅ Inserted/Updated {len(merged)} rows")
    
    # Verify migration
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM minigame_progression")
        sample = await conn.fetch("SELECT * FROM minigame_progression LIMIT 3")
    
    print(f"\n✔️  Verification:")
    print(f"  Total rows in minigame_progression: {count}")
    print(f"  Sample rows: {len(sample)}")
    if sample:
        print(f"  First row: gid={sample[0]['gid']}, uid={sample[0]['uid']}, " +
              f"schloss={sample[0]['kingdom_schloss']}, xp={sample[0]['xp']}, prestige={sample[0]['prestige']}")


async def main():
    import sys
    
    # Create DB pool
    pool = await asyncpg.create_pool(
        database="db",
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host="localhost"
    )
    
    try:
        print("=" * 60)
        print("MIGRATION: Firebase → PostgreSQL minigame_progression")
        print("=" * 60)

        # Delete table first
        async with pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS minigame_progression")
            print("🗑️  Dropped existing minigame_progression table")
        
        # Create table
        await create_table(pool)
        
        # Confirm before migrating if not --no-prompt
        if "--no-prompt" not in sys.argv:
            response = input("\n⚠️  This will migrate Firebase data to PostgreSQL. Continue? (yes/no): ").strip().lower()
            if response != "yes":
                print("❌ Migration cancelled")
                return
        
        # Migrate
        await migrate_data(pool)
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Test PostgreSQL helper functions with mock data")
        print("2. Update code files to use new helper functions")
        print("3. Monitor logs for any Firebase → PostgreSQL inconsistencies")
        
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
