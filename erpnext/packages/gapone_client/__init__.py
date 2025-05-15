from erpnext.packages.gapone_client.branch_client import BranchClient

class GapOneClient():
    """
    Package to connect GapOne api 
    """
    def __init__(self, api_key):

        self.__branch_client = BranchClient(api_key)

    @property
    def branch(self):
        return self.__branch_client