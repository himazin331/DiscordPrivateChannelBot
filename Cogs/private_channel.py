import discord
from discord import app_commands, Guild, CategoryChannel, TextChannel, VoiceChannel, Embed
from discord.ext import commands, tasks
import asyncio

from datetime import datetime, timezone, timedelta
from loguru import logger
from typing import Optional

from ui.interaction_ui import *
from utils.embed_template import *
from utils.rw_pvch_data import PvchDataCsv

from settings import *

pvch_data_csv: PvchDataCsv = PvchDataCsv()

class PrivateChannel:
    def __init__(self, user_id: int, txt_channel: TextChannel, vc_channel: VoiceChannel):
        self.user_id: int = user_id
        self.txt_channel: TextChannel = txt_channel
        self.vc_channel: VoiceChannel = vc_channel

    def __str__(self) -> str:
        return f"PrivateChannel(user_id={self.user_id}, text_channel={self.txt_channel}, voice_channel={self.vc_channel})"

    async def send_welcome_message(self):
        """Send a Welcome message to the private channel you created"""
        try:
            sent_message = await self.txt_channel.send(embed=welcome_embed_template())
            await sent_message.pin()
        except discord.HTTPException:
            logger.error("Failed to send message to private channel.")

    async def delete_channel(self, ctx: discord.Interaction):
        """Delete private channel"""
        try:
            if ctx.channel.id == self.txt_channel.id:  # In my private channel
                await self.txt_channel.send(embed=info_embed_template(f"約5秒後に、プライベートチャンネルを削除します。"))

                await asyncio.sleep(5.0)
                await self.txt_channel.delete()
                await self.vc_channel.delete()
            else: # In public channel
                await self.txt_channel.delete()
                await self.vc_channel.delete()
                await ctx.followup.send(embed=success_embed_template("あなたのプライベートチャンネルを削除しました。"), ephemeral=True)
            del pvch_data[self.user_id]
            pvch_data_csv.update(pvch_data)
        except (discord.NotFound, discord.HTTPException):
            logger.error("Failed to delete private channel.")
            await ctx.followup.send(embed=error_embed_template("プライベートチャンネルの削除に失敗しました。"), ephemeral=True)

    async def force_delete(self):
        """Forced deletion (automatic deletion or deletion by authority)"""
        try:
            await self.txt_channel.delete()
            await self.vc_channel.delete()
            del pvch_data[self.user_id]
            pvch_data_csv.update(pvch_data)
        except (discord.NotFound, discord.HTTPException):
            logger.error("Failed to delete private channel.")

    async def invite_user(self, users: list[discord.Member]) -> Embed:
        """User Invitation"""
        success_users: list[str] = []
        failed_users: list[str] = []
        ignore_users: list[str] = []

        for user in users:
            if user.top_role.id in [MODERATOR_ROLE_ID, OWNER_ROLE_ID] or user.id == self.user_id or user.bot:
                ignore_users.append(user.name)
                continue

            try:
                await self.txt_channel.set_permissions(user, view_channel=True)
                await self.vc_channel.set_permissions(user, view_channel=True)
                success_users.append(user.display_name)
            except discord.HTTPException:
                failed_users.append(user.display_name)

        embed: Embed = invite_embed_template()
        if len(success_users) > 0:
            embed.add_field(name="成功", value="- "+"\n- ".join(filter(None, success_users)), inline=False)
        if len(failed_users) > 0:
            embed.add_field(name="失敗", value="- "+"\n- ".join(filter(None, failed_users)), inline=False)
        if len(ignore_users) > 0:
            embed.add_field(name="無効", value="- "+"\n- ".join(filter(None, ignore_users)), inline=False)
        await self.txt_channel.send(embed=embed)

    async def kick_user(self, users: list[discord.Member]) -> Embed:
        """User Kick"""
        success_users: list[str] = []
        failed_users: list[str] = []
        ignore_users: list[str] = []

        for user in users:
            if user.top_role.id in [MODERATOR_ROLE_ID, OWNER_ROLE_ID] or user.id == self.user_id or user.bot:
                ignore_users.append(user.name)
                continue

            try:
                await self.txt_channel.set_permissions(user, overwrite=None)
                await self.vc_channel.set_permissions(user, view_channel=False)
                success_users.append(user.display_name)
            except discord.HTTPException:
                failed_users.append(user.display_name)

        embed: Embed = kick_embed_template()
        if len(success_users) > 0:
            embed.add_field(name="成功", value="- "+"\n- ".join(filter(None, success_users)), inline=False)
        if len(failed_users) > 0:
            embed.add_field(name="失敗", value="- "+"\n- ".join(filter(None, failed_users)), inline=False)
        if len(ignore_users) > 0:
            embed.add_field(name="無効", value="- "+"\n- ".join(filter(None, ignore_users)), inline=False)
        await self.txt_channel.send(embed=embed)

    async def is_expired(self, inactive: int) -> bool:
        """Check if private channel is expired"""
        last_active_datetime: datetime = self.txt_channel.created_at.astimezone(timezone(timedelta(hours=9)))
        last_msg: discord.Message = [message async for message in self.txt_channel.history(limit=1)]
        if len(last_msg) > 0:
            last_active_datetime = last_msg[0].created_at
        last_active_datetime = last_active_datetime.astimezone(timezone(timedelta(hours=9)))
        now: datetime = datetime.now().astimezone(timezone(timedelta(hours=9)))

        exp: datetime = last_active_datetime + timedelta(days=inactive)
        if exp <= now:
            return True
        return False


