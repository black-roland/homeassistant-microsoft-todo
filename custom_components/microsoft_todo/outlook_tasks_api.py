class OutlookTasksApi:

    api_endpoint = "https://graph.microsoft.com"

    def __init__(self, client):
        self.client = client

    def create_task(self, subject):
        uri = self.api_endpoint + "/beta/me/outlook/tasks"

        task_req = {
            "subject": subject,
        }

        req_headers = {
            "Prefer": "outlook.timezone",
        }

        return self.client.post(uri, json=task_req, headers=req_headers)
