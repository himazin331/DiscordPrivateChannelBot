import discord
from discord import app_commands, Guild, CategoryChannel, TextChannel, Embed
from discord.ext import commands, tasks
import asyncio

from datetime import datetime, timezone, timedelta
from loguru import logger
from typing import Optional

from ui.interaction_ui import *
from utils.embed_template import *

from settings import *


class PrivateChannel:
    def __init__(self, user_id: int, channel: TextChannel):
        self.user_id: int = user_id
        self.channel: TextChannel = channel
        self.exp: datetime = channel.created_at.astimezone(timezone(timedelta(hours=9))) + timedelta(hours=CHANNEL_TTL_HOUR)
        self.delete_notice: bool = False

    def __str__(self) -> str:
        return f"PrivateChannel(user_id={self.user_id}, channel={self.channel}, exp={self.exp})"

    async def send_welcome_message(self):
        """Send a Welcome message to the private channel you created"""
        embed: Embed = welcome_embed_template(self.exp.strftime('%Y/%m/%d　%H:%M:%S'))
        try:
            sent_message = await self.channel.send(embed=embed)
            await sent_message.pin()
        except discord.HTTPException:
            logger.error("Failed to send message to private channel.")

    async def delete_channel(self, ctx: discord.Interaction):
        """Delete private channel"""
        try:
            if ctx.channel.id == self.channel.id:  # In my private channel
                await self.channel.send(embed=info_embed_template(f"約5秒後に、このプライベートチャンネルを削除します。"))

                await asyncio.sleep(5.0)
                await self.channel.delete()
            else: # In public channel
                await self.channel.delete()
                await ctx.followup.send(embed=success_embed_template("あなたのプライベートチャンネルを削除しました。"), ephemeral=True)
            del used_pvch_userid[self.user_id]
        except (discord.NotFound, discord.HTTPException):
            logger.error("Failed to delete private channel.")
            await ctx.followup.send(embed=error_embed_template("プライベートチャンネルの削除に失敗しました。"), ephemeral=True)

    async def force_delete(self):
        """Forced deletion (automatic deletion or deletion by authority)"""
        try:
            await self.channel.delete()
            del used_pvch_userid[self.user_id]
        except (discord.NotFound, discord.HTTPException):
            logger.error("Failed to delete private channel.")

    async def invite_user(self, users: list[discord.Member]) -> Embed:
        """User Invitation"""
        success_users: list[str] = []
        failed_users: list[str] = []
        ignore_users: list[str] = []

        for user in users:
            if user.bot or user.id == self.user_id or user.roles[0].id == MODERATOR_ROLE_ID:
                ignore_users.append(user.name)
                continue

            try:
                await self.channel.set_permissions(user, read_messages=True, send_messages=True)
                success_users.append(user.global_name)
            except discord.HTTPException:
                failed_users.append(user.global_name)

        embed: Embed = invite_embed_template()
        if len(success_users) > 0:
            embed.add_field(name="成功", value="- "+"\n- ".join(success_users), inline=False)
        if len(failed_users) > 0:
            embed.add_field(name="失敗", value="- "+"\n- ".join(failed_users), inline=False)
        if len(ignore_users) > 0:
            embed.add_field(name="無効", value="- "+"\n- ".join(ignore_users), inline=False)
        await self.channel.send(embed=embed)

    async def kick_user(self, users: list[discord.Member]) -> Embed:
        """User Kick"""
        success_users: list[str] = []
        failed_users: list[str] = []
        ignore_users: list[str] = []

        for user in users:
            if user.bot or user.id == self.user_id or user.roles[0].id == MODERATOR_ROLE_ID:
                ignore_users.append(user.name)
                continue

            try:
                await self.channel.set_permissions(user, overwrite=None)
                success_users.append(user.global_name)
            except discord.HTTPException:
                failed_users.append(user.global_name)

        embed: Embed = kick_embed_template()
        if len(success_users) > 0:
            embed.add_field(name="成功", value="- "+"\n- ".join(success_users), inline=False)
        if len(failed_users) > 0:
            embed.add_field(name="失敗", value="- "+"\n- ".join(failed_users), inline=False)
        if len(ignore_users) > 0:
            embed.add_field(name="無効", value="- "+"\n- ".join(ignore_users), inline=False)
        await self.channel.send(embed=embed)

    async def extension_exp(self, ctx: discord.Interaction) -> bool:
        """Extend private channel expiration date"""
        new_exp: datetime = datetime.now().astimezone(timezone(timedelta(hours=9))) + timedelta(hours=EXTEND_TTL_HOUR)
        if new_exp < self.exp:
            msg: str = f"""現在、有効期限を延長できません。\n
延長が可能になる時刻は`{(self.exp - timedelta(hours=EXTEND_TTL_HOUR) + timedelta(minutes=1)).strftime('%Y/%m/%d　%H:%M:%S')}`からです。"""
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return False
        self.exp = new_exp

        msg: str = f"有効期限を延長しました。\n新しい有効期限は`{self.exp.strftime('%Y/%m/%d　%H:%M:%S')}`です。"
        if ctx.channel.id == self.channel.id:  # In my private channel
            await ctx.response.send_message(embed=success_embed_template(msg))
        else: # In public channel
            await ctx.response.send_message(embed=success_embed_template(msg), ephemeral=True)

        # Welcome message updated
        pinned_messages = await ctx.channel.pins()
        if len(pinned_messages) == 0:
            return True
        welcome_message = pinned_messages[0]

        embed: Embed = welcome_embed_template(self.exp.strftime('%Y/%m/%d　%H:%M:%S'))
        await welcome_message.edit(embed=embed)
        return True

    async def is_expired(self) -> bool:
        """Check if private channel is expired"""
        now: datetime = datetime.now().astimezone(timezone(timedelta(hours=9)))
        if self.exp - timedelta(minutes=15) <= now:
            if self.exp <= now:
                return True

            if not self.delete_notice:
                await self.channel.send(embed=info_embed_template(f"あと15分で、このプライベートチャンネルは削除されます。"))
                self.delete_notice = True
        return False


