--
-- PostgreSQL database dump
--

\restrict U23O7cWo8mfcSxilaqG5ugxAD9unNZhSeXX29rlcRlzqRbikEnAoVDjbIbouIYi

-- Dumped from database version 16.11
-- Dumped by pg_dump version 16.11

-- Started on 2026-05-01 21:21:13

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

--
-- TOC entry 880 (class 1247 OID 16724)
-- Name: alert_level; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.alert_level AS ENUM (
    'low',
    'medium',
    'high'
);


ALTER TYPE public.alert_level OWNER TO postgres;

--
-- TOC entry 859 (class 1247 OID 16562)
-- Name: alertlevel; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.alertlevel AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH'
);


ALTER TYPE public.alertlevel OWNER TO postgres;

--
-- TOC entry 883 (class 1247 OID 16732)
-- Name: comparison_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.comparison_status AS ENUM (
    'good',
    'damaged',
    'warning'
);


ALTER TYPE public.comparison_status OWNER TO postgres;

--
-- TOC entry 856 (class 1247 OID 16554)
-- Name: comparisonstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.comparisonstatus AS ENUM (
    'GOOD',
    'DAMAGED',
    'WARNING'
);


ALTER TYPE public.comparisonstatus OWNER TO postgres;

--
-- TOC entry 874 (class 1247 OID 16712)
-- Name: device_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.device_status AS ENUM (
    'online',
    'offline'
);


ALTER TYPE public.device_status OWNER TO postgres;

--
-- TOC entry 865 (class 1247 OID 16576)
-- Name: devicestatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.devicestatus AS ENUM (
    'ONLINE',
    'OFFLINE'
);


ALTER TYPE public.devicestatus OWNER TO postgres;

--
-- TOC entry 877 (class 1247 OID 16718)
-- Name: image_type; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.image_type AS ENUM (
    'baseline',
    'inspection'
);


ALTER TYPE public.image_type OWNER TO postgres;

--
-- TOC entry 853 (class 1247 OID 16548)
-- Name: imagetype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.imagetype AS ENUM (
    'BASELINE',
    'INSPECTION'
);


ALTER TYPE public.imagetype OWNER TO postgres;

--
-- TOC entry 886 (class 1247 OID 16740)
-- Name: inspection_type_enum; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.inspection_type_enum AS ENUM (
    'scheduled',
    'sudden'
);


ALTER TYPE public.inspection_type_enum OWNER TO postgres;

--
-- TOC entry 868 (class 1247 OID 16701)
-- Name: inspectiontype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.inspectiontype AS ENUM (
    'SCHEDULED',
    'SUDDEN'
);


ALTER TYPE public.inspectiontype OWNER TO postgres;

--
-- TOC entry 871 (class 1247 OID 16706)
-- Name: user_role; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.user_role AS ENUM (
    'admin',
    'operator'
);


ALTER TYPE public.user_role OWNER TO postgres;

--
-- TOC entry 862 (class 1247 OID 16570)
-- Name: userrole; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.userrole AS ENUM (
    'ADMIN',
    'OPERATOR'
);


ALTER TYPE public.userrole OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 16750)
-- Name: alert_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.alert_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.alert_id_seq OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 228 (class 1259 OID 16867)
-- Name: alerts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alerts (
    alert_id character varying(6) DEFAULT lpad((nextval('public.alert_id_seq'::regclass))::text, 6, '0'::text) NOT NULL,
    artifact_id character varying(6) NOT NULL,
    comparison_id character varying(6) NOT NULL,
    alert_level public.alert_level NOT NULL,
    is_handled boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.alerts OWNER TO postgres;

--
-- TOC entry 217 (class 1259 OID 16747)
-- Name: artifact_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.artifact_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.artifact_id_seq OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16777)
-- Name: artifacts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.artifacts (
    artifact_id character varying(6) DEFAULT lpad((nextval('public.artifact_id_seq'::regclass))::text, 6, '0'::text) NOT NULL,
    name character varying(255) NOT NULL,
    location character varying(255),
    description text,
    status character varying(32) DEFAULT 'good'::character varying NOT NULL,
    baseline_image_id character varying(6),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    inspection_interval_days integer DEFAULT 0
);


ALTER TABLE public.artifacts OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16749)
-- Name: comparison_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.comparison_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.comparison_id_seq OWNER TO postgres;

