"""DB epoch — data substrate for all NeuroDb epochs.

This package is the target home for all DB epoch modules. Current flat-layout
modules migrate here when next significantly changed:

  schema.py       → db/schema.py
  migrations.py   → db/migrations.py
  db.py           → db/connection.py
  provenance.py   → db/provenance.py
  query.py        → db/query.py
  embedder.py     → db/embedder.py
  embed_hooks.py  → db/embed_hooks.py
  enrichment.py   → db/enrichment.py
  study.py        → db/study.py
  vector_store.py → db/vector_store.py
  connectors/     → db/connectors/

Interface to other epochs: SQLAlchemy engine (injected), named query helper
functions, DuckDB views. No other epoch executes raw SQL or calls ORM methods
directly outside a helper in this package.
"""

# Re-export db.py functions for backward compatibility during migration.
# Once all imports have migrated to db.connection, these can be removed.
from pathlib import Path

# Import from the legacy db.py module (not from this package)
import importlib.util
_db_module_path = Path(__file__).parent.parent / "db.py"
_spec = importlib.util.spec_from_file_location("_db_legacy", _db_module_path)
_db_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_db_legacy)

# Re-export all public functions and internal migration registry
get_engine = _db_legacy.get_engine
init_db = _db_legacy.init_db
seed_learning_sources = _db_legacy.seed_learning_sources
create_views = _db_legacy.create_views
get_session = _db_legacy.get_session
_MIGRATIONS = _db_legacy._MIGRATIONS
_migration_016_question_topic_tables = _db_legacy._migration_016_question_topic_tables
_migration_017_groupings = _db_legacy._migration_017_groupings
_migration_018_seed_grouping_hierarchy = _db_legacy._migration_018_seed_grouping_hierarchy
_migration_019_resync_grouping_sequences = _db_legacy._migration_019_resync_grouping_sequences

__all__ = ["get_engine", "init_db", "seed_learning_sources", "create_views", "get_session"]
