from discord import Embed

from typing import Optional

from settings import GUILD_NAME, CHANNEL_TTL_HOUR


def success_embed_template(message: str) -> Embed:
    embed: Embed = Embed(title="成功", description=message, color=0x00ff00)
    return embed

def error_embed_template(message: str) -> Embed:
    embed: Embed = Embed(title="問題が発生しました", description=message, color=0xff0000)
    return embed

def warning_embed_template(message: str) -> Embed:
    embed: Embed = Embed(title="警告", description=message, color=0xed4245)
    return embed

def info_embed_template(message: str) -> Embed:
    embed: Embed = Embed(title="情報", description=message, color=0x3498db)
    return embed

def invite_embed_template(message: Optional[str] = None) -> Embed:
    embed: Embed = Embed(title="プライベートチャンネル招待", description=message, color=0x9b59b6)
    return embed

def kick_embed_template(message: Optional[str] = None) -> Embed:
    embed: Embed = Embed(title="プライベートチャンネル追放", description=message, color=0xf1c40f)
    return embed

def welcome_embed_template(exp: str) -> Embed:
    msg: str = f"""
このチャンネルはあなたとあなたが招待した方のみ閲覧できます。(ただし、権限者は閲覧可)\n
チャンネルは**作成から{CHANNEL_TTL_HOUR}時間経過すると自動的に削除**されます。`/pvch_delete`で手動で削除することもできます。\n
"""
    embed: Embed = Embed(title="ようこそ！ここはプライベートチャンネルです！", description=msg, color=0x3498db)
    embed.add_field(name="注意", value=f"プライベートチャンネルにおいても{GUILD_NAME} Discordサーバー利用におけるガイドラインは適用されます。", inline=False)
    embed.add_field(name="チャンネル有効期限", value=f"`{exp}`", inline=False)
    return embed