"""只校验模型边界；存档结算不接受结构损坏的回合。"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Item(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str = Field(min_length=1, max_length=80)
    desc: str = ""
    # 允许 0：模型常给"无花费"占位条目（count=0），校验放过、结算时丢弃，
    # 不能为它拒掉整个回合（曾致跨城/消费类行动 60% 整回合失败）
    count: int = Field(default=1, ge=0, le=9999)
    reason: str = ""


class AffinityChange(BaseModel):
    model_config = ConfigDict(strict=True)
    npc: str
    delta: int = Field(default=0, ge=-100, le=100)
    reason: str = ""


class Updates(BaseModel):
    model_config = ConfigDict(strict=True)
    realm_progress_delta: int = Field(default=0, ge=-100, le=100)
    realm_breakthrough: bool = False
    item_gained: list[Item] = Field(default_factory=list, max_length=30)
    item_spent: list[Item] = Field(default_factory=list, max_length=30)
    affinity_changes: list[AffinityChange] = Field(default_factory=list, max_length=30)
    # NPC 生活状态：goal/status/mood/next，只对已知人物生效
    npc_life: list[dict] = Field(default_factory=list, max_length=8)
    npc_events: list[str] = Field(default_factory=list, max_length=20)
    new_npc: list[dict] = Field(default_factory=list, max_length=16)
    new_places: list[dict] = Field(default_factory=list, max_length=16)
    new_side_quest: dict | None = None
    identity_update: dict | None = None
    technique_grant: dict | None = None
    location: dict | None = None
    quest_progress: str | None = None
    quest_complete: str | list[str] | None = None
    # 玩家自定义目标的推进：[{"id":"goal_x","delta":1-25,"note":"..."}]
    goal_progress: list[dict] = Field(default_factory=list, max_length=6)
    date_with: str | None = None
    scene_npcs: list[str] = Field(default_factory=list, max_length=16)
    # 分钟计时；大跨度只在玩家主动的结构化日程中允许。
    duration_minutes: int = Field(default=0, ge=0, le=1576800)
    fact_records: list[dict] = Field(default_factory=list, max_length=12)
    action_request: dict | None = None
    time_cost: int = Field(default=0, ge=0, le=3)
    power_progress: int = Field(default=0, ge=0, le=15)
    # 技能练习申报：[{"skill": id, "xp": 1-25, "reason": "..."}]，引擎钳 ≤2 项/回合
    skill_progress: list[dict] = Field(default_factory=list, max_length=4)
    hook_done: str | None = None
    fact_record: str | list[str] | None = None
    fact_resolved: str | list[str] | None = None
    # 知情变化：[{"npc":"姓名","fact":"账本原文片段","learned":true}]
    knowledge: list[dict] = Field(default_factory=list, max_length=12)
    npc_reveals: list[dict] = Field(default_factory=list, max_length=16)


class TurnResult(BaseModel):
    model_config = ConfigDict(strict=True)
    story_text: str = Field(min_length=1, max_length=6000)
    narration_world: Literal["urban"]
    choices: list[str] = Field(min_length=2, max_length=6)
    state_updates: Updates = Field(default_factory=Updates)
    system_notice: str = Field(default="", max_length=1500)


def validate_turn(data: dict) -> dict:
    return TurnResult.model_validate(data).model_dump()


class OfflineResult(BaseModel):
    model_config = ConfigDict(strict=True)
    events: list[dict] = Field(default_factory=list, max_length=10)
    messages: list[dict] = Field(default_factory=list, max_length=10)
    moments: list[dict] = Field(default_factory=list, max_length=4)
    npc_life: list[dict] = Field(default_factory=list, max_length=8)
    knowledge: list[dict] = Field(default_factory=list, max_length=12)
    npc_events: list[str] = Field(default_factory=list, max_length=20)


class ChatResult(BaseModel):
    """短信回复与可选记忆建议；约定是否成立由玩家原话与结算规则决定。"""
    model_config = ConfigDict(strict=True)
    reply: str = Field(min_length=1, max_length=600)
    image: str = Field(default="", max_length=40)
    video: str = Field(default="", max_length=40)
    sticker: str = Field(default="", max_length=80)
    memory: str = Field(default="", max_length=240)
    fact_record: str | None = Field(default=None, max_length=160)
    appointment: str | None = Field(default=None, max_length=160)
