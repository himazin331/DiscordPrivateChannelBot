import discord
from discord import Guild, CategoryChannel, TextChannel, Embed
from discord.ext import commands
import asyncio

from datetime import timezone, timedelta
from loguru import logger
from typing import Optional

from utils.embed_template import success_embed_template, error_embed_template, info_embed_template

from settings import GUILD_NAME, GUILD_ID, CATEGORY_ID, MODERATOR_ROLE_ID, GENERAL_ROLE_ID

MSG_DELETE_DELAY = 5.0

class PrivateChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Login successful.")
        self.guild: Guild = self.bot.get_guild(GUILD_ID)
        self.category: CategoryChannel = self.guild.get_channel(CATEGORY_ID)

        # Delete all existing private channels
        for ch in self.category.text_channels:
            await ch.delete()

        self.ch_permission: dict = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.guild.get_role(MODERATOR_ROLE_ID): discord.PermissionOverwrite(read_messages=True),
            self.guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        self.used_pvch_userid: dict[int, TextChannel] = {}

    @commands.command(description="Display help")
    async def pvch_help(self, ctx: commands.Context):
        # TODO : ヘルプの表示
        pass

    @commands.command(description="Create private channel")
    async def pvch_create(self, ctx: commands.Context):
        """Create private channel"""

        user_id: int = ctx.author.id
        # Check if private channels already exists.
        if (ch := self.used_pvch_userid.get(user_id)) is not None:
            if self.guild.get_channel(ch.id) is not None:
                msg: str = f"あなたのプライベートチャンネル{self.used_pvch_userid[user_id].mention}は既に存在します。\n\nヒント: `$pvch_delete`でプライベートチャンネルを削除することができます。"
                await ctx.message.delete(delay=MSG_DELETE_DELAY)
                await ctx.message.reply(embed=error_embed_template(msg), delete_after=MSG_DELETE_DELAY)
                return
            else:
                del self.used_pvch_userid[user_id]

        # Create private channel
        ch_name: str = f"pvch-{ctx.author.global_name}"
        self.ch_permission[ctx.author] = discord.PermissionOverwrite(read_messages=True)
        try:
            channel: TextChannel = await self.category.create_text_channel(name=ch_name, overwrites=self.ch_permission, slowmode_delay=5)
        except discord.HTTPException:
            logger.error("Failed to create private channel.")
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("プライベートチャンネルの作成に失敗しました。"), delete_after=MSG_DELETE_DELAY)
            return

        await ctx.message.delete(delay=MSG_DELETE_DELAY)
        await ctx.message.reply(embed=success_embed_template(f"{channel.mention}を作成しました。"), delete_after=MSG_DELETE_DELAY)
        self.used_pvch_userid[user_id] = channel

        await self.init_private_channel(channel)

    async def init_private_channel(self, channel: TextChannel):
        """Send a Welcome message to the private channel you created"""
        msg: str = """
このチャンネルはあなたとあなたが招待した方のみ閲覧できます。(ただし、権限者は閲覧可)\n
チャンネルは作成から24時間経過すると自動的に削除されます。`$pvch_delete`で手動で削除することもできます。\n
"""
        channel_exp: str = (channel.created_at.astimezone(timezone(timedelta(hours=9))) + timedelta(days=1)).strftime("%Y/%m/%d %H:%M:%S")
        embed: Embed = Embed(title="ようこそ！ここはプライベートチャンネルです！", description=msg, color=0x3498db)
        embed.add_field(name="注意", value=f"プライベートチャンネルにおいても{GUILD_NAME} Discordサーバー利用におけるガイドラインは適用されます。", inline=False)
        embed.add_field(name="チャンネル有効期限", value=f"{channel_exp}", inline=False)
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to send message to private channel.")

    @commands.command(description="Delete private channel")
    async def pvch_delete(self, ctx: commands.Context):
        """Delete private channel"""
        channel: Optional[TextChannel] = self.used_pvch_userid.pop(ctx.author.id, None)
        if channel is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `$pvch_create`で作成することができます。"
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template(msg), delete_after=MSG_DELETE_DELAY)
            return

        try:
            if ctx.channel.id == channel.id:  # In private channel
                await ctx.message.reply(embed=info_embed_template(f"約5秒後に、このプライベートチャンネルを削除します！"))

                await asyncio.sleep(5.0)
                await channel.delete()
            else:
                await channel.delete()
                await ctx.message.delete(delay=MSG_DELETE_DELAY)
                await ctx.message.reply(embed=success_embed_template("あなたのプライベートチャンネルを削除しました。"), delete_after=MSG_DELETE_DELAY)
        except (discord.NotFound, discord.HTTPException):
            logger.error("Failed to delete private channel.")
            await ctx.send(embed=error_embed_template("プライベートチャンネルの削除に失敗しました。"), delete_after=MSG_DELETE_DELAY)

    @commands.command(description="Invite user to private channel")
    async def pvch_invite(self, ctx: commands.Context):
        """Invite user to private channel"""
        mentions_members: list[discord.Member] = ctx.message.mentions
        if len(mentions_members) == 0:
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("招待するユーザーを指定してください。"), delete_after=MSG_DELETE_DELAY)
            return

        user_id: int = ctx.author.id
        channel: Optional[TextChannel] = self.used_pvch_userid.get(user_id)
        if channel is None:
            return # TODO : 作成&招待 `$pvch_create @user`

        failed_members: list[str] = await self.invite(channel, mentions_members)
        embed: Embed = Embed(title="プライベートチャンネル招待", color=0x9b59b6)
        
        success_members: list[str] = [member.global_name for member in mentions_members if member.global_name not in failed_members]
        if len(failed_members) == 0:
            embed.add_field(name="成功", value="- "+"\n- ".join(success_members), inline=False)
        else:
            embed.add_field(name="失敗", value="- "+"\n- ".join(failed_members), inline=False)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to send message to private channel.")
        await ctx.message.delete(delay=MSG_DELETE_DELAY)
        await ctx.message.reply(embed=info_embed_template("プライベートチャンネルをご確認ください。"), delete_after=MSG_DELETE_DELAY)

    async def invite(self, channel: TextChannel, mentions_members: list[discord.Member]) -> list:
        """Invitation link issued and sent"""
        failed_members: list[str] = []

        for member in mentions_members:
            if member.bot:
                continue

            try:
                await channel.set_permissions(member, read_messages=True, send_messages=True)
            except discord.HTTPException:
                failed_members.append(member.global_name)
        return failed_members

# TODO : 他人のプライベートチャンネルを抜けるコマンド
# TODO : プライベートチャンネルを抜けさせるコマンド
# TODO : コマンド候補リスト表示..
# TODO : $pvch_create @user_name[...]で作成時に指定したユーザーを招待する
# TODO : 自動で24時間後に削除する
# TODO : クールダウンの設定

def setup(bot: commands.Bot):
    return bot.add_cog(PrivateChannel(bot))
