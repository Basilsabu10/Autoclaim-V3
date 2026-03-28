import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("HIVE_API_KEY")

test_img = os.path.join("test_images", "baleno", "damage.png")
url = "https://api.thehive.ai/api/v2/task/sync"
headers = {
    "authorization": f"token {api_key}",
    "accept": "application/json"
}

print(f"Testing Hive API with {test_img}")
with open(test_img, "rb") as f:
    files = {"media": (os.path.basename(test_img), f, "image/png")}
    data = {"classes": "ai_generated_image"}
    response = requests.post(url, headers=headers, files=files, data=data)

print("STATUS:", response.status_code)
print("RESPONSE:", response.text)
