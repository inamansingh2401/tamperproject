# Deployment guide

## Frontend

From `Tamper_admin/frontend`:

```powershell
npm install
npm run build
npx vercel --prod
```

The static site includes the shared login, admin pages, `user/`, `vendor/` and active video assets. Keep Vercel project metadata private. Assign the public alias `safetrack-portal.vercel.app` in the owning Vercel account after deployment; manual aliases must point to the latest release.

## API

Deploy `Tamper_admin/backend` using its existing Vercel configuration. Set `DATABASE_URL`, `JWT_SECRET`, `DEVICE_API_KEY`, `BOOTSTRAP_ADMIN_PASSWORD`, `DEMO_USER_PASSWORD` and `SAFETRACK_ENV` privately. Set `CORS_ORIGINS` to approved frontend origins, including `https://safetrack-portal.vercel.app`. Redeploy after environment changes. The API routes use `/api`; a 404 at the root does not establish an outage.

## Gateway and hardware

Follow `LIVE_GATEWAY_RUNBOOK.md`. Configure private hotspot credentials, device enrollment and the gateway LAN address locally. Firmware sends signed readings to the gateway; the gateway verifies, queues and forwards them to the API. A second laptop can run the gateway on the same LAN. The web portal does not require USB, but fresh readings require the hardware, network and gateway.

## Release checks

1. Build the frontend and run `python -m unittest discover -s tests -p test_security.py` in an isolated environment with backend dependencies installed.
2. Verify real admin/user login, role routing, assigned shipment access and logout.
3. Verify Vehicles navigation, fleet search/filter, vehicle details and return navigation.
4. Verify shipment readings, parcel tilt, reset camera, animation playback and mobile layout.
5. Check gateway status, record freshness and delivery acknowledgements separately from webpage availability.

Never publish `.env`, local configuration, passwords, private keys, databases, runtime logs or unpublished presentation files. Ignoring a file does not remove it from prior Git history; rotate credentials if any have previously been exposed.
