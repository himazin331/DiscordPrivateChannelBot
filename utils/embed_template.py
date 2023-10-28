from discord import Embed

from typing import Optional

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