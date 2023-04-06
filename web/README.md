## Dashboard Tutorial
Click on the image below to watch the tutorial on Youtube.

[![Dashboard](https://img.youtube.com/vi/5Y5GPO95uxE/maxresdefault.jpg)](https://youtu.be/5Y5GPO95uxE)

## Configuration
1. **Fill in `CLIENT_SECRET_ID` and `SERCET_KEY` values in `.env`**

| Values | Description |
| --- | --- |
| CLIENT_SECRET_ID | Your Discord bot client secret id [(Discord Portal)](https://discord.com/developers/applications) ***(optional)*** |
| SERCET_KEY | Secret key for dashboard ***(optional)*** |

2. **Add `ipc_server` configuration in `settings.json`**
```json
"ipc_server": {
    "host": "127.0.0.1",
    "port": 8000,
    "enable": false
},
```

## Quick Start
```sh
cd web                    #Go to the web directory
python webapp.py          #Start the web server
```