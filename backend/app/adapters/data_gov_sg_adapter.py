"""Boundary for venue ingestion; dataset IDs remain a documented team decision."""


class DataGovSgAdapter:
    async def load_venues(self):
        raise RuntimeError("Approve exact data.gov.sg dataset IDs and mappings before importing venue data")
