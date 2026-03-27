#!/usr/bin/env python3
"""
Events Data Migration Script
Migrates Events system data from old Firebase paths to new Chat Minigames structure.

Usage:
    python3 migration.py --dry-run    # Preview changes without making them
    python3 migration.py              # Execute migration
    
Migration Plan:
1. Global User Quests/{uid}/{gid} → Chat Minigames Quests/{gid}/{uid}
2. Global Progression Rewards/{gid}/{uid}/* → Chat Minigames Cosmetics/{gid}/{uid}/*
3. Global User Titles/{uid}/global_titles/{timestamp} → Chat Minigames Cosmetics/{gid}/{uid}/titles/{timestamp}
4. Global Events Rewards/{randomKey} → Chat Minigames Rewards/{gid}/shop
5. Milestones/{gid}/{randomKey} → Chat Minigames Rewards/{gid}/milestones
6. Global Events System/{randomKey} → Chat Minigames System/{cid}

User Events Inventory is NOT migrated (kept in original location)
"""

import argparse
import sys
import time
import json
import firebase_admin
from typing import Dict, List, Any, Tuple
from firebase_admin import credentials, db

# Initialize Firebase
try:
    from assets.secret import DATABASE_PATH, DATABASE_URL
    cred = credentials.Certificate(DATABASE_PATH)
    firebase_app = firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
except Exception as e:
    print(f"✗ Firebase initialization failed: {e}")
    print("Make sure DATABASE_PATH and DATABASE_URL are set correctly in assets/secret.py")
    sys.exit(1)


