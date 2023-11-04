from __future__ import annotations
from discord import CategoryChannel, TextChannel, VoiceChannel

import csv

from Cogs import private_channel

from settings import PVCH_DATA_FILE_PATH

class PvchDataCsv:
    def __init__(self):
        self.category: CategoryChannel = None

    def write(self, pvch: 'private_channel.PrivateChannel'):
        """Write private channel data to csv file"""
        row: str = f"{pvch.user_id},{pvch.txt_channel.id},{pvch.vc_channel.id}\n"
        with open(PVCH_DATA_FILE_PATH, "a") as f:
            f.write(row)

    def read(self, category: CategoryChannel) -> dict[int, 'private_channel.PrivateChannel']:
        """Read private channel data from csv file"""
        self.category = category
        raw_data: list[str] = []
        with open(PVCH_DATA_FILE_PATH, "r") as f:
            reader = csv.reader(f)
            raw_data = list(reader)
        return self._parse(raw_data)

    def update(self, pvch_data: dict[int, 'private_channel.PrivateChannel']):
        """Update(Delete) private channel data in csv file"""
        with open(PVCH_DATA_FILE_PATH, "w") as f:
            for pvch in pvch_data.values():
                row: str = f"{pvch.user_id},{pvch.txt_channel.id},{pvch.vc_channel.id}\n"
                f.write(row)

    def _parse(self, raw_data: list[str]) -> dict[int, 'private_channel.PrivateChannel']:
        """Parse CSV raw data into praivate channel data"""
        pvch_data: dict[int, 'private_channel.PrivateChannel'] = {}
        for data in raw_data:
            user_id, txt_ch_id, vc_ch_id = [int(d) for d in data]

            txt_ch: TextChannel = None
            for ch in self.category.text_channels:
                if ch.id == txt_ch_id:
                    txt_ch = ch
                    break

            vc_ch: VoiceChannel = None
            for ch in self.category.voice_channels:
                if ch.id == vc_ch_id:
                    vc_ch = ch
                    break
            if txt_ch is not None and vc_ch is not None:
                pvch_data[user_id] = private_channel.PrivateChannel(user_id, txt_ch, vc_ch)
        return pvch_data