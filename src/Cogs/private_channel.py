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

    @commands.command(description="Create private channel [For public channel use only]")
    async def pvch_create(self, ctx: commands.Context):
        """Create private channel"""
        if ctx.channel.category_id == CATEGORY_ID:
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("このコマンドはプライベートチャンネル内では実行できません。"), delete_after=MSG_DELETE_DELAY)
            return

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
            channel: TextChannel = await self.category.create_text_channel(name=ch_name, overwrites=self.ch_permission)
        except discord.HTTPException:
            logger.error("Failed to create private channel.")
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("プライベートチャンネルの作成に失敗しました。"), delete_after=MSG_DELETE_DELAY)
            return

        invite_embed: Optional[Embed] = None
        if len(ctx.message.mentions) > 0:  # Invite invited users, if any
            invite_embed = await self.invite(channel, ctx.message.mentions)

        await ctx.message.delete(delay=MSG_DELETE_DELAY)
        await ctx.message.reply(embed=success_embed_template(f"{channel.mention}を作成しました。"), delete_after=MSG_DELETE_DELAY)
        self.used_pvch_userid[user_id] = channel

        await self.init_private_channel(channel)
        if invite_embed is not None:
            await channel.send(embed=invite_embed)

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
    
        if ctx.channel.category_id == CATEGORY_ID and ctx.channel.id != channel.id:  # In someone else's private channel
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), delete_after=MSG_DELETE_DELAY)
            return

        try:
            if ctx.channel.id == channel.id:  # In my private channel
                await ctx.message.reply(embed=info_embed_template(f"約5秒後に、このプライベートチャンネルを削除します！"))

                await asyncio.sleep(5.0)
                await channel.delete()
            else: # In public channel
                await channel.delete()
                await ctx.message.delete(delay=MSG_DELETE_DELAY)
                await ctx.message.reply(embed=success_embed_template("あなたのプライベートチャンネルを削除しました。"), delete_after=MSG_DELETE_DELAY)
        except (discord.NotFound, discord.HTTPException):
            logger.error("Failed to delete private channel.")
            await ctx.send(embed=error_embed_template("プライベートチャンネルの削除に失敗しました。"), delete_after=MSG_DELETE_DELAY)

    @commands.command(description="Invite user to private channel [For public channel use only]")
    async def pvch_invite(self, ctx: commands.Context):
        """Invite user to private channel"""
        if ctx.channel.category_id == CATEGORY_ID:
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("このコマンドはプライベートチャンネル内では実行できません。"), delete_after=MSG_DELETE_DELAY)
            return
        
        user_id: int = ctx.author.id
        channel: Optional[TextChannel] = self.used_pvch_userid.get(user_id)
        if channel is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `$pvch_create @user [@user...]`でユーザーを招待して作成することができます。"
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template(msg), delete_after=MSG_DELETE_DELAY)
            return

        mentions_members: list[discord.Member] = ctx.message.mentions
        if len(mentions_members) == 0:
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("招待するユーザーを指定してください。"), delete_after=MSG_DELETE_DELAY)
            return

        embed: Embed = await self.invite(channel, mentions_members)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.error("Failed to send message to private channel.")
        await ctx.message.delete(delay=MSG_DELETE_DELAY)
        await ctx.message.reply(embed=info_embed_template("プライベートチャンネルをご確認ください。"), delete_after=MSG_DELETE_DELAY)

    async def invite(self, channel: TextChannel, mentions_members: list[discord.Member]) -> Embed:
        """Invitation link issued and sent"""
        failed_members: list[str] = []

        for member in mentions_members:
            if member.bot:
                continue
            if member.roles[-1].id == MODERATOR_ROLE_ID:
                continue
            # TODO 自分自身のメンションもスルーするようにする

            try:
                await channel.set_permissions(member, read_messages=True, send_messages=True)
            except discord.HTTPException:
                failed_members.append(member.global_name)

        embed: Embed = Embed(title="プライベートチャンネル招待", color=0x9b59b6)
        success_members: list[str] = [member.global_name for member in mentions_members if member.global_name not in failed_members]
        if len(success_members) > 0:
            embed.add_field(name="成功", value="- "+"\n- ".join(success_members), inline=False)
        if len(failed_members) > 0:
            embed.add_field(name="失敗", value="- "+"\n- ".join(failed_members), inline=False)
        return embed

    @commands.command(description="Leave private channel")
    async def pvch_leave(self, ctx: commands.Context):
        """Leave private channel"""
        if ctx.channel.category_id != CATEGORY_ID:
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("このコマンドはプライベートチャンネルでのみ使用できます。"), delete_after=MSG_DELETE_DELAY)
            return

        this_user_ch: Optional[TextChannel] = self.used_pvch_userid.get(ctx.author.id)
        if this_user_ch is not None and this_user_ch.id == ctx.channel.id:
            await ctx.message.reply(embed=error_embed_template("このコマンドはこのプライベートチャンネルの作成者は実行できません。\n\nヒント: `$pvch_delete`で削除することができます。"))
            return

        try:
            await ctx.channel.set_permissions(ctx.author, overwrite=None)
            await ctx.message.reply(embed=info_embed_template(f"{ctx.author.global_name}さんがプライベートチャンネルを退出しました。"))
        except discord.HTTPException:
            logger.error("Failed to leave private channel.")
            await ctx.message.reply(embed=error_embed_template("プライベートチャンネルの退出に失敗しました。"))
            return

    @commands.command(description="Kick private channel")
    async def pvch_kick(self, ctx: commands.Context):
        """Kick private channel"""
        channel: Optional[TextChannel] = self.used_pvch_userid.get(ctx.author.id)
        if channel is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `$pvch_create`で作成することができます。"
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template(msg), delete_after=MSG_DELETE_DELAY)
            return
        
        if ctx.channel.category_id == CATEGORY_ID and ctx.channel.id != channel.id:  # In someone else's private channel
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), delete_after=MSG_DELETE_DELAY)
            return
        
        mentions_members: list[discord.Member] = ctx.message.mentions
        if len(mentions_members) == 0:
            await ctx.message.delete(delay=MSG_DELETE_DELAY)
            await ctx.message.reply(embed=error_embed_template("追放するユーザーを指定してください。"), delete_after=MSG_DELETE_DELAY)
            return

        try:
            # TODO 追放処理
            await ctx.channel.set_permissions(ctx.author, overwrite=None)
            await ctx.message.reply(embed=info_embed_template(f"{ctx.author.global_name}さんをプライベートチャンネルから追放しました。"))
        except discord.HTTPException:
            logger.error("Failed to leave private channel.")
            await ctx.message.reply(embed=error_embed_template("プライベートチャンネルからの追放に失敗しました。"))
            return

# TODO : プライベートチャンネルを抜けさせるコマンド
# TODO : 自動削除の実装 
    # 作成から24時間後に削除
    # 削除15分前に通知
# TODO : 延長機能の実装
    # 最大6時間延長 延長時点から+6h
    # 作成してから18時間(=24h-6h)以上経過してから延長できる
# TODO : コマンド候補リスト表示..
# TODO : admin専用コマンドの作成
    # 他人のプライベートチャンネル削除
# TODO : クールダウンの設定

def setup(bot: commands.Bot):
    return bot.add_cog(PrivateChannel(bot))
