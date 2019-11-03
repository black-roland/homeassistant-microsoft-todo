from requests.exceptions import HTTPError


class OutlookTasksApi:

    api_endpoint = "https://graph.microsoft.com"

    def __init__(self, client, logger, timezone):
        self.client = client
        self.logger = logger
        self.timezone = timezone

    def create_task(self, subject, note=None, reminder_date_time=None):
        uri = self.api_endpoint + "/beta/me/outlook/tasks"

        task_req = {
            "subject": subject,
        }

        if note:
            task_req["body"] = {
                "contentType": "Text",
                "content": note
            }

        if reminder_date_time:
            task_req["reminderDateTime"] = {
                "dateTime": reminder_date_time,
                "timeZone": self.timezone.zone
            }
            task_req["isReminderOn"] = True

        try:
            res = self.client.post(uri, json=task_req)
            res.raise_for_status()
        except HTTPError as e:
            self.logger.error("%s. Response: %s", e, res.json())

        return res
