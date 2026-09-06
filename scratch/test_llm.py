import asyncio
from src.llm.orchestrator import LLMOrchestrator
from src.schemas.models import ResearchPaper

async def main():
    o = LLMOrchestrator()
    sample_text = """
    Source URL: https://arxiv.org/abs/1706.03762
    Title: Attention Is All You Need
    Authors: Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin
    Abstract: The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.
    """
    res = await o.extract_structured(sample_text, ResearchPaper)
    print("Successfully extracted paper:")
    print("  Title:", res.title)
    print("  Authors:", res.authors)
    print("  Source URL:", res.source.url)
    print("  Record Type:", res.recordType)

if __name__ == "__main__":
    asyncio.run(main())
