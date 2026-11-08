# SafeTrack security model

Scope: local backend/gateway implementation and software-generated P-256 signatures. Caching remains OFF. Hosted Supabase policies, network/TLS deployment and ATECC508A hardware signing have not been verified here. Security controls and their verification results are added below as implemented; this document is not a certification.

## Assets and trust boundaries

Assets: device credentials and signing keys; shipment assignments; sensor evidence, order and completeness; recipient information; operator accounts; durable queues and availability. Boundaries: sensors/firmware -> untrusted local network -> gateway -> HTTPS API -> PostgreSQL -> authenticated dashboard. The API, database owner and administrator are trusted for enrollment and authorization, but are potential adversaries for evidence retention.

| Attacker | Controls and purpose | Remaining exposure |
|---|---|---|
| Network attacker | Cloud HTTPS, enrolled P-256 signature verification, request identity checks and strict-device replay checks prevent altered or newly replayed signed readings | Can delay/drop traffic. Device-to-gateway acknowledgments are currently unauthenticated: a forged successful ACK can cause device queue deletion. TLS must be deployed correctly. |
| Stolen device | Per-device credential, shipment binding, revocation and rotation limit which identity/assignment can submit | A functioning stolen signer can sign false but valid readings. Secure boot, flash encryption, sensor substitution and physical extraction are not verified. |
| Compromised gateway | Backend independently verifies enrolled signatures; idempotency prevents duplicate stored events | Can withhold events, delete its queue, forge local ACKs, steal gateway credentials and expose metadata. Signatures cannot force delivery. |
| Malicious insider/admin | Role checks, browser-role database isolation, chain verification and external checkpoints aid detection and least privilege | Existing administrator deletion routes intentionally delete history. Database owners can rewrite/delete data and enrollment. No external transparency log, immutable retention or dual control. |
| Browser/API attacker | Server-side roles/assignment checks, input/body bounds, explicit CORS, headers and per-process ingest throttles | Login throttling, full CSP/XSS remediation, distributed DDoS defenses and independent penetration testing remain out of scope. |

## Existing boundaries and known limits

- `Tamper_admin/backend/auth.py`: HS256 JWT algorithm is fixed; users' current roles/status are checked on requests. Tokens last 12 hours; password changes do not revoke existing tokens. Browser session storage is exposed to successful XSS.
- `Tamper_admin/backend/main.py`: enrolled devices require signed envelopes; legacy un-enrolled devices retain API-key compatibility. Legacy bootstrap devices share an environment-supplied key: enroll unique credentials before production. Authentication does not establish physical sensor truth.
- `Tamper_admin/backend/ingest_limits.py`: ordinary traffic is limited per device/IP, with separate failed-auth limits; authenticated critical events bypass ordinary quotas. This prevents ordinary polling quotas suppressing tamper alerts, but a compromised authenticated signer can flood critical traffic. Counters are per-process, not distributed.
- `Tamper_admin/backend/evidence.py`: SHA-256 links and signed-source checks detect covered record edits. A chain without an independently retained count/tail checkpoint cannot prove completeness, especially deletion of its suffix or entirety. A server-provided public key or checkpoint is not an independent trust anchor.
- `gateway/gateway.py` and `firmware/tracksure_gateway/tracksure_gateway.ino`: delivery custody depends on gateway ACKs. Queue durability tests do not validate hardware wear, power-loss behavior, or secure-element configuration. Check the actual gateway entry point in `gateway/` when deploying.
- Database transport security depends on `DATABASE_URL` SSL settings; application code does not itself enforce a hosted CA policy. Ignored local secret files require OS access protection. No hosted database operation was performed.

## Firmware/operator work still needed

Provision unique credentials through environment variables, independently verify enrollment public-key fingerprints, drain queues before rotation, and retain trusted external chain checkpoints. Strict replay enrollment requires a signed key epoch, boot counter, sequence and usable capture timestamp. Firmware already persists a boot counter in NVS; it still needs the key epoch, rollback/reset handling and hardware reboot/power-loss verification. Persist counters and queued signed bytes together so retries reuse their original identity. Handle every batch item's ACK individually. Authenticate gateway ACKs or require verifiable cloud custody before deleting device records. Provide clock recovery and an explicit workflow for offline captures beyond the acceptance window. Hardware signing performance and hosted behavior remain unmeasured.

## Implemented controls and verification

