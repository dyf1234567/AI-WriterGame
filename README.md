# 双界录 · 都市心动互动小说

AI 主持的持续都市人生沙盒。从京华大学入学开始，你可以学习、兼职、创业、进入娱乐业、经营战队或去其他城市生活。人物有自己的计划，事业和感情可以跨越多个阶段，校园「星河计划」是一个可选篇章。

本轮完整改造说明见 [人生沙盒与地图更新](docs/SANDBOX-UPDATE-2026-10-22.md)。
都市连载文风、人物对白和长期记忆改进见 [叙事与记忆更新](docs/NARRATIVE-UPDATE-2026-10-22.md)，包含公开项目的核实来源。
询问执行、角色知情、重复约定和演示剧情的一致性修复见 [审查修复记录](docs/REVIEW-FIXES-2026-10-22.md)。

## 运行方法

### 1. 安装依赖（首次）

```bash
cd /path/to/AI-WriterGame        # 进入项目目录（Windows 例：cd "D:\Program Files (x86)\AI WriterGame"）
python -m venv .venv   # 需 Python 3.10+（代码按 3.10+ 语法编写，3.12+ 亦可）
.venv/Scripts/python -m pip install -r requirements.txt
```

Mac/Linux 用户：`python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`，
启动命令把 `.venv/Scripts/python` 换成 `.venv/bin/python`（存档锁与数据目录已做双平台适配）。

### 2. 配置模型 API

复制 `.env.example` 为 `.env`，填入你的国内 OpenAI 兼容服务信息，例如（以 DeepSeek 为例）：

```
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxxxxxxx
LLM_MODEL=deepseek-chat
```

智谱等兼容服务同理，把 `LLM_BASE_URL` 换成对应端点（如 `https://open.bigmodel.cn/api/paas/v4`），`LLM_MODEL` 换成对应模型名。

**不配置也能启动**：游戏会进入"演示模式"，使用内置示例剧情跑通全部流程，界面顶部会明确提示。

### 3. 启动

