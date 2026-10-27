"""Recommendation engine: candidate generation, feasibility and scoring.

SRS Sections 4.3 and 4.4 (FR-C1 to FR-C6, FR-D1 to FR-D10), Appendix E.2
"Control - Recommender". See README.md in this folder for how the service
layer calls it.

Import from the submodules, for example::

    from app.recommender.engine import RecommendationEngine
    from app.recommender.types import RecommendationRequest

(This package deliberately has no eager imports: ``app.adapters.ports``
depends on ``app.recommender.types``, and the engine depends on the ports.)
"""
