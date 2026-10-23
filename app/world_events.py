"""世界事件：日历驱动的周期活动＋导演层偶遇注入。

事件的参与选项带技能/属性门槛（skills.skill_check 门控），
结果由引擎结算——技能经验、金币（内部通道）、名望、机遇标记
（写入 career.opportunities，事业入门的钥匙）、在场 NPC 好感。
行动前缀【活动】由 before_turn 拦截，模板叙事不经过模型。
"""
from datetime import date, timedelta

from . import skills as sk
from .models import WORLD_URBAN, find_npc, game_today, now_iso

PREFIX = "【活动】"
DROUGHT_TURNS = 10  # 连续未参加活动的回合数阈值（导演层注入用）
DIRECTOR_COOLDOWN = 6  # 两次导演事件之间至少隔多少回合
DIRECTOR_HISTORY_KEPT = 6

# 事件定义：id → {name, cat, desc, options:[{id,label,req:{skill,diff}|None,
#   win:{text,xp,gold,fame,opp,npcs}, half:..., lose:...}]}
_EVENTS = {
    "gala": {
        "name": "校园晚会", "cat": "娱乐", "npcs": ["梁雅婷", "傲寒", "乐乐"],
        "desc": "周五晚的大礼堂灯火通明，节目单还缺一个压轴。",
        "options": [
            {"id": "sing", "label": "登台唱一首", "req": ("vocal", 2),
             "win": {"text": "你的嗓音镇住了全场，谢幕时礼堂的掌声久久不停——后台角落里，一位戴着工牌的经纪公司星探朝你递来了名片。",
                     "xp": ("vocal", 40), "gold": 0, "fame": ("娱乐", 8),
                     "opp": "经纪公司试镜邀请"},
             "half": {"text": "副歌唱到一半破了音，好在台下掌声还算善意——同班的梁雅婷在侧幕冲你比了个加油的手势。",
                      "xp": ("vocal", 20), "gold": 0, "fame": ("娱乐", 3), "opp": None},
             "lose": {"text": "你在台上脑子一片空白，草草唱完逃下台——有些事，果然要练过再上。",
                      "xp": ("vocal", 10), "gold": 0, "fame": None, "opp": None}},
            {"id": "host", "label": "毛遂自荐当主持", "req": ("speech", 2),
             "win": {"text": "你串场救了两次冷场，晚会导演散场后拍着你的肩说下次校庆还找你。",
                     "xp": ("speech", 40), "gold": 30, "fame": ("娱乐", 5), "opp": None},
             "half": {"text": "念错了一个赞助商的名字，全场笑成一片——也算留下了印象。",
                      "xp": ("speech", 20), "gold": 15, "fame": None, "opp": None},
             "lose": {"text": "你在台上腿肚子转筋，把话筒递给了救场的学长。",
                      "xp": ("speech", 10), "gold": 0, "fame": None, "opp": None}},
            {"id": "watch", "label": "坐在台下看热闹", "req": None,
             "win": {"text": "你在台下嗑着瓜子看完了整场，跟旁边音乐系的女生聊得很开心。",
                     "xp": None, "gold": 0, "fame": None, "opp": None},
             "half": None, "lose": None},
        ],
    },
    "arena": {
        "name": "电竞擂台赛", "cat": "电竞", "npcs": ["小杨", "韩冰", "歪歪"],
        "desc": "周六的电竞馆人声鼎沸，擂台赛的报名处排着长队，冠军奖金八十华夏币。",
        "options": [
            {"id": "solo", "label": "报名单人赛", "req": ("mech", 2),
             "win": {"text": "决胜局一波三杀收割比赛，全场喊你 ID 的声音盖过解说——青训营的教练在场边记下了你的名字。",
                     "xp": ("mech", 40), "gold": 80, "fame": ("电竞", 8),
                     "opp": "青训营测试资格"},
             "half": {"text": "你打进了四强，倒在了一个套路极其脏的老哥手里——电竞社的小杨场外直呼可惜。",
                      "xp": ("mech", 20), "gold": 30, "fame": ("电竞", 3), "opp": None},
             "lose": {"text": "小组赛两连败出局——手速这东西，骗不了人。",
                      "xp": ("mech", 10), "gold": 0, "fame": None, "opp": None}},
            {"id": "cast", "label": "蹭解说席分析战术", "req": ("sense", 2),
             "win": {"text": "你的局势预判连解说都跟着点头，直播间弹幕刷起了\"这兄弟懂游戏\"。",
                     "xp": ("sense", 40), "gold": 20, "fame": ("电竞", 4), "opp": None},
             "half": {"text": "你预言的翻盘没来，弹幕笑称你是\"毒奶\"——车车转发了你的片段。",
                      "xp": ("sense", 20), "gold": 10, "fame": None, "opp": None},
             "lose": None},
        ],
    },
    "market": {
        "name": "创意集市", "cat": "商业", "npcs": ["花碎花", "吃不饱", "小新"],
        "desc": "周日的步行街支起了集市摊位，人流量正旺，摊位费五十。",
        "options": [
            {"id": "stall", "label": "支个小摊试水", "req": ("manage", 1),
             "win": {"text": "你挑的货和喊的价都对了路，收摊时数钱数到手软——花碎花隔壁摊的奶茶都跟着多卖了几杯。",
                     "xp": ("manage", 40), "gold": 120, "fame": ("商业", 5), "opp": None},
             "half": {"text": "不算亏，但也只赚回了摊位费——隔壁吃不饱的摊位排着队，你默默记下了她的选品。",
                      "xp": ("manage", 20), "gold": 50, "fame": None, "opp": None},
             "lose": {"text": "进货砸在手里了，收摊时你把剩下的货半卖半送。",
                      "xp": ("manage", 10), "gold": 20, "fame": None, "opp": None}},
            {"id": "busk", "label": "街头卖艺", "req": ("vocal", 1),
             "win": {"text": "你的吉他弹唱围起了里三层外三层，琴盒里的零钱铺满了底。",
                     "xp": ("vocal", 30), "gold": 60, "fame": None, "opp": None},
             "half": {"text": "唱了三首，赚了份奶茶钱——路过的小新给你直播刷了个火箭。",
                      "xp": ("vocal", 15), "gold": 25, "fame": None, "opp": None},
             "lose": None},
        ],
    },
    "roadshow": {
        "name": "商业路演日", "cat": "商业", "npcs": ["炭炭", "杨幂", "邓碧瑶"],
        "desc": "月末的路演厅里挤满了投资人和创业者，五分钟一个项目。",
        "options": [
            {"id": "pitch", "label": "上台讲一个点子", "req": ("speech", 3),
             "win": {"text": "你的五分钟讲得全场安静，散场后两位投资人主动交换了联系方式——炭炭在台下朝你举了举咖啡。",
                     "xp": ("speech", 50), "gold": 0, "fame": ("商业", 10), "opp": "天使投资人名片"},
             "half": {"text": "点子被夸了，但商业模式被问得体无完肤——评委建议你先从练摊开始。",
                      "xp": ("speech", 25), "gold": 0, "fame": ("商业", 3), "opp": None},
             "lose": {"text": "PPT 翻到第三页你就忘了词，全场礼貌的掌声像在送葬。",
                      "xp": ("speech", 10), "gold": 0, "fame": None, "opp": None}},
            {"id": "network", "label": "混进茶歇社交", "req": None,
             "win": {"text": "你端着咖啡蹭了三轮谈资，加到了五个微信——其中一个备注写着\"投资人\"。",
                     "xp": None, "gold": 0, "fame": ("商业", 3), "opp": None},
             "half": None, "lose": None},
        ],
    },
    # 偶遇型（导演层注入）
    "street": {
        "name": "街头演出", "cat": "偶遇", "npcs": ["乐乐"],
        "desc": "路过商街时，一台突然罢工的音响前站着不知所措的街头歌手。",
        "options": [
            {"id": "help", "label": "上去救场唱两首", "req": ("vocal", 1),
             "win": {"text": "你接过失灵的话筒救了场，围观人群里的欢呼声比原主唱还响。",
                     "xp": ("vocal", 25), "gold": 20, "fame": ("娱乐", 3), "opp": None},
             "half": {"text": "你唱得磕磕绊绊，但好歹把场子救回来了。",
                      "xp": ("vocal", 12), "gold": 10, "fame": None, "opp": None},
             "lose": None},
        ],
    },
    # ---- 导演层事件：没有固定活动的日子，按世界状态择机出现 ----
    "relation_window": {
        "name": "关系契机", "cat": "关系", "npcs": [], "dynamic_npc": True,
        "desc": "{npc}发来一条消息，问你现在有没有空，想和你单独走走。",
        "options": [
            {"id": "walk", "label": "赴约，认真听她说话", "req": None,
             "win": {"text": "你和{npc}沿着江边走了很久。她说起最近一直没对别人说过的事，也问起你的打算。你们没有急着给关系下定义，但回去时都走得比来时慢。",
                     "memo": "与你同台/同行，记住了这次经历",
                     "fact": "{npc}在夜里向主角说起一件没对别人说过的事"},
             "half": {"text": "你们走了一段路，话题几次停住。{npc}没有勉强自己，你也没有追问。",
                      "memo": "对你有了印象"},
             "lose": None},
            {"id": "decline", "label": "这次先不去了", "req": None,
             "win": {"text": "你回消息说这会儿想一个人待着。{npc}只回了一个“好”，没有追问。对话停在这里，你把手机收好。",
                     "memo": "觉得你今天的发挥有些失礼"}},
        ],
    },
    "industry_offer": {
        "name": "行业机会", "cat": "事业", "npcs": ["炭炭", "杨幂", "车车"],
        "desc": "一场圈内小聚上，一位前辈叫住了你：手头有个位置，想先听听你的想法。",
        "options": [
            {"id": "talk", "label": "坐下来认真聊", "req": ("speech", 2),
             "win": {"text": "你把眼下在做的事讲得很清楚，也坦白了自己还缺什么。前辈没有当场许诺，但把联系方式留给了你，说下次有合适的位置会再找你。",
                     "xp": ("speech", 30), "gold": 30, "fame_any": 5},
             "half": {"text": "你聊得有些急，前辈听完只点了点头。临走时他说：先把手上那件事做完，再谈下一步。",
                      "xp": ("speech", 15), "gold": 15, "fame_any": 2},
             "lose": {"text": "你准备得不够，话到一半就被带了过去。前辈客气地结束了话题，你在门口站了一会儿。",
                      "xp": ("speech", 8)}},
            {"id": "observe", "label": "先听听别人怎么说", "req": None,
             "win": {"text": "你没有急着递话，而是听完了整场。散场时你记下了三条有用的判断，也认清了谁在说真话。",
                     "xp": ("speech", 15), "fame_any": 1}},
        ],
    },
    "competition": {
        "name": "同行竞争", "cat": "事业", "npcs": ["车车", "小杨", "炭炭"],
        "desc": "你的名字开始被人拿来比较。对手放出话，要在下一场活动上压你一头。",
        "options": [
            {"id": "fight", "label": "正面接招", "req": ("speech", 2),
             "win": {"text": "你没有回避，把该拿出的东西都拿了出来。结果不算碾压，但对手收回了那句大话，圈里也记住了你的名字。",
                     "xp": ("speech", 25), "gold": 20, "fame_any": 4},
             "half": {"text": "你接住了场面，却没有赢下所有回合。对手在散场时和你握了手，说下次再来。",
                      "xp": ("speech", 12), "fame_any": 1},
             "lose": {"text": "你被对方的节奏带着走，结束时才想起自己原本想说什么。回去的路上，你把复盘记在了手机里。",
                      "xp": ("speech", 8)}},
            {"id": "study", "label": "先研究对手", "req": ("sense", 2),
             "win": {"text": "你没有急着应战，而是把对手最近的动作拆开来看。第二天你带着一套更有针对性的方案出现，风向开始变了。",
                     "xp": ("sense", 25), "fame_any": 2},
             "half": {"text": "你看出了对手的一个习惯，但还没想好怎么用。至少这一次，你没有盲目跟着跑。",
                      "xp": ("sense", 12)}},
        ],
    },
    "hidden_clue": {
        "name": "深夜微光", "cat": "探索", "npcs": [],
        "desc": "云顶天文台的方向又亮起微光。你翻出手机里那张旧照片，轮廓和记忆里的某一晚对上了。",
        "options": [
            {"id": "go", "label": "今晚去看看", "req": None,
             "win": {"text": "你独自上了山。天文台的铁门没有锁，里面却干净得不像废弃多年。你在一台旧仪器的底座上看见一串刻痕，和系统偶尔闪过的字符很像。",
                     "fact": "云顶天文台的旧仪器刻痕与主角的系统字符相似（未解线索）"},
             "half": {"text": "你走到半山腰就起了雾，只能远远看见那点微光。下山时它已经灭了，但你知道自己还会再来。"}},
            {"id": "ignore", "label": "当作没看见", "req": None,
             "win": {"text": "你把照片翻了过去，继续做眼前的事。那点微光在窗外亮了一夜，第二天早上又恢复成一段普通的传闻。"}},
        ],
    },
    "craft_showcase": {
        "name": "作品被看见", "cat": "成长", "npcs": ["乐乐", "小杨", "炭炭"],
        "desc": "你长期投入的东西终于有了一个能被看见的窗口：有人愿意给你十分钟。",
        "options": [
            {"id": "show", "label": "把作品拿出来", "req": None,
             "win": {"text": "你没有再等一个更完美的版本。十分钟里，你把最想让人看见的部分完整地展示了出来；有人认真问了细节，这比客套的夸奖更让你踏实。",
                     "xp_any": 20, "gold": 10, "fame_any": 2},
             "half": {"text": "展示到一半你发现了明显的瑕疵。你还是把它讲完了，也在反馈里记下了下一次要改的地方。",
                      "xp_any": 10}},
            {"id": "polish", "label": "再打磨一轮", "req": None,
             "win": {"text": "你婉拒了这次窗口，把时间留给手上的作品。没有人看见，但你自己知道它比昨天更完整了一点。",
                     "xp_any": 25}},
        ],
    },
}

