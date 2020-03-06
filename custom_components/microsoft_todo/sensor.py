import os
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from requests_oauthlib import OAuth2Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from homeassistant.helpers.entity import generate_entity_id

from homeassistant.components.calendar import (
    PLATFORM_SCHEMA,
)

import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json
from homeassistant.util import dt
from typing import List, Any, Callable

from .outlook_tasks_api import OutlookTasksApi

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    AUTH_CALLBACK_PATH,
    TOKEN_URL,
    SCOPE,
    MS_TODO_AUTH_FILE,
    CONF_LIST_NAME,
    CONF_SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_LIST_NAME): cv.ensure_list,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            vol.All(cv.time_period, cv.positive_timedelta),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None, scan_interval=SCAN_INTERVAL):
    config_path = hass.config.path(MS_TODO_AUTH_FILE)
    config_file = None
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    list_name = config.get(CONF_LIST_NAME, [])

    if os.path.isfile(config_path):
        config_file = load_json(config_path)

    def token_saver(token):
        save_json(hass.config.path(MS_TODO_AUTH_FILE), token)

    # TODO: create a separate HTTP client class
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
    retry = Retry(status=3, connect=3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    oauth.mount("http://", adapter)
    oauth.mount("https://", adapter)

    tasks_api = OutlookTasksApi(client=oauth, logger=_LOGGER, timezone=dt.DEFAULT_TIME_ZONE)
    create_my_sensor: Callable[[Any], MSToDOSensor] = lambda sn: MSToDOSensor(hass,
                                                                              tasks_api,
                                                                              sn,
                                                                              scan_interval)
    sensors: List[MSToDOSensor] = list(map(create_my_sensor, list_name))

    if sensors:
        add_entities(sensors, True)


class MSToDOSensor(Entity):
    """Representation of a Sensor."""
    _state: str
    _list_id: str

    def __init__(self, hass, controller, list_name, scan_interval):
        """Initialize the sensor."""

        self.controller = controller
        self.isStart = True
        self._state = ""
        self._attributes = dict()
        self._attributes.update({
            'friendly_name': list_name
        })
        self._list_id = controller.get_list_id_by_name(list_name)
        self._list_name = list_name
        self._entity_id = generate_entity_id("sensor.mstodo_{}", list_name, hass=hass)

        self.set_scan_interval(hass, scan_interval)

    def set_scan_interval(self, hass: object, scan_interval: timedelta):
        """Update scan interval."""

        def refresh(event_time):
            """Get the latest data from Transmission."""
            self.update()

        track_time_interval(
            hass, refresh, scan_interval
        )

    @property
    def current_meter(self):
        return self.controller.get_uncompleted_tasks(self._list_id)

    @property
    def entity_id(self):
        """Return the entity_id of the sensor."""
        return self._entity_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        return 'mdi:counter'

    @property
    def device_state_attributes(self):
        return self._attributes

    def fetch_state(self):
        """Retrieve latest state."""
        meter = self.current_meter
        str_return_value = meter['@odata.count']

        self._attributes.update({
            'friendly_name': self._list_name
        })
        self.isStart = False

        return str_return_value

    def update(self):
        self._state = self.fetch_state()
