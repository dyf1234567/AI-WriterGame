"""现实事业的跨领域、经营实体与长时段结算回归；不读写正式存档。"""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import career, enterprises, skills
from app.models import CASH, CURRENCY, default_state, normalize_state


def cash(state, amount):
    item = next((i for i in state["player"]["items"] if i["name"] == CASH), None)
    if item:
        item["count"] = amount
    else:
        state["player"]["items"].append({"name": CASH, "desc": "现实资金", "count": amount})


def enter(state, domain):
    career.give_opportunity(state, career.ENTRY_OPPORTUNITIES[domain])
    return career.before_turn(state, f"【事业】入门 {domain}")


class SandboxCareerTest(unittest.TestCase):
    def test_parallel_domains_and_projects_survive_switching(self):
        state = default_state("跨界")
        cash(state, 3000)
        for domain in career.DOMAINS:
            enter(state, domain)
            skills.add_xp(state, {"娱乐": "vocal", "电竞": "mech", "商业": "manage"}[domain], 600)
            project = next(iter(career.PROJECTS[domain]))
            self.assertTrue(career.start_project(state, project)[0])
        cv = career.career_view(state)
        self.assertEqual(set(cv["positions"]), set(career.DOMAINS))
        self.assertEqual(len(cv["active_projects"]), 3)
        career.before_turn(state, "【事业】切换 娱乐")
        career.before_turn(state, "【事业】职业 演员")
        self.assertEqual(career.ensure_career(state)["positions"]["娱乐"]["roles"], ["歌手", "演员"])
        self.assertFalse(career.start_project(state, "single")[0])
        state["time"]["day"] = 15
        career.settle_until(state, 1, 15)
        self.assertTrue(all(p["status"] == "completed" for p in state["player"]["career"]["projects"]))
        self.assertEqual(len(career.career_view(state)["all_positions"]), 3)

    def test_first_day_company_and_team_require_cash_not_system_points(self):
        state = default_state("创业")
        cash(state, 200)
        points = next(i["count"] for i in state["player"]["items"] if i["name"] == CURRENCY)
        result = career.before_turn(state, "【事业】创办 校园工作室")
        self.assertEqual(state["time"]["day"], 1)
        self.assertEqual(skills.level(state, "manage"), 0)
        self.assertEqual(career.cash_count(state), 0)
        self.assertEqual(result["state_updates"]["duration_minutes"], 60)
        self.assertEqual(next(i["count"] for i in state["player"]["items"] if i["name"] == CURRENCY), points)
        company = enterprises.find(state, "", "company")
        self.assertEqual(company["equity"], {"player": 100, "external": 0})
        self.assertEqual(company["cash"], 150)
        with self.assertRaises(ValueError):
            career.before_turn(state, "【事业】收购战队")
        cash(state, 800)
        career.before_turn(state, "【事业】收购战队 校园战队")
        self.assertEqual(career.cash_count(state), 0)
        self.assertEqual(len(enterprises.find(state, "", "team")["roster"]), 6)
        self.assertEqual(set(state["player"]["career"]["positions"]), {"商业", "电竞"})

    def test_28_day_jump_pays_four_weeks_and_is_idempotent(self):
        state = default_state("工资")
        enter(state, "娱乐")
        before = career.cash_count(state)
        state["time"]["day"] = 29
        notices = career.settle_until(state, 1, 29)
        self.assertEqual(career.cash_count(state)-before, 4*40)
        self.assertEqual(sum("周结算" in n for n in notices), 4)
        after = deepcopy(state)
        self.assertEqual(career.settle_until(state, 1, 29), [])
        self.assertEqual(state, after)

    def test_legacy_week_api_also_backfills_missing_weeks(self):
        state = default_state("周键")
        enter(state, "电竞")
        career.settle_week(state, "2026-W35")
        before = career.cash_count(state)
        notices = career.settle_week(state, "2026-W39")
        self.assertEqual(career.cash_count(state)-before, 4*35)
        self.assertEqual(sum("周结算" in n for n in notices), 4)
        self.assertEqual(career.settle_week(state, "2026-W39"), [])

    def test_project_delivery_uses_due_day_and_creates_releasable_work(self):
        state = default_state("作品")
        cash(state, 1000)
        enter(state, "娱乐")
        skills.add_xp(state, "vocal", 800)
        self.assertTrue(career.start_project(state, "single")[0])
        state["time"]["day"] = 29
        career.settle_until(state, 1, 29)
        project = state["player"]["career"]["projects"][0]
        self.assertEqual(project["completed_day"], 15)
        work = enterprises.find(state, project["work_id"], "work")
        self.assertEqual(work["created_day"], 15)
        self.assertEqual(work["status"], "ready")
        self.assertTrue(enterprises.release_work(state, work["id"], "流媒体")[0])
        self.assertGreater(work["audience"], 0)
        self.assertGreater(work["sales"], 0)
        settled_cash = career.cash_count(state)
        self.assertFalse(enterprises.release_work(state, work["id"], "网络")[0])
        self.assertEqual(career.cash_count(state), settled_cash)

    def test_equity_is_conserved_and_finance_is_business_cash(self):
        state = default_state("股权")
        cash(state, 2000)
        career.before_turn(state, "【事业】创办 星河传媒")
        company = enterprises.find(state, "", "company")
        player_cash, business_cash = career.cash_count(state), company["cash"]
        self.assertTrue(enterprises.finance(state, company["id"], 49)[0])
        self.assertEqual(career.cash_count(state), player_cash)
        self.assertEqual(company["cash"], business_cash+98)
        self.assertTrue(enterprises.finance(state, company["id"], 49)[0])
        self.assertFalse(enterprises.finance(state, company["id"], 2)[0])
        self.assertEqual(sum(company["equity"].values()), 100)
        self.assertTrue(enterprises.buy_equity(state, company["id"], 98)[0])
        self.assertEqual(company["equity"], {"player": 100, "external": 0})
        self.assertFalse(enterprises.buy_equity(state, company["id"], 1)[0])

    def test_repeat_project_asset_does_not_create_more_shares(self):
        state = default_state("奖励股权")
        spec = career.PROJECTS["电竞"]["league"]["asset"]
        first, is_new = enterprises.award_asset(state, spec, "project:电竞:league", "电竞")
        second, second_new = enterprises.award_asset(state, spec, "project:电竞:league", "电竞")
        self.assertTrue(is_new)
        self.assertFalse(second_new)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["equity"]["player"], 5)
        self.assertEqual(len(state["player"]["assets"]), 1)

    def test_pricing_changes_customer_demand_and_cashflow_is_idempotent(self):
        base = default_state("经营")
        cash(base, 3000)
        career.before_turn(base, "【事业】创办 定价实验公司")
        low, high = deepcopy(base), deepcopy(base)
        enterprises.set_price(low, "", 10)
        enterprises.set_price(high, "", 60)
        for state in (low, high):
            state["time"]["day"] = 8
            career.settle_until(state, 1, 8)
        low_company, high_company = enterprises.find(low, "", "company"), enterprises.find(high, "", "company")
        self.assertGreater(low_company["customers"], high_company["customers"])
        self.assertNotEqual(low_company["profit"], high_company["profit"])
        count = len(high_company["ledger"])
        enterprises.settle_day(high, 8)
        self.assertEqual(len(high_company["ledger"]), count)

    def test_roster_matches_and_training_have_persistent_results(self):
        state = default_state("战队")
        cash(state, 3000)
        career.before_turn(state, "【事业】收购战队 新星")
        team = enterprises.find(state, "", "team")
        self.assertFalse(enterprises.set_lineup(state, team["id"], ["member_1"]*5)[0])
        self.assertTrue(enterprises.set_lineup(state, team["id"], [f"member_{i}" for i in range(2,7)])[0])
        previous = team["roster"][0]["ability"]
        career.before_turn(state, "【事业】经营 培训")
        self.assertEqual(team["roster"][0]["ability"], previous+3)
        self.assertTrue(enterprises.team_match(state, team["id"])[0])
        before = career.cash_count(state)
        self.assertFalse(enterprises.team_match(state, team["id"])[0])
        self.assertEqual(career.cash_count(state), before)
        self.assertEqual(team["matches"], 1)

    def test_delegated_team_reinvests_but_keeps_living_reserve(self):
        state = default_state("委托")
        cash(state, 3000)
        enter(state, "娱乐")
        skills.add_xp(state, "vocal", 700)
        with self.assertRaises(ValueError):
            career.before_turn(state, "【事业】委托")
        career.before_turn(state, "【事业】经营 招聘 阿宁")
        career.before_turn(state, "【事业】委托")
        state["time"]["day"] = 29
        career.settle_until(state, 1, 29)
        projects = state["player"]["career"]["projects"]
        self.assertTrue(any(p["status"] == "completed" for p in projects))
        self.assertTrue(any(p["status"] == "active" for p in projects))
        self.assertGreaterEqual(career.cash_count(state), 50)
        self.assertEqual(state["player"]["career"]["positions"]["娱乐"]["employees"][0]["name"], "阿宁")

    def test_old_career_and_assets_survive_normalization(self):
        state = default_state("旧档")
        state["player"]["career"] = {"domain": "电竞", "stage": 3,
            "ops": {"staff": 1, "quality": 2, "marketing": 1}, "projects": []}
        state["player"]["assets"] = [{"name": "旧合约", "type": "合约", "weekly": 10}]
        normalize_state(state)
        c = career.ensure_career(state)
        self.assertEqual(c["positions"]["电竞"]["stage"], 3)
        self.assertEqual(c["ops"]["quality"], 2)
        before = career.cash_count(state)
        state["time"]["day"] = 29
        career.settle_until(state, 1, 29)
        self.assertEqual(career.cash_count(state)-before, 4*(260-15+10))

    def test_training_returns_duration_without_mutating_clock(self):
        state = default_state("训练")
        enter(state, "娱乐")
        time = deepcopy(state["time"])
        result = career.before_turn(state, "【事业】特训")
        self.assertEqual(result["state_updates"]["duration_minutes"], 120)
        self.assertEqual(state["time"], time)

    def test_role_label_cannot_create_a_salary_contract(self):
        state = default_state("身份")
        cash(state, 200)
        career.before_turn(state, "【事业】创办 星河传媒")
        career.before_turn(state, "【事业】职业 歌手")
        state["time"]["day"] = 8
        notices = career.settle_until(state, 1, 8)
        self.assertFalse(any("日工资" in n for n in notices))
        self.assertEqual(career.career_view(state)["weekly_income"], 0)

    def test_minority_shareholder_cannot_change_company_decisions(self):
        state = default_state("股东")
        cash(state, 1000)
        career.before_turn(state, "【事业】创办 控股公司")
        company = enterprises.find(state, "", "company")
        enterprises.finance(state, company["id"], 49)
        self.assertTrue(enterprises.set_price(state, company["id"], 25)[0])
        enterprises.finance(state, company["id"], 2)
        self.assertFalse(enterprises.set_price(state, company["id"], 30)[0])

    def test_legacy_equity_migrates_without_duplicating_asset_value(self):
        state = default_state("股份旧档")
        state["player"]["assets"] = [{"name": "旧战队 10% 股份", "type": "战队股份", "value": 800, "weekly": 40}]
        career.ensure_career(state)
        team = enterprises.find(state, "", "team")
        self.assertIsNotNone(team)
        self.assertEqual(team["equity"]["player"], 10)
        self.assertEqual(team["valuation"], 8000)
        self.assertEqual(len(state["player"]["assets"]), 1)
        self.assertEqual(state["player"]["assets"][0]["entity_id"], team["id"])
        self.assertEqual(state["player"]["assets"][0]["weekly"], 0)
        career.ensure_career(state)
        self.assertEqual(len(state["player"]["enterprises"]), 1)

    def test_same_day_refresh_settles_already_due_legacy_project(self):
        state = default_state("已到期")
        cash(state, 1000)
        enter(state, "娱乐")
        skills.add_xp(state, "vocal", 600)
        career.start_project(state, "single")
        state["time"]["day"] = 15
        state["player"]["career"]["settled_through"] = 15
        notices = career.settle_until(state, 15, 15)
        self.assertTrue(any("经营项目" in n for n in notices))
        self.assertEqual(state["player"]["career"]["projects"][0]["status"], "completed")
        self.assertEqual(career.settle_until(state, 15, 15), [])


if __name__ == "__main__":
    unittest.main()
