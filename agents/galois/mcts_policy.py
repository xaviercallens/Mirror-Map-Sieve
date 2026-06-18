import os
from agents.common.secrets import get_secret
import json
import logging
import requests

logger = logging.getLogger(__name__)


class MCTSPolicy:
    """LLM-based tactic generator for the Galois MCTS engine.

    Supports optional Alexandrie RAG injection: before each LLM call,
    queries the semantic memory for similar historical proof states and
    prepends them as few-shot examples in the system prompt.
    """

    def __init__(self, api_key: str = None, alexandrie_hub=None):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        if not api_key:
            api_key = os.environ.get("GALOIS_GEMINI_KEY") or get_secret("GEMINI_API_KEY")
            
        if not api_key:
            logger.warning("No API key provided, MCTS Policy will fail.")
            
        self.api_key = api_key
        self.model_name = "gemini-2.5-pro"

        # Alexandrie RAG integration (optional)
        self._alexandrie_hub = alexandrie_hub
        self._rag_hits = 0
        self._rag_misses = 0
        
        self.system_prompt = (
            "You are an expert Lean 4 tactic generator. Look at the current Goal State.\n"
            "First, provide a brief <thought> analyzing the mathematical strategy (e.g., \"I need to proceed by contradiction and define a diagonal set\").\n"
            "Then, provide the 5 best <tactic> strings to execute the next immediate step.\n"
            "Hint: For deep logic, actively construct new terms using `let`, `have`, or `obtain`.\n"
            "Return ONLY a valid JSON object with two keys: 'thought' (a string) and 'tactics' (a list of 5 strings). Do not include markdown or explanations outside the JSON."
        )

    def _get_gcloud_token(self) -> str:
        import subprocess
        try:
            res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return ""

    def _build_rag_augmented_prompt(self, goal_state: str) -> str:
        """Build the user prompt WITHOUT raw RAG text injection.
        
        Per Evolution 4: We do not inject paragraphs of text which destroy the context window.
        Instead, Alexandrie actionable tactics are injected natively during expansion with prior=1.0.
        """
        return f"Current Goal State:\n{goal_state}"

    def memorize_success(
        self,
        lean_state: str,
        blueprint: str,
        winning_tactic: str,
        source_agent: str = "galois",
    ) -> None:
        """Memorize a successful proof closure into Alexandrie.

        Called by the MCTS engine when a sorry gap is closed. The winning
        tactic and state are encoded into the FAISS index for future RAG.

        Args:
            lean_state: The Lean 4 tactic state at the moment of success.
            blueprint: The informal English strategy description.
            winning_tactic: The exact tactic string that closed the gap.
            source_agent: Which agent discovered this proof.
        """
        if self._alexandrie_hub is None or self._alexandrie_hub.semantic_memory is None:
            return

        try:
            self._alexandrie_hub.semantic_memory.memorize_success(
                lean_state=lean_state,
                informal_blueprint=blueprint,
                winning_tactic=winning_tactic,
                source_agent=source_agent,
            )
            logger.info(f"Memorized tactic '{winning_tactic[:60]}' into Alexandrie")
        except Exception as e:
            logger.warning(f"Failed to memorize into Alexandrie: {e}")

    def _parse_llm_response(self, data: dict) -> list[str]:
        """Parse a Gemini API response and extract filtered tactic list."""
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            # LLMs sometimes wrap JSON in markdown blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].strip()

            obj = json.loads(text)
            tactics = obj.get("tactics", [])

            banned_keywords = ["exact?", "apply?", "aesop", "tauto", "library_search"]
            filtered = [t for t in tactics if not any(b in t for b in banned_keywords)]

            if not isinstance(filtered, list):
                logger.error(f"Expected list, got {type(filtered)}: {filtered}")
                return []
            return filtered
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse Gemini response: {e}\nResponse: {data}")
            return []

    def _get_optimal_k(self) -> int:
        """Load the auto-optimized k value from config.json, fallback to 3."""
        import os
        import json
        config_path = os.path.join(os.path.dirname(__file__), "rag_config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    data = json.load(f)
                    return data.get("optimal_k", 3)
        except Exception as e:
            logger.warning(f"Failed to read rag_config.json: {e}")
        return 3

    def generate_tactics(self, goal_state: str, failed_tactics: list[str] = None, num_candidates: int = 8) -> list[str]:
        """Generate candidate tactics for the current Lean 4 goal state.

        Optionally augmented with Alexandrie RAG-retrieved historical tactics.

        Args:
            goal_state: The current Lean 4 tactic state.
            failed_tactics: Previously failed tactics for this state.
            num_candidates: Optional limit.

        Returns:
            List of tactic strings to try.
        """
        # Prepend raw RAG tactics directly from Alexandrie if available (prior = 1.0)
        rag_tactics = []
        if self._alexandrie_hub is not None:
            try:
                optimal_k = self._get_optimal_k()
                rag_tactics = self._alexandrie_hub.get_rag_tactics(goal_state, k=optimal_k)
                if failed_tactics:
                    rag_tactics = [t for t in rag_tactics if t not in failed_tactics]
            except Exception as e:
                logger.warning(f"Failed to retrieve raw RAG tactics from Alexandrie: {e}")

        prompt = self._build_rag_augmented_prompt(goal_state)
        if failed_tactics:
            prompt += f"\n\nNote: You have already tried {failed_tactics} on this state and they failed or did nothing. Propose novel tactics."
        
        # Try Vertex AI first if gcloud token is available
        token = self._get_gcloud_token()
        llm_tactics = []
        if token:
            url = "https://us-central1-aiplatform.googleapis.com/v1/projects/gen-lang-client-0625573011/locations/us-central1/publishers/google/models/gemini-2.5-pro:generateContent"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "systemInstruction": {
                    "parts": [{"text": self.system_prompt}]
                },
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.7
                }
            }
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                resp = requests.post(url, json=payload, headers=headers, verify=False, timeout=75)
                if resp.status_code == 200:
                    llm_tactics = self._parse_llm_response(resp.json())
            except Exception as e:
                logger.warning(f"Vertex AI call failed, falling back to public endpoint: {e}")

        if not llm_tactics:
            # Fallback to public developer endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
            payload = {
                "systemInstruction": {
                    "parts": [{"text": self.system_prompt}]
                },
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.7
                }
            }
            
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                resp = requests.post(url, json=payload, verify=False, timeout=75)
                if resp.status_code != 200:
                    logger.error(f"API Error {resp.status_code}: {resp.text}")
                resp.raise_for_status()
                llm_tactics = self._parse_llm_response(resp.json())
                    
            except Exception as e:
                logger.error(f"Failed to generate tactics via requests: {e}")

        # Combine prepended RAG tactics (high-priority) with LLM generated ones
        combined = []
        for t in rag_tactics:
            if t not in combined:
                combined.append(t)
        for t in llm_tactics:
            if t not in combined:
                combined.append(t)
        return combined

    @property
    def rag_stats(self) -> dict[str, int]:
        """Statistics on RAG injection usage."""
        return {
            "rag_hits": self._rag_hits,
            "rag_misses": self._rag_misses,
            "total_queries": self._rag_hits + self._rag_misses,
        }
