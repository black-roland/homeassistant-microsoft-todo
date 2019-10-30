import os
import logging

import voluptuous as vol
from requests_oauthlib import OAuth2Session
from aiohttp.web import Response

from homeassistant.core import callback
from homeassistant.components.calendar import (
    PLATFORM_SCHEMA,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.util.json import load_json, save_json

from .outlook_tasks_api import OutlookTasksApi
from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    AUTH_CALLBACK_PATH,
    AUTHORIZATION_BASE_URL,
    TOKEN_URL,
    SCOPE,
    MS_TODO_AUTH_FILE,
    SERVICE_NEW_TASK,
    SUBJECT,
)

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
    }
)

# FIXME: find a proper way or change the OAuth implementation
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'


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

    callback_url = f"{hass.config.api.base_url}{AUTH_CALLBACK_PATH}"
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
    tasks_api = OutlookTasksApi(oauth)

    if not config_file:
        authorization_url, state = oauth.authorization_url(AUTHORIZATION_BASE_URL)
        request_configuration(hass, config, add_entities, authorization_url)

    hass.http.register_view(MSToDoAuthCallbackView(add_entities, oauth, config.get(CONF_CLIENT_SECRET)))

    def handle_new_task(call):
        subject = call.data.get(SUBJECT)
        tasks_api.create_task(subject)

    hass.services.register(
        DOMAIN, SERVICE_NEW_TASK, handle_new_task, schema=NEW_TASK_SERVICE_SCHEMA
    )


class MSToDoAuthCallbackView(HomeAssistantView):

    url = AUTH_CALLBACK_PATH
    name = "auth:ms_todo:callback"
    requires_auth = False

    def __init__(self, add_entities, oauth, client_secret):
        self.add_entities = add_entities
        self.oauth = oauth
        self.client_secret = client_secret

    @callback
    def get(self, request):
        hass = request.app["hass"]
        data = request.query

        html_response = """<html><head><title>Microsoft To Do authorization</title></head>
                           <body><h1>{}</h1></body></html>"""

        if data.get("code") is None:
            error_msg = "No code returned from Microsoft Graph Auth API"
            _LOGGER.error(error_msg)
            return Response(text=html_response.format(error_msg), content_type="text/html")

        token = self.oauth.fetch_token(TOKEN_URL, client_secret=self.client_secret, code=data.get("code"))

        save_json(hass.config.path(MS_TODO_AUTH_FILE), token)

        response_message = """Microsoft To Do has been successfully authorized!
                              You can close this window now!"""

        hass.async_add_job(setup_platform, hass, hass.config, self.add_entities)

        return Response(
            text=html_response.format(response_message), content_type="text/html"
        )
