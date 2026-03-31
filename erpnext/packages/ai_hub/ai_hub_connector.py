import requests

class AIHubConnector: 
    def __init__ (self, url , token, webhook_url):
        self.url = f"{url}/api"
        self.token = token 
        self.webhook_url = webhook_url
        self.headers = self._get_headers(token)
    
    def _get_headers(self, token : str):
        headers = {
            'Content-Type' : 'application/json',
            'Authorization' : f'Bearer {token}'
        }

        return headers
    
    async def get(self, endpoint, params=None):
        url = f'{self.url}/{endpoint}'
        return requests.get(url, params=params)

    async def post(self, endpoint, data=None, json=None):
        url = f'{self.url}/{endpoint}'
        return requests.post(url,data=data, json=json, headers=self.headers)
    
    async def put(self, endpoint, data):
        url = f'{self.url}/{endpoint}'
        return requests.put(url, data=data)

    async def delete(self, endpoint):
        url = f'{self.url}/{endpoint}'
        return requests.delete(url)

