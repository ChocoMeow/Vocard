"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
import asyncio
import discord
import voicelink
import function as func

from discord.ext import commands

class Listeners(commands.Cog):
    """Music Cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voicelink = voicelink.NodePool()

        bot.loop.create_task(self.start_nodes())
        bot.loop.create_task(self.restore_last_session_players())
        
    async def start_nodes(self) -> None:
        """Connect and intiate nodes."""
        for n in func.settings.nodes.values():
            try:
                await self.voicelink.create_node(
                    bot=self.bot,
                    logger=func.logger,
                    **n
                )
            except Exception as e:
                func.logger.error(f'Node {n["identifier"]} is not able to connect! - Reason: {e}')

    async def restore_last_session_players(self) -> None:
        """Re-establish connections for players from the last session."""
        await self.bot.wait_until_ready()
        players = func.open_json(func.LAST_SESSION_FILE_NAME)
        if not players:
            return

        for data in players:
            try:
                channel_id = data.get("channel_id")
                if not channel_id:
                    continue

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                elif not any(False if member.bot or member.voice.self_deaf else True for member in channel.members):
                    continue
                    
                dj_member = channel.guild.get_member(data.get("dj"))
                if not dj_member:
                    continue

                # Get the guild settings
                settings = await func.get_settings(channel.guild.id)

                # Connect to the channel and initialize the player.
                player: voicelink.Player = await channel.connect(
                    cls=voicelink.Player(self.bot, channel, func.TempCtx(dj_member, channel), settings)
                )

                # Restore the queue.
                queue_data = data.get("queue", {})
                for track_data in queue_data.get("tracks", []):
                    track_id = track_data.get("track_id")
                    if not track_id:
                        continue

                    decoded_track = voicelink.decode(track_id)
                    requester = channel.guild.get_member(track_data.get("requester_id"))
                    track = voicelink.Track(track_id=track_id, info=decoded_track, requester=requester)
                    player.queue._queue.append(track)
                
                # Restore queue settings.
                player.queue._position = queue_data.get("position", 0) - 1
                repeat_mode = queue_data.get("repeat_mode", "OFF")
                try:
                    loop_mode = voicelink.LoopType[repeat_mode]
                except KeyError:
                    loop_mode = voicelink.LoopType.OFF
                player.queue._repeat.set_mode(loop_mode)
                player.queue._repeat_position = queue_data.get("repeat_position")

                # Restore player settings
                player.dj = dj_member
                player.settings['autoplay'] = data.get('autoplay', False)

                # Resume playback or invoke the controller based on the player's state.
                if not player.is_playing:
                    await player.do_next()

                    if is_paused := data.get("is_paused"):
                        await player.set_pause(is_paused, self.bot.user)
                    
                    if position := data.get("position"):
                        await player.seek(int(position), self.bot.user)

                await asyncio.sleep(5)

            except Exception as e:
                func.logger.error(f"Error encountered while restoring a player for channel ID {channel_id}.", exc_info=e)

        # Delete the last session file if it exists.
        try:
            file_path = os.path.join(func.ROOT_DIR, func.LAST_SESSION_FILE_NAME)
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as del_error:
            func.logger.error("Failed to remove session file: %s", file_path, exc_info=del_error)

    @commands.Cog.listener()
    async def on_voicelink_track_end(self, player: voicelink.Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_voicelink_track_stuck(self, player: voicelink.Player, track, _):
        await asyncio.sleep(10)
        await player.do_next()

    @commands.Cog.listener()
    async def on_voicelink_track_exception(self, player: voicelink.Player, track, error: dict):
        try:
            player._track_is_stuck = True
            await player.context.send(f"{error['message']} The next song will begin in the next 5 seconds.", delete_after=10)
        except:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        
        if before.channel == after.channel:
            return

        player: voicelink.Player = member.guild.voice_client
        if not player:
            return

        is_joined = True
        
        if not before.channel and after.channel:
            if after.channel.id != player.channel.id:
                return

        elif before.channel and not after.channel:
            is_joined = False
        
        elif before.channel and after.channel:
            if after.channel.id != player.channel.id:
                is_joined = False
                
        if is_joined and player.settings.get("24/7", False):
            if player.is_paused and len([m for m in player.channel.members if not m.bot]) == 1:
                await player.set_pause(False, member)
                  
        if self.bot.ipc._is_connected:
            await self.bot.ipc.send({
                "op": "updateGuild",
                "user": {
                    "userId": str(member.id),
                    "avatarUrl": member.display_avatar.url,
                    "name": member.name,
                },
                "channelName": member.voice.channel.name if is_joined else "",
                "guildId": str(member.guild.id),
                "isJoined": is_joined
            })

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Listeners(bot))
