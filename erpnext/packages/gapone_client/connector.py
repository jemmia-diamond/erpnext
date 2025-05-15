import json
import requests

class Connector:
    def __init__(self, api_key) -> None:
        self.__base_url = "https://api.gapone.vn/v1"
        self.__headers  = {
            'Authorization': f'Basic {api_key}'
        }

    def __generate_headers(self):
        return self.__headers
    
    def _make_request(self, path, payload = "", params = {}, method="GET",  print_payload=False):
        url = self.__base_url + path
        payload = json.dumps(payload)
        if print_payload:
            print_payload(payload)

        headers = self.__generate_headers()
        response = requests.request(method=method, url=url, headers=headers, data=payload, params=params)
        return response
