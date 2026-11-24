import asyncio
import json
import time
from app.schemas import ProspectDiscoveryRequest
from app.services.prospect_service import prospect_service

TEST_QUERIES = [
    "Football lovers in Washington DC in USA",
    "Digital marketing agency owners in New York USA",
    "Startup founders in London UK",
    "Cricket lovers in Ahmedabad India",
    "Restaurant owners in Dubai UAE"
]


async def run_all_test_queries():
    print("=" * 80)
    print("AI-POWERED MULTI-PLATFORM PROSPECT DISCOVERY API - DEMO EXECUTION")
    print("=" * 80)

    for idx, query in enumerate(TEST_QUERIES, 1):
        print(f"\n[Test Case {idx}/5] Query: \"{query}\"")
        start = time.perf_counter()
        req = ProspectDiscoveryRequest(query=query)
        res = await prospect_service.discover_prospects(req)
        elapsed = time.perf_counter() - start

        print(f"Elapsed Time: {elapsed:.2f} seconds | Prospects Found: {res.total_prospects}")
        print("Response JSON:")
        print(json.dumps(res.model_dump(), indent=2))
        print("-" * 80)


if __name__ == "__main__":
    asyncio.run(run_all_test_queries())
