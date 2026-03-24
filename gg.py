import requests
import json

response = requests.get(
  url="https://openrouter.ai/api/v1/key",
  headers={
    "Authorization": f"Bearer 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"
  }
)

print(json.dumps(response.json(), indent=2))
