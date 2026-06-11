--
-- PostgreSQL database dump
--

\restrict 0fHCoyDK2PJaB78lQWC0b4oYcziXBRfm83fhc9MSeuxupO9LWOVpKKAcjgTVjrs

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.schedules DROP CONSTRAINT IF EXISTS schedules_artifact_id_fkey;
ALTER TABLE IF EXISTS ONLY public.images DROP CONSTRAINT IF EXISTS images_operator_id_fkey;
ALTER TABLE IF EXISTS ONLY public.images DROP CONSTRAINT IF EXISTS images_device_id_fkey;
ALTER TABLE IF EXISTS ONLY public.images DROP CONSTRAINT IF EXISTS images_artifact_id_fkey;
ALTER TABLE IF EXISTS ONLY public.image_comparisons DROP CONSTRAINT IF EXISTS image_comparisons_schedule_id_fkey;
ALTER TABLE IF EXISTS ONLY public.image_comparisons DROP CONSTRAINT IF EXISTS image_comparisons_previous_image_id_fkey;
ALTER TABLE IF EXISTS ONLY public.image_comparisons DROP CONSTRAINT IF EXISTS image_comparisons_current_image_id_fkey;
ALTER TABLE IF EXISTS ONLY public.image_comparisons DROP CONSTRAINT IF EXISTS image_comparisons_artifact_id_fkey;
ALTER TABLE IF EXISTS ONLY public.artifacts DROP CONSTRAINT IF EXISTS fk_artifact_baseline_image;
ALTER TABLE IF EXISTS ONLY public.alerts DROP CONSTRAINT IF EXISTS alerts_comparison_id_fkey;
ALTER TABLE IF EXISTS ONLY public.alerts DROP CONSTRAINT IF EXISTS alerts_artifact_id_fkey;
DROP INDEX IF EXISTS public.ix_users_username;
DROP INDEX IF EXISTS public.ix_users_user_id;
DROP INDEX IF EXISTS public.ix_schedules_id;
DROP INDEX IF EXISTS public.ix_iot_devices_device_id;
DROP INDEX IF EXISTS public.ix_iot_devices_device_code;
DROP INDEX IF EXISTS public.ix_images_image_id;
DROP INDEX IF EXISTS public.ix_image_comparisons_comparison_id;
DROP INDEX IF EXISTS public.ix_artifacts_name;
DROP INDEX IF EXISTS public.ix_artifacts_artifact_id;
DROP INDEX IF EXISTS public.ix_alerts_alert_id;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY public.schedules DROP CONSTRAINT IF EXISTS schedules_pkey;
ALTER TABLE IF EXISTS ONLY public.iot_devices DROP CONSTRAINT IF EXISTS iot_devices_pkey;
ALTER TABLE IF EXISTS ONLY public.images DROP CONSTRAINT IF EXISTS images_pkey;
ALTER TABLE IF EXISTS ONLY public.image_comparisons DROP CONSTRAINT IF EXISTS image_comparisons_pkey;
ALTER TABLE IF EXISTS ONLY public.artifacts DROP CONSTRAINT IF EXISTS artifacts_pkey;
ALTER TABLE IF EXISTS ONLY public.alerts DROP CONSTRAINT IF EXISTS alerts_pkey;
DROP TABLE IF EXISTS public.users;
DROP TABLE IF EXISTS public.schedules;
DROP TABLE IF EXISTS public.iot_devices;
DROP TABLE IF EXISTS public.images;
DROP TABLE IF EXISTS public.image_comparisons;
DROP TABLE IF EXISTS public.artifacts;
DROP TABLE IF EXISTS public.alerts;
DROP TYPE IF EXISTS public.inspection_type_enum;
DROP TYPE IF EXISTS public.image_type;
DROP TYPE IF EXISTS public.device_status;
DROP TYPE IF EXISTS public.comparison_status;
DROP TYPE IF EXISTS public.alert_level;
--
-- Name: alert_level; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.alert_level AS ENUM (
    'low',
    'medium',
    'high'
);


--
-- Name: comparison_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.comparison_status AS ENUM (
    'good',
    'damaged',
    'warning'
);


--
-- Name: device_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.device_status AS ENUM (
    'online',
    'offline'
);


--
-- Name: image_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.image_type AS ENUM (
    'baseline',
    'inspection'
);


