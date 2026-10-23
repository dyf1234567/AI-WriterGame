"""Shared canon and live character context for scene and phone generation.

Keep channel formatting in prompts.py. Never give a phone character the DM's
unfiltered story, secret ledger or other people's private conversations.
"""
from . import narrative
from .models import affinity_stage, ensure_boundaries, is_romanceable
from .relationships import CONFIRM_AFFINITY_GATE, MODES, STATUS_LABELS


GAME_TITLE = "都市人生·心动系统"

WORLD_RULES = """这是同一个持续的现代都市世界：华夏、东瀛、法兰西、星联、南洋、北境六国，多座城市可旅行。现实钱币叫华夏币，系统货币叫系统积分，两者不能混用。
人物正典：梁雅婷是报到时初识的同班好友，非发小；郭瑞莹是魔都音乐学院的青梅；邓碧瑶是在魔都网聊两年、未线下见面的游戏网友，非邻居或插画师。后续见面、身份与居所变化服从已确认记录，不重复初遇；GM已改写的人设按当前档案演绎。
人物边界（重要）：所有角色均为成年人（大学生、职场人士等）。本作按成人尺度叙事：心动、暧昧、吃醋与亲密情节都可直接描写，身体与感官细节不必留白；亲密情节以双方愿意为前提，不写涉及未成年人的内容。"""

RELATIONSHIP_RULES = f"""关系有阶段：初识/熟识保持礼貌距离，朋友可以熟络，亲近可以关心和打趣；心动（好感≥{CONFIRM_AFFINITY_GATE}）才写明显暧昧；好感满100「羁绊」则全心依恋主角，百依百顺、有求必应，几乎不会拒绝主角的请求——表达方式仍保留各自性格（嘴硬的嘴硬心软、直球的黏人），但心意与行动都以主角为先。高好感不自动成为恋人；正式关系以relationship.status为准，partner/distance才是已确认恋人，分手后不沿用恋人称呼。标签、旧文与假设范例不能覆盖正式状态；已确认恋人不因好感临时降低就被重写成陌生人。
确立恋爱以好感≥{CONFIRM_AFFINITY_GATE}为条件，专一/开放/多人由玩家直接选择，不需要逐人协商；不能仅凭NPC回复替玩家确立、复合或变更模式。角色各有意愿和边界，家人不进入恋爱线。带【主持人已改写人设】指令时，新人设的表达与主动意愿优先于默认铺垫节奏，正式关系仍由已结算状态决定。"""

MEMORY_RULES = """人物、关系与记忆跨正文和手机共享：换成短信不会重置性格、称呼、距离或共同经历，也不因回到现场就忘记刚才的交流。两种渠道只改变表达形式，不另造一套人物。
当前档案与已确认事实优先；带来源的原文用于核对，摘要只是派生索引，角色卡示例不是事实。分清谁说过、谁答应、仅提议、已发生和已取消；不确定旧事就不补编。GM修改的是当前人设，不是凭空新增共同经历。
主持人知道不等于角色知道：NPC只可谈公共事实、亲历或明确被告知的内容，不读取他人私聊、主角心声、系统秘密或幕后设定；名字被提到不代表在场知情。没见面的角色只通过实际通信出现。"""


def shared_rules_block() -> str:
    return (f"【共同世界与人物规则·《{GAME_TITLE}》】\n{WORLD_RULES}\n"
            f"{RELATIONSHIP_RULES}\n{MEMORY_RULES}")


def relationship_line(npc: dict) -> str:
    """Read the canonical state without repairing/mutating the save in a prompt."""
    rel = npc.get("relationship") or {}
    status = rel.get("status")
    if status not in STATUS_LABELS:
        # Legacy labels are fallback only; a stale label cannot override friend/breakup.
        status = next((key for key, label in STATUS_LABELS.items()
                       if label == npc.get("relationship_status")), "friend")
    label = STATUS_LABELS[status]
    mode = MODES.get(rel.get("mode"), MODES["exclusive"])
    if not is_romanceable(npc):
        return "正式关系：家人，不进入恋爱线"
    if status in ("partner", "distance"):
        return f"正式关系：{label}（{status}）；相处模式：{mode}"
    return f"正式关系：{label}（{status}），尚无已确认恋爱关系"


def character_block(npc: dict, *, details: bool = True) -> str:
    """The same live identity, relationship and voice in either writing channel."""
    affinity = int(npc.get("affinity", 0))
    text = (f"{npc['name']}（{npc.get('role', '')}，常在：{npc.get('place') or '行踪不定'}）："
            f"人设（仅主持人/角色本人可知，不等于已向主角公开）：{str(npc.get('persona') or npc.get('role', ''))[:170]}。"
            + (f"【{npc['persona_directive']}】" if npc.get("persona_directive") else "")
            + f"好感{affinity}·「{affinity_stage(affinity)}」，关系标签「{npc.get('label', '')}」；"
            + ("【羁绊·百依百顺】好感已满：TA 对主角全心依恋、有求必应，几乎不会拒绝主角的请求，主动顺从；表达方式保留各自性格。" if affinity >= 100 else "")
            + relationship_line(npc) + "。")
    if details:
        boundaries = ensure_boundaries(npc)
        text += (f"相处原则：{boundaries['principles']}；边界：{boundaries['boundary']}；"
                 f"恋爱观：{boundaries['romance_style']}。声口：{narrative.voice_hint(npc)}")
    return text
