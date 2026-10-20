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
    npc_events: list[str] = Field(default_factory=list, max_length=20)
    new_npc: list[dict] = Field(default_factory=list, max_length=16)
    new_places: list[dict] = Field(default_factory=list, max_length=16)
    new_side_quest: dict | None = None
    identity_update: dict | None = None
    technique_grant: dict | None = None
    location: dict | None = None
    quest_progress: str | None = None
    quest_complete: str | list[str] | None = None
    date_with: str | None = None
    time_cost: int = Field(default=0, ge=0, le=3)
    power_progress: int = Field(default=0, ge=0, le=15)
    hook_done: str | None = None
    fact_record: str | list[str] | None = None
    fact_resolved: str | list[str] | None = None
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
    affinity_changes: list[AffinityChange] = Field(default_factory=list, max_length=30)
    npc_events: list[str] = Field(default_factory=list, max_length=20)


class ChatResult(BaseModel):
    """手机短信回复的最小契约。image＝随信附图的标题（如「琴房刚拍的一张」），可为空。"""
    model_config = ConfigDict(strict=True)
    reply: str = Field(min_length=1, max_length=600)
    image: str = Field(default="", max_length=40)
