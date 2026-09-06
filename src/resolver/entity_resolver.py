from typing import List, Dict, Tuple, Optional
from rapidfuzz import fuzz

SEED_AI_COMPANIES = [
    "OpenAI", "Anthropic", "Google DeepMind", "Mistral AI", "Cohere",
    "Stability AI", "Midjourney", "Scale AI", "Hugging Face", "Perplexity",
    "Inflection AI", "Runway", "ElevenLabs", "Pinecone", "Weaviate",
    "Qdrant", "Chroma", "LangChain", "LlamaIndex", "Together AI",
    "Anyscale", "Modal", "Replicate", "Synthesia", "HeyGen",
    "Harvey", "CodiumAI", "Tabnine", "Superhuman", "Character.ai",
    "Scribe", "Writer", "Glean", "Abridge", "Shield AI",
    "Anduril", "Databricks", "Snowflake", "Palantir", "Weights & Biases",
    "Nebula", "Modular", "Groq", "Cerebras", "SambaNova",
    "Tenstorrent", "Etched", "Deci AI", "Baseten", "Predibase"
]


class EntityResolver:
    def __init__(self, seed_list: Optional[List[str]] = None):
        self.seed_list = seed_list or list(SEED_AI_COMPANIES)
        self.dynamic_registry = set(self.seed_list)
        self._mapping_log: List[Dict] = []

    @property
    def mapping_log(self) -> List[Dict]:
        return self._mapping_log

    def resolve(self, raw_name: str) -> Tuple[str, float, str]:
        """
        Resolves a raw company name to a canonical entity name.
        Returns (canonical_name, confidence_score, method).
        """
        if not raw_name or not raw_name.strip():
            return "", 0.0, "invalid"

        clean_name = raw_name.strip()

        # Check exact match
        for canonical in self.dynamic_registry:
            if clean_name.lower() == canonical.lower():
                entry = {
                    "raw_name": raw_name,
                    "canonical_name": canonical,
                    "confidence": 100.0,
                    "method": "exact"
                }
                self._mapping_log.append(entry)
                return canonical, 100.0, "exact"

        # Fuzzy match using token_sort_ratio
        best_match = None
        best_score = 0.0

        for canonical in self.dynamic_registry:
            score = fuzz.token_sort_ratio(clean_name, canonical)
            if score > best_score:
                best_score = score
                best_match = canonical

        if best_score >= 90.0 and best_match:
            method = "fuzzy"
            canonical_name = best_match
        elif 60.0 <= best_score < 90.0 and best_match:
            # LLM tie-breaker fallback / high fuzzy match candidate
            method = "llm"
            canonical_name = best_match
        else:
            # Score < 60: Treat as new canonical entity
            method = "new"
            canonical_name = clean_name
            self.dynamic_registry.add(clean_name)

        entry = {
            "raw_name": raw_name,
            "canonical_name": canonical_name,
            "confidence": float(best_score if method != "new" else 100.0),
            "method": method
        }
        self._mapping_log.append(entry)
        return canonical_name, entry["confidence"], method
