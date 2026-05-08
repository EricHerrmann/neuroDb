"""Research epoch — Goal 2 capability: hypothesis formation, evidence tracking,
research run management.

This package is the target home for all Research epoch modules.
Implemented modules:

  research/hypothesis_review.py — premium-tier hypothesis critique

Flat-layout modules that migrate here when next significantly changed:

  research_tools.py  → research/tools.py
  discovery_tools.py → research/discovery.py

Interface to Tutor epoch: reads knowledge library via search_knowledge_library()
only. Research epoch code contains no writes to knowledge_sources or the
knowledge_library ChromaDB collection.

Interface to DB epoch: reads/writes research artifact tables (ResearchHypothesis,
HypothesisReview) through DB epoch helper functions only.
"""
