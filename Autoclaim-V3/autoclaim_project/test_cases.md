# Test Cases Document: Functional and Load Testing

## 1. Functional Testing

| Test Case ID | Module | Test Scenario | Preconditions | Steps to Execute | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FC-01** | Auth | Verify User Registration | API server is running | Send `POST /auth/register` with valid user details | HTTP status `201 Created` is returned. | Pass |
| **FC-02** | Auth | Verify User Login | User is registered | Send `POST /auth/login` with valid credentials | HTTP status `200 OK` is returned along with a JWT token. | Pass |
| **FC-03** | Claims | Verify robust Claim Submission | User is authenticated | Send `POST /claims` with valid claim payload and images | HTTP status `200 OK` is returned with a distinct `claim_id`. | Pass |
| **FC-04** | Claims | Verify fetching own claims list | User is authenticated | Send `GET /claims/my` | HTTP status `200 OK` is returned containing the user's claims list. | Pass |
| **FC-05** | Claims | Verify PDF Report generation | Claim ID exists | Send `GET /claims/{id}/report` | HTTP status `200 OK` is returned with a PDF stream download. | Pass |
| **FC-06** | Claims | Verify Claim Status update | Admin is authenticated | Send `PUT /claims/{id}/status` with valid status data | HTTP status `200 OK` is returned & notification is created. | Pass |
| **FC-07** | Claims | Verify manual Claim Analysis | Admin is authenticated | Send `POST /claims/{id}/analyze` | HTTP status `200 OK` is returned and AI analysis begins. | Pass |
| **FC-08** | Security| Verify Policyholder access limits | Policyholder is logged in | Send `GET /claims/all` using policyholder JWT token | HTTP status `403 Forbidden` is returned (access denied). | Pass |
| **FC-09** | Security| Verify Agent access limits | Agent is logged in | Send `POST /claims/{id}/analyze` (Admin-only endpoint) | HTTP status `403 Forbidden` is returned (access denied). | Pass |

***

## 2. Load Testing

| Test Case ID | Metric Tested | Test Scenario | Steps to Execute | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LT-01** | API Response Time | Verify endpoint latency during submission | 1. Send claim submission requests to `POST /claims`. <br>2. Measure the API returning time. | Response returns in **< 500 ms** (immediate response while processing runs in background). | Pass |
| **LT-02** | Background Processing | Verify AI pipeline duration per claim | 1. Submit a claim successfully. <br>2. Measure time taken for AI to finish processing it. | Complete processing takes **20-45 seconds** (if on GPU) or **90-180 seconds** (if on CPU). | Pass |
| **LT-03** | Database Integrity | Verify DB transaction locks on concurrent writes | 1. Submit **5 concurrent claim submissions** simultaneously. | All 5 claims save without database transaction conflicts or data loss. | Pass |
| **LT-04** | YOLO Threading | Verify Model thread safety | 1. Send concurrent image processing requests to YOLO. | Single instance is confirmed, model processes inferences sequentially safely. | Pass |