# 三十个新增模板与前十个共同构成四十种活动。每种主行动有独立门槛、代价与后续方向。
# 其余身份可组合使用：准备→表演/经营/参赛，或赞助、主持、社交、旁观、忽略。
def _add_event(eid, name, cat, desc, skill, difficulty, role, label,
               success, partial, failure, opportunity, world_result, npcs=(), gold=20):
    _EVENTS[eid] = {"name": name, "cat": cat, "desc": desc, "npcs": list(npcs),
        "world_result": world_result, "followup": opportunity,
        "options": [{"id": role, "label": label, "req": (skill, difficulty),
            "win": {"text": success, "xp": (skill, 35), "gold": gold,
                    "fame": (cat, 5) if cat in ("商业", "娱乐", "电竞") else None,
                    "opp": opportunity},
            "half": {"text": partial, "xp": (skill, 18), "gold": max(0, gold // 3)},
            "lose": {"text": failure, "xp": (skill, 8)}}]}


_NEW_TEMPLATES = [
 ("club_fair", "社团招新日", "校园", "操场上的摊位正在招募新成员，空白报名表等着新的名字。", "speech", 1, "recruit", "帮社团招募成员", "你把社团最有趣的经历讲给新生听，收下了一批真实报名。", "来咨询的人不少，最后只有几人留下联系方式。", "介绍太散，没有人听清社团究竟做什么。你向老成员补问了具体安排。", "跨社团联合演出邀请", "社团公布新成员名单，未满员的岗位交由现有成员兼任。", ("郭瑞莹",)),
 ("research_demo", "学生研究展", "校园", "展厅向非本专业学生开放，演示台上摆着还不够成熟的原型。", "coding", 3, "demo", "演示自己的原型", "现场提问暴露了边界，也证明原型能解决实际问题，实验室留下了试用需求。", "核心流程能跑通，边缘问题还需要修复。", "原型在演示中中断。你保留了故障日志，承认暂时不能交付。", "实验室软件试用需求", "研究展留下公开演示记录，评审团将试用名额交给完成演示的团队。", ("邓碧瑶",)),
 ("sports_day", "校园运动日", "校园", "运动场正在进行团体项目，志愿者询问你想上场还是帮忙组织。", "sense", 2, "relay", "参加团队接力", "你判断好交接节奏，和队友一起完成了接力，校队邀请你参加开放训练。", "交接稍慢，但你们没有放弃最后一棒。", "配合失误丢了节奏。你主动和队友复盘，没有把责任推给别人。", "校队开放训练邀请", "团体赛如期结束，新的训练名单由实际参赛成绩决定。", ("傲寒",)),
 ("alumni_forum", "校友职业论坛", "校园", "不同职业的校友把收入、失败和转行的经历摆到了桌面上。", "speech", 2, "question", "带着自己的项目提问", "你问清楚了客户从哪里来，校友愿意安排一次真实岗位见习。", "问题有些宽泛，你记下了下一次应当带来的数据。", "你的假设被追问住了，讨论让你认清了当前准备的不足。", "跨领域岗位见习", "校友按实际需求安排见习，论坛结束后公开整理了问答记录。", ("郭瑞莹",)),
 ("campus_debate", "公共议题辩论", "校园", "辩论席上争论着校园空间该如何分配，组织方也欢迎旁听意见。", "speech", 3, "debate", "提交论据并上台辩论", "你用实地调查支撑观点，建议被写进了议事备忘。", "论据还缺一块，但对方认可你对事实的认真。", "一句未经核验的话被指出错误，你当场更正了说法。", "学生议事会观察席", "议事会留下各方意见，之后按程序公布空间使用方案。", ("邓碧瑶",)),
 ("supplier_talk", "供应链洽谈", "商业", "本地供应商带来了报价单，交期与售后条款比口头优惠更值得注意。", "manage", 2, "negotiate", "核对样品并谈交期", "你把验收和违约条款谈清楚，拿到一份可复核的试供方案。", "价格谈下来了，账期仍需继续协商。", "样品与承诺不符，你结束了这次洽谈，保住了未支付的货款。", "小批量试供渠道", "供需双方各自确认采购意向，未签约的报价到期失效。", ("炭炭",)),
 ("product_test", "产品用户测试", "商业", "真实用户坐在体验桌前，等着使用你带来的产品。", "manage", 3, "test", "现场观察产品使用", "你没有替用户解释，记录下了真实障碍，试用者愿意参与下一轮付费测试。", "产品有用，但体验的几个问题阻碍了付款。", "核心需求与你想象的不同，你把负面反馈完整收进了复盘。", "付费试用客户线索", "测试结束后，参与者把意见交还团队，市场评价继续传播。", ("花碎花",)),
 ("hiring_fair", "人才招聘会", "商业", "求职者更关心岗位职责与薪酬是否兑现，而不是公司口号。", "manage", 3, "interview", "带岗位预算面试候选人", "你和候选人讲清职责边界，几位有经验的人愿意进入正式招聘流程。", "双方愿意再聊，但薪酬与排班还没谈拢。", "预算覆盖不了承诺，你撤回了不成熟的招聘需求。", "资深员工招聘渠道", "招聘会结束，候选人按各自条件继续选择工作。", ("炭炭",)),
 ("finance_review", "企业财务复盘", "商业", "会计把收入、成本和应付工资列成了表，决定需要建立在现金流上。", "invest", 3, "review", "审查现金流与风险", "你识别了虚高回款预期，调整支出次序，一位合作方愿意重新谈账期。", "收支大体算清，还缺一笔旧账的凭据。", "乐观估计经不起核对，你暂停扩张并要求补齐资料。", "经营授信咨询资格", "经营者提交了账本，合作方据此调整信用条件。", ("炭炭",)),
 ("media_company", "传媒创业圆桌", "商业", "演出经历让你收到小型传媒圆桌的邀请，创作者与经营者坐在同一张桌上。", "manage", 3, "found", "提出独立厂牌方案", "你把制作、发行与预算讲成了可执行的小计划，合作方愿意提供试单渠道；公司仍需你亲自出资设立。", "创意得到兴趣，但大家要求先看第一件可交付作品。", "合作方指出版权和现金流缺口，你记下问题后保留独立创作的选择。", "天使投资人名片", "创作者各自选择签约或独立经营，试单名额分配给准备充分的团队。", ("乐乐", "炭炭")),
 ("audition", "公开试镜", "娱乐", "试镜室没有预设赢家，剧组按角色需要逐个看表演。", "acting", 3, "act", "试演一段角色场景", "你演出了人物的动机，选角导演给了下一轮回访机会。", "表演有亮点，但角色理解仍需调整。", "紧张盖过了角色，你离开时收下了具体的修改意见。", "经纪公司试镜邀请", "剧组按试演记录继续选角，未到场的演员不会被自动留位。", ("杨幂",)),
 ("recording_session", "独立录音合作", "娱乐", "录音师把棚期空了出来，合作取决于你是否准备好了作品。", "vocal", 3, "record", "录制现场样带", "你完成了稳定的样带，录音师愿意介绍独立发行渠道。", "有两段需要重录，样带留下了明确的修改清单。", "气息与节拍没有跟上，录音师建议先把基础练稳。", "独立音乐发行渠道", "棚期结束，录音师按实际完成的音轨整理交付记录。", ("乐乐",)),
 ("film_set", "短片拍摄现场", "娱乐", "一支独立剧组正在拍短片，镜头前后都有可以承担的工作。", "acting", 2, "shoot", "出演短片角色", "你配合走位和重拍完成了镜头，导演把你加入下次试戏名单。", "镜头完成了，节奏还需要剪辑师修补。", "进度因你的准备不足而放缓，你留下来完成了补拍。", "独立短片试戏名单", "剧组完成当天拍摄，工作人员各自继续后期与下一场筹备。", ("杨幂",)),
 ("release_party", "作品发行交流会", "娱乐", "发行方想看的是作品完成度、受众定位和明确的权利归属。", "stage", 4, "premiere", "向发行方展示作品", "展示引来了具体发行询价，权利与分成仍需你在合同中确认。", "有人愿意试听完整版，但还没有发行承诺。", "受众定位不清，你带回了修改建议，保留作品所有权。", "作品联合发行洽谈", "发行方根据实际作品安排档期，未签约项目不会凭空上映。", ("乐乐", "杨幂")),
 ("fan_meet", "创作者见面会", "娱乐", "看过你作品的人带着具体问题来到现场，也有不同意你的人。", "speech", 3, "meet", "面对面回答观众提问", "你坦诚回答创作与失误，观众自发建立了后续活动联络群。", "问答有些生涩，但你认真记下了批评。", "一段夸大的说法被追问，你向观众澄清并更正。", "创作者观众社群", "观众按真实体验分享评价，创作者需要继续用作品回应。", ("乐乐",)),
 ("team_tryout", "战队公开试训", "电竞", "试训教练会同时看操作、沟通和能否履行训练安排。", "mech", 3, "trial", "参加位置试训", "你打出了稳定发挥，教练愿意给正式测试的席位。", "个人表现合格，团队沟通还需要磨合。", "对抗强度超出预期，你拿到了录像和需要训练的要点。", "青训营测试资格", "教练保存试训录像，按照位置需求安排后续测试。", ("小杨",)),
 ("tactics_lab", "战术训练交流", "电竞", "训练室开放了复盘席位，战术判断需要比赛录像来验证。", "sense", 4, "analyse", "带录像制定针对战术", "你找出了对方阵容的薄弱环节，教练愿意安排一场训练赛验证。", "看出了习惯，但落地指令不够清楚。", "分析把偶然当规律，教练让你补看完整样本。", "跨队训练赛邀请", "各队带着复盘结论继续训练，战术效果要在实战中检验。", ("韩冰",)),
 ("club_invest", "俱乐部投资交流", "电竞", "俱乐部拿出了人员、赛程与现金流资料，热爱之外还需要经营。", "invest", 4, "diligence", "审查俱乐部投资条件", "你找到了合理估价和关键风险，持有人愿意开放小额股权洽谈；股份尚未成交。", "资料还不完整，你要求补充后再做决定。", "开价与收入不匹配，你拒绝了冲动出资。", "电竞俱乐部股权洽谈", "俱乐部继续寻找合适投资人，出资与股权转让需要另行签约。", ("小杨", "车车")),
 ("sponsor_cup", "跨界品牌邀请赛", "电竞", "品牌想把创作者、观众和电竞赛事连在一起，合作各有实际条件。", "manage", 3, "produce", "设计赛事与品牌合作", "你把赛程、预算和曝光承诺对齐，品牌愿意提供一次正式合作询价。", "活动设想可行，但曝光估计需要收敛。", "赞助回报经不起核验，你撤回了过度承诺。", "品牌赛事承办邀约", "赛事按照已确认的预算开办，未落实的赞助不会算作收入。", ("车车",)),
 ("season_final", "赛季决赛观摩", "电竞", "决赛将决定这一季的排名，观摩席能听到教练的即时判断。", "sense", 4, "coach", "提交临场战术建议", "你的建议得到一次现场验证，俱乐部愿意邀请你做赛后复盘。", "判断方向正确，时机稍晚了一些。", "建议与选手习惯冲突，教练解释了为什么不能照做。", "俱乐部战术顾问面谈", "决赛产生正式冠军，未报名的主角不会被记作冠军。", ("韩冰", "小杨")),
 ("npc_exhibition", "朋友的成果展", "关系", "{npc}筹备很久的成果展到了开放日，她希望你能来，也尊重你的安排。", "photo", 2, "support", "认真看展并留下具体反馈", "你记得她做过的修改，也问了作品本身的问题。她愿意让你参与下一次筹备。", "你没有完全看懂，但认真听完了她的解释。", "一句随口评价伤到了她，你听明白原因后承认了草率。", "朋友下次创作筹备邀请", "展览按时开放，创作者收获自己的观众与反馈。", ()),
 ("npc_career_choice", "朋友的职业岔路", "关系", "{npc}拿到两个方向不同的机会，想听听你的看法，但决定属于她。", "speech", 3, "listen", "帮她梳理取舍", "你先问她真正看重什么，再一起列出得失。她做出自己的选择，并请你陪她完成第一步。", "你们列清了顾虑，她决定再向业内人求证。", "你把自己的目标套在她身上，她明确表示要自己考虑。", "朋友职业新阶段", "她在期限内作出职业决定，生活继续向她选择的方向发展。", ()),
 ("boundary_talk", "关系边界长谈", "关系", "{npc}想谈清彼此的期待，这次谈话不会自动替任何人决定恋爱关系。", "speech", 2, "listen", "先听清她的界限", "你复述并确认了她的界限，约好有变化时再谈。正式关系仍由双方另行协商。", "仍有分歧，但你们把不愿接受的事说清楚了。", "她拒绝了你替她作出的假设，你停下来重新听她说。", "关系协商准备", "关系中的双方继续按各自界限生活，未回应不代表同意。", ()),
 ("reunion_trip", "朋友短途同行", "关系", "{npc}提议安排一次短途同行，行程与分工需要先商量好。", "photo", 2, "plan", "共同安排一段轻松行程", "你们给彼此留了独处的时间，也留下了一段愿意再提起的回忆。", "天气打乱了计划，你们临时改成坐在小店里聊天。", "安排没有考虑她的体力，你调整了路线并提前返回。", "共同旅行回忆", "朋友按自己的安排出行，沿途见闻变成各自的生活记忆。", ()),
 ("community_meal", "社区共食夜", "生活", "附近住户带来各自做的菜，大家只想轻松吃一顿饭。", "cooking", 1, "cook", "做一道拿手菜", "一道热菜让陌生人聊起了家常，你得到下一次共食的邀请。", "火候差一点，大家还是把菜分完了。", "菜没做好，你和邻居一起补做了一份简单的面。", "邻里共食邀请", "住户吃完饭一起收拾桌椅，平常的一晚也有自己的温度。", ("吃不饱",)),
 ("city_photo", "城市影像征集", "生活", "城市记录项目正在收集普通人的日常，拍摄需要先征得被摄者同意。", "photo", 2, "submit", "提交取得同意的街头影像", "你的影像留下了生活的细节，编辑愿意给下一期留一个投稿位置。", "照片有故事，说明文字还需补充。", "编辑指出画面信息不足，你带着建议继续观察城市。", "城市影像编辑约稿", "编辑按授权与质量整理影像，街道上的生活继续发生。", ()),
 ("weekend_hike", "周末慢行", "生活", "一支小队准备走一条安全的近郊路线，目标只是舒服地看完沿途风景。", "sense", 1, "walk", "照顾节奏一起走完", "你及时调整了休息节奏，大家轻松走完路线，约好下次再来。", "走到一半改了短线，仍看到了不错的风景。", "你察觉疲劳后及时回程，安全到家比完成里程更重要。", "近郊慢行小队", "慢行者按天气调整路线，城市之外也有平静的日常。", ()),
 ("night_market", "旅途夜市", "生活", "夜市摊主介绍着当地食物与小生意，你可以尝尝、聊天或试着合作。", "manage", 1, "learn", "向摊主学习当地生意", "你问清了客流与损耗，摊主愿意让你观察一次备货过程。", "了解了一些门道，真实利润仍要看完整账本。", "你误把排队当盈利，摊主耐心算了一遍成本。", "异地小生意观察", "夜市按当地节奏开张收摊，摊主有自己的客人和打算。", ()),
 ("archive_visit", "旧档案开放日", "探索", "档案馆公开一批旧记录，其中有一段与你见过的微光相似的描述。", "coding", 2, "compare", "核对公开记录与时间线", "你找到两份互相印证的记录，留下了一条可继续核实的线索。", "记载相似却没有直接证据，你标明了存疑之处。", "关键日期对不上，你排除了一个错误猜测。", "微光旧档案索引", "档案按开放规则供人查询，没有调查的人照常度过这一天。", ()),
 ("hidden_contact", "陌生研究者来信", "探索", "你调查过的微光记录引来一封克制的来信，对方只愿在公开地点交换可验证信息。", "speech", 3, "verify", "在公开场所核实来信", "对方提供了能交叉核对的资料，并提到一个长期研究异常现象的小组。你可以决定是否继续接触。", "你们交换了公开信息，仍保留彼此身份的疑问。", "你发现来信中的一处矛盾，结束了会面，没有交出私人资料。", "异常研究小组公开联络点", "研究者继续自己的调查，没有回复的来信被归档，不会强迫主角介入。", ()),
]
for _template in _NEW_TEMPLATES:
    _add_event(*_template)
for _eid in ("npc_exhibition", "npc_career_choice", "boundary_talk", "reunion_trip"):
    _EVENTS[_eid]["dynamic_npc"] = True

_EVENTS["market"]["options"][0]["cost"] = 50  # 摊位费与叙事一致，先核验再扣款。

FINAL_STATUSES = {"completed", "ignored", "expired"}


def _event_state(state: dict) -> dict:
    st = state.setdefault("events", {})
    if not isinstance(st, dict):
        st = state["events"] = {}
    for key, default in (("instances", {}), ("history", []), ("experience", [])):
        if not isinstance(st.get(key), type(default)):
            st[key] = default
    return st


def _instance(state: dict, eid: str, day: str | None = None, context=None) -> dict:
    day = day or game_today(state)
    st = _event_state(state)
    iid = f"{eid}:{day}"
    if iid not in st["instances"]:
        st["instances"][iid] = {"id": iid, "template": eid, "day": day,
            "status": "open", "preparation": 0, "context": dict(context or {})}
    return st["instances"][iid]


def _iso(state: dict) -> tuple:
    return date.fromisoformat(game_today(state)).isocalendar()


def _scheduled_on(day: date) -> list[str]:
    year, week, wd = day.isocalendar()
    if wd == 5:
        return ["gala"]
    if wd == 6:
        return ["roadshow" if (day + timedelta(days=7)).month != day.month else "arena"]
    if wd == 7 and day.day <= 7:
        return ["market"]
    # 两个平日窗口轮换新模板，关系/超凡内容仍由因果导演给出。
    calendar = [t[0] for t in _NEW_TEMPLATES if t[2] not in ("关系", "探索")]
    if wd in (1, 4):
        return [calendar[(week * 2 + (wd == 4)) % len(calendar)]]
    return []


def scheduled_for(state: dict) -> list[str]:
    return _scheduled_on(date.fromisoformat(game_today(state)))


def _director_state(state: dict) -> dict:
    director = state.setdefault("director", {})
    if not isinstance(director, dict):
        director = state["director"] = {}
    for key, default in (("active", None), ("history", []), ("last_event_turn", -999),
                         ("last_npc", ""), ("last_place_count", 0)):
        director.setdefault(key, default)
    return director


def _director_context(state: dict, ev_id: str | None = None) -> dict | None:
    director = _director_state(state)
    active = director.get("active")
    if not isinstance(active, dict) or not active.get("id"):
        return None
    if active.get("day") != game_today(state):
        director["active"] = None
        return None
    if ev_id and active.get("id") != ev_id:
        return None
    return active


def _format_event(text, ctx: dict | None) -> str:
    return str(text or "").replace("{npc}", str((ctx or {}).get("npc") or "熟识的朋友"))


def _top_relationship_npc(state: dict) -> dict | None:
    known = [n for n in state.get("npcs", [])
             if n.get("known_to_player") and int(n.get("affinity", 0)) >= 65]
    known.sort(key=lambda n: int(n.get("affinity", 0)), reverse=True)
    last = _director_state(state).get("last_npc", "")
    return next((n for n in known if n["name"] != last), known[0] if known else None)


def _top_skill(state: dict) -> tuple[str, int]:
    return max(((sid, sk.level(state, sid)) for sid in sk.SKILLS), key=lambda x: x[1])


def _discovered_count(state: dict) -> int:
    return sum(bool(p.get("discovered")) for p in state.get("map", {}).get(WORLD_URBAN, []))


def _director_pick(state: dict) -> dict | None:
    director = _director_state(state)
    if int(state.get("turn", 0)) == 0:
        return None  # 先让开场落地，初始关系数值不等于本周目已发生新的邀约。
    if (active := _director_context(state)):
        return active
    turn = int(state.get("turn", 0))
    if turn - int(director.get("last_event_turn", -999)) < DIRECTOR_COOLDOWN:
        return None
    candidates = []
    npc = _top_relationship_npc(state)
    experience = _event_state(state)["experience"]
    done = {e.get("template") for e in experience if e.get("outcome") in ("win", "half")}
    from . import career
    c = career.ensure_career(state)
    enterprises = (state.get("player") or {}).get("enterprises", [])
    goals = [g for g in state.get("goals", []) if g.get("status") == "active"]
    history = director.get("history") or []
    def add(score, eid, reason, who=""):
        if _EVENTS[eid].get("dynamic_npc") and not who:
            return
        candidates.append((score, eid, who, reason))
    if npc:
        add(4 + 2 * any(h.get("npc") == npc["name"] for h in state.get("hooks", [])),
            "relation_window", "彼此已经熟悉，留一点安静相处的时间", npc["name"])
        if "relation_window" in done:
            add(5, "npc_exhibition" if "npc_exhibition" not in done else "npc_career_choice",
                "共同经历后，朋友也有自己的事业要推进", npc["name"])
    if any(e.get("domain") == "娱乐" and e.get("outcome") == "win" for e in experience):
        add(6, "media_company", "你的公开表演经历让经营者愿意听一份厂牌方案")
    if "media_company" in done or any(e.get("kind") == "company" for e in enterprises):
        add(6, "club_invest", "经营经验带来俱乐部投资资料的接触机会")
    if any(e.get("kind") == "work" and e.get("status") == "released" for e in enterprises):
        add(6, "fan_meet", "已发行作品有了实际受众")
        add(5, "sponsor_cup", "作品和观众让赛事方想到一次跨界合作")
    if any(e.get("kind") == "team" for e in enterprises):
        add(6, "tactics_lab", "你持有的战队需要训练和复盘")
    for goal in goals:
        domain = goal.get("domain")
        pick = {"商业": "supplier_talk", "娱乐": "recording_session", "电竞": "team_tryout",
                "学业": "research_demo", "生活": "community_meal"}.get(domain)
        if pick:
            add(4, pick, f"与你自己定下的目标「{goal.get('title', '')}」有关")
    fame = max((c.get("fame") or {}).values() or [0])
    if c.get("domain") and (int(c.get("stage", 0)) >= 2 or fame >= 25):
        previous = [h for h in history if h.get("category") == "事业"]
        add(3, "competition" if previous and previous[-1].get("id") == "industry_offer" else "industry_offer",
            "你已经有可被同行看见的实际事业")
    discovered = _discovered_count(state)
    if discovered >= 6 and director.get("last_place_count") != discovered:
        add(3, "hidden_clue", "你主动探索过城市，偶然注意到异常线索")
    if "hidden_clue" in done:
        add(5, "archive_visit", "你已亲自调查微光，可以自行选择核实旧档案")
    if "archive_visit" in done:
        add(6, "hidden_contact", "公开档案中的检索记录引来研究者回信")
    if _top_skill(state)[1] >= 4:
        add(2, "craft_showcase", "长期练习已经积累可展示的成果")
    last_join = int(_event_state(state).get("last_join_turn", -999))
    if turn >= DROUGHT_TURNS and turn - last_join >= DROUGHT_TURNS:
        add(2, "street", "闲逛中遇到一件可参与也可绕过的小事")
    if len(history) >= 2 and all(h.get("category") in ("事业", "商业", "娱乐", "电竞", "成长") for h in history[-2:]):
        add(8, "community_meal", "最近的行程很紧，附近有一顿无需竞争的便饭")
    scored = []
    for score, eid, who, reason in candidates:
        existing = _event_state(state)["instances"].get(f"{eid}:{game_today(state)}")
        if existing and existing.get("status") in FINAL_STATUSES:
            continue
        recent = [h for h in history[-4:] if h.get("id") == eid]
        score -= len(recent) * 3
        if eid in done and eid in ("media_company", "club_invest", "archive_visit", "hidden_contact"):
            score -= 8
        if history and history[-1].get("id") == eid:
            score -= 2
        scored.append((score, eid, who, reason))
    if not scored:
        return None
    score, eid, who, reason = sorted(scored, key=lambda x: (-x[0], x[1]))[0]
    if score <= 0:
        return None
    category = "事业" if eid in ("industry_offer", "competition") else _EVENTS[eid]["cat"]
    picked = {"id": eid, "npc": who, "category": category, "day": game_today(state), "turn": turn, "reason": reason}
    director["active"] = picked
    director["last_event_turn"] = turn
    director["last_npc"] = who or director.get("last_npc", "")
    if eid == "hidden_clue":
        director["last_place_count"] = discovered
    director["history"] = (history + [dict(picked)])[-24:]
    _instance(state, eid, context=picked)["context"] = dict(picked)
    return picked


def active_events(state: dict) -> list[str]:
    scheduled = scheduled_for(state)
    if scheduled:
        return [eid for eid in scheduled if _instance(state, eid)["status"] not in FINAL_STATUSES]
    if int(state.get("turn", 0)) == 0:
        return []
    active = _director_context(state) or _director_pick(state)
    return [active["id"]] if active and _instance(state, active["id"])["status"] not in FINAL_STATUSES else []


def _options(ev: dict) -> list[dict]:
    options = [dict(o) for o in ev["options"]]
    if ev.get("cat") == "关系":
        return options  # 私人邀约没有主办方，不能附加赞助、主持、来宾等公共活动操作。
    ids = {o["id"] for o in options}
    common = [
        {"id": "prepare", "label": "提前准备与了解规则", "req": None, "preparation": True,
         "win": {"text": "你核对日程和要求，准备了需要的材料。正式参与时，这份准备会帮助你。"}},
        {"id": "sponsor", "label": "出资赞助（30华夏币）", "req": None, "cost": 30,
         "win": {"text": "你把赞助预算和用途写清，主办方确认到账后记下了这次支持。赞助没有替你赢得比赛，也没有购买任何人的感情。", "fame_any": 2}},
        {"id": "host", "label": "报名承担现场主持", "req": ("speech", 2),
         "win": {"text": "你按流程稳住现场，把时间留给了每位参与者。主办方愿意下次再联系你。", "xp": ("speech", 25), "gold": 15},
         "half": {"text": "串场略显生涩，你在志愿者帮助下完成了工作。", "xp": ("speech", 12)},
         "lose": {"text": "你还不足以独立主持，主办方请有经验的人接手，你转到台下学习。", "xp": ("speech", 6)}},
        {"id": "network", "label": "作为来宾交流", "req": None,
         "win": {"text": "你和在场的人交换了近况，认真听完他们正在做的事。联系可以继续，合作还需要以后的实际行动。", "xp": ("speech", 8)}},
        {"id": "watch", "label": "在场旁观，轻松体验", "req": None,
         "win": {"text": "你安静看完了活动，没有给自己加任务。别人的努力和这一天的气氛也值得记住。"}},
        {"id": "ignore", "label": "按自己的安排度过今天", "req": None,
         "win": {"text": "你选择继续自己的生活。活动照常进行，下次是否参加仍由你决定。"}},
    ]
    return options + [o for o in common if o["id"] not in ids]


def event_today(state: dict) -> dict | None:
    ids = active_events(state)
    if not ids:
        return None
    eid = ids[0]
    ev = _EVENTS[eid]
    instance = _instance(state, eid)
    ctx = instance.get("context") or _director_context(state, eid)
    return {"id": eid, "instance_id": instance["id"], "status": instance["status"],
        "name": _format_event(ev["name"], ctx), "cat": ev["cat"],
        "desc": _format_event(ev["desc"], ctx), "reason": (ctx or {}).get("reason", "日历中的公开活动，可自行选择是否参加"),
        "preparation": instance["preparation"],
        "options": [{"id": o["id"], "label": _format_event(o["label"], ctx),
                     "need": f"{sk.SKILLS[o['req'][0]][0]}≥L{o['req'][1]}" if o.get("req") else "",
                     "cost": int(o.get("cost", 0))}
                    for o in _options(ev) if not (o.get("preparation") and instance["preparation"])]}


def events_view(state: dict) -> dict:
    st = _event_state(state)
    return {"today": event_today(state), "history": [dict(x) for x in st["history"][-40:]],
            "experience": [dict(x) for x in st["experience"][-40:]],
            "instances": [dict(x) for x in st["instances"].values()][-80:], "template_count": len(_EVENTS)}


def on_new_day(state: dict) -> str:
    st = _event_state(state)
    ev = event_today(state)
    st["today"] = ev["id"] if ev else None
    if ev and st.get("notified_day") != game_today(state):
        st["notified_day"] = game_today(state)
        state["inbox"] = (state.get("inbox") or [])[-49:] + [{"ts": now_iso(), "type": "event", "world": WORLD_URBAN,
            "title": f"今日活动 · {ev['name']}", "text": f"{ev['desc']}（是否参加由你决定）"}]
    return f"【系统】今日活动：{ev['name']}——{ev['desc']}" if ev else ""


def action_label(state: dict, action: str) -> str | None:
    if not action.startswith(PREFIX):
        return None
    eid, _, oid = action[len(PREFIX):].partition(":")
    ev = _EVENTS.get(eid)
    if not ev:
        return None
    opt = next((o for o in _options(ev) if o["id"] == oid), None)
    ctx = _instance(state, eid).get("context") or _director_context(state, eid)
    return f"{ev['name']}·{_format_event(opt['label'], ctx)}" if opt else ev["name"]


def resolve_action(state: dict, text: str) -> str | None:
    """仅路由明确参加当前活动的意图，问询、计划和否定不冒充参与。"""
    import re
    if text.startswith(PREFIX):
        return text
    if re.search(r"(?:不参加|不去|不报名|别去|不要|以后|明天|打算|计划|想了解|问问|能否|能不能|可以吗|怎么|如何|[？?])", text):
        return None
    ev = event_today(state)
    if not ev or not (ev["name"] in text or "今天活动" in text or "当前活动" in text):
        return None
    mapping = (("prepare", ("准备", "了解规则")), ("sponsor", ("赞助", "出资")),
               ("host", ("主持",)), ("network", ("社交", "交流", "来宾")),
               ("watch", ("旁观", "观众", "看热闹", "观看")), ("ignore", ("忽略", "放弃")))
    for oid, words in mapping:
        if any(word in text for word in words) and any(o["id"] == oid for o in ev["options"]):
            return f"{PREFIX}{ev['id']}:{oid}"
    for option in ev["options"]:
        if option["label"] in text:
            return f"{PREFIX}{ev['id']}:{option['id']}"
    if re.search(r"参加|报名|登台|上台|参赛|表演", text):
        return f"{PREFIX}{ev['id']}:{ev['options'][0]['id']}"
    return None


def _record_end(state: dict, instance: dict, role: str, outcome: str, text: str) -> None:
    ev = _EVENTS[instance["template"]]
    instance.update(status="ignored" if role == "ignore" else "expired" if role == "absent" else "completed",
                    role=role, outcome=outcome, result=text)
    st = _event_state(state)
    record = {"id": instance["id"], "template": instance["template"], "day": instance["day"],
              "name": ev["name"], "domain": ev["cat"], "role": role, "outcome": outcome,
              "preparation": instance.get("preparation", 0), "npcs": list(dict.fromkeys(list(ev.get("npcs", [])) + ([instance["context"]["npc"]] if (instance.get("context") or {}).get("npc") else []))),
              "result": text, "world_result": ev.get("world_result", f"{ev['name']}按日程结束，参与者带着各自的结果继续生活。"),
              "followups": [ev["followup"]] if ev.get("followup") and outcome == "win" else []}
    st["history"].append(dict(record))
    if role not in ("ignore", "absent"):
        st["experience"].append(dict(record))
    # 历史结果持久保留，导演只读取近期片段，避免遗忘早先事业缘起。


def settle_elapsed(state: dict, from_day: int, to_day: int) -> list[str]:
    """结算跨过的公开活动；不参加也有世界结果，不给玩家发奖金或强加损失。"""
    from .models import GAME_EPOCH
    st = _event_state(state)
    start = max(1, int(from_day), int(st.get("settled_through_day", 0)) + 1)
    end = max(start, int(to_day))
    expired = []
    for number in range(start, end):
        day = (GAME_EPOCH + timedelta(days=number - 1)).isoformat()
        for eid in _scheduled_on(date.fromisoformat(day)):
            _instance(state, eid, day)
    end_iso = (GAME_EPOCH + timedelta(days=max(1, int(to_day)) - 1)).isoformat()
    for instance in list(st["instances"].values()):
        if instance.get("day", end_iso) < end_iso and instance.get("status") not in FINAL_STATUSES:
            _record_end(state, instance, "absent", "world", _EVENTS[instance["template"]].get("world_result", "活动如期结束，参与者按各自安排继续生活。"))
            expired.append(instance)
    st["settled_through_day"] = max(int(st.get("settled_through_day", 0)), int(to_day) - 1)
    if expired:
        state["inbox"] = (state.get("inbox") or [])[-49:] + [{"ts": now_iso(), "type": "event", "world": WORLD_URBAN,
            "title": "城市近况", "text": f"这段时间有{len(expired)}场公开活动如期结束。你可以在活动经历里查看结果，未参加的活动不会记成你的成绩。"}]
        return [f"【世界】{len(expired)}场活动按各自日程结束，相关结果已记录。"]
    return []


def before_turn(state: dict, action: str) -> dict | None:
    if not action.startswith(PREFIX):
        return None
    eid, _, oid = action[len(PREFIX):].partition(":")
    ev = _EVENTS.get(eid)
    if ev is None:
        raise ValueError("没有这个活动。")
    instance = _instance(state, eid)
    if instance["status"] in FINAL_STATUSES:
        raise ValueError(f"「{ev['name']}」这一场已经结束，不能重复参加或领取报酬。")
    if eid not in active_events(state):
        raise ValueError(f"「{ev['name']}」今日不在活动表内。")
    opt = next((o for o in _options(ev) if o["id"] == oid), None)
    if opt is None:
        raise ValueError("没有这个参与方式。")
    ctx = instance.get("context") or _director_context(state, eid)
    if ev.get("dynamic_npc") and not (ctx and ctx.get("npc")):
        raise ValueError("这场邂逅已经散场。")
    if opt.get("preparation"):
        if instance["preparation"]:
            raise ValueError("这场活动已经准备过了。")
        instance["preparation"] = 1
        instance["status"] = "prepared"
        return {"story_text": opt["win"]["text"], "narration_world": "urban",
                "choices": [f"{PREFIX}{eid}:{o['id']}" for o in _options(ev)[:3] if o['id'] != 'prepare'],
                "state_updates": {"duration_minutes": 60}, "system_notice": "", "_notices": []}
    from .engine import _apply_items, _remove_items, npc_remember
    from .models import CASH
    from .shop import currency_count
    cost = int(opt.get("cost", 0))
    if cost and currency_count(state, currency=CASH) < cost:
        raise ValueError(f"这次参与需要{cost}华夏币，当前现金不足。")
    result_key = "win"
    if opt.get("req"):
        sid, diff = opt["req"]
        effective = sk.level(state, sid) + sk.attr_bonus(state, sid) + int(instance.get("preparation", 0))
        result_key = "win" if effective >= diff else "half" if effective == diff - 1 else "lose"
    # 无对应失败文本也不升级成获胜；用最相近的较低结果承接。
    res = opt.get(result_key)
    if not res:
        res = opt.get("lose") if result_key == "lose" else opt.get("half")
        res = res or {"text": "你尝试了这件事，但还未达到要求。下一次可以准备得更充分。"}
    notices = []
    if cost:
        _remove_items(state, CASH, cost)
        notices.append(f"【活动】{'赞助' if oid == 'sponsor' else '参与'}支出：华夏币 -{cost}。")
    if res.get("xp"):
        notices.extend(sk.add_xp(state, *res["xp"]))
    if res.get("xp_any"):
        notices.extend(sk.add_xp(state, _top_skill(state)[0], int(res["xp_any"])))
    if res.get("gold"):
        _apply_items(state, [{"name": CASH, "desc": "现实现金", "count": int(res["gold"])}])
        notices.append(f"【活动】现实报酬：华夏币 +{res['gold']}。")
    from . import career, memory
    if res.get("fame"):
        career.add_fame(state, *res["fame"])
        notices.append(f"【系统】{res['fame'][0]}名望 +{res['fame'][1]}。")
    if res.get("fame_any"):
        career.add_fame(state, career.ensure_career(state).get("domain") or "商业", int(res["fame_any"]))
    if res.get("opp") and career.give_opportunity(state, res["opp"]):
        notices.append(f"【系统】获得机遇：「{res['opp']}」。")
    target = find_npc(state, (ctx or {}).get("npc", ""))
    if target is None:
        target = next((n for name in ev.get("npcs", [])[:2] if (n := find_npc(state, name)) and n.get("known_to_player")), None)
    if target and oid not in ("ignore", "sponsor"):
        if res.get("memo"):
            npc_remember(target, state.get("turn", 0), str(res["memo"]))
    if res.get("fact"):
        memory.append_fact(state, _format_event(res["fact"], ctx), state.get("turn", 0), known_by=[target["name"]] if target else [])
    if result_key in ("win", "half") and oid not in ("ignore", "sponsor"):
        for name in ev.get("npcs", [])[:2]:
            if (npc := find_npc(state, name)) and npc.get("known_to_player"):
                npc_remember(npc, state.get("turn", 0), "和你一起完成了这场活动，印象深刻")
    story = _format_event(res["text"], ctx)
    _record_end(state, instance, oid, result_key, story)
    if res.get("opp"):
        _event_state(state)["history"][-1]["opportunity"] = res["opp"]
        if _event_state(state)["experience"]:
            _event_state(state)["experience"][-1]["opportunity"] = res["opp"]
    _event_state(state)["last_join_turn"] = int(state.get("turn", 0))
    active = _director_state(state).get("active")
    if isinstance(active, dict) and active.get("id") == eid:
        _director_state(state)["active"] = None
    return {"story_text": f"{_format_event(ev['desc'], ctx)}\n\n{story}", "narration_world": "urban",
            "choices": ["继续今天的行程", "联系今天认识的人", "回去休息，整理这次经历"],
            "state_updates": {"duration_minutes": 120 if oid not in ("ignore", "network") else 15 if oid == "ignore" else 60},
            "system_notice": "", "_notices": notices}
