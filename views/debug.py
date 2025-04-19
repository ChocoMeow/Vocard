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

import discord
import io
import os
import contextlib
import textwrap
import traceback
import voicelink
import function as func

from typing import Optional
from discord.ext import commands

class ExecuteModal(discord.ui.Modal):
    def __init__(self, code: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.code: str = code

        self.add_item(
            discord.ui.TextInput(
                label="Code Runner",
                placeholder="Input Your Code",
                style=discord.TextStyle.long,
                default=self.code
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.code = self.children[0].value
        self.stop()

class AddNodeModal(discord.ui.Modal):
    def __init__(self, view, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        
        self.view: NodesPanel = view
        
        self.add_item(
            discord.ui.TextInput(
                label="Host",
                placeholder="Enter the lavalink host e.g 0.0.0.0"
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="Port",
                placeholder="Enter the lavalink port e.g 2333"
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="Password",
                placeholder="Enter the lavalink password"
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="Secure",
                placeholder="Specify if your Lavalink uses SSL. Enter 'true' or 'false'"
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="Identifier",
                placeholder="Enter a name for your lavalink server"
            )
        )
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            config = {
                "host": self.children[0].value,
                "port": int(self.children[1].value),
                "password": self.children[2].value,
                "secure": self.children[3].value.lower() == "true",
                "identifier": self.children[4].value
            }
        except Exception:
            return await interaction.response.send_message("Some of your input is invalid! Please try again.", ephemeral=True)
        
        await interaction.response.defer()
        try:
            await voicelink.NodePool.create_node(
                bot=interaction.client,
                logger=func.logger,
                **config
            )
            await interaction.followup.send(f"Node {self.children[4].value} is connected!", ephemeral=True)
            await self.view.message.edit(embed=self.view.build_embed(), view=self.view)
            
        except Exception as e:
            return await interaction.followup.send(e, ephemeral=True)
        
class CogsDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

        super().__init__(
            placeholder="Select a cog to reload...",
            options=[discord.SelectOption(label="All", description="All the cogs")] +
            [
                discord.SelectOption(label=name.capitalize(), description=cog.description[:50])
                for name, cog in bot.cogs.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0].lower()
        try:
            if selected == "all":
                for name in self.bot.cogs.copy().keys():
                    await self.bot.reload_extension(f"cogs.{name.lower()}")
            else:
                await self.bot.reload_extension(f"cogs.{selected}")
        except Exception as e:
            return await interaction.response.send_message(f"Unable to reload `{selected}`! Reason: {e}", ephemeral=True)

        await interaction.response.send_message(f"Reloaded `{selected}` successfully!", ephemeral=True)

class NodesDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.view: NodesPanel
    
        super().__init__(
            placeholder="Select a node to edit...",
            options=self.get_nodes()
        )
    
    def get_nodes(self) -> list[discord.SelectOption]:
        nodes = [
            discord.SelectOption(
                label=name,
                description=("🟢 Connected" if node._available else "🔴 Disconnected") + f" - Players: {node.player_count} ({node.latency if node._available else 0:.2f}ms)")
            for name, node in voicelink.NodePool._nodes.items()
        ]
        
        if not nodes:
            nodes = [discord.SelectOption(label="The node could not be found!")]
            
        return nodes
    
    def update(self) -> None:
        self.options = self.get_nodes()
        
    async def callback(self, interaction: discord.Interaction) -> None:
        selected_node = self.values[0]
        node = voicelink.NodePool._nodes.get(selected_node, None)
        if not node:
            return await interaction.response.send_message("The node could not be found!", ephemeral=True)
        
        self.view.selected_node = node
        await interaction.response.defer()
        await self.view.message.edit(embed=self.view.build_embed(), view=self.view)
        
class ExecutePanel(discord.ui.View):
    def __init__(self, bot, *, timeout = 180):
        self.bot: commands.Bot = bot

        self.message: discord.WebhookMessage = None
        self.code: str = None
        self._error: Exception = None

        super().__init__(timeout=timeout)

    def toggle_button(self, name: str, status: bool):
        child: discord.ui.Button
        for child in self.children:
            if child.label == name:
                child.disabled = status
                break

    def clear_code(self, content: str):
        """Automatically removes code blocks from the code."""
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        return content.strip('` \n')
    
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def execute(self, interaction: discord.Interaction):
        modal = ExecuteModal(self.code, title="Enter Your Code")
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not (code := modal.code):
            return
        
        self._error = None
        text = ""

        local_variables = {
            "discord": discord,
            "bot": self.bot,
            "interaction": interaction,
            "input": None
        }

        self.code = self.clear_code(code)
        str_obj = io.StringIO() #Retrieves a stream of data
        try:
            with contextlib.redirect_stdout(str_obj):
                exec(f"async def func():\n{textwrap.indent(self.code, '  ')}", local_variables)
                obj = await local_variables["func"]()
                result = f"{str_obj.getvalue()}\n-- {obj}\n"
        except Exception as e:
            text = f"{e.__class__.__name__}: {e}"
            self._error = e

        if not self._error:
            text = "\n".join([f"{'%03d' % index} | {i}" for index, i in enumerate(result.split("\n"), start=1)])

        self.toggle_button("Error", True if self._error is None else False)

        if not self.message:
            self.message = await interaction.followup.send(f"```{text}```", view=self, ephemeral=True)
        else:
            await self.message.edit(content=f"```{text}```", view=self)

    @discord.ui.button(label="End", emoji="🗑️", custom_id="end")
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.message:
            await self.message.delete()
        self.stop()

    @discord.ui.button(label="Rerun", emoji="🔄", custom_id="rerun")
    async def rerun(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute(interaction)

    @discord.ui.button(label="Error", emoji="👾", custom_id="Error")
    async def error(self, interaction: discord.Interaction, button: discord.ui.Button):
        result = ''.join(traceback.format_exception(self._error, self._error, self._error.__traceback__))
        await self.message.edit(content=f"```py\n{result}```")

class NodesPanel(discord.ui.View):
    def __init__(self, bot, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self.selected_node: Optional[voicelink.Node] = None
        
        self.add_item(NodesDropdown(bot))
    
    def update_btn_status(self) -> None:
        for child in self._children:
            if isinstance(child, discord.ui.Button) and child.label != "Add":
                child.disabled = self.selected_node is None
            
            if isinstance(child, discord.ui.Select):
                child.update()
        
    def build_embed(self) -> discord.Embed:
        self.update_btn_status()
        embed = discord.Embed(title="📡 Nodes Panel", color=func.settings.embed_color)
        
        if not voicelink.NodePool._nodes:
            embed.description = "```There are no nodes are connected!```"
        
        else:
            for name, node in voicelink.NodePool._nodes.items():
                if self.selected_node and self.selected_node._identifier != node._identifier:
                    continue
                
                if node._available:
                    total_memory = node.stats.used + node.stats.free
                    embed.add_field(
                        name=f"{name} Node - 🟢 Connected",
                        value=f"```• ADDRESS: {node._host}:{node._port}\n" \
                            f"• PLAYERS: {len(node._players)}\n" \
                            f"• CPU:     {node.stats.cpu_process_load:.1f}%\n" \
                            f"• RAM:     {func.format_bytes(node.stats.free)}/{func.format_bytes(total_memory, True)} ({(node.stats.free/total_memory) * 100:.1f}%)\n"
                            f"• LATENCY: {node.latency:.2f}ms\n" \
                            f"• UPTIME:  {func.time(node.stats.uptime)}```"
                    )
                else:
                    embed.add_field(
                        name=f"{name} Node - 🔴 Disconnected",
                        value=f"```• ADDRESS: {node._host}:{node._port}\n" \
                            f"• PLAYERS: {len(node._players)}\nNo extra data is available for display```",
                    )
                    
        return embed
    
    async def on_error(self, interaction: discord.Interaction, error, item) -> None:
        return await interaction.followup.send(error, ephemeral=True)
    
    @discord.ui.button(label="Add", emoji="➕", style=discord.ButtonStyle.green)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddNodeModal(self, title="Create Node")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Remove", emoji="➖", style=discord.ButtonStyle.red, disabled=True)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_node:
            return await interaction.response.send_message("Please ensure that you have selected a node!", ephemeral=True)

        identifier = self.selected_node._identifier
        await self.selected_node.disconnect(remove_from_pool=True)
        
        self.selected_node = None
        
        await self.message.edit(embed=self.build_embed(), view=self)
        await interaction.response.send_message(f"Removed {identifier} Node from the bot.", ephemeral=True)
        
    @discord.ui.button(label="Reconnect", disabled=True, row=1)
    async def reconnect(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.selected_node.is_connected:
            await self.selected_node.disconnect()
            await self.selected_node.connect()
            await self.message.edit(embed=self.build_embed(), view=self)
    
    @discord.ui.button(label="Connect", disabled=True, row=1)
    async def connect(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not self.selected_node.is_connected:
            await self.selected_node.connect()
            await self.message.edit(embed=self.build_embed(), view=self)
        
    @discord.ui.button(label="Disconnect", style=discord.ButtonStyle.red, disabled=True, row=1)
    async def disconnect(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.selected_node.is_connected:
            await self.selected_node.disconnect()
            
            await self.message.edit(embed=self.build_embed(), view=self)
        
class CogsView(discord.ui.View):
    def __init__(self, bot, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)

        self.add_item(CogsDropdown(bot))
   
class DebugView(discord.ui.View):
    def __init__(self, bot, *, timeout: float | None = 180):
        self.bot: commands.Bot = bot
        self.panel: ExecutePanel = ExecutePanel(bot)

        super().__init__(timeout=timeout)

    @discord.ui.button(label='Command', emoji="▶️", style=discord.ButtonStyle.green)
    async def run_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.panel.execute(interaction)
    
    @discord.ui.button(label='Cogs', emoji="⚙️")
    async def reload_cog(self, interaction: discord.Interaction, button: discord.ui.Button):
        return await interaction.response.send_message("Reload Cogs", view=CogsView(self.bot), ephemeral=True)
    
    @discord.ui.button(label="Re-Sync", emoji="🔄")
    async def sync(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔄 Synchronizing all your commands and language settings!", ephemeral=True)
        await self.bot.tree.sync()
        await interaction.edit_original_response(content="✅ All commands and settings have been successfully synchronized!")
    
    @discord.ui.button(label="Nodes", emoji="📡")
    async def nodes(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = NodesPanel(self.bot)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)
        view.message = await interaction.original_response()
    
    @discord.ui.button(label="Stop-Bot", emoji="🔴")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        for name in self.bot.cogs.copy().keys():
            try:
                await self.bot.unload_extension(name)
            except:
                pass

        player_data = []
        for identifier, node in voicelink.NodePool._nodes.items():
            for guild_id, player in node._players.copy().items():
                if player.guild.me is None or player.guild.me.voice or not player.current:
                    continue

                player_data.append(player.data)
                try:
                    await player.teardown()
                except:
                    pass

        session_file_path = os.path.join(func.ROOT_DIR, func.LAST_SESSION_FILE_NAME)
        if os.path.exists(session_file_path):
            os.remove(session_file_path)    

        func.update_json(func.LAST_SESSION_FILE_NAME, player_data)
        await interaction.client.close()