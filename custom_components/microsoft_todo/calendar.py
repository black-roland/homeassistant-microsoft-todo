import logging
import os
from datetime import timedelta, datetime

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp.web import Response
from homeassistant.components.calendar import (
    PLATFORM_SCHEMA,
    CalendarEntity,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.helpers.network import get_url
from homeassistant.util import dt, Throttle
from homeassistant.util.json import load_json, save_json
from requests.adapters import HTTPAdapter
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
from urllib3.util import Retry

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    AUTH_CALLBACK_PATH,
    AUTHORIZATION_BASE_URL,
    TOKEN_URL,
    SCOPE,
    AUTH_REQUEST_SCOPE,
    MS_TODO_AUTH_FILE,
    SERVICE_NEW_TASK,
    SUBJECT,
    LIST_CONF,
    LIST_NAME,
    LIST_ID,
    NOTE,
    DUE_DATE,
    REMINDER_DATE_TIME,
    ALL_TASKS,
)
from .outlook_tasks_api import OutlookTasksApi

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
    }
)

NEW_TASK_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(SUBJECT): cv.string,
        vol.Exclusive(LIST_NAME, LIST_CONF): cv.string,
        vol.Exclusive(LIST_ID, LIST_CONF): cv.string,
        vol.Optional(NOTE): cv.string,
        vol.Optional(DUE_DATE): cv.date,
        vol.Optional(REMINDER_DATE_TIME): cv.datetime,
    }
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


def request_configuration(hass, config, add_entities, authorization_url):
    configurator = hass.components.configurator
    hass.data[DOMAIN] = configurator.request_config(
        "Microsoft To Do",
        lambda _: None,
        link_name="Link Microsoft To Do account",
        link_url=authorization_url,
        description="To link your Microsoft To Do account, "
                    "click the link, login, and authorize:",
        submit_caption="I authorized successfully",
    )