--
-- TOC entry 216 (class 1259 OID 16746)
-- Name: device_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.device_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.device_id_seq OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 16835)
-- Name: image_comparisons; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.image_comparisons (
    comparison_id character varying(6) DEFAULT lpad((nextval('public.comparison_id_seq'::regclass))::text, 6, '0'::text) NOT NULL,
    artifact_id character varying(6) NOT NULL,
    previous_image_id character varying(6) NOT NULL,
    current_image_id character varying(6) NOT NULL,
    schedule_id character varying(6),
    damage_score double precision DEFAULT 0.0 NOT NULL,
    ssim_score character varying(16),
    heatmap_path character varying(500),
    status public.comparison_status DEFAULT 'good'::public.comparison_status NOT NULL,
    inspection_type public.inspection_type_enum DEFAULT 'sudden'::public.inspection_type_enum NOT NULL,
    description text,
    detections_json text,
    created_by character varying(100),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.image_comparisons OWNER TO postgres;

--
-- TOC entry 218 (class 1259 OID 16748)
-- Name: image_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.image_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.image_id_seq OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 16788)
-- Name: images; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.images (
    image_id character varying(6) DEFAULT lpad((nextval('public.image_id_seq'::regclass))::text, 6, '0'::text) NOT NULL,
    artifact_id character varying(6) NOT NULL,
    device_id character varying(6),
    operator_id character varying(6),
    image_type public.image_type NOT NULL,
    image_path character varying(500) NOT NULL,
    captured_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_valid boolean DEFAULT true NOT NULL
);


ALTER TABLE public.images OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 16765)
-- Name: iot_devices; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.iot_devices (
    device_id character varying(6) DEFAULT lpad((nextval('public.device_id_seq'::regclass))::text, 6, '0'::text) NOT NULL,
    device_code character varying(100) NOT NULL,
    description text,
    status public.device_status DEFAULT 'offline'::public.device_status NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_active_at timestamp with time zone
);


ALTER TABLE public.iot_devices OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16751)
-- Name: schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.schedule_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.schedule_id_seq OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16818)
-- Name: schedules; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.schedules (
    id character varying(6) DEFAULT lpad((nextval('public.schedule_id_seq'::regclass))::text, 6, '0'::text) NOT NULL,
    artifact_id character varying(6) NOT NULL,
    scheduled_date timestamp with time zone NOT NULL,
    scheduled_time character varying(8) DEFAULT '09:00'::character varying NOT NULL,
    operator_username character varying(100) DEFAULT ''::character varying NOT NULL,
    notes text,
    completed boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.schedules OWNER TO postgres;

--
-- TOC entry 215 (class 1259 OID 16745)
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_id_seq OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 16752)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    user_id character varying(6) DEFAULT lpad((nextval('public.user_id_seq'::regclass))::text, 6, '0'::text) NOT NULL,
    username character varying(100) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role public.user_role DEFAULT 'operator'::public.user_role NOT NULL,
    full_name character varying(200),
    age integer,
    email character varying(255),
    phone character varying(20),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.users OWNER TO postgres;

--
-- TOC entry 5014 (class 0 OID 16867)
-- Dependencies: 228
-- Data for Name: alerts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alerts (alert_id, artifact_id, comparison_id, alert_level, is_handled, created_at) FROM stdin;
\.


--
-- TOC entry 5010 (class 0 OID 16777)
-- Dependencies: 224
-- Data for Name: artifacts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.artifacts (artifact_id, name, location, description, status, baseline_image_id, created_at, updated_at, inspection_interval_days) FROM stdin;
\.


--
-- TOC entry 5013 (class 0 OID 16835)
-- Dependencies: 227
-- Data for Name: image_comparisons; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.image_comparisons (comparison_id, artifact_id, previous_image_id, current_image_id, schedule_id, damage_score, ssim_score, heatmap_path, status, inspection_type, description, detections_json, created_by, created_at) FROM stdin;
\.


--
-- TOC entry 5011 (class 0 OID 16788)
-- Dependencies: 225
-- Data for Name: images; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.images (image_id, artifact_id, device_id, operator_id, image_type, image_path, captured_at, is_valid) FROM stdin;
\.


--
-- TOC entry 5009 (class 0 OID 16765)
-- Dependencies: 223
-- Data for Name: iot_devices; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.iot_devices (device_id, device_code, description, status, created_at, last_active_at) FROM stdin;
\.


--
-- TOC entry 5012 (class 0 OID 16818)
-- Dependencies: 226
-- Data for Name: schedules; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.schedules (id, artifact_id, scheduled_date, scheduled_time, operator_username, notes, completed, created_at) FROM stdin;
\.


--
-- TOC entry 5008 (class 0 OID 16752)
-- Dependencies: 222
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (user_id, username, password_hash, role, full_name, age, email, phone, is_active, created_at) FROM stdin;
000001	admin	$2b$12$FaKjVgO5AK/juXv82CmAIe7UOhLx3Lukx4uh1yKNXALwDKVpMLrx6	admin	System Administrator	\N	\N	\N	t	2026-04-30 12:12:37.231343+07
000002	user01	$2b$12$TrzSMcRJhV03qvaJD.d.9uMZrw.VCYCfFpzsxu61XwnIui1wv.oE6	operator	Operator 01	\N	\N	\N	t	2026-04-30 12:12:37.231343+07
\.


