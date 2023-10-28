from math import e
import discord
from discord import app_commands, Guild, CategoryChannel, TextChannel, Embed
from discord.ext import commands
import asyncio

from datetime import datetime, timezone, timedelta
from loguru import logger
from typing import Optional

from utils.embed_template import success_embed_template, error_embed_template, info_embed_template

from settings import *


class PrivateChannel:
    def __init__(self, user_id: int, channel: TextChannel):
        self.user_id: int = user_id
        self.channel: TextChannel = channel
        self.exp: datetime = channel.created_at.astimezone(timezone(timedelta(hours=9))) + timedelta(hours=24)

    def __str__(self):
        return f"PrivateChannel(user_id={self.user_id}, channel={self.channel}, exp={self.exp})"

    def extension_exp(self):
        self.exp = datetime.utcnow() + timedelta(hours=15)  # UTC+9(JST) + 6h(extension)

    def is_expired(self):
        return True if self.exp <= (datetime.utcnow() + timedelta(hours=9)) else False


class PrivateChannelBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Login successful.")
        await self.bot.tree.sync(guild=discord.Object(GUILD_ID))

        self.guild: Guild = self.bot.get_guild(GUILD_ID)
        self.category: CategoryChannel = self.guild.get_channel(CATEGORY_ID)

        # Delete all existing private channels
        for ch in self.category.text_channels:
            await ch.delete()

        self.used_pvch_userid: dict[int, PrivateChannel] = {}

    @app_commands.command(name="pvch_create", description="自分のプライベートチャンネルを作成する")
    @app_commands.guilds(GUILD_ID)
    async def pvch_create(self, ctx: discord.Interaction, invite_user: discord.Member = None):
        """Create private channel"""
        if ctx.channel.category_id == CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネル内では実行できません。"), ephemeral=True)
            return

        user_id: int = ctx.user.id
        # Check if private channels already exists.
        if (pvch := self.used_pvch_userid.get(user_id)) is not None:
            if self.guild.get_channel(pvch.channel.id) is not None:
                msg: str = f"あなたのプライベートチャンネル{pvch.channel.mention}は既に存在します。\n\nヒント: `/pvch_delete`でプライベートチャンネルを削除することができます。"
                await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
                return
            else:
                del self.used_pvch_userid[user_id]

        # Create private channel
        ch_name: str = f"pvch-{ctx.user.global_name}"
        ch_permission: dict = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.guild.get_role(MODERATOR_ROLE_ID): discord.PermissionOverwrite(read_messages=True),
            self.guild.me: discord.PermissionOverwrite(read_messages=True),
            ctx.user: discord.PermissionOverwrite(read_messages=True)
        }
        try:
            channel: TextChannel = await self.category.create_text_channel(name=ch_name, overwrites=ch_permission)
        except discord.HTTPException:
            logger.error("Failed to create private channel.")
            await ctx.response.send_message(embed=error_embed_template("プライベートチャンネルの作成に失敗しました。"), ephemeral=True)
            return

        invite_embed: Optional[Embed] = None
        if invite_user is not None:  # Invite invited users, if any
            invite_embed = await self.invite(channel, user_id, invite_user)

        await ctx.response.send_message(embed=success_embed_template(f"{channel.mention}を作成しました。"), ephemeral=True)
        self.used_pvch_userid[user_id] = PrivateChannel(user_id, channel)

        await self.init_private_channel(channel)
        if invite_embed is not None:
            await channel.send(embed=invite_embed)

    async def init_private_channel(self, channel: TextChannel):
        """Send a Welcome message to the private channel you created"""
        msg: str = """
このチャンネルはあなたとあなたが招待した方のみ閲覧できます。(ただし、権限者は閲覧可)\n
チャンネルは作成から24時間経過すると自動的に削除されます。`/pvch_delete`で手動で削除することもできます。\n
"""
        channel_exp: str = (channel.created_at.astimezone(timezone(timedelta(hours=9))) + timedelta(hours=24)).strftime("%Y/%m/%d %H:%M:%S")
        embed: Embed = Embed(title="ようこそ！ここはプライベートチャンネルです！", description=msg, color=0x3498db)
        embed.add_field(name="注意", value=f"プライベートチャンネルにおいても{GUILD_NAME} Discordサーバー利用におけるガイドラインは適用されます。", inline=False)
        embed.add_field(name="チャンネル有効期限", value=f"{channel_exp}", inline=False)
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to send message to private channel.")

    @app_commands.command(name="pvch_delete", description="自分のプライベートチャンネルを削除する")
    @app_commands.guilds(GUILD_ID)
    async def pvch_delete(self, ctx: discord.Interaction):
        """Delete private channel"""
        pvch: Optional[PrivateChannel] = self.used_pvch_userid.pop(ctx.user.id, None)
        if pvch is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `/pvch_create`で作成することができます。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return
    
        channel: TextChannel = pvch.channel
        if ctx.channel.category_id == CATEGORY_ID and ctx.channel.id != channel.id:  # In someone else's private channel
            await ctx.response.send_message(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), ephemeral=True)
            return

        try:
            if ctx.channel.id == channel.id:  # In my private channel
                await ctx.response.send_message(embed=info_embed_template(f"約5秒後に、このプライベートチャンネルを削除します。"))

                await asyncio.sleep(5.0)
                await channel.delete()
            else: # In public channel
                await channel.delete()
                await ctx.response.send_message(embed=success_embed_template("あなたのプライベートチャンネルを削除しました。"), ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            logger.error("Failed to delete private channel.")
            await ctx.response.send_message(embed=error_embed_template("プライベートチャンネルの削除に失敗しました。"), ephemeral=True)

    @app_commands.command(name="pvch_invite", description="自分のプライベートチャンネルにユーザーを招待する")
    @app_commands.guilds(GUILD_ID)
    async def pvch_invite(self, ctx: discord.Interaction, invite_user: discord.Member):
        """Invite user to private channel"""
        if ctx.channel.category_id == CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネル内では実行できません。"), ephemeral=True)
            return
        
        user_id: int = ctx.user.id
        pvch: Optional[PrivateChannel] = self.used_pvch_userid.get(user_id)
        if pvch is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `/pvch_create @user`でユーザーを招待して作成することができます。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        embed: Embed = await self.invite(pvch.channel, user_id, invite_user)
        try:
            await pvch.channel.send(embed=embed)
            await ctx.response.send_message(embed=info_embed_template("プライベートチャンネルをご確認ください。"), ephemeral=True)
        except discord.HTTPException:
            logger.error("Failed to send message to private channel.")

    async def invite(self, channel: TextChannel, exe_user_id: int, user: discord.Member) -> Embed:
        """User Invitation"""
        embed: Embed = Embed(title="プライベートチャンネル招待", color=0x9b59b6)
        name: str = ""
        if user.bot or user.id == exe_user_id or user.roles[0].id == MODERATOR_ROLE_ID:
            name = "無効"
        else:
            try:
                await channel.set_permissions(user, read_messages=True, send_messages=True)
                name = "成功"
            except discord.HTTPException:
                name = "失敗"

        embed.add_field(name=name, value=user.name if user.global_name is None else user.global_name, inline=False)
        return embed

    @app_commands.command(name="pvch_leave", description="他者のプライベートチャンネルを離脱する")
    @app_commands.guilds(GUILD_ID)
    async def pvch_leave(self, ctx: discord.Interaction):
        """Leave private channel"""
        if ctx.channel.category_id != CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでのみ使用できます。"), ephemeral=True)
            return

        pvch: Optional[PrivateChannel] = self.used_pvch_userid.get(ctx.user.id)
        if pvch is not None and pvch.channel.id == ctx.channel.id:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはこのプライベートチャンネルの作成者は実行できません。\n\nヒント: `/pvch_delete`で削除することができます。"),
                                            ephemeral=True)
            return

        try:
            await ctx.channel.set_permissions(ctx.user, overwrite=None)
            await ctx.response.send_message(embed=info_embed_template(f"{ctx.user.global_name}さんがプライベートチャンネルを退出しました。"))
        except discord.HTTPException:
            logger.error("Failed to leave private channel.")
            await ctx.response.send_message(embed=error_embed_template("プライベートチャンネルの退出に失敗しました。"), ephemeral=True)

    @app_commands.command(name="pvch_kick", description="自分のプライベートチャンネルからユーザーを追放する")
    @app_commands.guilds(GUILD_ID)
    async def pvch_kick(self, ctx: discord.Interaction, kick_user: discord.Member):
        """Kick private channel"""
        if ctx.channel.category_id != CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでのみ使用できます。"), ephemeral=True)
            return

        pvch: Optional[PrivateChannel] = self.used_pvch_userid.get(ctx.user.id)
        if pvch is None or pvch.channel.id != ctx.channel.id:  # In someone else's private channel
            await ctx.response.send_message(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), ephemeral=True)
            return

        embed: Embed = await self.kick(pvch.channel, ctx.user.id, kick_user)
        try:
            await ctx.response.send_message(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to leave private channel.")

    async def kick(self, channel: TextChannel, exe_user_id: int, user: discord.Member) -> Embed:
        """User Kick"""
        embed: Embed = Embed(title="プライベートチャンネル追放", color=0xf1c40f)
        name: str = ""
        if user.bot or user.id == exe_user_id or user.roles[0].id == MODERATOR_ROLE_ID:
            name = "無効"
        else:
            try:
                await channel.set_permissions(user, overwrite=None)
                name = "成功"
            except discord.HTTPException:
                name = "失敗"

        embed.add_field(name=name, value=user.name if user.global_name is None else user.global_name, inline=False)
        return embed


# TODO : 自動削除の実装 
    # 作成から24時間後に削除
    # 削除15分前に通知
# TODO : 延長機能の実装
    # 最大6時間延長 延長時点から+6h
    # 作成してから18時間(=24h-6h)以上経過してから延長できる
# TODO : admin専用コマンドの作成
    # 他人のプライベートチャンネル削除
# TODO : クールダウンの設定
# TODO : テンプレート機能の実装

def setup(bot: commands.Bot):
    return bot.add_cog(PrivateChannelBot(bot))
