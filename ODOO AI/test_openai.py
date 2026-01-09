from openai import OpenAI

client = OpenAI(api_key="YOUR API KEY HERE")

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say 'Michael online successfully'."}],
)

print(response.choices[0].message.content)

