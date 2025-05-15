
from erpnext.packages.gapone_client.connector import Connector

class BranchClient(Connector):
    def __init__(self, api_key) -> None:
        super().__init__(api_key)
    
    def get_branches(self):
        """
        get branch name which registered and approve
        """

        path = f"/sender/sms"
        response = self._make_request(path)

        return response.json()