--
-- Name: inspection_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.inspection_type_enum AS ENUM (
    'scheduled',
    'sudden'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alerts (
    alert_id character varying(6) NOT NULL,
    artifact_id character varying(6) NOT NULL,
    comparison_id character varying(6) NOT NULL,
    alert_level public.alert_level NOT NULL,
    is_handled boolean NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: artifacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.artifacts (
    artifact_id character varying(6) NOT NULL,
    name character varying(255) NOT NULL,
    location character varying(255),
    description text,
    status character varying(32) NOT NULL,
    inspection_interval_days integer NOT NULL,
    baseline_image_id character varying(6),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: image_comparisons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.image_comparisons (
    comparison_id character varying(6) NOT NULL,
    artifact_id character varying(6) NOT NULL,
    previous_image_id character varying(6) NOT NULL,
    current_image_id character varying(6) NOT NULL,
    schedule_id character varying(6),
    damage_score double precision NOT NULL,
    ssim_score character varying(16),
    heatmap_path character varying(500),
    status public.comparison_status NOT NULL,
    inspection_type public.inspection_type_enum NOT NULL,
    description text,
    detections_json text,
    created_by character varying(100),
    created_at timestamp with time zone NOT NULL
);


--
-- Name: images; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.images (
    image_id character varying(6) NOT NULL,
    artifact_id character varying(6) NOT NULL,
    device_id character varying(6),
    operator_id character varying(6),
    image_type public.image_type NOT NULL,
    image_path character varying(500) NOT NULL,
    captured_at timestamp with time zone NOT NULL,
    is_valid boolean NOT NULL
);


--
-- Name: iot_devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.iot_devices (
    device_id character varying(6) NOT NULL,
    device_code character varying(100) NOT NULL,
    description text,
    status public.device_status NOT NULL,
    created_at timestamp with time zone NOT NULL,
    last_active_at timestamp with time zone
);


--
-- Name: schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schedules (
    id character varying(6) NOT NULL,
    artifact_id character varying(6) NOT NULL,
    scheduled_date timestamp with time zone NOT NULL,
    scheduled_time character varying(8) NOT NULL,
    operator_username character varying(100) NOT NULL,
    notes text,
    completed boolean NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id character varying(6) NOT NULL,
    username character varying(100) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(8) NOT NULL,
    full_name character varying(200),
    age integer,
    email character varying(255),
    phone character varying(20),
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: alerts alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (alert_id);


--
-- Name: artifacts artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.artifacts
    ADD CONSTRAINT artifacts_pkey PRIMARY KEY (artifact_id);


--
-- Name: image_comparisons image_comparisons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_pkey PRIMARY KEY (comparison_id);


--
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (image_id);


--
-- Name: iot_devices iot_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iot_devices
    ADD CONSTRAINT iot_devices_pkey PRIMARY KEY (device_id);


--
-- Name: schedules schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schedules
    ADD CONSTRAINT schedules_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: ix_alerts_alert_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_alerts_alert_id ON public.alerts USING btree (alert_id);


--
-- Name: ix_artifacts_artifact_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_artifacts_artifact_id ON public.artifacts USING btree (artifact_id);


--
-- Name: ix_artifacts_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_artifacts_name ON public.artifacts USING btree (name);


--
-- Name: ix_image_comparisons_comparison_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_image_comparisons_comparison_id ON public.image_comparisons USING btree (comparison_id);


--
-- Name: ix_images_image_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_images_image_id ON public.images USING btree (image_id);


--
-- Name: ix_iot_devices_device_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_iot_devices_device_code ON public.iot_devices USING btree (device_code);


--
-- Name: ix_iot_devices_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_iot_devices_device_id ON public.iot_devices USING btree (device_id);


--
-- Name: ix_schedules_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_schedules_id ON public.schedules USING btree (id);


--
-- Name: ix_users_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_user_id ON public.users USING btree (user_id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: alerts alerts_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.artifacts(artifact_id) ON DELETE CASCADE;


--
-- Name: alerts alerts_comparison_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_comparison_id_fkey FOREIGN KEY (comparison_id) REFERENCES public.image_comparisons(comparison_id) ON DELETE CASCADE;


--
-- Name: artifacts fk_artifact_baseline_image; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.artifacts
    ADD CONSTRAINT fk_artifact_baseline_image FOREIGN KEY (baseline_image_id) REFERENCES public.images(image_id);


--
-- Name: image_comparisons image_comparisons_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.artifacts(artifact_id) ON DELETE CASCADE;


--
-- Name: image_comparisons image_comparisons_current_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_current_image_id_fkey FOREIGN KEY (current_image_id) REFERENCES public.images(image_id);


--
-- Name: image_comparisons image_comparisons_previous_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_previous_image_id_fkey FOREIGN KEY (previous_image_id) REFERENCES public.images(image_id);


--
-- Name: image_comparisons image_comparisons_schedule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_schedule_id_fkey FOREIGN KEY (schedule_id) REFERENCES public.schedules(id);


--
-- Name: images images_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.artifacts(artifact_id) ON DELETE CASCADE;


--
-- Name: images images_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.iot_devices(device_id);


--
-- Name: images images_operator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.users(user_id);


--
-- Name: schedules schedules_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schedules
    ADD CONSTRAINT schedules_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.artifacts(artifact_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 0fHCoyDK2PJaB78lQWC0b4oYcziXBRfm83fhc9MSeuxupO9LWOVpKKAcjgTVjrs

