from __future__ import annotations
import discord
from discord.ui import View, UserSelect, Button

from Cogs import private_channel
from utils.embed_template import info_embed_template


class InviteUserSelect(View):
    """User invitation select box"""
    def __init__(self, pvch: 'private_channel.PrivateChannel'):
        super().__init__()
        self.pvch: 'private_channel.PrivateChannel' = pvch

    @discord.ui.select(cls=UserSelect, max_values=25, placeholder="招待するユーザーを指定")
    async def selectMenu(self, ctx: discord.Interaction, select: UserSelect):
        select.disabled = True
        await ctx.response.edit_message(view=self)
        await self.pvch.invite_user(select.values)
        await ctx.followup.send(embed=info_embed_template("プライベートチャンネルをご確認ください。"), ephemeral=True)


class KickUserSelect(View):
    """User kick select box"""
    def __init__(self, pvch: 'private_channel.PrivateChannel'):
        super().__init__()
        self.pvch: 'private_channel.PrivateChannel' = pvch

    @discord.ui.select(cls=UserSelect, max_values=25, placeholder="追放するユーザーを指定")
    async def selectMenu(self, ctx: discord.Interaction, select: UserSelect):
        select.disabled = True
        await ctx.response.edit_message(view=self)
        await self.pvch.kick_user(select.values)


class DeletePrivateChannel(View):
    """Channel deletion confirmation button"""
    def __init__(self, pvch: 'private_channel.PrivateChannel', admin: bool = False):
        super().__init__()
        self.pvch: 'private_channel.PrivateChannel' = pvch
        self.admin: bool = admin

    @discord.ui.button(label="はい", style=discord.ButtonStyle.red)
    async def ok(self, ctx: discord.Interaction, button: Button):
        button.disabled = True
        self.cancel_.disabled = True
        await ctx.response.edit_message(view=self)
        if self.admin:
            await self.pvch.force_delete()  # Deletion by Authorized Person
        else:
            await self.pvch.delete_channel(ctx)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.gray)
    async def cancel_(self, ctx: discord.Interaction, button: Button):
        button.disabled = True
        self.ok.disabled = True
        await ctx.response.edit_message(view=self)
        await ctx.followup.send(embed=info_embed_template("削除をキャンセルしました。"), ephemeral=True)
