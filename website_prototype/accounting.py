"""
Per-event accounting.

Model (mirrors the club's existing trip-fee sheets):

- Every contribution has an amount. For a `driven_distance` contribution the
  amount is derived from the admin-configured distance formula (see
  formula.py and site_settings.distance_formula) evaluated at the km given,
  at the time it was recorded -- later formula changes don't retroactively
  change already-recorded contributions.
- If a contribution has no `consumed_by_ids`, its cost is shared evenly across
  every approved participant of the event (this is how a driver's distance
  cost turns into a per-person fee, while the driver's own payment still
  counts toward what they've "paid in" -- same mechanic as the Petrol/
  Distance/Maintenance-Credit columns on the paper sheets).
- If a contribution has `consumed_by_ids`, its full cost is split evenly
  across just that chosen subset of people (e.g. "cave access fee for
  Jasmine and Rowan" splits one fee between the two of them, not everyone).

For each participant:
    fee  = shared_pool / participant_count + sum(amounts consumed_by them)
    paid = sum(amounts they contributed)
    owe  = fee - paid   (positive = they owe the club/other participants,
                          negative = they are owed money back)
"""

from decimal import Decimal, ROUND_HALF_UP

import formula


def compute_contribution_amount(contribution_type: str, amount, km, distance_formula=None):
    """Returns (dollar_amount, effective_rate_per_km_or_None) for a
    contribution being recorded. `distance_formula` is required for
    driven_distance contributions -- see formula.py for what it supports."""
    if contribution_type == "driven_distance":
        if km is None:
            raise ValueError("km is required for driven_distance contributions")
        if not distance_formula:
            raise ValueError("a distance formula is required for driven_distance contributions")
        raw_amount = formula.evaluate(distance_formula, km)
        amount_decimal = Decimal(str(raw_amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        effective_rate = (amount_decimal / Decimal(str(km))) if km else Decimal("0")
        return amount_decimal, effective_rate.quantize(Decimal("0.001"))
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), None


def compute_event_accounting(participants, contributions):
    """
    participants: list of dicts with at least 'id' and 'name'
    contributions: list of dicts with 'contributor_id', 'consumed_by_ids' (a
    list of user ids, possibly empty), 'amount', and 'description'

    Returns a dict: {user_id: {"name", "fee", "paid", "owe",
                                "paid_items", "fee_items"}}
    "paid_items" and "fee_items" are lists of {"description", "amount"} that
    sum to "paid" and "fee" respectively -- the itemised breakdown behind
    each total.
    """
    participant_ids = [p["id"] for p in participants]
    count = len(participant_ids) or 1

    direct_fees = {uid: Decimal("0") for uid in participant_ids}
    paid = {uid: Decimal("0") for uid in participant_ids}
    paid_items = {uid: [] for uid in participant_ids}
    fee_items = {uid: [] for uid in participant_ids}
    shared_items = []  # each pooled contribution's own per-person share, listed individually

    for c in contributions:
        amount = Decimal(str(c["amount"]))
        contributor_id = c["contributor_id"]
        consumed_by_ids = c.get("consumed_by_ids") or []
        description = c.get("description") or "Contribution"
        paid_by = c.get("contributor_display_name") or c.get("contributor_name")

        if contributor_id in paid:
            paid[contributor_id] += amount
            paid_items[contributor_id].append({"description": description, "amount": amount, "paid_by": paid_by})

        if consumed_by_ids:
            share = (amount / len(consumed_by_ids)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for uid in consumed_by_ids:
                if uid in direct_fees:
                    direct_fees[uid] += share
                    fee_items[uid].append({"description": description, "amount": share, "paid_by": paid_by})
        else:
            per_person_share = (amount / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if per_person_share:
                shared_items.append({"description": f"Share of: {description}", "amount": per_person_share, "paid_by": paid_by})

    shared_total = sum((i["amount"] for i in shared_items), Decimal("0"))

    result = {}
    for p in participants:
        uid = p["id"]
        fee = shared_total + direct_fees.get(uid, Decimal("0"))
        paid_amount = paid.get(uid, Decimal("0"))
        owe = (fee - paid_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        items = shared_items + list(fee_items.get(uid, []))

        result[uid] = {
            "name": p["name"],
            "fee": fee,
            "paid": paid_amount,
            "owe": owe,
            "paid_items": paid_items.get(uid, []),
            "fee_items": items,
        }
    return result
