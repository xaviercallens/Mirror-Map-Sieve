from google.antigravity import LocalAgentConfig
from google.antigravity.types import GeminiConfig, ModelConfig, ModelEntry, GenerationConfig, ThinkingLevel

deep_think_cfg = GeminiConfig(
    models=ModelConfig(
        default=ModelEntry(
            name="gemini-2.5-pro",
            generation=GenerationConfig(thinking_level=ThinkingLevel.LOW)
        )
    )
)

cfg = LocalAgentConfig(gemini_config=deep_think_cfg)
print("SUCCESS")