used_pvch_userid: dict[int, PrivateChannel] = {}  # {user_id: PrivateChannel}

class PrivateChannelBot(commands.Cog):
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

        self.check_pv_exp.start()

        await self.bot.tree.sync()
        await self.bot.change_presence(activity=discord.Game("running..."))

    async def cog_app_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):  # Cooldown error message
            await ctx.response.send_message(f"クールダウン中...\n`{str(error)}`", ephemeral=True)

    @app_commands.command(name="pvch_help", description="ヘルプを表示する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    async def pvch_help(self, ctx: discord.Interaction):
        """Display command help"""
        embed: Embed = Embed(title="コマンドヘルプ", color=0x979c9f)
        for cmd in self.bot.tree.walk_commands():
            embed.add_field(name=f"`/{cmd.name}`", value=cmd.description, inline=False)
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pvch_create", description="自分のプライベートチャンネルを作成する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    async def pvch_create(self, ctx: discord.Interaction):
        """Create private channel"""
        if ctx.channel.category_id == CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでは実行できません。"), ephemeral=True)
            return

        user_id: int = ctx.user.id
        # Check if private channels already exists.
        if (pvch := used_pvch_userid.get(user_id)) is not None:
            if self.guild.get_channel(pvch.channel.id) is not None:
                msg: str = f"あなたのプライベートチャンネル{pvch.channel.mention}は既に存在します。\n\nヒント: `/pvch_delete`でプライベートチャンネルを削除することができます。"
                await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
                return
            else:
                del used_pvch_userid[user_id]

        # Create private channel
        ch_name: str = f"pvch-{ctx.user.global_name}"
        # ch_permission: dict = {
        #     self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        #     self.guild.get_role(MODERATOR_ROLE_ID): discord.PermissionOverwrite(read_messages=True),
        #     self.guild.me: discord.PermissionOverwrite(read_messages=True),
        #     ctx.user: discord.PermissionOverwrite(read_messages=True, )
        # }
        try:
            channel: TextChannel = await self.category.create_text_channel(name=ch_name)
            await channel.set_permissions(ctx.user, read_messages=True)
        except discord.HTTPException:
            logger.error("Failed to create private channel.")
            await ctx.response.send_message(embed=error_embed_template("プライベートチャンネルの作成に失敗しました。"), ephemeral=True)
            return
        pvch: PrivateChannel = PrivateChannel(user_id, channel)
        used_pvch_userid[user_id] = pvch
        await pvch.send_welcome_message()

        # Creating a User Invitation Component
        msg: str = f"{channel.mention}を作成しました。\n\nユーザーの招待は下のリストからできます(最大25人まで)"
        view: InviteUserSelect = InviteUserSelect(pvch)
        await ctx.response.send_message(embed=success_embed_template(msg), view=view, ephemeral=True)

    @app_commands.command(name="pvch_delete", description="自分のプライベートチャンネルを削除する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    async def pvch_delete(self, ctx: discord.Interaction):
        """Delete private channel"""
        pvch: Optional[PrivateChannel] = used_pvch_userid.get(ctx.user.id)
        if pvch is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `/pvch_create`で作成することができます。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        if ctx.channel.category_id == CATEGORY_ID and ctx.channel.id != pvch.channel.id:  # In someone else's private channel
            await ctx.response.send_message(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), ephemeral=True)
            return
        
        view: DeletePrivateChannel = DeletePrivateChannel(pvch)
        await ctx.response.send_message(embed=warning_embed_template("本当にこのプライベートチャンネルを削除しますか？"), view=view, ephemeral=True)

    @app_commands.command(name="pvch_invite", description="自分のプライベートチャンネルにユーザーを招待する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    async def pvch_invite(self, ctx: discord.Interaction):
        """Invite user to private channel"""
        if ctx.channel.category_id == CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネル内では実行できません。"), ephemeral=True)
            return
        
        pvch: Optional[PrivateChannel] = used_pvch_userid.get(ctx.user.id)
        if pvch is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `/pvch_create`で作成することができます。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        view: InviteUserSelect = InviteUserSelect(pvch)
        await ctx.response.send_message(embed=invite_embed_template("招待するユーザーを指定してください。"), view=view, ephemeral=True)

    @app_commands.command(name="pvch_leave", description="他者のプライベートチャンネルを離脱する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    async def pvch_leave(self, ctx: discord.Interaction):
        """Leave private channel"""
        if ctx.channel.category_id != CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでのみ使用できます。"), ephemeral=True)
            return

        pvch: Optional[PrivateChannel] = used_pvch_userid.get(ctx.user.id)
        if pvch is not None and ctx.channel.id == pvch.channel.id:
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
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    async def pvch_kick(self, ctx: discord.Interaction):
        """Kick private channel"""
        if ctx.channel.category_id != CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでのみ使用できます。"), ephemeral=True)
            return

        pvch: Optional[PrivateChannel] = used_pvch_userid.get(ctx.user.id)
        if pvch is None or ctx.channel.id != pvch.channel.id:  # In someone else's private channel
            await ctx.response.send_message(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), ephemeral=True)
            return

        view: KickUserSelect = KickUserSelect(pvch)
        await ctx.response.send_message(embed=kick_embed_template("追放するユーザーを指定してください。"), view=view, ephemeral=True)

    @app_commands.command(name="pvch_extend", description=f"自分のプライベートチャンネルの有効期限を最大{EXTEND_TTL_HOUR}時間延長する")
    @app_commands.checks.cooldown(1, 180.0, key=lambda i: (i.guild_id, i.user.id))
    async def pvch_extend(self, ctx: discord.Interaction):
        """Extend private channel"""
        pvch: Optional[PrivateChannel] = used_pvch_userid.get(ctx.user.id)
        if pvch is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `/pvch_create`で作成することができます。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        if ctx.channel.category_id == CATEGORY_ID and ctx.channel.id != pvch.channel.id:  # In someone else's private channel
            await ctx.response.send_message(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), ephemeral=True)
            return

        extended: bool = await pvch.extension_exp(ctx)
        if extended:
            self.sort_used_pvch_userid()

    @app_commands.command(name="pvch_admin_delete", description="[権限者専用] プライベートチャンネルの削除")
    @app_commands.checks.cooldown(3, 10.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.default_permissions(administrator=True)
    async def pvch_admin_delete(self, ctx: discord.Interaction, pv_user: discord.User):
        """[Admin only] Delete private channel"""
        pvch: PrivateChannel = used_pvch_userid.get(pv_user.id)
        if pvch is None:
            msg: str = f"指定した{pv_user.mention}のプライベートチャンネルが見つかりませんでした。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        view: DeletePrivateChannel = DeletePrivateChannel(pvch, admin=True)
        await ctx.response.send_message(embed=warning_embed_template(f"本当に{pvch.channel.mention}を削除しますか？"), view=view, ephemeral=True)

    @app_commands.command(name="pvch_admin_kick", description="[権限者専用] プライベートチャンネルからユーザーを追放")
    @app_commands.checks.cooldown(3, 10.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.default_permissions(administrator=True)
    async def pvch_admin_kick(self, ctx: discord.Interaction, private_channel: discord.TextChannel, pv_user: discord.User):
        """[Admin only] Kick private channel"""
        if private_channel.category_id != CATEGORY_ID:
            msg: str = f"指定した{private_channel.mention}はプライベートチャンネルではありません。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        if pv_user.bot:
            msg: str = f"指定した{pv_user.mention}はこのボットです。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        pvch: int = used_pvch_userid.get(pv_user.id)
        if pvch is not None and private_channel.id == pvch.channel.id:
            msg: str = f"指定した{pv_user.mention}はこのプライベートチャンネルの作成者です。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        try:
            await private_channel.set_permissions(pv_user, overwrite=None)
            await ctx.response.send_message(embed=kick_embed_template("成功"), ephemeral=True)
        except discord.HTTPException:
            await ctx.response.send_message(embed=kick_embed_template("失敗"), ephemeral=True)

    def sort_used_pvch_userid(self):
        """Sort the user's private channel list"""
        used_pvch_userid: dict[int, PrivateChannel] = dict(sorted(used_pvch_userid.items(), key=lambda item: item[1].exp))

    @tasks.loop(minutes=1)
    async def check_pv_exp(self):
        """Check private channel expiration date"""
        delete_pvchs: list[PrivateChannel] = []
        for user_id, pvch in used_pvch_userid.items():
            if await pvch.is_expired():
                delete_pvchs.append(user_id)
            else:
                break

        # Automatic deletion
        if len(delete_pvchs) > 0:
            for user_id in delete_pvchs:
                pvch: PrivateChannel = used_pvch_userid[user_id]
                await pvch.force_delete()


def setup(bot: commands.Bot):
    return bot.add_cog(PrivateChannelBot(bot))
