"""Yoachi Sync Manager - Syncs data from dizical to yoachi"""
import os
import shutil
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('yoachi.sync')


class SyncManager:
    """Manages synchronization from dizical to yoachi database"""

    def __init__(self, dizical_path, yoachi_path, interval_seconds=300):
        """
        Initialize sync manager

        Args:
            dizical_path: Path to dizical SQLite database
            yoachi_path: Path to yoachi SQLite database
            interval_seconds: Sync interval in seconds (default: 300 = 5 minutes)
        """
        self.dizical_path = Path(dizical_path).expanduser()
        self.yoachi_path = Path(yoachi_path).expanduser()
        self.interval_seconds = interval_seconds
        self.last_sync = None
        self._scheduler = None

    def validate_source(self):
        """Validate source database exists, is accessible, and passes integrity check"""
        if not self.dizical_path.exists():
            logger.error(f"Source database not found: {self.dizical_path}")
            return False

        if not self.dizical_path.is_file():
            logger.error(f"Source path is not a file: {self.dizical_path}")
            return False

        try:
            conn = sqlite3.connect(f"file:{self.dizical_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            # PRAGMA integrity_check validates the entire database
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            if result[0] != 'ok':
                logger.error(f"Source database integrity check failed: {result}")
                conn.close()
                return False

            cursor.execute("SELECT COUNT(*) FROM achievements")
            count = cursor.fetchone()[0]
            conn.close()
            logger.info(f"Source database validated: {count} achievements, integrity ok")
            return True
        except Exception as e:
            logger.error(f"Failed to validate source database: {e}")
            return False

    def validate_copy(self, copy_path):
        """Validate copied database passes PRAGMA integrity_check"""
        if not copy_path.exists():
            logger.error(f"Target database not found after copy: {copy_path}")
            return False

        try:
            conn = sqlite3.connect(f"file:{copy_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            # PRAGMA integrity_check on the copied file
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            if result[0] != 'ok':
                logger.error(f"Copied database integrity check failed: {result}")
                conn.close()
                return False

            conn.close()
            logger.info("Copy integrity check passed")
            return True
        except Exception as e:
            logger.error(f"Failed to validate copy: {e}")
            return False

    def sync_once(self):
        """Perform a single sync operation"""
        logger.info("Starting sync...")
        
        # Validate source
        if not self.validate_source():
            logger.error("Source validation failed, skipping sync")
            return False
        
        # Ensure target directory exists
        self.yoachi_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temporary file for atomic copy
        temp_path = self.yoachi_path.with_suffix('.db.tmp')
        
        try:
            # Use SQLite backup API for proper WAL handling
            source_conn = sqlite3.connect(str(self.dizical_path))
            dest_conn = sqlite3.connect(str(temp_path))
            
            source_conn.backup(dest_conn)
            source_conn.close()
            dest_conn.close()
            logger.info("Database copied using SQLite backup API")
            
            # Validate the copy
            if not self.validate_copy(temp_path):
                logger.error("Copy validation failed, removing temp file")
                temp_path.unlink(missing_ok=True)
                return False
            
            # Atomic rename
            temp_path.rename(self.yoachi_path)
            logger.info("Atomic rename completed")
            
            self.last_sync = datetime.now()
            logger.info(f"Sync completed successfully at {self.last_sync}")
            return True
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            # Cleanup temp file on error
            temp_path.unlink(missing_ok=True)
            return False

    def start_background(self):
        """Start background sync using APScheduler (BlockingScheduler)"""
        self._scheduler = BlockingScheduler()

        self._scheduler.add_job(
            self.sync_once,
            trigger=IntervalTrigger(seconds=self.interval_seconds),
            id='sync_job',
            name='dizical-to-yoachi sync',
            replace_existing=True,
        )

        # Run once immediately on start
        self.sync_once()

        self._scheduler.start()
        logger.info(f"Background sync started (APScheduler, interval: {self.interval_seconds}s)")
        return self._scheduler

    def stop(self):
        """Stop background sync scheduler"""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Background sync scheduler stopped")


def run_sync_cli():
    """CLI entry point for running sync"""
    import argparse

    parser = argparse.ArgumentParser(description='Yoachi Sync Manager')
    parser.add_argument('--source', default='~/dev/dizical/data/dizi.db',
                       help='Path to dizical database')
    parser.add_argument('--target', default='./data/yoachi.db',
                       help='Path to yoachi database')
    parser.add_argument('--interval', type=int, default=300,
                       help='Sync interval in seconds')
    parser.add_argument('--once', action='store_true',
                       help='Run sync once and exit')

    args = parser.parse_args()

    sync_manager = SyncManager(
        dizical_path=args.source,
        yoachi_path=args.target,
        interval_seconds=args.interval
    )

    if args.once:
        success = sync_manager.sync_once()
        return 0 if success else 1
    else:
        sync_manager.start_background()
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            sync_manager.stop()
            return 0


if __name__ == '__main__':
    import sys
    sys.exit(run_sync_cli())
