import discord, copy
import function as func

from typing import List
from discord.ext import commands

class Modal(discord.ui.Modal):
    def __init__(self, items: List[discord.ui.Item], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for item in items:
            self.add_item(item)
        
        self.values: dict = {}
        
    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        for children in self.children:
            self.values[children.label.lower()] = children.value

        self.stop()

class Dropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Active', description='The controller embed when music is playing', emoji='🟩'),
            discord.SelectOption(label='Inactive', description='The controller embed when music is not playing', emoji='🟥'),
        ]
        super().__init__(placeholder='Select a embed to edit...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.embedType = self.values[0].lower()
        if self.view.embedType not in self.view.data:
            self.view.data[self.view.embedType] = {}

        await interaction.response.edit_message(embed=self.view.build_embed())

class EmbedBuilderView(discord.ui.View):
    def __init__(self, context: commands.Context, data: dict) -> None:
        from voicelink import Placeholders, build_embed

        super().__init__(timeout=300)
        self.add_item(Dropdown())

        self.author: discord.Member = context.author
        self.response: discord.Message = None

        self.original_data: dict = copy.deepcopy(data)
        self.data: dict = copy.deepcopy(data)
        self.embedType: str = "active"

        self.ph: Placeholders = Placeholders(context.bot)
        self.build_embed = lambda: build_embed(self.data.get(self.embedType, {}), self.ph)
    
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user == self.author

    @discord.ui.button(label="Edit Content", style=discord.ButtonStyle.blurple)
    async def edit_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = self.data.get(self.embedType, {})
        items = [
            discord.ui.TextInput(
                label="Title",
                placeholder="The title of the embed",
                style=discord.TextStyle.paragraph,
                max_length=1000,
                default=data.get("title", {}).get("name"),
                required=False
            ),
            discord.ui.TextInput(
                label="Url",
                placeholder="The url of the title",
                style=discord.TextStyle.short,
                max_length=100,
                default=data.get("title", {}).get("url"),
                required=False
            ),
            discord.ui.TextInput(
                label="Color",
                placeholder="The color of the embed",
                style=discord.TextStyle.short,
                max_length=100,
                default=data.get("color"),
                required=False
            ),
            discord.ui.TextInput(
                label="Description",
                placeholder="The description of the title",
                style=discord.TextStyle.paragraph,
                max_length=200,
                default=data.get("description"),
                required=False
            )
        ]

        modal = Modal(items, title="Edit Content")
        await interaction.response.send_modal(modal)
        await modal.wait()

        v = modal.values
        try:
            data["description"] = v["description"]
            data["color"] = int(v["color"], 16)

            if "title" not in data:
                data["title"] = {}

            data["title"]["name"] = v['title']
            data["title"]["url"] = v['url']
        except:
            pass

        return await interaction.edit_original_response(embed=self.build_embed())

    @discord.ui.button(label="Edit Author",)
    async def edit_author(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = self.data.get(self.embedType, {})
        items = [
            discord.ui.TextInput(
                label="Name",
                placeholder="The name of the author",
                style=discord.TextStyle.paragraph,
                max_length=200,
                default=data.get("author", {}).get("name"),
                required=False
            ),
            discord.ui.TextInput(
                label="Url",
                placeholder="The url of the author",
                style=discord.TextStyle.short,
                max_length=100,
                default=data.get("author", {}).get("url"),
                required=False
            ),
            discord.ui.TextInput(
                label="Icon Url",
                placeholder="The icon url of the author",
                style=discord.TextStyle.short,
                max_length=100,
                default=data.get("author", {}).get("icon_url"),
                required=False
            ),
        ]

        modal = Modal(items, title="Edit Author")
        await interaction.response.send_modal(modal)
        await modal.wait()

        v = modal.values

        if v['name'] != "":
            if "author" not in data:
                data["author"] = {}
                
            data["author"]["name"] = v['name']
            data["author"]["url"] = v['url']
            data["author"]["icon_url"] = v['icon url']
        else:
            del data["author"]

        return await interaction.edit_original_response(embed=self.build_embed())
    
    @discord.ui.button(label="Edit Image")
    async def edit_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = self.data.get(self.embedType, {})
        items = [
            discord.ui.TextInput(
                label="Thumbnail",
                placeholder="The url of the thumbnail",
                style=discord.TextStyle.short,
                max_length=200,
                default=data.get("thumbnail"),
                required=False
            ),
            discord.ui.TextInput(
                label="Image",
                placeholder="The url of the image",
                style=discord.TextStyle.short,
                max_length=100,
                default=data.get("image"),
                required=False
            )
        ]

        modal = Modal(items, title="Edit Image")
        await interaction.response.send_modal(modal)
        await modal.wait()

        v = modal.values

        data["thumbnail"] = v['thumbnail']
        data["image"] = v['image']

        return await interaction.edit_original_response(embed=self.build_embed())
    
    @discord.ui.button(label="Edit Footer")
    async def edit_footer(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = self.data.get(self.embedType, {})
        items = [
            discord.ui.TextInput(
                label="Text",
                placeholder="The text of the footer",
                style=discord.TextStyle.paragraph,
                max_length=200,
                default=data.get("footer", {}).get("text"),
                required=False
            ),
            discord.ui.TextInput(
                label="Icon Url",
                placeholder="The url of the icon",
                style=discord.TextStyle.short,
                max_length=100,
                default=data.get("footer", {}).get("icon_url"),
                required=False
            )
        ]

        modal = Modal(items, title="Edit Footer")
        await interaction.response.send_modal(modal)
        await modal.wait()

        v = modal.values
        if "footer" not in data:
            data["footer"] = {}

        data["footer"]["text"] = v['text']
        data["footer"]["icon_url"] = v['icon url']

        return await interaction.edit_original_response(embed=self.build_embed())
    
    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.green, row=1)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = self.data.get(self.embedType)
        items = [
            discord.ui.TextInput(
                label="Name",
                placeholder="The name of the field",
                style=discord.TextStyle.paragraph,
                max_length=256
            ),
            discord.ui.TextInput(
                label="Value",
                placeholder="The value of the field",
                style=discord.TextStyle.long,
                max_length=1024
            ),
            discord.ui.TextInput(
                label="Inline",
                placeholder="The inline of the field, e.g. True or False",
                style=discord.TextStyle.short
            )
        ]

        if "fields" not in data:
            data["fields"] = []

        if len(data["fields"]) >= 25:
            return await interaction.response.send_message("You have already reached the maximum of fields!", ephemeral=True)
        
        modal = Modal(items, title="Add Field")
        await interaction.response.send_modal(modal)
        await modal.wait()

        v = modal.values
        data["fields"].append({
            "name": v["name"],
            "value": v["value"],
            "inline": True if v["inline"].lower() == "true" else False
        })

        return await interaction.edit_original_response(embed=self.build_embed())
    
    @discord.ui.button(label="Remove Field", style=discord.ButtonStyle.red, row=1)
    async def remove_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = [
            discord.ui.TextInput(
                label="Index",
                placeholder="The number of fields to remove, e.g. 1",
                style=discord.TextStyle.short
            )
        ]

        data = self.data.get(self.embedType)
        if "fields" not in data:
            data["fields"] = []

        if len(data["fields"]) == 0:
            return await interaction.response.send_message("There are no fields to remove!", ephemeral=True)
        
        modal = Modal(items, title="Remove Field")
        await interaction.response.send_modal(modal)
        await modal.wait()

        try:
            del data["fields"][int(modal.values["index"])]
        except:
            return await interaction.followup.send("Can't found the field", ephemeral=True)
        
        return await interaction.edit_original_response(embed=self.build_embed())

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.green, row=1)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await func.update_settings(
            interaction.guild_id,
            {"$set": {"default_controller.embeds": self.data}},
        )

        await self.on_timeout()
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.red, row=1)
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.data.update(copy.deepcopy(self.original_data))
        return await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(emoji='🗑️', row=1)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.response.delete()
        self.stop()

        