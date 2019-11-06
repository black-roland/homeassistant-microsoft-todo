# Microsoft To Do integration for Home Assistant

The integration allows you to create tasks in Microsoft To Do from Home Assistant.

## Work in progress

Work is still in progress. Next steps are tracked as [issues](https://github.com/black-roland/homeassistant-microsoft-todo/labels/todo).

## Installation

This component can be installed using [HACS](https://github.com/hacs/integration). Simply add a custom repository `black-roland/homeassistant-microsoft-todo` and install the integration.

Alternatively, that's possible to copy the content of the `custom_components` to [the config directory](https://developers.home-assistant.io/docs/en/creating_component_loading.html).

## Setup

To get access to Microsoft To Do API you need to register an application in Azure:

1. Open [Azure portal](https://portal.azure.com/#home);
1. Go to app registrations:<br />
   ![App registrations](https://share.roland.black/file/black-roland-share/96db74de-fb21-11e9-a480-f81654971495/app-registrations.gif)
1. Register a new personal app and obtain client ID and secret:<br />
   ![App registration and credentials](https://share.roland.black/file/black-roland-share/272d1efc-fb22-11e9-9aa9-f81654971495/register-app-obtain-creds.gif)
1. Add a redirect URI: `https://[YOUR HOME ASSISTANT URL:PORT]/api/microsoft-todo`, replace `[YOUR HOME ASSISTANT URL:PORT]` with the domain name and port of our Home Assistant instance:<br />
   ![Redirect URI](https://share.roland.black/file/black-roland-share/d9a41612-fb22-11e9-8f90-f81654971495/redirect-uri.gif)

## Configuration

Add the following section to your `configuration.yaml` file:

```yaml
calendar:
  - platform: microsoft_todo
    client_id: YOUR_CLIENT_ID
    client_secret: YOUR_CLIENT_SECRET
```

Restart Home Assistant and finalize authorization through UI. There should be a new configuration request in notifications.

## Services

To create a task in Microsoft To Do you can call `microsoft_todo.ms_todo_new_task` service.

Simple example:

```yaml
- service: microsoft_todo.ms_todo_new_task
  data:
    subject: "Test task"
    list_name: "Home Assistant"
```

*TODO*: Use the list name instead of ID [#4](https://github.com/black-roland/homeassistant-microsoft-todo/issues/4).

Automation example:

```yaml
automation:
  - alias: "Remind to pay utility bill"
    trigger:
      platform: time
      at: "00:00:00"
    condition:
      condition: template
      value_template: "{{ now().day == 1 }}"
    action:
      - service: microsoft_todo.ms_todo_new_task
        data_template:
          subject: "Pay utility bill for {{ now().replace(month=now().month - 1).strftime('%B') }}" # previous month name
          list_name: "Home Assistant"
          note: "Pay online: http://example.com/pay/"
          due_date: "{{ now().strftime('%Y-%m-09') }}" # due 9th
          reminder_date_time: "{{ now().strftime('%Y-%m-%dT17:00:00') }}" # at 17:00 today
```

*NOTE*: Service name might be changed in future [#5](https://github.com/black-roland/homeassistant-microsoft-todo/issues/5).
