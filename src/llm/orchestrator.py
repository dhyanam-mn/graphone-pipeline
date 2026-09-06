import os
import json
import asyncio
import tiktoken
from pydantic import BaseModel
from typing import Type, TypeVar, Optional
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

T = TypeVar("T", bound=BaseModel)

TOKEN_LIMIT = 6000
MAX_TOKEN_CAP = 8000


def count_tokens(text: str, model_name: str = "gpt-4") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def chunk_text(text: str, max_tokens: int = TOKEN_LIMIT) -> list[str]:
    total_tokens = count_tokens(text)
    if total_tokens <= max_tokens:
        return [text]

    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)
        if current_tokens + para_tokens > max_tokens:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_tokens = para_tokens
        else:
            current_chunk.append(para)
            current_tokens += para_tokens

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def _clean_json(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


from dotenv import load_dotenv

class LLMOrchestrator:
    def __init__(self):
        load_dotenv()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

    async def _try_gemini(self, prompt: str, schema_json: str) -> Optional[str]:
        if not self.gemini_api_key:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.gemini_api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            full_prompt = f"{prompt}\nReturn ONLY valid JSON matching this schema:\n{schema_json}"
            completion = await asyncio.to_thread(
                client.chat.completions.create,
                model="gemini-3.6-flash",
                messages=[{"role": "user", "content": full_prompt}],
                response_format={"type": "json_object"}
            )
            print("[orchestrator.py] Succeeded using Tier 1 (Gemini 3.6 Flash)")
            return completion.choices[0].message.content
        except Exception as e:
            print(f"[orchestrator.py] Tier 1 (Gemini) failed: {e}")
            return None

    async def _try_groq(self, prompt: str, schema_json: str) -> Optional[str]:
        if not self.groq_api_key:
            return None
        try:
            from groq import Groq
            client = Groq(api_key=self.groq_api_key)
            full_prompt = f"{prompt}\nReturn ONLY valid JSON matching this schema:\n{schema_json}"
            completion = await asyncio.to_thread(
                client.chat.completions.create,
                model="groq/compound-mini",
                messages=[{"role": "user", "content": full_prompt}],
                response_format={"type": "json_object"}
            )
            print("[orchestrator.py] Succeeded using Tier 2 (Groq Compound Mini)")
            return completion.choices[0].message.content
        except Exception as e:
            print(f"[orchestrator.py] Tier 2 (Groq) failed: {e}")
            return None

    async def _try_deepseek(self, prompt: str, schema_json: str) -> Optional[str]:
        if not self.deepseek_api_key:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.deepseek_api_key, base_url="https://api.deepseek.com")
            full_prompt = f"{prompt}\nReturn ONLY valid JSON matching this schema:\n{schema_json}"
            completion = await asyncio.to_thread(
                client.chat.completions.create,
                model="deepseek-chat",
                messages=[{"role": "user", "content": full_prompt}],
                response_format={"type": "json_object"}
            )
            print("[orchestrator.py] Succeeded using Tier 3 (DeepSeek)")
            return completion.choices[0].message.content
        except Exception as e:
            print(f"[orchestrator.py] Tier 3 (DeepSeek) failed: {e}")
            return None

    async def extract_structured(self, raw_text: str, target_schema: Type[T]) -> T:
        chunks = chunk_text(raw_text, TOKEN_LIMIT)
        input_text = chunks[0] if chunks else raw_text
        schema_json = json.dumps(target_schema.model_json_schema(), indent=2)

        prompt = f"Extract structured data from the following text according to the requested schema.\n\nText:\n{input_text}"

        # Tier 1: Gemini
        res = await self._try_gemini(prompt, schema_json)
        if res:
            try:
                cleaned = _clean_json(res)
                return target_schema.model_validate_json(cleaned)
            except Exception as e:
                print(f"[orchestrator.py] Tier 1 JSON parsing failed: {e}")

        # Tier 2: Groq
        res = await self._try_groq(prompt, schema_json)
        if res:
            try:
                cleaned = _clean_json(res)
                return target_schema.model_validate_json(cleaned)
            except Exception as e:
                print(f"[orchestrator.py] Tier 2 JSON parsing failed: {e}")

        # Tier 3: DeepSeek
        res = await self._try_deepseek(prompt, schema_json)
        if res:
            try:
                cleaned = _clean_json(res)
                return target_schema.model_validate_json(cleaned)
            except Exception as e:
                print(f"[orchestrator.py] Tier 3 JSON parsing failed: {e}")

        raise RuntimeError("All LLM tiers failed or no valid API keys provided in environment.")

