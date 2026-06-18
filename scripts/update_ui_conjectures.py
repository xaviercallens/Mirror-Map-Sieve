import json
import re

enriched_path = "/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/callens_conjectures_enriched.json"
page_path = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/lmms-lab-writer/apps/web/src/app/openroom/page.tsx"

with open(enriched_path, "r") as f:
    data = json.load(f)

with open(page_path, "r") as f:
    page = f.read()

new_conjectures_str = "const CONJECTURES = " + json.dumps(data, indent=4) + ";"
page = re.sub(r'const CONJECTURES = \[.*?\];', lambda _: new_conjectures_str, page, flags=re.DOTALL)

with open(page_path, "w") as f:
    f.write(page)

print("Updated page.tsx with enriched conjectures data!")
