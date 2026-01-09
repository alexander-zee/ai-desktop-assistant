from openai import OpenAI

client = OpenAI(api_key="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")

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say 'Michael online successfully'."}],
)

print(response.choices[0].message.content)
