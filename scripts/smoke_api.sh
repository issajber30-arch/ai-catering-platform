#!/usr/bin/env bash
# End-to-end regression smoke test against a running server (default: local dev).
# Usage: scripts/smoke_api.sh [base_url]   Needs curl + jq, and dev seed data:
# a per_tray dish 22222222-... (₪120) and an active pickup slot 33333333-... (any weekday).
# Creates one throwaway draft order per run; touches nothing else.
set -uo pipefail
B="${1:-http://127.0.0.1:8000}"
DISH=22222222-2222-2222-2222-222222222222
SLOT=33333333-3333-3333-3333-333333333333
pass=0; fail=0
check() { # name, expected, actual
  if [[ "$2" == "$3" ]]; then pass=$((pass+1)); echo "  ok   $1"
  else fail=$((fail+1)); echo "  FAIL $1 (expected '$2', got '$3')"; fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
day() { date -v+"$1"d +%F 2>/dev/null || date -d "+$1 days" +%F; }
order_body() { # date
  jq -n --arg d "$1" --arg s "$SLOT" '{customer:{full_name:"Smoke Test",phone:"0500000000"},
    event:{event_type:"birthday",event_date:$d,adults:40,children:10,vegetarian_guests:8},
    fulfillment_type:"pickup",time_slot_id:$s}'
}

echo "Phase 1-2: health, catalog, admin guard"
check "health"                200 "$(code "$B/health")"
check "customer page"         200 "$(code "$B/customer/")"
check "admin page"            200 "$(code "$B/admin/")"
check "catalog categories"    200 "$(code "$B/api/catalog/categories")"
check "catalog dishes"        200 "$(code "$B/api/catalog/dishes?lang=en")"
check "availability"          200 "$(code "$B/api/availability")"
check "admin needs login"     401 "$(code "$B/api/admin/orders")"
check "admin settings guard"  401 "$(code "$B/api/admin/settings")"

echo "Phase 3.1: public rules"
S=$(curl -s "$B/api/public-settings")
check "lead time is 7 days"   7 "$(jq -r .lead_time_days <<<"$S")"
check "food minimum 500"      500.00 "$(jq -r .min_food_total <<<"$S")"
check "address too long"      422 "$(code -G "$B/api/delivery-quote" --data-urlencode "address=$(printf 'a%.0s' {1..501})")"
Q=$(curl -s -G "$B/api/delivery-quote" --data-urlencode "address=יפו 97, ירושלים")
check "jerusalem address found" true "$(jq -r .found <<<"$Q")"
Q=$(curl -s -G "$B/api/delivery-quote" --data-urlencode "address=הרצל 1, תל אביב")
check "tel aviv is too far"   true "$(jq -r .too_far <<<"$Q")"

echo "Phase 3: order lifecycle"
check "6 days out refused"    422 "$(code -X POST "$B/api/orders" -H 'Content-Type: application/json' -d "$(order_body "$(day 6)")")"
R=$(curl -s -X POST "$B/api/orders" -H 'Content-Type: application/json' -d "$(order_body "$(day 14)")")
ID=$(jq -r .id <<<"$R"); T=$(jq -r .access_token <<<"$R")
check "draft created"         draft "$(jq -r .status <<<"$R")"
check "no token is 404"       404 "$(code "$B/api/orders/$ID")"
check "wrong token is 404"    404 "$(code -H 'X-Order-Token: nope' "$B/api/orders/$ID")"
H=(-H "X-Order-Token: $T" -H 'Content-Type: application/json')
R=$(curl -s -X PUT "$B/api/orders/$ID/items/$DISH" "${H[@]}" -d '{"quantity":2,"version":1}')
check "2 trays = 240.00"      240.00 "$(jq -r .subtotal <<<"$R")"
check "stale version 409"     order_version_conflict "$(curl -s -X PUT "$B/api/orders/$ID/items/$DISH" "${H[@]}" -d '{"quantity":3,"version":1}' | jq -r .error.code)"
check "below minimum refused" 422 "$(code -X POST "$B/api/orders/$ID/submit" "${H[@]}" -d '{"version":2}')"
check "recommendations"       200 "$(code -H "X-Order-Token: $T" "$B/api/orders/$ID/recommendations")"
R=$(curl -s -X PUT "$B/api/orders/$ID/items/$DISH" "${H[@]}" -d '{"quantity":5,"version":2}')
check "5 trays = 600.00"      600.00 "$(jq -r .subtotal <<<"$R")"
R=$(curl -s -X POST "$B/api/orders/$ID/submit" "${H[@]}" -d '{"version":3}')
check "submitted"             pending_approval "$(jq -r .status <<<"$R")"
check "edit after submit 409" invalid_transition "$(curl -s -X DELETE "$B/api/orders/$ID/items/$DISH?version=4" "${H[@]}" | jq -r .error.code)"

echo "$pass passed, $fail failed"
exit $((fail > 0))
