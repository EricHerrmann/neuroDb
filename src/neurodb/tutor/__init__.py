"""Tutor epoch — Goal 1 capability: knowledge library, literature search,
chapter registry, session memory.

This package is the target home for all Tutor epoch modules.
Current flat-layout modules migrate here when next significantly changed:

  knowledge_store.py   → tutor/knowledge_store.py
  literature_client.py → tutor/literature_client.py
  chapter_registry.py  → tutor/chapter_registry.py

Ownership: the Tutor epoch owns the write path to the knowledge library.
It is the only epoch that writes to the papers table and the
knowledge_library ChromaDB collection.
"""