class DataMigrator:
    """Handles all data migrations from old paths to new Chat Minigames structure."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.migration_stats = {
            "quests": 0,
            "cosmetics": 0,
            "titles": 0,
            "rewards": 0,
            "milestones": 0,
            "system": 0,
        }
        self.errors = []
        self.changes = []
    
    def log_change(self, change_type: str, source: str, destination: str, count: int = 1):
        """Log a change for dry-run reporting."""
        self.changes.append({
            "type": change_type,
            "source": source,
            "destination": destination,
            "count": count
        })
    
    def _write(self, path: str, data: Any) -> bool:
        """Write data to Firebase, or log if dry-run."""
        if self.dry_run:
            self.log_change("WRITE", path, path, 1)
            return True
        try:
            db.reference(path).set(data)
            return True
        except Exception as e:
            self.errors.append(f"Write error to {path}: {str(e)}")
            return False
    
    # ============= 1. GLOBAL USER QUESTS =============
    def migrate_quests(self) -> bool:
        """Migrate Global User Quests: {uid}/{gid} → {gid}/{uid}"""
        try:
            old_ref = db.reference("/Global User Quests")
            old_data = old_ref.get() or {}
            
            if not old_data:
                print("✓ No quest data to migrate")
                return True
            
            new_structure = {}
            for uid, guild_data in old_data.items():
                for gid, quest_data in guild_data.items():
                    if gid not in new_structure:
                        new_structure[gid] = {}
                    new_structure[gid][uid] = quest_data
            
            for gid, user_data in new_structure.items():
                self._write(f"/Chat Minigames Quests/{gid}", user_data)
                self.log_change("QUESTS", f"/Global User Quests/*/{{users}}", f"/Chat Minigames Quests/{gid}", len(user_data))
            
            self.migration_stats["quests"] = len(old_data)
            print(f"✓ Migrated {len(new_structure)} guild quest records")
            return True
            
        except Exception as e:
            self.errors.append(f"Quests migration error: {str(e)}")
            print(f"✗ Quests migration failed: {e}")
            return False
    
    # ============= 2. GLOBAL PROGRESSION REWARDS =============
    def migrate_cosmetics(self) -> bool:
        """Migrate Global Progression Rewards to Chat Minigames Cosmetics"""
        try:
            old_ref = db.reference("/Global Progression Rewards")
            old_data = old_ref.get() or {}
            
            if not old_data:
                print("✓ No cosmetics data to migrate")
                return True
            
            for gid, user_data in old_data.items():
                if isinstance(user_data, dict):
                    for uid, cosmetics in user_data.items():
                        if isinstance(cosmetics, dict) and "selected" in cosmetics:
                            selected = cosmetics.get("selected", {})
                            if isinstance(selected, dict) and "global_title" in selected:
                                # Extract timestamp from {gid}_{timestamp} format
                                global_title_value = selected["global_title"]
                                if "_" in global_title_value:
                                    parts = global_title_value.split("_", 1)
                                    timestamp = parts[1] if len(parts) > 1 else global_title_value
                                else:
                                    timestamp = global_title_value
                                
                                # Replace global_title with title
                                selected.pop("global_title")
                                selected["title"] = timestamp
                                cosmetics["selected"] = selected
                
                self._write(f"/Chat Minigames Cosmetics/{gid}", user_data)
                self.log_change("COSMETICS", f"/Global Progression Rewards/{gid}", f"/Chat Minigames Cosmetics/{gid}")
            
            self.migration_stats["cosmetics"] = len(old_data)
            print(f"✓ Migrated {len(old_data)} guild cosmetics records")
            return True
            
        except Exception as e:
            self.errors.append(f"Cosmetics migration error: {str(e)}")
            print(f"✗ Cosmetics migration failed: {e}")
            return False
    
    # ============= 3. GLOBAL USER TITLES =============
    def migrate_titles(self) -> bool:
        """Migrate Global User Titles into Chat Minigames Cosmetics/titles"""
        try:
            old_ref = db.reference("/Global User Titles")
            old_data = old_ref.get() or {}
            
            if not old_data:
                print("✓ No titles data to migrate")
                return True
            
            title_count = 0
            cosmetics_updates = {}
            
            for uid, user_titles_data in old_data.items():
                global_titles = user_titles_data.get("global_titles", {})
                
                for key, title_data in global_titles.items():
                    try:
                        title_count += 1
                        gid = title_data.get("guild_id")
                        
                        if not gid:
                            gid_str = key.split("_")[0]
                            gid = gid_str
                        
                        parts = key.split("_")
                        if len(parts) >= 2:
                            timestamp = "_".join(parts[1:])
                        else:
                            timestamp = str(int(time.time() * 1000))
                        
                        cosmetics_key = f"{gid}/{uid}"
                        if cosmetics_key not in cosmetics_updates:
                            cosmetics_updates[cosmetics_key] = {}
                        
                        if "titles" not in cosmetics_updates[cosmetics_key]:
                            cosmetics_updates[cosmetics_key]["titles"] = {}
                        
                        cosmetics_updates[cosmetics_key]["titles"][timestamp] = {"name": title_data.get("name", "")}
                        
                    except Exception as e:
                        self.errors.append(f"Title migration error for {uid} key {key}: {str(e)}")
                        continue
            
            for cosmetics_key, title_updates in cosmetics_updates.items():
                gid, uid = cosmetics_key.split("/")
                cosmetics_path = f"/Chat Minigames Cosmetics/{gid}/{uid}"
                cosmetics_ref = db.reference(cosmetics_path)
                
                if not self.dry_run:
                    cosmetics_data = cosmetics_ref.get() or {}
                    if "titles" not in cosmetics_data:
                        cosmetics_data["titles"] = {}
                    cosmetics_data["titles"].update(title_updates["titles"])
                    cosmetics_ref.set(cosmetics_data)
                else:
                    self.log_change("TITLES", f"/Global User Titles/{uid}/global_titles", f"/Chat Minigames Cosmetics/{gid}/{uid}/titles", len(title_updates.get("titles", {})))
            
            self.migration_stats["titles"] = title_count
            print(f"✓ Migrated {title_count} titles into cosmetics")
            return True
            
        except Exception as e:
            self.errors.append(f"Titles migration error: {str(e)}")
            print(f"✗ Titles migration failed: {e}")
            return False
    
    # ============= 4. GLOBAL EVENTS REWARDS =============
    def migrate_rewards(self) -> bool:
        """Migrate Global Events Rewards to Chat Minigames Rewards/shop"""
        try:
            old_ref = db.reference("/Global Events Rewards")
            old_data = old_ref.get() or {}
            
            if not old_data:
                print("✓ No rewards data to migrate")
                return True
            
            rewards_by_guild = {}
            
            for key, reward_entry in old_data.items():
                try:
                    gid = reward_entry.get("Server ID")
                    rewards_list = reward_entry.get("Rewards", [])
                    
                    if not gid:
                        self.errors.append(f"Reward entry {key} missing Server ID, skipping")
                        continue
                    
                    if gid not in rewards_by_guild:
                        rewards_by_guild[gid] = []
                    
                    rewards_by_guild[gid].extend(rewards_list)
                except Exception as e:
                    self.errors.append(f"Reward entry error {key}: {str(e)}")
                    continue
            
            for gid, rewards_list in rewards_by_guild.items():
                existing = db.reference(f"/Chat Minigames Rewards/{gid}").get() or {} if not self.dry_run else {}
                existing["shop"] = rewards_list
                self._write(f"/Chat Minigames Rewards/{gid}", existing)
                self.log_change("REWARDS", f"/Global Events Rewards/*/Rewards", f"/Chat Minigames Rewards/{gid}/shop", len(rewards_list))
            
            self.migration_stats["rewards"] = len(rewards_by_guild)
            print(f"✓ Migrated rewards for {len(rewards_by_guild)} guilds")
            return True
            
        except Exception as e:
            self.errors.append(f"Rewards migration error: {str(e)}")
            print(f"✗ Rewards migration failed: {e}")
            return False
    
    # ============= 5. MILESTONES =============
    def migrate_milestones(self) -> bool:
        """Migrate Milestones to Chat Minigames Rewards/milestones as list format
        
        New format: Each milestone is [description, reward, threshold]
        """
        try:
            old_ref = db.reference("/Milestones")
            old_data = old_ref.get() or {}
            
            if not old_data:
                print("✓ No milestones data to migrate")
                return True
            
            milestones_count = 0
            
            for gid, milestones_entries in old_data.items():
                try:
                    milestones_list = []
                    
                    if isinstance(milestones_entries, dict):
                        for key, milestone_data in milestones_entries.items():
                            # Convert dict format to list format: [description, reward, threshold]
                            description = milestone_data.get("description", "")
                            reward = milestone_data.get("reward", "")
                            threshold = milestone_data.get("threshold", 0)
                            
                            milestones_list.append([description, reward, threshold])
                            milestones_count += 1
                    
                    rewards_path = f"/Chat Minigames Rewards/{gid}"
                    if not self.dry_run:
                        rewards_ref = db.reference(rewards_path)
                        rewards_data = rewards_ref.get() or {}
                        rewards_data["milestones"] = milestones_list
                        rewards_ref.set(rewards_data)
                    else:
                        self.log_change("MILESTONES", f"/Milestones/{gid}", f"/Chat Minigames Rewards/{gid}/milestones", len(milestones_list))
                    
                except Exception as e:
                    self.errors.append(f"Milestone error for guild {gid}: {str(e)}")
                    continue
            
            self.migration_stats["milestones"] = milestones_count
            print(f"✓ Migrated {milestones_count} milestone records")
            return True
            
        except Exception as e:
            self.errors.append(f"Milestones migration error: {str(e)}")
            print(f"✗ Milestones migration failed: {e}")
            return False
    
    # ============= 6. GLOBAL EVENTS SYSTEM =============
    def migrate_system(self) -> bool:
        """Migrate Global Events System to Chat Minigames System"""
        try:
            old_ref = db.reference("/Global Events System")
            old_data = old_ref.get() or {}
            
            if not old_data:
                print("✓ No system data to migrate")
                return True
            
            system_by_channel = {}
            
            for key, system_entry in old_data.items():
                try:
                    cid = system_entry.get("Channel ID")
                    frequency = system_entry.get("Frequency")
                    events = system_entry.get("Events", [])
                    
                    if not cid:
                        self.errors.append(f"System entry {key} missing Channel ID, skipping")
                        continue
                    
                    system_by_channel[cid] = {
                        "events": events,
                        "frequency": frequency
                    }
                except Exception as e:
                    self.errors.append(f"System entry error {key}: {str(e)}")
                    continue
            
            for cid, system_data in system_by_channel.items():
                self._write(f"/Chat Minigames System/{cid}", system_data)
                self.log_change("SYSTEM", f"/Global Events System/*, Channel ID={cid}", f"/Chat Minigames System/{cid}")
            
            self.migration_stats["system"] = len(system_by_channel)
            print(f"✓ Migrated {len(system_by_channel)} channel system configs")
            return True
            
        except Exception as e:
            self.errors.append(f"System migration error: {str(e)}")
            print(f"✗ System migration failed: {e}")
            return False
    
    # ============= VALIDATION =============
    def validate_migrations(self) -> Tuple[bool, Dict[str, Any]]:
        """Validate all migrations by comparing old vs new data."""
        validation_report = {
            "quests_valid": False,
            "cosmetics_valid": False,
            "titles_valid": False,
            "rewards_valid": False,
            "milestones_valid": False,
            "system_valid": False,
            "details": []
        }
        
        try:
            old_quests = db.reference("/Global User Quests").get() or {}
            new_quests = db.reference("/Chat Minigames Quests").get() or {}
            old_quest_count = sum(len(guild_data) for guild_data in old_quests.values()) if old_quests else 0
            new_quest_count = sum(len(user_data) for user_data in new_quests.values()) if new_quests else 0
            validation_report["quests_valid"] = old_quest_count == new_quest_count
            validation_report["details"].append(f"Quests: {old_quest_count} old == {new_quest_count} new")
            
            old_cosmetics = db.reference("/Global Progression Rewards").get() or {}
            new_cosmetics = db.reference("/Chat Minigames Cosmetics").get() or {}
            validation_report["cosmetics_valid"] = len(old_cosmetics) == len(new_cosmetics)
            validation_report["details"].append(f"Cosmetics: {len(old_cosmetics)} old == {len(new_cosmetics)} new")
            
            old_titles = db.reference("/Global User Titles").get() or {}
            old_title_count = sum(len(user_data.get("global_titles", {})) for user_data in old_titles.values()) if old_titles else 0
            new_cosmetics_with_titles = new_cosmetics
            new_title_count = 0
            for guild_data in new_cosmetics_with_titles.values():
                if isinstance(guild_data, dict):
                    for user_data in guild_data.values():
                        if isinstance(user_data, dict):
                            new_title_count += len(user_data.get("titles", {}))
            validation_report["titles_valid"] = old_title_count == new_title_count
            validation_report["details"].append(f"Titles: {old_title_count} old == {new_title_count} new")
            
            old_rewards = db.reference("/Global Events Rewards").get() or {}
            new_rewards = db.reference("/Chat Minigames Rewards").get() or {}
            validation_report["rewards_valid"] = (len(old_rewards) > 0 and len(new_rewards) > 0) or (len(old_rewards) == 0 and len(new_rewards) == 0)
            validation_report["details"].append(f"Rewards: {len(old_rewards)} old entries → {len(new_rewards)} new guild entries")
            
            old_milestones = db.reference("/Milestones").get() or {}
            new_milestones_data = db.reference("/Chat Minigames Rewards").get() or {}
            old_milestone_count = sum(len(guild_data) if isinstance(guild_data, dict) else 0 for guild_data in old_milestones.values()) if old_milestones else 0
            new_milestone_count = sum(len(guild_data.get("milestones", [])) for guild_data in new_milestones_data.values()) if new_milestones_data else 0
            validation_report["milestones_valid"] = old_milestone_count == new_milestone_count
            validation_report["details"].append(f"Milestones: {old_milestone_count} old == {new_milestone_count} new")
            
            old_system = db.reference("/Global Events System").get() or {}
            new_system = db.reference("/Chat Minigames System").get() or {}
            validation_report["system_valid"] = len(old_system) == len(new_system)
            validation_report["details"].append(f"System: {len(old_system)} old == {len(new_system)} new")
            
        except Exception as e:
            validation_report["details"].append(f"Validation error: {str(e)}")
        
        all_valid = all([
            validation_report["quests_valid"],
            validation_report["cosmetics_valid"],
            validation_report["titles_valid"],
            validation_report["rewards_valid"],
            validation_report["milestones_valid"],
            validation_report["system_valid"],
        ])
        
        return all_valid, validation_report
    
    # ============= MAIN MIGRATION FLOW =============
    def execute_migration(self) -> Tuple[bool, Dict[str, Any]]:
        """Execute all migrations in sequence."""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        print("\n" + "="*60)
        print(f"STARTING EVENTS DATA MIGRATION ({mode})")
        print("="*60 + "\n")
        
        all_success = True
        
        steps = [
            ("Migrating Quests", self.migrate_quests),
            ("Migrating Cosmetics", self.migrate_cosmetics),
            ("Migrating Titles", self.migrate_titles),
            ("Migrating Rewards", self.migrate_rewards),
            ("Migrating Milestones", self.migrate_milestones),
            ("Migrating System", self.migrate_system),
        ]
        
        for step_name, migration_func in steps:
            print(f"\n{step_name}...")
            success = migration_func()
            all_success = all_success and success
        
        print("\n" + "-"*60)
        print("VALIDATING MIGRATIONS")
        print("-"*60)
        
        validation_success, validation_report = self.validate_migrations()
        
        for detail in validation_report["details"]:
            print(f"  {detail}")
        
        print("\n" + "="*60)
        print("MIGRATION COMPLETE")
        print("="*60)
        print(f"Overall Status: {'✓ SUCCESS' if validation_success else '✗ FAILED'}")
        print(f"Mode: {mode}")
        print(f"\nMigration Stats:")
        for key, value in self.migration_stats.items():
            print(f"  {key}: {value}")
        
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.dry_run and self.changes:
            print(f"\nPlanned Changes ({len(self.changes)}):")
            for change in self.changes[:10]:
                print(f"  {change['type']}: {change['source']} → {change['destination']} ({change['count']} items)")
            if len(self.changes) > 10:
                print(f"  ... and {len(self.changes) - 10} more")
        
        return validation_success, {
            "success": validation_success,
            "stats": self.migration_stats,
            "validation": validation_report,
            "errors": self.errors,
            "mode": mode
        }


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Events data from old Firebase paths to Chat Minigames structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them"
    )
    
    args = parser.parse_args()
    
    migrator = DataMigrator(dry_run=args.dry_run)
    success, report = migrator.execute_migration()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