```bash
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000> 即可游玩。

## 玩法速览

- **两套账户**：现实收入、生活消费、旅行与事业使用**华夏币**；系统商城、签到、成长奖励使用**系统积分**，两者不互相替代。旧「系统金币」按原数量迁移为系统积分，现实账户一次性补齐200华夏币生活启动资金。
- **世界地图**：6个国家、16座城市、118个地点，保留原京都/魔都地点与探索记录。世界海岸与岛链、国家交通网络、城市街区地标分层绘制，支持缩放/平移/拖动、搜索筛选、地点清单与行程预览。各地提供学习、创作、交流和工作；旅行真实扣款并推进时间。
- **都市系统界面**：城市天际线、连接状态与模块布局；左侧行程和双钱包、中间宽阅读页、右侧人物消息。四种具名配色始终可见，GM控制中心同步适配主题与手机，资源、商城、角色分区管理。
- **游戏时间**：交谈和短信约15分钟，集中练习约120分钟。可安排完整天数的训练、工作、学习或休息，一次最多推进三年。工资、项目、企业、人物和世界事件沿途结算，现实离线不会消耗游戏时间。
- **三领域同时发展**：娱乐、电竞、商业各自保留职业、阶段、名望和项目；切换关注领域不会放弃原有事业。条件满足可第一天创办公司，也可以作为资本方收购战队，不必先成为职业选手。
- **真实经营对象**：公司、作品、战队、合同有稳定身份，记录股权、企业现金、融资、成员、账目与分红；作品可发行并获得受众，战队可安排阵容和比赛，企业可定价、注资、融资或委托经营。
- **40种世界事件**：校园、日常、商业、娱乐、电竞和探索等事件可准备、表演、主持、赞助、社交、旁观或忽略。每场有独立结果，不能重复领奖，不参加也有世界结果；导演读取真实经历安排后续机会。
- **人物有自己的生活**：按附近、相关远处、背景三层推进计划；8位核心人物各有3阶段成长事件，支持合作、支持、竞争、放手与忽略。反复相处的动态人物会获得更高保留优先级。
- **关系与秘密**：好感、信任、吸引、熟悉、依恋、承诺六维影响相处；交往、专一/开放/多人协商、确认、分手、复合和异地均有状态。关系需要各方真实同意；回忆、转述和被提及不使旁人知情。
- **自己定义目标**：客观目标按真实资产、估值、股权、作品、技能、冠军或毕业核验；主观目标仍可记录。学籍支持上课、休学、复学、退学和毕业，人生阶段结合身份与事业变化。
- **可选校园与暗线**：星河计划保留六个参与方向、三位搭档与完整学期收尾，可暂缓或继续；隐藏超凡受到世界规则约束，三份调查证据可回收为合作或旁观选择，也可随时搁置。
- **系统玩法**：商城、抽奖、签到、背包、装备、礼物、修炼、存档恢复、长期记忆、短信与朋友圈继续可用。系统物品使用积分，现实经营使用华夏币。

## 测试

新增隔离验收：`tests/sandbox_career_test.py`、`sandbox_events_goals_test.py`、`sandbox_people_test.py`、`sandbox_integration_test.py`，以及 `node tests/sandbox_frontend_test.cjs`。测试服务必须使用独立 `SJL_DATA_DIR`，不要指向正式存档。

```bash
.venv/Scripts/python tests/state_growth_test.py          # 离线单元测试，不需要服务与模型 API
.venv/Scripts/python tests/regression_test.py            # 规则边界、生成失败、备份恢复、并发提交（隔离临时目录）
node tests/frontend_regression_test.cjs                 # 完整初始化、目录、阅读、主线和终章交互
.venv/Scripts/python tests/campaign_regression_test.py   # 隔离 API 全流程、旧档兼容和主线边界
.venv/Scripts/python tests/gameplay_regression_test.py   # 收支、升级、关系、短信和奖励回归
.venv/Scripts/python tests/narrative_regression_test.py  # 叙事上下文及288条主线路径
# 接口冒烟需按下方方法启动隔离演示服务，再使用相同 SJL_DATA_DIR。
```

2026-10-18 修复说明：新游戏先生成验证，再备份替换；剧情、开局、恢复与终章等操作保留状态和归档恢复点，小操作使用事务保护；最近50份可从“恢复存档”选择。旧剧情可从“往事回看”阅读。手机以剧情为默认面板，通过“地图与状态 / 人物与消息”切换。未见面人物与后台秘密不提前公开。余额不足的剧情交易会拒绝整回合，未满100%进度不能升级。

冒烟测试会新建游戏并修改测试存档。服务和脚本都必须使用相同的独立 `SJL_DATA_DIR`。脚本会先创建一次性随机凭据，通过只读握手确认目标服务使用该目录且处于演示模式，验证失败时不会发送任何游戏写请求。正式 `data/`（含路径别名和子目录）不能签发验证结果；残留的旧测试存档也不能代替实例验证。

```bash
# 隔离 + 强制演示模式（清空三个模型变量即不烧 API），再打冒烟
SJL_DATA_DIR=/d/tmp/sjl-smoke LLM_BASE_URL= LLM_API_KEY= LLM_MODEL= \
  .venv/Scripts/python -m uvicorn app.main:app --port 8001
SJL_DATA_DIR=/d/tmp/sjl-smoke SMOKE_BASE=http://127.0.0.1:8001 \
  .venv/Scripts/python tests/smoke_test.py
```

PowerShell 可在单独测试终端设置 `$env:SJL_DATA_DIR`、`$env:SMOKE_BASE`，并将三个 `LLM_` 变量设为空；服务和脚本使用同一目录。握手凭据在检查结束后自动清理；若异常终止遗留 `.smoke-probe.json`，脚本会拒绝复用，确认没有其他冒烟任务后再移除该测试目录中的凭据。

## 目录结构

```
app/            后端（FastAPI + 剧情引擎 + 游戏时间世界模拟）
static/         前端（阅读式界面＋多风格主题，原生 HTML/CSS/JS）
docs/           TASK-LEDGER（任务与变更台账）、FIXES（修复记录）
tests/          单元测试与接口冒烟测试
data/state.json 运行时存档（自动生成）
data/story_archive.jsonl 移出状态窗口的旧剧情正文（自动追加；压缩失败也不会丢正文）
```