pvch_data: dict[int, PrivateChannel] = {}  # {user_id: PrivateChannel}

class PrivateChannelBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Login successful.")
        self.guild: Guild = self.bot.get_guild(GUILD_ID)
        self.category: CategoryChannel = self.guild.get_channel(CATEGORY_ID)
        await self.bot.tree.sync(guild=discord.Object(GUILD_ID))

        # PrivateChannel CSV read
        global pvch_data
        try:
            pvch_data = pvch_data_csv.read(self.category)
        except FileNotFoundError:
            pass

        self.check_pv_exp.start()
        await self.bot.change_presence(activity=discord.Game("running..."))

    async def cog_app_command_error(self, ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):  # Cooldown error message
            await ctx.response.send_message(f"クールダウン中...\n`{str(error)}`", ephemeral=True)

    @app_commands.command(name="pvch_help_test", description="ヘルプを表示する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.guilds(GUILD_ID)
    async def pvch_help(self, ctx: discord.Interaction):
        """Display command help"""
        embed: Embed = Embed(title="コマンドヘルプ", color=0x979c9f)
        for cmd in self.bot.tree.walk_commands(guild=self.guild):
            embed.add_field(name=f"`/{cmd.name}`", value=cmd.description, inline=False)
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pvch_info_test", description="プライベートチャンネル情報を表示する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.guilds(GUILD_ID)
    async def pvch_info(self, ctx: discord.Interaction):
        """Private channel information display"""
        if ctx.channel.category_id != CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでのみ使用できます。"), ephemeral=True)
            return

        pvch: PrivateChannel = None
        for p in pvch_data.values():
            if p.txt_channel.id == ctx.channel.id:
                pvch = p
                break
        user: discord.Member = self.guild.get_member(pvch.user_id)

        embed: Embed = Embed(title="プライベートチャンネル情報", color=0x979c9f)
        embed.add_field(name="チャンネル名", value=pvch.txt_channel.name, inline=False)
        embed.add_field(name="チャンネル作成者", value=user.display_name, inline=False)

        online_value: str = ""
        offline_value: str = ""
        for member in pvch.txt_channel.members:
            if not member.bot and member.top_role.id not in [OWNER_ROLE_ID, MODERATOR_ROLE_ID]:
                if member.status is discord.Status.offline:
                    offline_value += f"- {member.display_name}\n"
                else:
                    online_value += f"- {member.display_name}\n"

        if online_value != "":
            embed.add_field(name="オンライン", value=online_value)
        if offline_value != "":
            embed.add_field(name="オフライン", value=offline_value)
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pvch_create_test", description="自分のプライベートチャンネルを作成する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.guilds(GUILD_ID)
    async def pvch_create(self, ctx: discord.Interaction):
        """Create private channel"""
        if ctx.channel.category_id == CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでは実行できません。"), ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)
        user_id: int = ctx.user.id
        # Check if private channels already exists.
        if (pvch := pvch_data.get(user_id)) is not None:
            if self.guild.get_channel(pvch.txt_channel.id) is not None:
                msg: str = f"あなたのプライベートチャンネル{pvch.txt_channel.mention}は既に存在します。\n\nヒント: `/pvch_delete`でプライベートチャンネルを削除することができます。"
                await ctx.followup.send(embed=error_embed_template(msg), ephemeral=True)
                return
            else:
                del pvch_data[user_id]

        # Create private channel
        ch_name: str = f"pvch-{ctx.user.name}"
        try:
            txt_channel: TextChannel = await self.category.create_text_channel(name=ch_name)
            await txt_channel.set_permissions(ctx.user, overwrite=discord.PermissionOverwrite(view_channel=True))
            vc_channel: VoiceChannel = await self.category.create_voice_channel(name=ch_name)
            await vc_channel.set_permissions(ctx.user, overwrite=discord.PermissionOverwrite(view_channel=True))
        except discord.HTTPException:
            logger.error("Failed to create private channel.")
            await ctx.followup.send(embed=error_embed_template("プライベートチャンネルの作成に失敗しました。"), ephemeral=True)
            return

        pvch: PrivateChannel = PrivateChannel(user_id, txt_channel, vc_channel)
        pvch_data[user_id] = pvch
        pvch_data_csv.write(pvch)
        await pvch.send_welcome_message()

        # Creating a User Invitation Component
        msg: str = f"{txt_channel.mention}を作成しました。\n\nユーザーの招待は下のリストからできます(最大25人まで)"
        view: InviteUserSelect = InviteUserSelect(pvch)
        await ctx.followup.send(embed=success_embed_template(msg), view=view, ephemeral=True)

    @app_commands.command(name="pvch_delete_test", description="自分のプライベートチャンネルを削除する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.guilds(GUILD_ID)
    async def pvch_delete(self, ctx: discord.Interaction):
        """Delete private channel"""
        pvch: Optional[PrivateChannel] = pvch_data.get(ctx.user.id)
        if pvch is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `/pvch_create`で作成することができます。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        if ctx.channel.category_id == CATEGORY_ID and ctx.channel.id != pvch.txt_channel.id:  # In someone else's private channel
            await ctx.response.send_message(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), ephemeral=True)
            return
        
        view: DeletePrivateChannel = DeletePrivateChannel(pvch)
        await ctx.response.send_message(embed=warning_embed_template("本当にこのプライベートチャンネルを削除しますか？"), view=view, ephemeral=True)

    @app_commands.command(name="pvch_invite_test", description="自分のプライベートチャンネルにユーザーを招待する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.guilds(GUILD_ID)
    async def pvch_invite(self, ctx: discord.Interaction):
        """Invite user to private channel"""
        if ctx.channel.category_id == CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネル内では実行できません。"), ephemeral=True)
            return
        
        pvch: Optional[PrivateChannel] = pvch_data.get(ctx.user.id)
        if pvch is None:
            msg: str = "あなたはまだプライベートチャンネルを作成していないようです。\n\nヒント: `/pvch_create`で作成することができます。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        view: InviteUserSelect = InviteUserSelect(pvch)
        await ctx.response.send_message(embed=invite_embed_template("招待するユーザーを指定してください。"), view=view, ephemeral=True)

    @app_commands.command(name="pvch_leave_test", description="他者のプライベートチャンネルを離脱する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.guilds(GUILD_ID)
    async def pvch_leave(self, ctx: discord.Interaction):
        """Leave private channel"""
        if ctx.channel.category_id != CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでのみ使用できます。"), ephemeral=True)
            return

        await ctx.response.defer()
        pvch: Optional[PrivateChannel] = pvch_data.get(ctx.user.id)
        if pvch is not None and ctx.channel.id == pvch.txt_channel.id:
            await ctx.followup.send(embed=error_embed_template("このコマンドはこのプライベートチャンネルの作成者は実行できません。\n\nヒント: `/pvch_delete`で削除することができます。"),
                                            ephemeral=True)
            return

        for p in pvch_data.values():
            if p.txt_channel.id == ctx.channel.id:
                pvch = p
                break

        try:
            await pvch.txt_channel.set_permissions(ctx.user, overwrite=None)
            await pvch.vc_channel.set_permissions(ctx.user, view_channel=False)
            await ctx.followup.send(embed=info_embed_template(f"{ctx.user.display_name}さんがプライベートチャンネルを退出しました。"))
        except discord.HTTPException:
            logger.error("Failed to leave private channel.")
            await ctx.followup.send(embed=error_embed_template("プライベートチャンネルの退出に失敗しました。"), ephemeral=True)

    @app_commands.command(name="pvch_kick_test", description="自分のプライベートチャンネルからユーザーを追放する")
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.guilds(GUILD_ID)
    async def pvch_kick(self, ctx: discord.Interaction):
        """Kick private channel"""
        if ctx.channel.category_id != CATEGORY_ID:
            await ctx.response.send_message(embed=error_embed_template("このコマンドはプライベートチャンネルでのみ使用できます。"), ephemeral=True)
            return

        pvch: Optional[PrivateChannel] = pvch_data.get(ctx.user.id)
        if pvch is None or ctx.channel.id != pvch.txt_channel.id:  # In someone else's private channel
            await ctx.response.send_message(embed=error_embed_template("このコマンドは他人のプライベートチャンネル内では実行できません。"), ephemeral=True)
            return

        view: KickUserSelect = KickUserSelect(pvch)
        await ctx.response.send_message(embed=kick_embed_template("追放するユーザーを指定してください。"), view=view, ephemeral=True)

    @app_commands.command(name="pvch_admin_delete_test", description="[権限者専用] プライベートチャンネルの削除")
    @app_commands.checks.cooldown(3, 10.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.default_permissions(administrator=True)
    @app_commands.guilds(GUILD_ID)
    async def pvch_admin_delete(self, ctx: discord.Interaction, pv_user: discord.User):
        """[Admin only] Delete private channel"""
        pvch: PrivateChannel = pvch_data.get(pv_user.id)
        if pvch is None:
            msg: str = f"指定した{pv_user.mention}のプライベートチャンネルが見つかりませんでした。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        view: DeletePrivateChannel = DeletePrivateChannel(pvch, admin=True)
        await ctx.response.send_message(embed=warning_embed_template(f"本当に{pvch.txt_channel.mention}を削除しますか？"), view=view, ephemeral=True)

    @app_commands.command(name="pvch_admin_kick_test", description="[権限者専用] プライベートチャンネルからユーザーを追放")
    @app_commands.checks.cooldown(3, 10.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.default_permissions(administrator=True)
    @app_commands.guilds(GUILD_ID)
    async def pvch_admin_kick(self, ctx: discord.Interaction, pv_user: discord.User, kick_user: discord.User):
        """[Admin only] Kick private channel"""
        if pv_user.id == kick_user.id:
            msg: str = "プライベートチャンネルの作成者は追放できません。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        if kick_user.bot:
            msg: str = f"指定した{kick_user.mention}はボットです。"
            await ctx.response.send_message(embed=error_embed_template(msg), ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)
        pvch: PrivateChannel = pvch_data.get(pv_user.id)
        if pvch is None:
            msg: str = f"指定した{pv_user.mention}のプライベートチャンネルが見つかりませんでした。"
            await ctx.followup.send(embed=error_embed_template(msg), ephemeral=True)
            return

        try:
            await pvch.txt_channel.set_permissions(kick_user, overwrite=None)
            await pvch.vc_channel.set_permissions(kick_user, view_channel=False)
            await ctx.followup.send(embed=kick_embed_template("成功"), ephemeral=True)
        except discord.HTTPException:
            await ctx.followup.send(embed=kick_embed_template("失敗"), ephemeral=True)

    @tasks.loop(hours=24)
    async def check_pv_exp(self):
        """Check private channel expiration date"""
        delete_pvchs: list[int] = []

        inactive: int = INACTIVE_DAYS
        for user_id, pvch in pvch_data.items():
            for sb in self.guild.premium_subscribers:
                if user_id == sb.id:
                    inactive = INACTIVE_SB_DAYS
                    break

            if await pvch.is_expired(inactive):
                delete_pvchs.append(user_id)

        # Automatic deletion
        if len(delete_pvchs) > 0:
            for user_id in delete_pvchs:
                pvch: PrivateChannel = pvch_data[user_id]
                await pvch.force_delete()


def setup(bot: commands.Bot):
    return bot.add_cog(PrivateChannelBot(bot))