| Control | Implementation | Local regression evidence |
|---|---|---|
| Strict replay identity | `backend/device_security.py` (under `Tamper_admin/`): signed key epoch + boot counter + sequence, transactional ledger and device row lock. New captures accept up to seven days of delay (`REPLAY_MAX_AGE_SECONDS`, default 604800), five minutes future skew, 512 sequence positions and eight prior boot epochs. Out-of-window events are rejected with 409; missing strict metadata with 422. | `tests/test_device_security.py`: reused counter under a new ID rejected; unseen reordered/delayed events accepted within windows; old/future captures rejected; batch rollback does not consume nonce; exact retry after lost ACK or expiry returns the original hash with no extra row. |
| Idempotency versus replay | Authentication/current status/signature checks precede lookup; an exact accepted event ID returns its receipt **before** freshness checks. Changed payload/assignment conflicts return 409. | Same tests and original `tests/test_ingestion_features.py`. Revocation rejects even an otherwise valid duplicate. Rotation requires current credentials/signature. |
| Registration/revocation/rotation | Admin-only routes in `Tamper_admin/backend/main.py`; environment credential references; digest-only new credentials; epoch increment on rotation; queue-drain confirmation. Historical proofs retain their original key. | Registration, missing admin, invalid env namespace, old credential/signer rejection, new epoch acceptance and revocation tests in `tests/test_device_security.py`. |
| Chain verification | `Tamper_admin/backend/chain_verifier.py`, admin GET `/api/shipments/{code}/evidence/verify`; one streaming ordered SELECT, stops at first bad link. Optional external count/tail anchor. | `tests/test_chain_verifier.py`: deliberate row modification, interior deletion, ID reordering and suffix deletion. Suffix deletion is detected only with the external checkpoint, explicitly tested. |
| Input/resource bounds | `Tamper_admin/backend/main.py`: forbid unknown fields; bounds on sensor values/axes, identifiers, firmware metadata, counters, quaternion and signature envelope. Batch 1–100. `ingest_guard.py` caps actual streamed bytes before parsing: 32 KiB single, 2 MiB batch. Duplicate JSON keys, non-finite JSON, wrong content type and invalid JSON rejected without input echo. | `tests/test_ingest_validation.py`: field bounds, over-limit batch, streamed oversized bodies, claimed Content-Length, malformed/duplicate JSON, 415/413/422 behavior. |
| Secret handling and browser boundary | Existing explicit origins; wildcard CORS config rejected; no-store/nosniff/frame/referrer/permissions headers, HSTS on HTTPS responses. Sanitized validation errors; credential fields excluded from stored evidence; telemetry/auth prints removed. Gateway CLI reads cloud credentials only from environment. JWT requires expiry/sub and fixed HS256. | `tests/test_ingest_validation.py`, `tests/test_security.py`, `tests/test_gateway_credentials.py`: no keys in errors/logs/evidence, hostile origin denied, missing expiry/alternate algorithms rejected, file credentials ignored. |
| Direct database browser isolation | Alembic `0005_browser_role_isolation`, SQL in `migrations/sql/0005_browser_role_isolation.sql`: revoke browser DML and PUBLIC grants, enable RLS, restrictive false policies for both browser roles on all current application tables. | `tests/test_rls.py` actually SET ROLEs to anon/authenticated and tests DML denial; restoring permissive policies/grants still yields no visible/deletable rows and rejects inserts. Local PostgreSQL only. |

Replay policy is **not silently enabled for legacy devices**, preserving the original firmware/tests. Device-list responses identify `legacy` versus `counter_v1`. Existing bootstrap devices and existing plaintext DB credentials must be rotated/enrolled. Revocation/rotation takes effect for subsequent transactions; it cannot retract already committed history. The ledger grows with accepted strict events and has no automated pruning; storage/write overhead and Phase 4 throughput are unmeasured. SQLite tests validate logic, not PostgreSQL row-lock semantics or multi-process performance.

Unknown telemetry fields now return 422 rather than being silently retained. Existing firmware fields are explicitly supported; a new firmware field requires a reviewed schema update. Body credentials remain accepted for legacy compatibility but are not persisted; prefer headers. Browser validation responses deliberately no longer echo submitted values. No dashboard JS changes were needed.

Historical proofs produced by the old unsigned `api_key` body alias may already contain that credential. They are not rewritten, because rewriting would break the chain. Rotate such credentials before distributing historical exports; old copies/backups cannot be made secret again. A regression test reconstructs that old format and verifies an unchanged retry still succeeds while changed readings fail.

## Dependency audit results

Decision A and the original 50.0.1 throughput measurements are in [dependencies.md](security/dependencies.md). They describe Phase 3 code, not throughput after these security changes. Actual final tested runtime retains cryptography **50.0.1**, with PyJWT **2.15.1** and certifi **2026.10.23** after the audit fixes. The declared crypto range is `>=50.0.1,<51`; PyJWT is now `>=2.15,<3`, and gateway certifi is `>=2026.10.18`.

| Audit scope | Before | After | Evidence |
|---|---|---|---|
| Requirements-resolved backend + gateway | Old crypto range selected 46.0.7: seven advisory entries (four unique advisory IDs, with duplicated PYSEC responses) | No known vulnerabilities in fresh resolution, including crypto 50.0.2 | `docs/security/pip-audit-before.json`, `pip-audit-after.json` |
| Actual installed application dependency closure | 17 returned entries across PyJWT 2.13.0 and certifi 2026.7.22; this is not a count of distinct CVEs | No known vulnerabilities on the **tested** runtime, including crypto 50.0.1 | `runtime-requirements-before.txt`, `runtime-requirements.txt`, `pip-audit-runtime-before.json`, `pip-audit-runtime-after.json` |
| Repository's actual pnpm lock | Two build-time advisories: high source-map-js and moderate postcss-selector-parser | No known vulnerabilities after only these transitive patches: 1.2.1 -> 1.2.2 and 6.1.4 -> 6.1.5 | `pnpm-audit.json`, `pnpm-audit-after.json`, frontend lock diff |
| npm audit | No known vulnerabilities in a freshly resolved, isolated npm lock generated from the frontend manifest | Same manifest; this is **not** an audit of the old pnpm lock | `npm-audit.json` |

