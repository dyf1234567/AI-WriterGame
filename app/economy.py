"""Two independent purses: everyday money and system-only points."""
from .models import CASH, CURRENCY


def balance(state: dict, currency: str = CASH) -> int:
    return sum(max(0, int(item.get("count", 0))) for item in
               state.get("player", {}).get("items", []) if item.get("name") == currency)


def debit(state: dict, amount: int, currency: str = CASH) -> bool:
    amount = max(0, int(amount))
    if balance(state, currency) < amount:
        return False
    remaining = amount
    items = state["player"].setdefault("items", [])
    for item in list(items):
        if item.get("name") != currency:
            continue
        used = min(remaining, max(0, int(item.get("count", 0))))
        item["count"] -= used
        remaining -= used
        if item["count"] <= 0:
            items.remove(item)
    return True


def credit(state: dict, amount: int, currency: str = CASH) -> None:
    amount = max(0, int(amount))
    if not amount:
        return
    items = state.setdefault("player", {}).setdefault("items", [])
    item = next((item for item in items if item.get("name") == currency), None)
    if item is None:
        item = {"name": currency, "count": 0,
                "desc": "现实生活、旅行与经营使用" if currency == CASH else "系统商城与成长奖励使用"}
        items.append(item)
    item["count"] = max(0, int(item.get("count", 0))) + amount


def ensure_wallets(state: dict) -> None:
    player = state.setdefault("player", {})
    items = player.setdefault("items", [])
    # Preserve every old system coin as one point; seed the new everyday purse once.
    for item in items:
        if item.get("name") in ("系统金币", "下品灵石"):
            item["name"] = CURRENCY
    for currency in (CASH, CURRENCY):
        matches = [item for item in items if item.get("name") == currency]
        if len(matches) > 1:
            matches[0]["count"] = sum(max(0, int(item.get("count", 0))) for item in matches)
            for item in matches[1:]:
                items.remove(item)
    if not player.get("wallets_version"):
        if not any(item.get("name") == CASH for item in items):
            credit(state, 200, CASH)
        player["wallets_version"] = 1


def wallets_view(state: dict) -> dict:
    return {"cash_name": CASH, "cash": balance(state, CASH),
            "points_name": CURRENCY, "points": balance(state, CURRENCY)}