--
-- TOC entry 5020 (class 0 OID 0)
-- Dependencies: 220
-- Name: alert_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.alert_id_seq', 1, false);


--
-- TOC entry 5021 (class 0 OID 0)
-- Dependencies: 217
-- Name: artifact_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.artifact_id_seq', 2, true);


--
-- TOC entry 5022 (class 0 OID 0)
-- Dependencies: 219
-- Name: comparison_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.comparison_id_seq', 1, false);


--
-- TOC entry 5023 (class 0 OID 0)
-- Dependencies: 216
-- Name: device_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.device_id_seq', 1, false);


--
-- TOC entry 5024 (class 0 OID 0)
-- Dependencies: 218
-- Name: image_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.image_id_seq', 1, false);


--
-- TOC entry 5025 (class 0 OID 0)
-- Dependencies: 221
-- Name: schedule_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.schedule_id_seq', 1, false);


--
-- TOC entry 5026 (class 0 OID 0)
-- Dependencies: 215
-- Name: user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.user_id_seq', 3, true);


--
-- TOC entry 4846 (class 2606 OID 16874)
-- Name: alerts alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (alert_id);


--
-- TOC entry 4838 (class 2606 OID 16787)
-- Name: artifacts artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.artifacts
    ADD CONSTRAINT artifacts_pkey PRIMARY KEY (artifact_id);


--
-- TOC entry 4844 (class 2606 OID 16846)
-- Name: image_comparisons image_comparisons_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_pkey PRIMARY KEY (comparison_id);


--
-- TOC entry 4840 (class 2606 OID 16797)
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (image_id);


--
-- TOC entry 4834 (class 2606 OID 16776)
-- Name: iot_devices iot_devices_device_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.iot_devices
    ADD CONSTRAINT iot_devices_device_code_key UNIQUE (device_code);


--
-- TOC entry 4836 (class 2606 OID 16774)
-- Name: iot_devices iot_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.iot_devices
    ADD CONSTRAINT iot_devices_pkey PRIMARY KEY (device_id);


--
-- TOC entry 4842 (class 2606 OID 16829)
-- Name: schedules schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.schedules
    ADD CONSTRAINT schedules_pkey PRIMARY KEY (id);


--
-- TOC entry 4830 (class 2606 OID 16762)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- TOC entry 4832 (class 2606 OID 16764)
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- TOC entry 4856 (class 2606 OID 16875)
-- Name: alerts alerts_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.artifacts(artifact_id) ON DELETE CASCADE;


--
-- TOC entry 4857 (class 2606 OID 16880)
-- Name: alerts alerts_comparison_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_comparison_id_fkey FOREIGN KEY (comparison_id) REFERENCES public.image_comparisons(comparison_id) ON DELETE CASCADE;


--
-- TOC entry 4847 (class 2606 OID 16813)
-- Name: artifacts fk_artifact_baseline_image; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.artifacts
    ADD CONSTRAINT fk_artifact_baseline_image FOREIGN KEY (baseline_image_id) REFERENCES public.images(image_id);


--
-- TOC entry 4852 (class 2606 OID 16847)
-- Name: image_comparisons image_comparisons_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.artifacts(artifact_id) ON DELETE CASCADE;


--
-- TOC entry 4853 (class 2606 OID 16857)
-- Name: image_comparisons image_comparisons_current_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_current_image_id_fkey FOREIGN KEY (current_image_id) REFERENCES public.images(image_id);


--
-- TOC entry 4854 (class 2606 OID 16852)
-- Name: image_comparisons image_comparisons_previous_image_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_previous_image_id_fkey FOREIGN KEY (previous_image_id) REFERENCES public.images(image_id);


--
-- TOC entry 4855 (class 2606 OID 16862)
-- Name: image_comparisons image_comparisons_schedule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.image_comparisons
    ADD CONSTRAINT image_comparisons_schedule_id_fkey FOREIGN KEY (schedule_id) REFERENCES public.schedules(id);


--
-- TOC entry 4848 (class 2606 OID 16798)
-- Name: images images_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.artifacts(artifact_id) ON DELETE CASCADE;


--
-- TOC entry 4849 (class 2606 OID 16803)
-- Name: images images_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.iot_devices(device_id);


--
-- TOC entry 4850 (class 2606 OID 16808)
-- Name: images images_operator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.users(user_id);


--
-- TOC entry 4851 (class 2606 OID 16830)
-- Name: schedules schedules_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.schedules
    ADD CONSTRAINT schedules_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.artifacts(artifact_id) ON DELETE CASCADE;


-- Completed on 2026-05-01 21:21:14

--
-- PostgreSQL database dump complete
--

\unrestrict U23O7cWo8mfcSxilaqG5ugxAD9unNZhSeXX29rlcRlzqRbikEnAoVDjbIbouIYi

