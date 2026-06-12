# smoke_test.py
import asyncio, os
from dotenv import load_dotenv
from gpt_researcher import GPTResearcher
load_dotenv()

async def main():
    os.environ["RETRIEVER"] = "tavily,arxiv,semantic_scholar"  # confirm each works
    r = GPTResearcher(
        query="stateful detection of black-box query-based adversarial attacks",
        report_type="research_report",        # cheap mode for the smoke test
        verbose=True,
    )
    await r.conduct_research()
    print(await r.write_report())
    print("COSTS:", r.get_costs())

asyncio.run(main())