def setup_platform(hass, config, add_entities, discovery_info=None):
    config_path = hass.config.path(MS_TODO_AUTH_FILE)
    config_file = None
    if os.path.isfile(config_path):
        config_file = load_json(config_path)

    def token_saver(token):
        save_json(hass.config.path(MS_TODO_AUTH_FILE), token)

    # TODO: create a separate HTTP client class
    callback_url = f"{get_url(hass, prefer_external=True)}{AUTH_CALLBACK_PATH}"
    oauth = OAuth2Session(
        config.get(CONF_CLIENT_ID),
        scope=SCOPE,
        redirect_uri=callback_url,
        token=config_file,
        auto_refresh_url=TOKEN_URL,
        auto_refresh_kwargs={
            'client_id': config.get(CONF_CLIENT_ID),
            'client_secret': config.get(CONF_CLIENT_SECRET),
        },
        token_updater=token_saver
    )
    retry = Retry(status=3, connect=3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    oauth.mount("http://", adapter)
    oauth.mount("https://", adapter)

    tasks_api = OutlookTasksApi(client=oauth, logger=_LOGGER, timezone=dt.DEFAULT_TIME_ZONE)

    if not config_file:
        _LOGGER.info(f"Redirect URI: {callback_url}")
        # NOTE: request extra scope for the offline access and avoid
        # exception related to differences between requested and granted scopes
        oauth.scope = AUTH_REQUEST_SCOPE
        authorization_url, _state = oauth.authorization_url(AUTHORIZATION_BASE_URL)
        oauth.scope = SCOPE
        request_configuration(hass, config, add_entities, authorization_url)

    hass.http.register_view(
        MSToDoAuthCallbackView(
            oauth,
            config.get(CONF_CLIENT_SECRET),
            [hass, config, add_entities, discovery_info]
        )
    )

    if config_file:
        try:
            todo_lists = tasks_api.get_lists()["value"]
            calendar_devices = [
                MSToDoListDevice(tasks_api, todo_list['id'], OutlookTasksApi.strip_emoji_icon(todo_list['name'])) for
                todo_list in todo_lists]
            add_entities(calendar_devices)
        except InvalidGrantError as ex:
            _LOGGER.warn(f"InvalidGrantError - Triggering reconfiguration")
            oauth.scope = AUTH_REQUEST_SCOPE
            authorization_url, _state = oauth.authorization_url(AUTHORIZATION_BASE_URL)
            oauth.scope = SCOPE
            request_configuration(hass, config, add_entities, authorization_url)

    def handle_new_task(call):
        subject = call.data.get(SUBJECT)
        list_name = call.data.get(LIST_NAME)
        list_id = tasks_api.get_list_id_by_name(list_name) if list_name else call.data.get(LIST_ID)
        note = call.data.get(NOTE)
        due_date = call.data.get(DUE_DATE)
        reminder_date_time = call.data.get(REMINDER_DATE_TIME)
        tasks_api.create_task(subject, list_id, note, due_date, reminder_date_time)

    hass.services.register(
        DOMAIN, SERVICE_NEW_TASK, handle_new_task, schema=NEW_TASK_SERVICE_SCHEMA
    )


class MSToDoAuthCallbackView(HomeAssistantView):
    url = AUTH_CALLBACK_PATH
    name = "auth:ms_todo:callback"
    requires_auth = False

    def __init__(self, oauth, client_secret, setup_args):
        self.oauth = oauth
        self.client_secret = client_secret
        self.setup_args = setup_args

    def get_token(self, code):
        return self.oauth.fetch_token(
            TOKEN_URL,
            client_secret=self.client_secret,
            code=code
        )

    @callback
    async def get(self, request):
        hass = request.app["hass"]
        data = request.query

        html_response = """<html><head><title>Microsoft To Do authorization</title></head>
                           <body><h1>{}</h1></body></html>"""

        if data.get("code") is None:
            error_msg = "No code returned from Microsoft Graph Auth API"
            _LOGGER.error(error_msg)
            return Response(text=html_response.format(error_msg), content_type="text/html")

        token = await hass.async_add_executor_job(self.get_token, data.get("code"))

        save_json(hass.config.path(MS_TODO_AUTH_FILE), token)

        response_message = """Microsoft To Do has been successfully authorized!
                              You can close this window now!"""

        hass.async_add_job(setup_platform, *self.setup_args)

        return Response(
            text=html_response.format(response_message), content_type="text/html"
        )


class MSToDoListDevice(CalendarEntity):

    def __init__(self, tasks_api, list_id, list_name):
        self._tasks_api = tasks_api
        self._list_id = list_id
        self._list_name = list_name
        self._tasks = []

    @property
    def event(self):
        # TODO: implement this
        return None

    @property
    def name(self):
        return self._list_name

    @property
    def extra_state_attributes(self):
        _LOGGER.debug("Total Tasks: %i", len(self._tasks))
        if len(self._tasks) == 0:
            return None

        attributes = {}
        try:
            # all tasks
            attributes[ALL_TASKS] = [t["subject"] for t in self._tasks]
            _LOGGER.debug("ALL_TASKS count: %i", len(attributes[ALL_TASKS]))

            # due today
            __today = (
                lambda x: x["dueDateTime"] != None
                and datetime.strptime(
                    x["dueDateTime"]["dateTime"].split("T")[0], "%Y-%m-%d"
                ).date()
                == datetime.now().date()
            )
            attributes["duetoday_tasks"] = [
                t["subject"] for t in filter(__today, self._tasks)
            ]
            _LOGGER.debug("duetoday_tasks count: %i", len(attributes["duetoday_tasks"]))

            # overdue
            __overdue = (
                lambda x: x["dueDateTime"] != None
                and datetime.strptime(
                    x["dueDateTime"]["dateTime"].split("T")[0], "%Y-%m-%d"
                ).date()
                < datetime.now().date()
            )
            attributes["overdue_tasks"] = [
                t["subject"] for t in filter(__overdue, self._tasks)
            ]
            _LOGGER.debug("overdue_tasks count: %i", len(attributes["overdue_tasks"]))
        except Exception as ex:
            _LOGGER.error("Unable to set attributes: %s", ex)
            raise

        return attributes

    async def async_get_events(self, hass, start_date, end_date):
        # TODO: implement this
        return []

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        tasks_res = self._tasks_api.get_uncompleted_tasks(self._list_id)
        self._tasks = tasks_res["value"]
