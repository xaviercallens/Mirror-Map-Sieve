import json
from agents.galois.auth import GaloisAuthManager
from agents.common.a2a_models import ConjecturePayload, Lean4Sketch

class ConjectureGenerator:
    def __init__(self):
        # 1. Initialize our environment-aware Auth Manager
        self.auth = GaloisAuthManager()

    async def generate(self, problem_id: str, problem_prompt: str) -> dict:
        print(f"🧠 Galois [{problem_id}]: Thinking via Gemini 1.5 Pro...")
        
        system_instruction = (
            "You are the Galois Agent, an expert mathematician. "
            "Analyze the following HorizonMath problem. "
            "Respond ONLY with a valid JSON object containing exactly two keys: "
            "'statement' (your mathematical conjecture/insight) and "
            "'lean4_code' (a valid Lean 4 AST representing the formal sketch)."
        )
        
        try:
            # 2. 🚀 ACTUALLY CALL THE LLM HERE
            # (If local, it uses the .env key. If GCP, it uses the Workload Identity)
            response = self.auth.gemini_client.generate_content(
                f"{system_instruction}\n\nProblem: {problem_prompt}"
            )
            
            # 3. Parse and Clean the LLM Output
            raw_text = response.text.strip().replace("```json", "").replace("```", "")
            generated_data = json.loads(raw_text)
            
            # 4. Bind to the Strict A2A Payload (This enforces no GL(n, R) mocks!)
            payload = ConjecturePayload(
                problem_id=problem_id,
                statement=generated_data["statement"],
                lean4_sketch=Lean4Sketch.encode(generated_data["lean4_code"])
            )
            
            return {"conjecture_generator": json.loads(payload.model_dump_json())}
            
        except Exception as e:
            # 5. THIS is what Euler will safely catch if the API fails or rate-limits
            return {"conjecture_generator": {"error": f"Fail-loud: LLM Generation crashed - {str(e)}"}}
