from llmproxy import LLMProxy
from pathlib import Path
import pandas as pd

client = LLMProxy()

response_gpt4_1 = client.generate(model = 'gpt-4.1-mini', #part 1 hw1 is to use a model and call it twice on the same prompt
    system = '',
    query = 'There’s a ballot measure about housing in my town. Can you explain what it means?',
    temperature=0.0,
    lastk=0,
    session_id='HW1_Session1',
    rag_usage = False
)

response_gpt4_2 = client.generate(model = 'gpt-4.1-mini',
    system = '',
    query = 'There’s a ballot measure about housing in my town. Can you explain what it means?',
    temperature=0.0,
    lastk=0,
    session_id='HW1_Session2',
    rag_usage = False
)

response_gptmini = client.generate(model = '4o-mini', #part 2 hw1 is to use a second model and call it once on the same prompt as before
    system = '',
    query = 'There’s a ballot measure about housing in my town. Can you explain what it means?',
    temperature=0.0,
    lastk=0,
    session_id='HW1_Session3',
    rag_usage = False
)

output_csv_path = Path(__file__).parent / "hw1_responses.csv"

data = {
    "Response Number": ["4.1-mini_1", "4.1-mini_2", "GPT-4o-mini"],
    "Response": [
        response_gpt4_1.get('result'),
        response_gpt4_2.get('result'),
        response_gptmini.get('result')
    ]
}
df = pd.DataFrame(data)
df.to_csv(output_csv_path, index=False)

print(f"Responses saved to {output_csv_path} successfully!")