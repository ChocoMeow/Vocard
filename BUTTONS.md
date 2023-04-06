## Property you can use!
- Buttons

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
| Tracks | If there are tracks in the queue, a drop-down list will be appear. Up to 10 tracks. `(This will take one row)`|

- Colors

| Color Name | Description |
| --- | --- |
| Grey | Color the button grey. |
| Red | Color the button red. |
| Blue | Color the button blue. |
| Green | Color the button green. |

## Examples
Change the value of `controller` in `settings.json`.

1. Example 1
<img width="459" alt="image" src="https://user-images.githubusercontent.com/94597336/221099779-d458e274-6052-4265-afb2-b232de1b1fd4.png">

```json
"controller": [
    ["back", "resume", "skip", {"stop": "red"}, "add"],
    ["tracks"]
]
```

2. Example 2
<img width="480" alt="image" src="https://user-images.githubusercontent.com/94597336/221099004-9913ee28-5079-488a-b880-902c7ab7ce38.png">

```json
"controller": [
    ["back", "resume", "skip", {"stop": "red"}, {"add": "green"}],
    [{"loop": "green"}, {"volumeup": "blue"}, {"volumedown": "blue"}, {"volumemute": "red"}],
    ["tracks"]
]
```

3. Example 3
<img width="480" alt="image" src="https://user-images.githubusercontent.com/94597336/230248758-14ff7e1b-d6db-49f8-94a6-c55fd02f13df.png">

```json
"controller": [
    ["autoplay", "shuffle", {"loop": "green"}, "add"],
    ["back", "resume", "skip", {"stop": "red"}],
    ["volumeup", "volumedown", {"mute": "red"}]
]
```