The runtime audit includes the installed dependency closure with extras/markers, excluding unrelated lab packages. `pip-audit` 2.10.1 ran from an isolated tool environment; raw reports preserve advisory IDs/aliases, fix versions and descriptions. The initial clean fresh-resolution audit did not describe the older installed packages; both scopes were audited explicitly. Audit databases are point-in-time evidence, not proof of no vulnerabilities or certification of every version permitted by broad ranges. No exploitability or performance benefit is inferred from advisory counts.

Reproduce from the repo root, installing packaging/pip-audit as development tooling as needed:

```powershell
python operations/snapshot_runtime_requirements.py --output docs/security/runtime-requirements.txt
python -m pip_audit --no-deps --disable-pip -r docs/security/runtime-requirements.txt -f json
python -m pip_audit -r Tamper_admin/backend/requirements.txt -r gateway/requirements.txt -f json
pnpm --dir Tamper_admin/frontend audit --json
```

The npm check used an isolated copy of `package.json`, `npm install --package-lock-only --ignore-scripts --no-audit`, then `npm audit --json`; it did not add a second lockfile to the frontend. The canonical lock is pnpm. The frontend production build and all four original browser logic scripts passed. Those scripts use Node/WebCrypto and mocks, not a real hosted-browser penetration test.

## OWASP Top 10 checklist

Uses the current [OWASP Top 10:2025 list](https://owasp.org/Top10/2025/). Status is scoped to the controls below, not a claim of full category compliance. References are repository-relative paths.

| Category | Status | Evidence and remaining work |
|---|---|---|
| A01 Broken Access Control | Partly | `Tamper_admin/backend/main.py` current-user/admin/assignment checks; `tests/test_security.py`; RLS SQL and `tests/test_rls.py`. Hosted roles, views/functions and deployment grants remain unverified. |
| A02 Security Misconfiguration | Partly | Main's explicit CORS/security headers and `ingest_guard.py`; `tests/test_ingest_validation.py`. Hosted TLS/secret settings and static CSP require deployment review; existing frontend inline scripts/CDNs remain. |
| A03 Software Supply Chain Failures | Partly | Requirements, pnpm lock and archived audits above; both installed and freshly resolved packages checked. No signed builds, comprehensive SBOM/attestations or continuous audit pipeline. |
| A04 Cryptographic Failures | Partly | `Tamper_admin/backend/evidence.py`, `auth.py`, `device_security.py`; signature/hash/JWT tests. Software P-256 only measured; hardware provisioning, key extraction resistance and independent enrollment anchors unverified. |
| A05 Injection | Covered for SQL/ingest input | Main uses ORM/bound queries; new dynamic SQL identifiers are fixed migration/test lists. Pydantic + bounded parser tests. This is not a complete XSS audit; browser exposure is listed under A02/A07. |
| A06 Insecure Design | Partly | This threat model; `docs/ARCHITECTURE.md`; replay/lifecycle/chain tests. Forged gateway ACKs, privileged deletion and no external transparency log remain. |
| A07 Authentication Failures | Partly | `auth.py`, main device lifecycle, `tests/test_security.py`, `tests/test_device_security.py`. No MFA/login throttling/session revocation on password change; legacy devices require enrollment. |
| A08 Software or Data Integrity Failures | Partly | `evidence.py`, `chain_verifier.py`, `tests/test_chain_verifier.py`, browser evidence tests. Cannot prove capture truth or complete retention without trusted checkpoints; no firmware supply-chain attestation. |
| A09 Security Logging and Alerting Failures | Not covered end to end | Log redaction is tested; there is no immutable operator/enrollment audit trail, centralized security alerting or incident-response verification. Removing sensitive prints does not implement security monitoring. |
| A10 Mishandling of Exceptional Conditions | Partly | `ingest_guard.py`, batch transaction rollback, explicit 409/413/415/422/429, `tests/test_ingestion_features.py` and replay tests. Distributed exhaustion, machine crashes and hardware power loss remain unmeasured. |

## Rollout and local results

[Exact operator steps, backup/ACL preservation, enrollment and rollback](security/rollout.md). Keep caching OFF. The API/gateway configuration change and migration must be rolled out together; no dashboard JS change is required. Policy definitions are verified against local PostgreSQL behavior and the [Supabase RLS documentation](https://supabase.com/docs/guides/database/postgres/row-level-security); hosted behavior remains unverified.

Final test/audit counts, commands and resume-safe results are recorded in [the Phase 4 verification report](security/phase4-results.md). No new Phase 4 speedup or hardware-signing claim is supported.
