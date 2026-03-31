from erpnext.packages.ai_hub.ai_hub_connector import AIHubConnector

class AIHubClient(AIHubConnector): 
    """
    AI Hub Client
    """

    def summary_lead_conversation(
        self,
        conversation_id : str, 
        page_id : str,
    ):
        """
        request to summary data conversation from pancake
        response summary send to webhook url
        """
        endpoint = "lead-info"

        data = {
            "conversationId" : conversation_id,
            "pageId": page_id,
            "webhookUrl": f"{self.webhook_url}/webhook/ai-hub/erp/leads"
        }

        print(data)
        return self.post(endpoint, json=data)
