# Bot Activity (Activity are updated every 10 minutes)
> Usage: {"action": "@@value@@"}

Valuables

| Value Name | Description |
| --- | --- |
| guilds | Number of guilds in the bot |
| users | Number of users in the voice channel. |
| players | Number of players playing. |
| nodes | Number of nodes are connected. |

Actions

| Action Name | Description |
| --- | --- |
| player | Playing status. |
| listen | Listening status. |
| watch | Watching status. |
| stream | Streaming status. |

## Examples
Change the value of `activity` in `settings.json`.

1. Example 1
<img width="200" alt="image" src="https://user-images.githubusercontent.com/94597336/232210610-fb2b8dba-736e-4230-b315-c52b1cf37a22.png">

```json
"activity":[
    {"listen": "/help"}
]
```

2. Example 2
<img width="200" alt="image" src="https://user-images.githubusercontent.com/94597336/232210639-255025e2-f55b-422d-a8f8-01cdaeec1e8d.png">

```json
"activity":[
    {"watch": "@@players@@ players"}
]
```

3. Example 3 (Multiple activities)

```json
"activity":[
    {"listen": "/help"},
    {"watch": "@@players@@ players"}
]
```

# Controller Embeds
> Usage: @@value@@

Valuables

| Value Name | Description |
| --- | --- |
| channel_name | The name of the channel the bot is playing on. |
| track_name | The name of the track currently playing. |
| track_url | The url of the track currently playing. |
| track_thumbnail | The thumbnail of the track currently playing. |
| requester | The mention name of the requester of the currently playing track. |
| requester_name | The name of the requester of the currently playing track. |
| requester_avatar | The avatar url of the requester of the currently playing track. |
| queue_length | Number of queue lengths |
| volume | Music volume. |
| dj | DJ role. `(It can be a user or role)` |
| loop_mode | Current repeat mode. |
| default_embed_color | Default embed color. `(color_code in settings.json)` |
| bot_icon | The avatar of the bot. |
| server_invite_link | The invite url of the support server |
| invite_link | The invite url of the bot. |

Expression
> {{ EXPRESSION ?? TRUE // FALSE }}

## Examples
Change the value of `default_controller` in `settings.json`.

1. Example 1
<img width="450" alt="image" src="https://user-images.githubusercontent.com/94597336/232209745-e55de4e5-e4f2-47ce-ab78-69e9263f321a.png">
<img width="450" alt="image" src="https://user-images.githubusercontent.com/94597336/232209778-e30f2f92-a179-4eb6-90d9-865cb1903699.png">

```json
"default_controller": {
    "embeds": {
        "active": {
            "description": "**Now Playing: ```[@@track_name@@]```\nLink: [Click Me](@@track_url@@) | Requester: @@requester@@ | DJ: @@dj@@**",
            "footer": {
                "text": "Queue Length: @@queue_length@@ | Duration: @@duration@@ | Volume: @@volume@@% {{loop_mode!=Off ?? | Repeat: @@loop_mode@@}}"
            },
            "image": "@@track_thumbnail@@",
            "author": {
                "name": "Music Controller | @@channel_name@@",
                "icon_url": "@@bot_icon@@"
            },
            "color": "@@default_embed_color@@"
        },
        "inactive": {
            "title": {
                "name": "There are no songs playing right now"
            },
            "description": "[Support](@@server_invite_link@@) | [Invite](@@invite_link@@) | [Questionnaire](https://forms.gle/Qm8vjBfg2kp13YGD7)",
            "image": "https://i.imgur.com/dIFBwU7.png",
            "color": "@@default_embed_color@@"
        }
    }
},
```

# Controller Buttons
> Usage: "button" or {"button": "color"}

Buttons

| Button Name | Description |
| --- | --- |
| Back | Skips back to the previous song. |
| Resume | Resume or pause the music. |
| Skip | Skips to the next song. |
| Stop | Disconnects the bot from your voice channel and chears the queue. |
| Loop | Changes Loop mode. `[Off, Track, Queue]` |
| Add | Add the playing track in to your default custom playlist. |
| VolumeUp | Increase player volume by 20%. |
| VolumeDown | Decrease player volume by 20%. |
| VolumeMute | Mute or unmute the player. |
| Autoplay | Enable or disable autoplay mode. |
| Shuffle | Randomizes the tracks in the queue. |
| Forward | Forward 30 seconds in the current track. |
| Rewind | Rewind 30 seconds in the current track. |
| Tracks | If there are tracks in the queue, a drop-down list will be appear. Up to 10 tracks. `(This will take one row)`|

Colors

| Color Name | Description |
| --- | --- |
| Grey | Color the button grey. |
| Red | Color the button red. |
| Blue | Color the button blue. |
| Green | Color the button green. |

## Examples
Change the value of `default_buttons` in `default_controller`.

1. Example 1
<img width="459" alt="image" src="https://user-images.githubusercontent.com/94597336/221099779-d458e274-6052-4265-afb2-b232de1b1fd4.png">

```json
"default_buttons": [
    ["back", "resume", "skip", {"stop": "red"}, "add"],
    ["tracks"]
]
```

2. Example 2
<img width="480" alt="image" src="https://user-images.githubusercontent.com/94597336/221099004-9913ee28-5079-488a-b880-902c7ab7ce38.png">

```json
"default_buttons": [
    ["back", "resume", "skip", {"stop": "red"}, {"add": "green"}],
    [{"loop": "green"}, {"volumeup": "blue"}, {"volumedown": "blue"}, {"volumemute": "red"}],
    ["tracks"]
]
```

3. Example 3
<img width="480" alt="image" src="https://user-images.githubusercontent.com/94597336/230248758-14ff7e1b-d6db-49f8-94a6-c55fd02f13df.png">

```json
"default_buttons": [
    ["autoplay", "shuffle", {"loop": "green"}, "add"],
    ["back", "resume", "skip", {"stop": "red"}],
    ["volumeup", "volumedown", {"mute": "red"}]
]
```
