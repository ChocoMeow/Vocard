<a href="https://discord.gg/wRCgB7vBQv">
    <img src="https://img.shields.io/discord/811542332678996008?color=7289DA&label=Support&logo=discord&style=for-the-badge" alt="Discord">
</a>

# Vocard (Discord Music Bot)
> Vocard is a simple custom Disocrd Music Bot built with Python & [discord.py](https://discordpy.readthedocs.io/en/stable/) <br>
Demo: [Discord Bot Demo](https://discord.com/api/oauth2/authorize?client_id=890399639008866355&permissions=36708608&scope=bot%20applications.commands),
[Dashboard Demo](https://vocard.xyz)

# Host for you?
<a href="https://www.patreon.com/Vocard">
    <img src="https://img.shields.io/endpoint.svg?url=https%3A%2F%2Fshieldsio-patreon.vercel.app%2Fapi%3Fusername%3Dendel%26type%3Dpatrons&style=for-the-badge" alt="Patreon">
</a>

# Tutorial
Click on the image below to watch the tutorial on Youtube.

[![Discord Music Bot](https://img.youtube.com/vi/f_Z0RLRZzWw/maxresdefault.jpg)](https://www.youtube.com/watch?v=f_Z0RLRZzWw)
 
## Screenshot
### Discord Bot
<img src="https://user-images.githubusercontent.com/94597336/227766331-dfa7d360-18d7-4014-ac6a-4fca55907d99.png">
<img src="https://user-images.githubusercontent.com/94597336/227766379-c824512e-a6f7-4ca5-9342-cc8e78d52491.png">
<img src="https://user-images.githubusercontent.com/94597336/227766408-37d733f7-c849-4cbd-9e17-0cd5800affb3.png">
<img src="https://user-images.githubusercontent.com/94597336/227766416-22ae3d91-40d9-44c0-bde1-9d40bd54c3af.png">

### Dashboard
<img src="https://github.com/ChocoMeow/Vocard/assets/94597336/53f31f9f-57c5-452c-8317-114125ddbf03">
<img src="https://github.com/ChocoMeow/Vocard/assets/94597336/b2acd87a-e910-4247-8d5a-418f3782f63f">

## Requirements
* [Python 3.10+](https://www.python.org/downloads/)
* [Lavalink Server (Requires 4.0.0+)](https://github.com/freyacodes/Lavalink)

## Quick Start
```sh
git clone https://github.com/ChocoMeow/Vocard.git  #Clone the repository
cd Vocard                                          #Go to the directory
python -m pip install -r requirements.txt          #Install required packages
```
After installing all packages, you must configure the bot before to start! [How To Configure](https://docs.vocard.xyz/configuration/)<br />
Start your bot with `python main.py`

## Configuration
1. Rename `.env Example` to `.env` and [customize your env](https://docs.vocard.xyz/configuration/#settings-up-env).
2. Rename `settings Example.json` to `settings.json` and [customize your settings](https://docs.vocard.xyz/configuration/#settings-up-settingsjson).
3. Now, you can start your bot with `python main.py`.

## How to update? (For Windows and Linux)
***Note: Make sure there are no personal files in the directory! Otherwise it will be deleted.***
```sh
# Check the current version
python update.py -c

# Install the latest version
python update.py -l

# Install the specified version
python update.py -v VERSION

# Install the beta version
python update.py -b
```