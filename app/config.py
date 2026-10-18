"""全局配置：路径、.env 加载、模型接入状态。"""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
ENV_FILE = ROOT / ".env"


def _load_env_file() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


def _data_dir() -> pathlib.Path:
    """数据目录，可用 SJL_DATA_DIR 改道。

    默认所有实例共用一个 data/，而冒烟测试第一步就是 /api/new——
    并行起第二个服务会把正式存档直接覆盖掉，所以必须能整体改道。
    """
    raw = os.environ.get("SJL_DATA_DIR", "").strip()
    return pathlib.Path(raw).resolve() if raw else ROOT / "data"


DATA_DIR = _data_dir()
STATE_FILE = DATA_DIR / "state.json"
# 记忆手册：每次存档后自动导出的人可读记忆文档
MEMORY_MANUAL_FILE = DATA_DIR / "memory" / "记忆手册.md"
# 手册导出的成败记录：导出是旁路功能，失败只该让手册停在旧版，但必须留下可查的痕迹
MEMORY_STATUS_FILE = DATA_DIR / "memory" / "_导出状态.json"
# 移出状态窗口的旧剧情正文追加到这里，压缩失败也不允许静默销毁
STORY_ARCHIVE_FILE = DATA_DIR / "story_archive.jsonl"
# 被名册淘汰的生成人物档案落在这里；同名人物再次登场时恢复旧档（好感/行事录不失）
NPC_ARCHIVE_FILE = DATA_DIR / "npc_archive.jsonl"

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")

# 三项齐全才启用真实模型，否则进入演示模式
DEMO_MODE = not (LLM_BASE_URL and LLM_API_KEY and LLM_MODEL)

# 离线演化判定：离开超过该分钟数才结算
OFFLINE_THRESHOLD_MINUTES = 45
# 离线结算封顶（现实小时数），防止离开一年烧穿 token
OFFLINE_MAX_HOURS = 24 * 7

# 模型申报所得的护栏。签到与支线奖励走引擎内部通道，不受此限。
GAIN_CURRENCY_CAP = 30  # 单回合可发放的灵石上限
GAIN_CATALOG_CAP = 1    # 单回合可发放的商城在售物品件数（能卖出变现，必须收紧）
GAIN_KIND_CAP = 3       # 单回合可发放的其他物品种类数
