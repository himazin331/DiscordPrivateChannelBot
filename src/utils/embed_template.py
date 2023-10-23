from discord import Embed

def success_embed_template(message: str) -> Embed:
  embed: Embed = Embed(title="成功", description=message, color=0x00ff00)
  return embed

def error_embed_template(message: str) -> Embed:
  embed: Embed = Embed(title="問題が発生しました", description=message, color=0xff0000)
  return embed

def info_embed_template(message: str) -> Embed:
  embed: Embed = Embed(title="情報", description=message, color=0x3498db)
  return embed