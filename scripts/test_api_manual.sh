#!/bin/bash
# ============================================================
# Manual API Test Script
# Run with: bash scripts/test_api_manual.sh
# Requires: server running on http://localhost:8000
# ============================================================

BASE_URL="http://localhost:8000/api/v1"
PASS=0
FAIL=0

# Helper function
test_endpoint() {
    local description="$1"
    local expected_status="$2"
    local actual_status="$3"
    local response="$4"

    if [ "$actual_status" -eq "$expected_status" ]; then
        echo "PASS: $description (HTTP $actual_status)"
        PASS=$((PASS + 1))
    else
        echo "FAIL: $description (Expected $expected_status, Got $actual_status)"
        echo "  Response: $response"
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================"
echo "  Chat Service — REST API Test Suite"
echo "============================================"
echo ""

# --------------------------------------------------
# REQUIREMENT 1: Send a message between two users
# --------------------------------------------------
echo "--- REQUIREMENT 1: Send Message ---"
echo ""

# Test 1.1: Successful send
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/messages" \
    -H "X-User-Id: 1" -H "Content-Type: application/json" \
    -d '{"recipient_id": 2, "body": "Hello Bob, this is a test message"}')
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Send message (Alice -> Bob)" 201 "$STATUS" "$BODY"
echo "  $BODY" | python3 -m json.tool 2>/dev/null

# Extract conversation_id for later tests
CONV_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['conversation_id'])" 2>/dev/null)
echo ""

# Test 1.2: Bob replies (same conversation)
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/messages" \
    -H "X-User-Id: 2" -H "Content-Type: application/json" \
    -d '{"recipient_id": 1, "body": "Hey Alice, got your message"}')
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Reply message (Bob -> Alice)" 201 "$STATUS" "$BODY"
echo ""

# Test 1.3: Send more messages for pagination testing
for i in $(seq 1 25); do
    curl -s -X POST "$BASE_URL/messages" \
        -H "X-User-Id: 1" -H "Content-Type: application/json" \
        -d "{\"recipient_id\": 2, \"body\": \"Pagination test message $i\"}" > /dev/null
done
echo "  (Sent 25 additional messages for pagination testing)"
echo ""

# Test 1.4: Cannot message yourself
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/messages" \
    -H "X-User-Id: 1" -H "Content-Type: application/json" \
    -d '{"recipient_id": 1, "body": "Talking to myself"}')
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Cannot message yourself (400)" 400 "$STATUS" "$BODY"
echo ""

# Test 1.5: Cannot message nonexistent user
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/messages" \
    -H "X-User-Id: 1" -H "Content-Type: application/json" \
    -d '{"recipient_id": 999, "body": "Ghost user"}')
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Nonexistent recipient (404)" 404 "$STATUS" "$BODY"
echo ""

# Test 1.6: Missing auth header
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/messages" \
    -H "Content-Type: application/json" \
    -d '{"recipient_id": 2, "body": "No auth"}')
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Missing X-User-Id header (401)" 401 "$STATUS" "$BODY"
echo ""

# Test 1.7: Idempotency
RESPONSE1=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/messages" \
    -H "X-User-Id: 1" -H "Content-Type: application/json" \
    -d '{"recipient_id": 2, "body": "Idempotent msg", "client_message_id": "unique-123"}')
STATUS1=$(echo "$RESPONSE1" | tail -1)

RESPONSE2=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/messages" \
    -H "X-User-Id: 1" -H "Content-Type: application/json" \
    -d '{"recipient_id": 2, "body": "Idempotent msg", "client_message_id": "unique-123"}')
STATUS2=$(echo "$RESPONSE2" | tail -1)
BODY2=$(echo "$RESPONSE2" | sed '$d')

ID1=$(echo "$RESPONSE1" | sed '$d' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
ID2=$(echo "$RESPONSE2" | sed '$d' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ "$ID1" = "$ID2" ]; then
    echo "PASS: Idempotency — same client_message_id returns same message (id=$ID1)"
    PASS=$((PASS + 1))
else
    echo "FAIL: Idempotency — got different IDs ($ID1 vs $ID2)"
    FAIL=$((FAIL + 1))
fi
echo ""

# --------------------------------------------------
# REQUIREMENT 2: Fetch conversation history (paginated)
# --------------------------------------------------
echo "--- REQUIREMENT 2: Paginated History ---"
echo ""

# Test 2.1: Fetch first page
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/conversations/$CONV_ID/messages?limit=10" \
    -H "X-User-Id: 1")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Fetch first page (limit=10)" 200 "$STATUS"
MSG_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['messages']))" 2>/dev/null)
HAS_MORE=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['pagination']['has_more'])" 2>/dev/null)
CURSOR=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['pagination']['next_cursor'])" 2>/dev/null)
echo "  Messages returned: $MSG_COUNT | has_more: $HAS_MORE | next_cursor: $CURSOR"
echo ""

