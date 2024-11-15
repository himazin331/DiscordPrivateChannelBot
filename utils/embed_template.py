from discord import Embed

from typing import Optional

from settings import GUILD_NAME, INACTIVE_DAYS, INACTIVE_SB_DAYS, DOCS_URL


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

def welcome_embed_template() -> Embed:
    msg: str = f"""
このチャンネルはあなたとあなたが招待した方のみ閲覧できます。(ただし、権限者は閲覧可)\n
チャンネルは**非アクティブ期間が{INACTIVE_DAYS}日間を超えると自動的に削除**されます。
※チャンネル作成者がServer Boosterである場合、非アクティブ期間が{INACTIVE_SB_DAYS}日間を超えると削除されます。
手動でチャンネルを削除したい場合は`/pvch_delete`を実行してください。\n
"""
    embed: Embed = Embed(title="ようこそ！ここはプライベートチャンネルです！", description=msg, color=0x3498db)
    embed.add_field(name="注意", value=f"プライベートチャンネル内で発生した抗争やトラブルなどに関して、{GUILD_NAME}運営は関与せず、責任を負いません。", inline=False)
    embed.add_field(name="ヒント", value=f"PrivateChannelBotのコマンドヘルプは`/pvch_help`で確認できます。\n詳細な説明については、[こちら]({DOCS_URL})をご参照ください。", inline=False)
    return embed