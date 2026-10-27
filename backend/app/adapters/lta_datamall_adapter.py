"""Conditional LTA boundary retained for diagram traceability.

No generic origin/destination routing call is claimed: DataMall road-segment estimates
are not equivalent. Use OneMap unless the team validates a specific LTA endpoint.
"""


class LtaDataMallAdapter:
    async def route(self, *args, **kwargs):
        raise RuntimeError("No approved LTA origin/destination routing endpoint")
