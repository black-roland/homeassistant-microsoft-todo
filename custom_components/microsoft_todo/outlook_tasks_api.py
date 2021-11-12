import re

from requests.exceptions import HTTPError
import emoji # pylint: disable=import-error


class OutlookTasksApi:

    api_endpoint = "https://graph.microsoft.com"

    def __init__(self, client, logger, timezone):
        self.client = client
        self.logger = logger
        self.timezone = timezone

    def create_task(self, subject, list_id=None, note=None, due_date=None, reminder_date_time=None):
        uri = self.api_endpoint + "/beta/me/outlook/tasks"
        if list_id:
            uri = self.api_endpoint + "/beta/me/outlook/taskFolders/{}/tasks".format(list_id)

        task_req = {
            "subject": subject,
        }

        if note:
            task_req["body"] = {
                "contentType": "Text",
                "content": note
            }

        if due_date:
            task_req["dueDateTime"] = {
                "dateTime": due_date.isoformat(),
                "timeZone": str(self.timezone)
            }

        if reminder_date_time:
            task_req["reminderDateTime"] = {
                "dateTime": reminder_date_time.isoformat(),
                "timeZone": str(self.timezone)
            }
            task_req["isReminderOn"] = True

        try:
            self.logger.debug("Create task request: %s", task_req)
            res = self.client.post(uri, json=task_req)
            res.raise_for_status()
            self.logger.debug("Create task response: %s", res.json())
        except HTTPError as ex:
            self.logger.error("Unable to create task: %s. Response: %s", ex, res.json())
            raise

        return res

    def get_uncompleted_tasks(self, list_id):
        uri = self.api_endpoint + "/beta/me/outlook/taskFolders/{}/tasks".format(list_id)
        query_params = {
            "$filter": "status ne 'completed'",
            "$top": 100
        }

        try:
            self.logger.debug("Fetching To Do lists info")
            res = self.client.get(uri, params=query_params)
            res.raise_for_status()
            self.logger.debug("To Do tasks response: %s", res.json())
        except HTTPError as ex:
            self.logger.error("Unable to get tasks: %s. Response: %s", ex, res.json())
            raise

        return res.json()

    def get_list_id_by_name(self, list_name):
        lists = self.get_lists()

        try:
            return next(
                l["id"] for l in lists["value"]
                if l["name"] == list_name
                # To Do allows to set an icon (emoji) for a list and this emoji
                # is prepended to the list name so it needs to be stripped.
                or OutlookTasksApi.strip_emoji_icon(l["name"]) == list_name
            )
        except StopIteration as ex:
            self.logger.error("No list with the name %s. %s", list_name, ex)
            raise

    def get_lists(self):
        uri = self.api_endpoint + "/beta/me/outlook/taskFolders"
        # NOTE: don't increase more, implement proper pagination instead
        query_params = {"$top": 100}

        try:
            self.logger.debug("Fetching To Do lists info")
            res = self.client.get(uri, params=query_params)
            res.raise_for_status()
            self.logger.debug("To Do lists response: %s", res.json())
        except HTTPError as ex:
            self.logger.error("Unable to get lists info: %s. Response: %s", ex, res.json())
            raise

        return res.json()

    @staticmethod
    def strip_emoji_icon(list_name):
        emoji_re = emoji.get_emoji_regexp()
        list_emoji_icon_re = re.compile(u"^" + emoji_re.pattern)
        return list_emoji_icon_re.sub(r"", list_name)
