"""阶段2最小持久层：SQLite 周目/分支/实体/事件/回合（协议见 content/protocols.md）。

不接管现有引擎（P2-08：整个周目选引擎）；本包仅供新引擎与测试使用。
"""

from .db import connect, migrate, MIGRATIONS
from .repo import CampaignRepo

__all__ = ["connect", "migrate", "MIGRATIONS", "CampaignRepo"]