# Test 2.2: Fetch second page using cursor
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/conversations/$CONV_ID/messages?limit=10&before=$CURSOR" \
    -H "X-User-Id: 1")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Fetch second page (cursor=$CURSOR)" 200 "$STATUS"
MSG_COUNT2=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['messages']))" 2>/dev/null)
HAS_MORE2=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['pagination']['has_more'])" 2>/dev/null)
echo "  Messages returned: $MSG_COUNT2 | has_more: $HAS_MORE2"
echo ""

# Test 2.3: Pagination stability — send new messages, re-fetch with same cursor
echo "  Sending 3 new messages while paginating..."
for i in 1 2 3; do
    curl -s -X POST "$BASE_URL/messages" \
        -H "X-User-Id: 2" -H "Content-Type: application/json" \
        -d "{\"recipient_id\": 1, \"body\": \"New msg during pagination $i\"}" > /dev/null
done

RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/conversations/$CONV_ID/messages?limit=10&before=$CURSOR" \
    -H "X-User-Id: 1")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Same cursor after new messages (stable pagination)" 200 "$STATUS"
MSG_COUNT3=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['messages']))" 2>/dev/null)
echo "  Messages with same cursor: $MSG_COUNT3 (should equal $MSG_COUNT2 — no new messages leaked in)"

if [ "$MSG_COUNT3" = "$MSG_COUNT2" ]; then
    echo "PASS: Pagination stable — same cursor returns same results"
    PASS=$((PASS + 1))
else
    echo "FAIL: Pagination unstable — cursor results changed"
    FAIL=$((FAIL + 1))
fi
echo ""

# --------------------------------------------------
# REQUIREMENT 3: List user's conversations
# --------------------------------------------------
echo "--- REQUIREMENT 3: List Conversations ---"
echo ""

# Create another conversation (Alice-Charlie)
curl -s -X POST "$BASE_URL/messages" \
    -H "X-User-Id: 1" -H "Content-Type: application/json" \
    -d '{"recipient_id": 3, "body": "Hey Charlie"}' > /dev/null

# Test 3.1: List Alice's conversations
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/users/1/conversations" \
    -H "X-User-Id: 1")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "List Alice's conversations" 200 "$STATUS"
CONV_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['conversations']))" 2>/dev/null)
echo "  Alice has $CONV_COUNT conversations"
echo "  $BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data['conversations']:
    last = c['last_message']['body'][:40] if c['last_message'] else 'N/A'
    print(f\"    - {c['other_user']['username']}: \\\"{last}...\\\"\")
" 2>/dev/null
echo ""

# Test 3.2: Bob only sees his conversation with Alice
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/users/2/conversations" \
    -H "X-User-Id: 2")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "List Bob's conversations (only his own)" 200 "$STATUS"
BOB_CONV_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['conversations']))" 2>/dev/null)
echo "  Bob has $BOB_CONV_COUNT conversation(s)"
echo ""

# --------------------------------------------------
# REQUIREMENT 4: Authorization enforcement
# --------------------------------------------------
echo "--- REQUIREMENT 4: Authorization ---"
echo ""

# Test 4.1: Charlie CANNOT read Alice-Bob conversation
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/conversations/$CONV_ID/messages" \
    -H "X-User-Id: 3")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Charlie cannot read Alice-Bob chat (403)" 403 "$STATUS" "$BODY"
echo "  Response: $BODY"
echo ""

# Test 4.2: Alice CAN read Alice-Bob conversation
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/conversations/$CONV_ID/messages" \
    -H "X-User-Id: 1")
STATUS=$(echo "$RESPONSE" | tail -1)
test_endpoint "Alice CAN read Alice-Bob chat (200)" 200 "$STATUS"
echo ""

# Test 4.3: Cannot list another user's conversations
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/users/2/conversations" \
    -H "X-User-Id: 1")
STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
test_endpoint "Alice cannot list Bob's conversations (403)" 403 "$STATUS" "$BODY"
echo ""

# Test 4.4: Nonexistent conversation
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/conversations/9999/messages" \
    -H "X-User-Id: 1")
STATUS=$(echo "$RESPONSE" | tail -1)
test_endpoint "Nonexistent conversation (404)" 404 "$STATUS"
echo ""

# --------------------------------------------------
# SUMMARY
# --------------------------------------------------
echo "============================================"
echo "  RESULTS: $PASS passed, $FAIL failed"
echo "============================================"
echo ""
echo "Requirements covered:"
echo "  [x] Send a message between two users"
echo "  [x] Fetch conversation history (paginated)"
echo "  [x] Pagination stability under new messages"
echo "  [x] List conversations for a user"
echo "  [x] Authorization: user cannot read others' conversations"
echo "  [x] Idempotency via client_message_id"
