# SafeTrack shared portal

The production site is https://safetrack-portal.vercel.app. A common login routes admin accounts to `/index.html` and user accounts to `/user/dashboard.html`. JWT sessions remain in tab-scoped sessionStorage. API role checks and shipment assignments enforce authorization.

## Source ownership

The current unified user dashboard lives in `Tamper_admin/frontend/user/`, including the restored `parcel.js` renderer. This bundle is preserved by the frontend build. `Tamper_user/frontend` retains the standalone/legacy interface; do not overwrite the unified bundle from it. The sync script only imports the standalone interface when the current parcel bundle is absent.

## Interface

- Login: truck video, optional audio replay, smooth form reveal and reduced-motion fallback.
- Admin: fleet overview, dedicated Vehicles page, vehicle details, shipments, alerts, reports and account settings.
- User: Overview, Conditions and Events. Conditions displays telemetry plus pitch, roll, acceleration, angular velocity and last synchronization alongside the interactive 3D parcel.
- Mouse dragging changes the inspection camera, not sensor readings. Reset Camera restores the view.

## Validation and limits

Production browser checks covered real admin/user login, shipment/live API responses, restored parcel rendering, video/audio controls, mobile fallback, vehicle list/search, add-vehicle modal and detail navigation. Alert requests can still be slow. Form opening was tested without creating production records. Hardware readings require the ESP32 and gateway to remain running.
