import http from 'k6/http';
import { check, sleep } from 'k6';

// ── Configuration ─────────────────────────────────────────────
export const options = {
    scenarios: {
        regular_users: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '10s', target: 20 },
                { duration: '30s', target: 20 },
                { duration: '10s', target: 0 },
            ],
            exec: 'regularUserFlow',
        },
        agent_users: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '10s', target: 5 },
                { duration: '30s', target: 5 },
                { duration: '10s', target: 0 },
            ],
            exec: 'agentUserFlow',
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<500'],   // 95% of requests must complete in < 500ms
        checks: ['rate>0.90'],              // 90%+ checks must pass
    },
};

const BASE_URL = 'http://localhost:8000';

// ── Seed accounts (created by seed_loadtest_users.py) ─────────
const LOAD_TEST_USERS = [
    { email: 'loadtest1@autoclaim.com', password: 'loadtest123' },
    { email: 'loadtest2@autoclaim.com', password: 'loadtest123' },
    { email: 'loadtest3@autoclaim.com', password: 'loadtest123' },
    { email: 'loadtest4@autoclaim.com', password: 'loadtest123' },
    { email: 'loadtest5@autoclaim.com', password: 'loadtest123' },
];

const AGENT_CREDS = { email: 'loadtest_agent@autoclaim.com', password: 'loadtest123' };

function getRandomUser() {
    return LOAD_TEST_USERS[Math.floor(Math.random() * LOAD_TEST_USERS.length)];
}

// ── Helper: Login and return auth headers ─────────────────────
function login(email, password, label) {
    // FastAPI OAuth2PasswordRequestForm expects form-encoded with 'username' field
    const res = http.post(`${BASE_URL}/login`, {
        username: email,
        password: password,
    }, { tags: { name: label } });

    const ok = check(res, {
        [`${label} status 200`]: (r) => r.status === 200,
    });

    if (ok && res.status === 200) {
        const token = res.json('access_token');
        return { Authorization: `Bearer ${token}` };
    }
    return null;
}

// ── Regular User Flow ─────────────────────────────────────────
export function regularUserFlow() {
    const creds = getRandomUser();
    const headers = login(creds.email, creds.password, 'login [user]');
    if (!headers) return; // skip iteration if login failed

    const params = { headers };

    // Weighted random task selection (total weight = 11)
    const actions = [
        { weight: 5, fn: () => {
            // GET /claims/my — list own claims
            const r = http.get(`${BASE_URL}/claims/my`, params);
            check(r, { 'GET /claims/my (200)': (r) => r.status === 200 });
        }},
        { weight: 3, fn: () => {
            // GET /notifications/my — poll notifications
            const r = http.get(`${BASE_URL}/notifications/my`, params);
            check(r, { 'GET /notifications/my (200)': (r) => r.status === 200 });
        }},
        { weight: 2, fn: () => {
            // GET /wallet/me — check wallet balance
            const r = http.get(`${BASE_URL}/wallet/me`, params);
            check(r, { 'GET /wallet/me (200)': (r) => r.status === 200 });
        }},
        { weight: 1, fn: () => {
            // GET /me — fetch profile
            const r = http.get(`${BASE_URL}/me`, params);
            check(r, { 'GET /me (200)': (r) => r.status === 200 });
        }},
    ];

    const totalWeight = actions.reduce((sum, a) => sum + a.weight, 0);
    const rand = Math.random() * totalWeight;
    let cumulative = 0;
    for (const action of actions) {
        cumulative += action.weight;
        if (rand < cumulative) {
            action.fn();
            break;
        }
    }

    // Think time: 1–3 seconds
    sleep(Math.random() * 2 + 1);
}

// ── Agent User Flow ───────────────────────────────────────────
export function agentUserFlow() {
    const headers = login(AGENT_CREDS.email, AGENT_CREDS.password, 'login [agent]');
    if (!headers) return;

    const params = { headers };

    // Weighted random task selection (total weight = 5)
    const rand = Math.random() * 5;

    if (rand < 4) {
        // GET /claims/all — agent views assigned claims
        const r = http.get(`${BASE_URL}/claims/all`, params);
        check(r, { 'GET /claims/all [agent] (200)': (r) => r.status === 200 });
    } else {
        // GET /notifications/my — agent polls notifications
        const r = http.get(`${BASE_URL}/notifications/my`, params);
        check(r, { 'GET /notifications/my [agent] (200)': (r) => r.status === 200 });
    }

    // Think time: 2–5 seconds
    sleep(Math.random() * 3 + 2);
}
