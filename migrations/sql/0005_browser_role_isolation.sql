-- Backend-only application tables. Reviewed list, never dynamic client identifiers.
-- Run as the table owner; backend must connect as a trusted owner/BYPASSRLS role.
DO $isolation$
DECLARE tab text; browser_role text;
BEGIN
  FOREACH tab IN ARRAY ARRAY['users','devices','shipments','vehicles','sensor_events',
      'shipment_alerts','system_settings','cache_revisions','device_replay_nonces','alembic_version']
  LOOP
    IF to_regclass(format('public.%I',tab)) IS NULL THEN CONTINUE; END IF;
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tab);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC',tab);
    FOREACH browser_role IN ARRAY ARRAY['anon','authenticated'] LOOP
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=browser_role) THEN
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I',tab,browser_role);
        EXECUTE format('DROP POLICY IF EXISTS safetrack_browser_deny_%s ON public.%I',browser_role,tab);
        -- Restrictive denial also defeats pre-existing permissive policies if a
        -- later operator accidentally restores table grants to browser roles.
        EXECUTE format('CREATE POLICY safetrack_browser_deny_%s ON public.%I AS RESTRICTIVE FOR ALL TO %I USING (false) WITH CHECK (false)',browser_role,tab,browser_role);
      END IF;
    END LOOP;
  END LOOP;
  FOREACH browser_role IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=browser_role) THEN
      FOR tab IN SELECT sequence_name FROM information_schema.sequences
                 WHERE sequence_schema='public' AND sequence_name IN
                 ('users_id_seq','devices_id_seq','shipments_id_seq','vehicles_id_seq',
                  'sensor_events_id_seq','shipment_alerts_id_seq','system_settings_id_seq') LOOP
        EXECUTE format('REVOKE ALL ON SEQUENCE public.%I FROM PUBLIC, %I',tab,browser_role);
      END LOOP;
    END IF;
  END LOOP;
END $isolation$;
