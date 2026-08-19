"""
Unified provider package for Windows-Use.

Each provider lives in its own sub-package and exposes capabilities it supports.
"""

# Base protocols & data models
from windows_use.providers.base import BaseChatLLM, BaseSTT, BaseTTS
from windows_use.providers.events import LLMEvent, LLMStreamEvent, Thinking, ToolCall
from windows_use.providers.views import Metadata, TokenUsage

try:
    from windows_use.providers.anthropic import ChatAnthropic
except Exception:
    ChatAnthropic = None

try:
    from windows_use.providers.azure_openai import ChatAzureOpenAI
except Exception:
    ChatAzureOpenAI = None

try:
    from windows_use.providers.cerebras import ChatCerebras
except Exception:
    ChatCerebras = None

try:
    from windows_use.providers.deepseek import ChatDeepSeek
except Exception:
    ChatDeepSeek = None

try:
    from windows_use.providers.google import ChatGoogle, STTGoogle, TTSGoogle
except Exception:
    ChatGoogle = STTGoogle = TTSGoogle = None

try:
    from windows_use.providers.groq import ChatGroq, STTGroq, TTSGroq
except Exception:
    ChatGroq = STTGroq = TTSGroq = None

try:
    from windows_use.providers.litellm import ChatLiteLLM
except Exception:
    ChatLiteLLM = None

try:
    from windows_use.providers.mistral import ChatMistral
except Exception:
    ChatMistral = None

try:
    from windows_use.providers.nvidia import ChatNvidia
except Exception:
    ChatNvidia = None

try:
    from windows_use.providers.ollama import ChatOllama
except Exception:
    ChatOllama = None

try:
    from windows_use.providers.open_router import ChatOpenRouter
except Exception:
    ChatOpenRouter = None

try:
    from windows_use.providers.openai import ChatOpenAI, STTOpenAI, TTSOpenAI
except Exception:
    ChatOpenAI = STTOpenAI = TTSOpenAI = None

try:
    from windows_use.providers.vllm import ChatVLLM
except Exception:
    ChatVLLM = None

try:
    from windows_use.providers.elevenlabs import STTElevenLabs, TTSElevenLabs
except Exception:
    STTElevenLabs = TTSElevenLabs = None

try:
    from windows_use.providers.deepgram import STTDeepgram, TTSDeepgram
except Exception:
    STTDeepgram = TTSDeepgram = None

__all__ = [
    "BaseChatLLM",
    "BaseSTT",
    "BaseTTS",
    "LLMEvent",
    "LLMStreamEvent",
    "Thinking",
    "ToolCall",
    "Metadata",
    "TokenUsage",
    "ChatOllama",
    "ChatOpenAI",
]
