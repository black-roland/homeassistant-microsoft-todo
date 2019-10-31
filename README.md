# Microsoft To Do integration for Home Assistant

The integration allows you to create tasks in Microsoft To Do from Home Assistant.

## Work in progress

Work is still in progress. Next steps are documented as [issues](https://github.com/black-roland/homeassistant-microsoft-todo/labels/todo).

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

To create a task in Microsoft To Do you can call `microsoft_todo.ms_todo_new_task` service. Currently, only `subject` property is supported.

Example:

```yaml
- service: microsoft_todo.ms_todo_new_task
  data:
    subject: "Test task"
```
