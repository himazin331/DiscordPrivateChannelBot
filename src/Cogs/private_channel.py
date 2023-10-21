import discord
from discord import CategoryChannel, Guild, TextChannel
from discord.ext import commands
import asyncio

from loguru import logger
from typing import Optional

from settings import GUILD_NAME, GUILD_ID, CHANNEL_ID, CATEGORY_ID


class PrivateChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Login successful.")
        self.used_pvch_userid: dict[int, TextChannel] = {}

    @commands.command(description="Display help")
    async def pvch_help(self, ctx: commands.Context):
        # TODO : ヘルプの表示
        pass

    @commands.command(description="Create private channel")
    async def pvch_create(self, ctx: commands.Context):
        logger.debug(f"Create private channel. called by {ctx.author.global_name}")
        await ctx.message.delete()

        user_id: int = ctx.author.id
        if self.used_pvch_userid.get(user_id) is not None:
            logger.debug("Skipped because a private channel already exists.")
            await ctx.send(f"あなたのプライベートチャンネル{self.used_pvch_userid[user_id].mention}は既に存在します。", delete_after=5.0)
            return

        ch_name: str = f"pvch-{ctx.author.global_name}"
        permission: dict = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        category: CategoryChannel = ctx.guild.get_channel(CATEGORY_ID)
        channel: TextChannel = await category.create_text_channel(name=ch_name, overwrites=permission)

        if channel is not None:
            logger.debug("Successfully created a private channel.")

            await ctx.send(f"{channel.mention} を作成しました。", delete_after=5.0)
            self.used_pvch_userid[user_id] = channel

            await self.init_private_channel(channel)
        else:
            logger.error("Failed to create private channel.")
            await ctx.send("プライベートチャンネルの作成に失敗しました。", delete_after=5.0)

    async def init_private_channel(self, channel: TextChannel):
        logger.debug("Sending the initial message after creating a private channel.")
        text: str = f"""
ようこそ！ここはプライベートチャンネルです！
このチャンネルはあなたとあなたが招待した方のみ閲覧できます。(ただし、権限者は例外です)\n
チャンネルは作成から24時間経過すると自動的に削除されます。`$pvch_delete`で手動で削除することもできます。\n
注意: プライベートチャンネルにおいても{GUILD_NAME} Discordサーバー利用におけるガイドラインは適用されます。
"""
        await channel.send(text)

    @commands.command(description="Delete private channel")
    async def pvch_delete(self, ctx: commands.Context):
        logger.debug(f"Delete private channel. called by {ctx.author.global_name}")
        await ctx.message.delete()

        channel: Optional[TextChannel] = self.used_pvch_userid.pop(ctx.author.id, None)
        if channel is None:
            logger.debug("Skip if private channel does not exist.")
            await ctx.send("あなたはまだプライベートチャンネルを作成していないようです。\n`$pvch_create`で作成することができます。", delete_after=5.0)
            return

        try:
            if ctx.channel.id == channel.id:
                await ctx.send("このプライベートチャンネルを削除します！")

                await asyncio.sleep(5)
                await channel.delete()
            else:
                await channel.delete()
                await ctx.send("あなたのプライベートチャンネルを削除しました。", delete_after=5.0)
        except discord.HTTPException:
            logger.error("Failed to delete private channel.")
            await ctx.send("プライベートチャンネルの削除に失敗しました。", delete_after=5.0)

# TODO : コマンド候補リスト表示..
# TODO : $pvch_create @user_name[...]で作成時に指定したユーザーを招待する
# TODO : $pvch_invite @user_name[...]で招待する
# TODO : 自動で24時間後に削除する
# TODO : ボットメッセージの可視性を高める

def setup(bot: commands.Bot):
    return bot.add_cog(PrivateChannel(bot))
