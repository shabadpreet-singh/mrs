import requests

response = requests.post('http://127.0.0.1:5000/recommend', json={'movie': 'Batman Begins'})
print(response.json())
