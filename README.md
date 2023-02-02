![Support Server](https://discordapp.com/api/guilds/811542332678996008/widget.png?style=shield)

# Vocard (Discord Music Bot)
> Vocard is a simple custom Disocrd Music Bot built with Python & [discord.py](https://discordpy.readthedocs.io/en/stable/)

## Requirements
* [Python 3.8+](https://www.python.org/downloads/)
* [Modules in requirements](https://github.com/ChocoMeow/Vocard/blob/main/requirements.txt)
* [Lavalink Server](https://github.com/freyacodes/Lavalink)

## Quick Start
```sh
git clone https://github.com/ChocoMeow/Vocard.git  #Clone the repository
cd Vocard                                          #Go to the directory
python -m pip install -r requirements.txt          #Install required packages
```
After installing all packages, you must configure the bot before to start! [How To Configure](https://github.com/ChocoMeow/Vocard#configuration)<br />
Start your bot with `python main.py`

## Configuration
1. **Rename `.env Example` to `.env` and fill all the values**
```sh
TOKEN = XXXXXXXXXXXXXXXXXXXXXXXX.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXX
CLIENT_ID = 123456789012345678
BUG_REPORT_CHANNEL_ID = 123456789012345678

SPOTIFY_CLIENT_ID = 0XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
SPOTIFY_CLIENT_SECRET = 0XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

YOUTUBE_API_KEY = AXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

MONGODB_URL = mongodb+srv://user:password@clusterURL
MONGODB_NAME = Vocard
```
| Values | Description |
| --- | --- |
| TOKEN | Your Discord bot token [(Discord Portal)](https://discord.com/developers/applications) |
| CLIENT_ID | Your Discord bot client id [(Discord Portal)](https://discord.com/developers/applications) |
| BUG_REPORT_CHANNEL_ID | All the error messages will send to this text channel ***(optional)*** |
| SPOTIFY_CLIENT_ID | Your Spoity client id [(Spotify Portal)](https://developer.spotify.com/dashboard/applications) ***(optional)*** |
| SPOTIFY_CLIENT_SECRET | Your Spoity client sercret id [(Spotify Portal)](https://developer.spotify.com/dashboard/applications) ***(optional)*** |
| YOUTUBE_API_KEY | Your youtube api key [(Google API)](https://cloud.google.com/apis) ***(optional)*** |
| MONGODB_URL | Your Mongo datebase url [(Mongodb)](https://www.mongodb.com/) |
| MONGODB_NAME | The datebase name that you created on [Mongodb](https://www.mongodb.com/) |

2. **Rename `settings Example.json` to `settings.json` and customize your settings**
***(Note: Do not change any keys from `settings.json`)***
```json
{
    "nodes": {
        "DEFAULT": {
            "host": "127.0.0.1", 
            "port": 2333,
            "password": "password",
            "secure": false,
            "identifier": "DEFAULT"
        }   
    },
    "bot_access_user": [],
    "color_code":"0xb3b3b3",
    "emoji_source_raw": {
        "youtube": "<:youtube:826661982760992778>",
        "youtube music": "<:youtube:826661982760992778>",
        "spotify": "<:spotify:826661996615172146>",
        "soundcloud": "<:soundcloud:852729280027033632>",
        "twitch": "<:twitch:852729278285086741>",
        "bandcamp": "<:bandcamp:864694003811221526>",
        "vimeo": "<:vimeo:864694001919721473>",
        "apple": "<:applemusic:994844332374884413>",
        "reddit": "<:reddit:996007566863773717>",
        "tiktok": "<:tiktok:996007689798811698>"
    }
}
```
* For `nodes` you have to provide host, port, password and identifier of the [Lavalink Server](https://github.com/freyacodes/Lavalink)
* For `bot_access_user` you can pass the [discord user id](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-). Example: `[123456789012345678]`
* For `color_code` you must pass a [Hexadecimal color code](https://htmlcolorcodes.com/) and add `0x` before the color code. Example: `"0xb3b3b3"`
* For `emoji_source_raw` you can change the source emoji of the track with discord emoji like `<:EMOJI_NAME:EMOJI_ID>`

## How to update?
1. Run `python update --check` to check if your bot is up to date
2. Run `python update --start` to start update your bot <br/>
***Note: Make sure there are no personal files in the directory! Otherwise it will be deleted.***
