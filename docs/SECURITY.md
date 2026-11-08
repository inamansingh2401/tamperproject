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
