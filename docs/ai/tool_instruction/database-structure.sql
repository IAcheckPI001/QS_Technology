--
-- PostgreSQL database dump
--

\restrict O6dD4haqu3c6AWhBoOll6pLaTTcNL3beqez8vKmIo8y2WrGCktnuDfPokhuPow4

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

-- Started on 2026-11-10 07:07:51 UTC

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 8 (class 2615 OID 31423)
-- Name: public; Type: SCHEMA; Schema: -; Owner: admin
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO admin;

--
-- TOC entry 5387 (class 0 OID 0)
-- Dependencies: 8
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: admin
--

COMMENT ON SCHEMA public IS '';


--
-- TOC entry 2 (class 3079 OID 31424)
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- TOC entry 5389 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- TOC entry 3 (class 3079 OID 31505)
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- TOC entry 5390 (class 0 OID 0)
-- Dependencies: 3
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- TOC entry 4 (class 3079 OID 31542)
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- TOC entry 5391 (class 0 OID 0)
-- Dependencies: 4
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- TOC entry 1248 (class 1247 OID 31550)
-- Name: data_scope; Type: TYPE; Schema: public; Owner: admin
--

CREATE TYPE public.data_scope AS ENUM (
    'SELF',
    'ORGANIZATION',
    'ORGANIZATION_AND_CHILDREN',
    'ALL'
);


ALTER TYPE public.data_scope OWNER TO admin;

--
-- TOC entry 406 (class 1255 OID 31559)
-- Name: roles_reject_product_role_assignment(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.roles_reject_product_role_assignment() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM roles WHERE id = NEW.role_id AND kind = 'product') THEN
        RAISE EXCEPTION
            'cannot assign product role % to a user globally: product roles are granted per product via product_user_access',
            NEW.role_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.roles_reject_product_role_assignment() OWNER TO admin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 226 (class 1259 OID 31560)
-- Name: activities; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.activities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    activityable_type character varying(20) NOT NULL,
    activityable_id uuid NOT NULL,
    sales_id uuid NOT NULL,
    action character varying(100) NOT NULL,
    content text NOT NULL,
    contact_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT chk_activityable_type CHECK (((activityable_type)::text = ANY (ARRAY[('lead'::character varying)::text, ('customer'::character varying)::text])))
);


ALTER TABLE public.activities OWNER TO admin;

--
-- TOC entry 227 (class 1259 OID 31568)
-- Name: app_settings; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.app_settings (
    key text NOT NULL,
    value text NOT NULL
);


ALTER TABLE public.app_settings OWNER TO admin;

--
-- TOC entry 228 (class 1259 OID 31573)
-- Name: auth_users; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.auth_users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    username character varying(100) NOT NULL,
    password_hash text NOT NULL,
    ref_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    email character varying(255),
    phone character varying(20),
    email_verified_at timestamp without time zone,
    phone_verified_at timestamp without time zone,
    region text DEFAULT 'VN'::text NOT NULL,
    email_notify_activation_request boolean DEFAULT false NOT NULL,
    email_notify_service_request boolean DEFAULT false NOT NULL
);


ALTER TABLE public.auth_users OWNER TO admin;

--
-- TOC entry 341 (class 1259 OID 45183)
-- Name: bom_components; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.bom_components (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bom_id uuid NOT NULL,
    component_type character varying(20) NOT NULL,
    component_id uuid NOT NULL,
    qty numeric(18,4) NOT NULL,
    warehouse_id uuid,
    CONSTRAINT bom_components_component_type_check CHECK (((component_type)::text = ANY ((ARRAY['material'::character varying, 'product_item'::character varying])::text[]))),
    CONSTRAINT bom_components_qty_check CHECK ((qty > (0)::numeric))
);


ALTER TABLE public.bom_components OWNER TO admin;

--
-- TOC entry 340 (class 1259 OID 45168)
-- Name: boms; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.boms (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_id uuid,
    version integer DEFAULT 1 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    product_name text DEFAULT ''::text NOT NULL,
    created_by uuid
);


ALTER TABLE public.boms OWNER TO admin;

--
-- TOC entry 229 (class 1259 OID 31585)
-- Name: business_fields; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.business_fields (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    label_vi character varying(255),
    label_en character varying(255)
);


ALTER TABLE public.business_fields OWNER TO admin;

--
-- TOC entry 230 (class 1259 OID 31593)
-- Name: campaign_registrations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.campaign_registrations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    campaign_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    note text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.campaign_registrations OWNER TO admin;

--
-- TOC entry 231 (class 1259 OID 31601)
-- Name: campaign_visits; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.campaign_visits (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    campaign_id uuid NOT NULL,
    visited_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.campaign_visits OWNER TO admin;

--
-- TOC entry 232 (class 1259 OID 31606)
-- Name: campaigns; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.campaigns (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    product_id uuid,
    business_field_id uuid,
    organization_id uuid NOT NULL,
    funnel_type text NOT NULL,
    channel_type text,
    status text DEFAULT 'active'::text NOT NULL,
    sla_hours integer,
    created_by uuid NOT NULL,
    assigned_person_id uuid,
    start_at timestamp with time zone,
    end_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    note text,
    CONSTRAINT campaigns_funnel_type_check CHECK ((funnel_type = ANY (ARRAY['sales'::text, 'course'::text]))),
    CONSTRAINT campaigns_status_check CHECK ((status = ANY (ARRAY['active'::text, 'ended'::text])))
);


ALTER TABLE public.campaigns OWNER TO admin;

--
-- TOC entry 311 (class 1259 OID 37554)
-- Name: chat_conversations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.chat_conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    kind text DEFAULT 'direct'::text NOT NULL,
    direct_key text,
    name text,
    created_by uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_message_at timestamp with time zone,
    owner_id uuid,
    CONSTRAINT chat_conversations_kind_check CHECK ((kind = ANY (ARRAY['direct'::text, 'group'::text])))
);


ALTER TABLE public.chat_conversations OWNER TO admin;

--
-- TOC entry 313 (class 1259 OID 37589)
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.chat_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    sender_id uuid NOT NULL,
    body text DEFAULT ''::text NOT NULL,
    reply_to_id uuid,
    recalled_at timestamp with time zone,
    pinned_at timestamp with time zone,
    pinned_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    forwarded boolean DEFAULT false NOT NULL,
    kind text DEFAULT 'text'::text NOT NULL,
    CONSTRAINT chat_messages_kind_check CHECK ((kind = ANY (ARRAY['text'::text, 'system'::text])))
);


ALTER TABLE public.chat_messages OWNER TO admin;

--
-- TOC entry 312 (class 1259 OID 37572)
-- Name: chat_participants; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.chat_participants (
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    last_read_at timestamp with time zone,
    cleared_at timestamp with time zone,
    pinned_at timestamp with time zone,
    muted boolean DEFAULT false NOT NULL,
    archived_at timestamp with time zone,
    can_add boolean DEFAULT false NOT NULL
);


ALTER TABLE public.chat_participants OWNER TO admin;

--
-- TOC entry 309 (class 1259 OID 33542)
-- Name: company_doc_node_products; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.company_doc_node_products (
    node_id uuid NOT NULL,
    product_id uuid NOT NULL
);


ALTER TABLE public.company_doc_node_products OWNER TO admin;

--
-- TOC entry 233 (class 1259 OID 31617)
-- Name: company_doc_node_versions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.company_doc_node_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    node_id uuid NOT NULL,
    version integer NOT NULL,
    name text NOT NULL,
    description text,
    file_url text,
    document_type character varying(64),
    language character varying(16),
    created_by_name text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.company_doc_node_versions OWNER TO admin;

--
-- TOC entry 234 (class 1259 OID 31624)
-- Name: company_doc_nodes; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.company_doc_nodes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    parent_id uuid,
    node_type text NOT NULL,
    name text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    file_url text DEFAULT ''::text NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    manualhub_product_id uuid,
    manualhub_document_id uuid,
    manualhub_document_type text,
    manualhub_language text,
    status text DEFAULT 'draft'::text NOT NULL,
    rejection_reason text,
    pre_delete_status text,
    version text,
    language text,
    document_type text,
    pdf_cache_file_id uuid,
    pdf_cache_source text,
    root_id uuid,
    document_group_id uuid,
    is_current boolean DEFAULT true NOT NULL,
    lineage_version text DEFAULT '1'::text NOT NULL,
    connection_types text[] DEFAULT '{}'::text[] NOT NULL,
    CONSTRAINT company_doc_nodes_language_check CHECK (((language IS NULL) OR (language = ANY (ARRAY['vi'::text, 'en'::text])))),
    CONSTRAINT company_doc_nodes_node_type_check CHECK ((node_type = ANY (ARRAY['folder'::text, 'document'::text]))),
    CONSTRAINT company_doc_nodes_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'review'::text, 'released'::text, 'rejected'::text, 'hidden'::text, 'pending_delete'::text])))
);


ALTER TABLE public.company_doc_nodes OWNER TO admin;

--
-- TOC entry 235 (class 1259 OID 31641)
-- Name: contact_messages; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.contact_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id uuid NOT NULL,
    name text NOT NULL,
    phone text NOT NULL,
    email text DEFAULT ''::text NOT NULL,
    business_field text DEFAULT ''::text NOT NULL,
    services text DEFAULT ''::text NOT NULL,
    message text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    read_at timestamp with time zone
);


ALTER TABLE public.contact_messages OWNER TO admin;

--
-- TOC entry 236 (class 1259 OID 31652)
-- Name: customer_business_fields; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_business_fields (
    customer_id uuid NOT NULL,
    business_field_id uuid NOT NULL
);


ALTER TABLE public.customer_business_fields OWNER TO admin;

--
-- TOC entry 237 (class 1259 OID 31655)
-- Name: customer_customer_groups; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_customer_groups (
    customer_id uuid NOT NULL,
    customer_group_id uuid NOT NULL
);


ALTER TABLE public.customer_customer_groups OWNER TO admin;

--
-- TOC entry 238 (class 1259 OID 31658)
-- Name: customer_groups; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_groups (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    label_vi character varying(255),
    label_en character varying(255)
);


ALTER TABLE public.customer_groups OWNER TO admin;

--
-- TOC entry 239 (class 1259 OID 31666)
-- Name: customer_logs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    action character varying(32) NOT NULL,
    target_type character varying(32) DEFAULT 'customer'::character varying NOT NULL,
    target_id uuid,
    changes jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.customer_logs OWNER TO admin;

--
-- TOC entry 240 (class 1259 OID 31675)
-- Name: customer_new_interactions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_new_interactions (
    customer_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.customer_new_interactions OWNER TO admin;

--
-- TOC entry 241 (class 1259 OID 31679)
-- Name: customer_status_groups; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_status_groups (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    label_vi character varying(255),
    label_en character varying(255),
    stage text NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT customer_status_groups_stage_check CHECK ((stage = ANY (ARRAY['lead'::text, 'student'::text, 'official'::text, 'lost'::text, 'spam'::text])))
);


ALTER TABLE public.customer_status_groups OWNER TO admin;

--
-- TOC entry 242 (class 1259 OID 31689)
-- Name: customer_statuses; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_statuses (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    label_vi character varying(255),
    label_en character varying(255),
    "group" text NOT NULL,
    status_group_id uuid,
    CONSTRAINT customer_statuses_group_check CHECK (("group" = ANY (ARRAY['lead'::text, 'student'::text, 'official'::text, 'lost'::text])))
);


ALTER TABLE public.customer_statuses OWNER TO admin;

--
-- TOC entry 243 (class 1259 OID 31698)
-- Name: customer_team_members; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_team_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id uuid NOT NULL,
    auth_user_id uuid NOT NULL,
    full_name text NOT NULL,
    phone text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.customer_team_members OWNER TO admin;

--
-- TOC entry 244 (class 1259 OID 31705)
-- Name: customer_views; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customer_views (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id uuid NOT NULL,
    sales_id uuid NOT NULL,
    viewed_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.customer_views OWNER TO admin;

--
-- TOC entry 245 (class 1259 OID 31710)
-- Name: customers; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.customers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    full_name character varying(255) NOT NULL,
    email character varying(255),
    phone character varying(20),
    company_name character varying(255),
    source character varying(100),
    assigned_sales_id uuid,
    organization_id uuid,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    created_by uuid,
    main_phone character varying(20),
    website character varying(255),
    status_id uuid,
    address character varying(500),
    main_email character varying(255),
    last_contact_at timestamp without time zone,
    gender character varying(10),
    region text DEFAULT 'VN'::text NOT NULL,
    merged_into_id uuid,
    customer_type text DEFAULT 'official'::text NOT NULL,
    source_campaign_id uuid,
    notes text,
    self_of_organization_id uuid,
    assigned_at timestamp without time zone,
    last_inbound_at timestamp with time zone,
    CONSTRAINT customers_customer_type_check CHECK ((customer_type = ANY (ARRAY['lead'::text, 'student'::text, 'official'::text, 'spam'::text, 'lost'::text]))),
    CONSTRAINT customers_gender_check CHECK (((gender IS NULL) OR ((gender)::text = ANY (ARRAY[('male'::character varying)::text, ('female'::character varying)::text]))))
);


ALTER TABLE public.customers OWNER TO admin;

--
-- TOC entry 246 (class 1259 OID 31722)
-- Name: file_links; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.file_links (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    file_id uuid NOT NULL,
    entity_type character varying(64) NOT NULL,
    entity_id uuid NOT NULL,
    purpose character varying(64) NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT file_links_display_order_check CHECK ((display_order >= 0)),
    CONSTRAINT file_links_entity_purpose_check CHECK ((((entity_type)::text <> ''::text) AND ((purpose)::text <> ''::text)))
);


ALTER TABLE public.file_links OWNER TO admin;

--
-- TOC entry 247 (class 1259 OID 31730)
-- Name: files; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    original_name text NOT NULL,
    storage_key text NOT NULL,
    mime_type text NOT NULL,
    size_bytes bigint NOT NULL,
    visibility character varying(32) NOT NULL,
    uploaded_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    deleted_at timestamp without time zone,
    CONSTRAINT files_size_bytes_check CHECK ((size_bytes >= 0)),
    CONSTRAINT files_visibility_check CHECK (((visibility)::text = ANY (ARRAY[('internal'::character varying)::text, ('customer_visible'::character varying)::text])))
);


ALTER TABLE public.files OWNER TO admin;

--
-- TOC entry 349 (class 1259 OID 45361)
-- Name: finished_goods_receipt_items; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.finished_goods_receipt_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    finished_goods_receipt_id uuid NOT NULL,
    product_item_id uuid
);


ALTER TABLE public.finished_goods_receipt_items OWNER TO admin;

--
-- TOC entry 348 (class 1259 OID 45343)
-- Name: finished_goods_receipts; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.finished_goods_receipts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    work_order_id uuid NOT NULL,
    qty numeric(18,4) NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    qty_scrap numeric(18,4) DEFAULT 0 NOT NULL,
    is_final boolean DEFAULT true NOT NULL,
    CONSTRAINT finished_goods_receipts_qty_check CHECK ((qty >= (0)::numeric)),
    CONSTRAINT finished_goods_receipts_qty_scrap_check CHECK ((qty_scrap >= (0)::numeric))
);


ALTER TABLE public.finished_goods_receipts OWNER TO admin;

--
-- TOC entry 355 (class 1259 OID 101514)
-- Name: goods_issue_code_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.goods_issue_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.goods_issue_code_seq OWNER TO admin;

--
-- TOC entry 328 (class 1259 OID 44903)
-- Name: goods_issue_items; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.goods_issue_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    goods_issue_id uuid NOT NULL,
    material_id uuid NOT NULL,
    serial_lot_id uuid,
    qty numeric(18,4) NOT NULL,
    reason text,
    CONSTRAINT goods_issue_items_qty_check CHECK ((qty > (0)::numeric))
);


ALTER TABLE public.goods_issue_items OWNER TO admin;

--
-- TOC entry 327 (class 1259 OID 44876)
-- Name: goods_issues; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.goods_issues (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    warehouse_id uuid NOT NULL,
    source_type character varying(20),
    source_id uuid,
    customer_id uuid,
    status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    decided_by uuid,
    decided_at timestamp without time zone,
    code character varying(30) DEFAULT ('PX-'::text || lpad((nextval('public.goods_issue_code_seq'::regclass))::text, 5, '0'::text)) NOT NULL,
    CONSTRAINT goods_issues_source_type_check CHECK (((source_type IS NULL) OR ((source_type)::text = ANY ((ARRAY['material_request'::character varying, 'work_order'::character varying, 'manual'::character varying])::text[])))),
    CONSTRAINT goods_issues_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'completed'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.goods_issues OWNER TO admin;

--
-- TOC entry 354 (class 1259 OID 101510)
-- Name: goods_receipt_code_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.goods_receipt_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.goods_receipt_code_seq OWNER TO admin;

--
-- TOC entry 326 (class 1259 OID 44856)
-- Name: goods_receipt_items; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.goods_receipt_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    goods_receipt_id uuid NOT NULL,
    material_id uuid NOT NULL,
    qty_received numeric(18,4) NOT NULL,
    price numeric(18,4) DEFAULT 0 NOT NULL,
    serial_lot_code character varying(100),
    supplier_id uuid,
    CONSTRAINT goods_receipt_items_qty_received_check CHECK ((qty_received > (0)::numeric))
);


ALTER TABLE public.goods_receipt_items OWNER TO admin;

--
-- TOC entry 325 (class 1259 OID 44835)
-- Name: goods_receipts; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.goods_receipts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    warehouse_id uuid NOT NULL,
    delivery_note_ref character varying(255) DEFAULT ''::character varying NOT NULL,
    status character varying(10) DEFAULT 'draft'::character varying NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    decided_by uuid,
    decided_at timestamp without time zone,
    code character varying(30) DEFAULT ('PN-'::text || lpad((nextval('public.goods_receipt_code_seq'::regclass))::text, 5, '0'::text)) NOT NULL,
    CONSTRAINT goods_receipts_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'completed'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.goods_receipts OWNER TO admin;

--
-- TOC entry 339 (class 1259 OID 45144)
-- Name: goods_return_items; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.goods_return_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    return_id uuid NOT NULL,
    material_id uuid NOT NULL,
    qty numeric(18,4) NOT NULL,
    reason text NOT NULL,
    CONSTRAINT goods_return_items_qty_check CHECK ((qty > (0)::numeric))
);


ALTER TABLE public.goods_return_items OWNER TO admin;

--
-- TOC entry 338 (class 1259 OID 45119)
-- Name: goods_returns; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.goods_returns (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    po_id uuid NOT NULL,
    goods_receipt_id uuid,
    warehouse_id uuid NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT goods_returns_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'sent_to_supplier'::character varying, 'resolved'::character varying])::text[])))
);


ALTER TABLE public.goods_returns OWNER TO admin;

--
-- TOC entry 248 (class 1259 OID 31739)
-- Name: iot_devices; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.iot_devices (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    device_id text NOT NULL,
    user_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    mac text,
    firmware_version text,
    secret_hash text
);


ALTER TABLE public.iot_devices OWNER TO admin;

--
-- TOC entry 310 (class 1259 OID 37529)
-- Name: iot_firmware_updates; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.iot_firmware_updates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    device_id text NOT NULL,
    firmware_id uuid NOT NULL,
    version text NOT NULL,
    from_version text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    pushed_at timestamp with time zone,
    confirmed_at timestamp with time zone,
    closed_at timestamp with time zone
);


ALTER TABLE public.iot_firmware_updates OWNER TO admin;

--
-- TOC entry 249 (class 1259 OID 31746)
-- Name: iot_firmwares; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.iot_firmwares (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    version text NOT NULL,
    sha256 text NOT NULL,
    size bigint NOT NULL,
    data bytea NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    filename text DEFAULT ''::text NOT NULL,
    enabled boolean DEFAULT true NOT NULL
);


ALTER TABLE public.iot_firmwares OWNER TO admin;

--
-- TOC entry 250 (class 1259 OID 31753)
-- Name: issue_reports; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.issue_reports (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    reporter_id uuid NOT NULL,
    category character varying(30) NOT NULL,
    alarm_code character varying(50),
    description text NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp without time zone,
    converted_case_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    severity character varying(20) DEFAULT 'normal'::character varying NOT NULL,
    CONSTRAINT chk_issue_reports_severity CHECK (((severity)::text = ANY (ARRAY[('normal'::character varying)::text, ('urgent'::character varying)::text])))
);


ALTER TABLE public.issue_reports OWNER TO admin;

--
-- TOC entry 251 (class 1259 OID 31764)
-- Name: keygen_history; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.keygen_history (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    key_type character varying(20) NOT NULL,
    input_data jsonb NOT NULL,
    output_data jsonb NOT NULL,
    generated_by uuid,
    organization_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    product_item_id uuid
);


ALTER TABLE public.keygen_history OWNER TO admin;

--
-- TOC entry 252 (class 1259 OID 31771)
-- Name: leads; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.leads (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    phone character varying(50) NOT NULL,
    email character varying(255),
    services jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    deleted_at timestamp without time zone,
    business_field text,
    notes text,
    source_campaign_id uuid
);


ALTER TABLE public.leads OWNER TO admin;

--
-- TOC entry 253 (class 1259 OID 31780)
-- Name: lock_requests; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.lock_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    requester_id uuid NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    reason text,
    approved_by uuid,
    unlock_key text,
    reject_reason text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    resolved_at timestamp without time zone,
    device_input text DEFAULT ''::text NOT NULL
);


ALTER TABLE public.lock_requests OWNER TO admin;

--
-- TOC entry 254 (class 1259 OID 31789)
-- Name: manualhub_activities; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.manualhub_activities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid,
    actor_id uuid,
    actor_name text,
    action character varying(64) NOT NULL,
    content text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.manualhub_activities OWNER TO admin;

--
-- TOC entry 255 (class 1259 OID 31796)
-- Name: manualhub_document_versions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.manualhub_document_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    version character varying(32) NOT NULL,
    title text NOT NULL,
    content jsonb,
    file_url text,
    created_by_name text,
    created_at timestamp without time zone DEFAULT now(),
    format character varying(32)
);


ALTER TABLE public.manualhub_document_versions OWNER TO admin;

--
-- TOC entry 256 (class 1259 OID 31803)
-- Name: manualhub_documents; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.manualhub_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    parent_id uuid,
    product_id uuid NOT NULL,
    title text NOT NULL,
    description text,
    document_type character varying(64),
    format character varying(32),
    content jsonb,
    status character varying(32) DEFAULT 'draft'::character varying NOT NULL,
    language character varying(16) DEFAULT 'vi'::character varying NOT NULL,
    version character varying(32) DEFAULT '1'::character varying NOT NULL,
    author_id uuid,
    author_name text,
    is_current boolean DEFAULT true NOT NULL,
    file_count integer DEFAULT 0 NOT NULL,
    submitted_at timestamp without time zone,
    released_at timestamp without time zone,
    rejection_reason text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    root_id uuid,
    document_group_id uuid NOT NULL,
    submitted_by_id uuid,
    submitted_by_name text,
    connection_types text[] DEFAULT '{}'::text[] NOT NULL
);


ALTER TABLE public.manualhub_documents OWNER TO admin;

--
-- TOC entry 342 (class 1259 OID 45197)
-- Name: manufacturing_work_orders; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.manufacturing_work_orders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    type character varying(10) NOT NULL,
    output_type character varying(20) DEFAULT 'none'::character varying NOT NULL,
    product_id uuid,
    product_item_id uuid,
    bom_id uuid,
    qty numeric(18,4),
    project_id uuid,
    task_id uuid,
    status character varying(20) DEFAULT 'planned'::character varying NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    product_name text DEFAULT ''::text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    start_date date,
    due_date date,
    CONSTRAINT manufacturing_work_orders_output_type_check CHECK (((output_type)::text = ANY ((ARRAY['product_item'::character varying, 'project_asset'::character varying, 'none'::character varying])::text[]))),
    CONSTRAINT manufacturing_work_orders_status_check CHECK (((status)::text = ANY ((ARRAY['planned'::character varying, 'in_progress'::character varying, 'qc'::character varying, 'done'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT manufacturing_work_orders_type_check CHECK (((type)::text = ANY ((ARRAY['production'::character varying, 'repair'::character varying])::text[])))
);


ALTER TABLE public.manufacturing_work_orders OWNER TO admin;

--
-- TOC entry 344 (class 1259 OID 45260)
-- Name: material_consumptions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.material_consumptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    work_order_id uuid NOT NULL,
    material_id uuid NOT NULL,
    qty_actual numeric(18,4) NOT NULL,
    serial_lot_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT material_consumptions_qty_actual_check CHECK ((qty_actual > (0)::numeric))
);


ALTER TABLE public.material_consumptions OWNER TO admin;

--
-- TOC entry 350 (class 1259 OID 45373)
-- Name: material_serial_lot_consumptions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.material_serial_lot_consumptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    output_type character varying(20) NOT NULL,
    output_id uuid NOT NULL,
    serial_lot_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT material_serial_lot_consumptions_output_type_check CHECK (((output_type)::text = ANY ((ARRAY['product_item'::character varying, 'project_asset'::character varying])::text[])))
);


ALTER TABLE public.material_serial_lot_consumptions OWNER TO admin;

--
-- TOC entry 323 (class 1259 OID 44776)
-- Name: material_serial_lots; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.material_serial_lots (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    material_id uuid NOT NULL,
    warehouse_id uuid NOT NULL,
    code character varying(100) NOT NULL,
    label_code character varying(100) NOT NULL,
    qty numeric(18,4) DEFAULT 1 NOT NULL,
    status character varying(10) DEFAULT 'in_stock'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT material_serial_lots_qty_check CHECK ((qty >= (0)::numeric)),
    CONSTRAINT material_serial_lots_status_check CHECK (((status)::text = ANY ((ARRAY['in_stock'::character varying, 'consumed'::character varying])::text[])))
);


ALTER TABLE public.material_serial_lots OWNER TO admin;

--
-- TOC entry 357 (class 1259 OID 101554)
-- Name: material_suppliers; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.material_suppliers (
    material_id uuid NOT NULL,
    supplier_id uuid NOT NULL,
    is_primary boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.material_suppliers OWNER TO admin;

--
-- TOC entry 320 (class 1259 OID 44731)
-- Name: materials; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.materials (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    sku character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    unit character varying(20) NOT NULL,
    tracking_type character varying(10) DEFAULT 'none'::character varying NOT NULL,
    reorder_point numeric(18,4),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    location text DEFAULT ''::text NOT NULL,
    CONSTRAINT materials_tracking_type_check CHECK (((tracking_type)::text = ANY ((ARRAY['none'::character varying, 'lot'::character varying, 'serial'::character varying])::text[])))
);


ALTER TABLE public.materials OWNER TO admin;

--
-- TOC entry 257 (class 1259 OID 31817)
-- Name: notification_delivery_log; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.notification_delivery_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    channel text DEFAULT 'email'::text NOT NULL,
    provider text NOT NULL,
    recipient text NOT NULL,
    template text,
    status text NOT NULL,
    error text,
    provider_message_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    sent_at timestamp with time zone,
    CONSTRAINT notification_delivery_log_channel_check CHECK ((channel = ANY (ARRAY['email'::text, 'zalo'::text, 'whatsapp'::text]))),
    CONSTRAINT notification_delivery_log_status_check CHECK ((status = ANY (ARRAY['sent'::text, 'failed'::text])))
);


ALTER TABLE public.notification_delivery_log OWNER TO admin;

--
-- TOC entry 258 (class 1259 OID 31827)
-- Name: notifications; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.notifications (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    type character varying(100) NOT NULL,
    params jsonb DEFAULT '{}'::jsonb NOT NULL,
    link character varying(500),
    data jsonb,
    read_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    device_acked_at timestamp with time zone,
    device_acked_by text,
    device_pushed_at timestamp with time zone,
    device_dismissed_at timestamp with time zone
);


ALTER TABLE public.notifications OWNER TO admin;

--
-- TOC entry 259 (class 1259 OID 31834)
-- Name: organizations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.organizations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    parent_id uuid,
    path text NOT NULL,
    level integer NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    agent_type character varying(20),
    created_by uuid,
    CONSTRAINT organizations_agent_type_check CHECK (((agent_type)::text = ANY (ARRAY[('managing'::character varying)::text, ('support'::character varying)::text])))
);


ALTER TABLE public.organizations OWNER TO admin;

--
-- TOC entry 260 (class 1259 OID 31844)
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.password_reset_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    token_hash text NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.password_reset_tokens OWNER TO admin;

--
-- TOC entry 261 (class 1259 OID 31851)
-- Name: permissions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.permissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(100) NOT NULL,
    description text
);


ALTER TABLE public.permissions OWNER TO admin;

--
-- TOC entry 317 (class 1259 OID 44648)
-- Name: phases; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.phases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    phase_order integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'todo'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT phases_status_check CHECK (((status)::text = ANY ((ARRAY['todo'::character varying, 'in_progress'::character varying, 'done'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.phases OWNER TO admin;

--
-- TOC entry 337 (class 1259 OID 45096)
-- Name: po_backorders; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.po_backorders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    po_id uuid NOT NULL,
    material_id uuid NOT NULL,
    qty_outstanding numeric(18,4) NOT NULL,
    status character varying(10) DEFAULT 'open'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT po_backorders_qty_outstanding_check CHECK ((qty_outstanding > (0)::numeric)),
    CONSTRAINT po_backorders_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'closed'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.po_backorders OWNER TO admin;

--
-- TOC entry 336 (class 1259 OID 45083)
-- Name: po_goods_receipts; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.po_goods_receipts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    po_id uuid NOT NULL,
    goods_receipt_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.po_goods_receipts OWNER TO admin;

--
-- TOC entry 262 (class 1259 OID 31857)
-- Name: product_agents; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_agents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    agent_organization_id uuid NOT NULL,
    agent_role character varying(20) NOT NULL,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone
);


ALTER TABLE public.product_agents OWNER TO admin;

--
-- TOC entry 263 (class 1259 OID 31862)
-- Name: product_item_activation_requests; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_item_activation_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    sales_user_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    organization_id uuid,
    inputs jsonb NOT NULL,
    status character varying(20) NOT NULL,
    result jsonb,
    reject_reason text,
    submitted_at timestamp with time zone DEFAULT now() NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    request_type character varying(32) DEFAULT 'activation'::character varying NOT NULL,
    warranty_expiry timestamp with time zone,
    CONSTRAINT chk_par_request_type CHECK (((request_type)::text = ANY (ARRAY[('activation'::character varying)::text, ('supplemental_product'::character varying)::text]))),
    CONSTRAINT product_item_activation_requests_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('approved'::character varying)::text, ('rejected'::character varying)::text])))
);


ALTER TABLE public.product_item_activation_requests OWNER TO admin;

--
-- TOC entry 264 (class 1259 OID 31874)
-- Name: product_item_aliases; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_item_aliases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    owner_customer_id uuid NOT NULL,
    alias text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.product_item_aliases OWNER TO admin;

--
-- TOC entry 265 (class 1259 OID 31882)
-- Name: product_item_logs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_item_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    event_type character varying(40) NOT NULL,
    actor_id uuid,
    actor_role character varying(40),
    source character varying(40),
    customer_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    occurred_at timestamp without time zone DEFAULT now() NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.product_item_logs OWNER TO admin;

--
-- TOC entry 266 (class 1259 OID 31891)
-- Name: product_item_recall_requests; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_item_recall_requests (
    id uuid NOT NULL,
    product_item_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    requested_by uuid NOT NULL,
    return_to_qs boolean DEFAULT true NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    confirmed_by uuid,
    confirmed_at timestamp with time zone,
    cancelled_by uuid,
    cancelled_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.product_item_recall_requests OWNER TO admin;

--
-- TOC entry 267 (class 1259 OID 31900)
-- Name: product_item_return_requests; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_item_return_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    requested_by uuid NOT NULL,
    organization_id uuid NOT NULL,
    item_ids jsonb NOT NULL,
    notes text DEFAULT ''::text NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    reject_reason text DEFAULT ''::text NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT product_item_return_requests_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('approved'::character varying)::text, ('rejected'::character varying)::text])))
);


ALTER TABLE public.product_item_return_requests OWNER TO admin;

--
-- TOC entry 268 (class 1259 OID 31911)
-- Name: product_items; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(100) NOT NULL,
    product_id uuid,
    customer_id uuid,
    manufacturing_date date,
    installation_date date,
    warranty_expiry date,
    status character varying(50) DEFAULT 'stock'::character varying NOT NULL,
    activated_at timestamp without time zone,
    activated_by uuid,
    activation_notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    recalled_at timestamp without time zone,
    recall_notes text DEFAULT ''::text NOT NULL,
    refurbished_at timestamp without time zone,
    refurbish_notes text DEFAULT ''::text NOT NULL,
    warranty_notified_at timestamp without time zone,
    device_input text,
    deleted_reason text
);


ALTER TABLE public.product_items OWNER TO admin;

--
-- TOC entry 314 (class 1259 OID 37691)
-- Name: product_ownership_transfer_requests; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_ownership_transfer_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    from_customer_id uuid NOT NULL,
    to_customer_id uuid NOT NULL,
    reason text DEFAULT ''::text NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    reject_reason text DEFAULT ''::text NOT NULL,
    requested_by uuid NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT product_ownership_transfer_requests_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'approved'::character varying, 'rejected'::character varying])::text[])))
);


ALTER TABLE public.product_ownership_transfer_requests OWNER TO admin;

--
-- TOC entry 269 (class 1259 OID 31922)
-- Name: product_ownerships; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_ownerships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    owner_customer_id uuid NOT NULL,
    is_current boolean DEFAULT true NOT NULL,
    transferred_from_ownership_id uuid,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone
);


ALTER TABLE public.product_ownerships OWNER TO admin;

--
-- TOC entry 270 (class 1259 OID 31928)
-- Name: product_support_limits; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_support_limits (
    product_id uuid NOT NULL,
    max_support_minutes integer DEFAULT 0 NOT NULL,
    max_messages integer DEFAULT 0 NOT NULL,
    max_emails integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.product_support_limits OWNER TO admin;

--
-- TOC entry 271 (class 1259 OID 31936)
-- Name: product_user_access; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.product_user_access (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    auth_user_id uuid NOT NULL,
    access_role character varying(20),
    invited_by uuid,
    created_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    role_id uuid,
    role_name text,
    CONSTRAINT chk_pua_builtin_or_custom CHECK ((((role_id IS NOT NULL) AND (access_role IS NULL)) OR ((role_id IS NULL) AND (access_role IS NOT NULL)) OR ((role_id IS NULL) AND (access_role IS NULL) AND (role_name IS NOT NULL))))
);


ALTER TABLE public.product_user_access OWNER TO admin;

--
-- TOC entry 272 (class 1259 OID 31944)
-- Name: products; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.products (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    model_number character varying(100),
    specifications jsonb,
    warranty_months integer DEFAULT 12,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    category character varying(20),
    CONSTRAINT products_category_check CHECK (((category)::text = ANY (ARRAY[('catalogue'::character varying)::text, ('controller'::character varying)::text, ('servo'::character varying)::text, ('inverter'::character varying)::text, ('software'::character varying)::text])))
);


ALTER TABLE public.products OWNER TO admin;

--
-- TOC entry 346 (class 1259 OID 45307)
-- Name: project_asset_components; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.project_asset_components (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_asset_id uuid NOT NULL,
    product_item_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    installed_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.project_asset_components OWNER TO admin;

--
-- TOC entry 345 (class 1259 OID 45279)
-- Name: project_assets; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.project_assets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    work_order_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    serial_no character varying(100),
    status character varying(20) DEFAULT 'building'::character varying NOT NULL,
    customer_id uuid,
    warranty_start date,
    warranty_end date,
    activated_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT project_assets_status_check CHECK (((status)::text = ANY ((ARRAY['building'::character varying, 'qc_passed'::character varying, 'delivered'::character varying, 'installed'::character varying, 'under_warranty'::character varying, 'recalled'::character varying, 'retired'::character varying])::text[])))
);


ALTER TABLE public.project_assets OWNER TO admin;

--
-- TOC entry 318 (class 1259 OID 44665)
-- Name: project_members; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.project_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    user_id uuid NOT NULL,
    added_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.project_members OWNER TO admin;

--
-- TOC entry 316 (class 1259 OID 44622)
-- Name: projects; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.projects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    project_type character varying(20) DEFAULT 'internal'::character varying NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    customer_id uuid,
    budget numeric(18,2),
    owner_id uuid NOT NULL,
    companydoc_node_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT projects_project_type_check CHECK (((project_type)::text = ANY ((ARRAY['rd'::character varying, 'project_build'::character varying, 'internal'::character varying])::text[]))),
    CONSTRAINT projects_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'on_hold'::character varying, 'completed'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.projects OWNER TO admin;

--
-- TOC entry 356 (class 1259 OID 101522)
-- Name: purchase_order_code_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.purchase_order_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.purchase_order_code_seq OWNER TO admin;

--
-- TOC entry 335 (class 1259 OID 45064)
-- Name: purchase_order_items; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.purchase_order_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    po_id uuid NOT NULL,
    material_id uuid NOT NULL,
    qty numeric(18,4) NOT NULL,
    price numeric(18,4) DEFAULT 0 NOT NULL,
    CONSTRAINT purchase_order_items_qty_check CHECK ((qty > (0)::numeric))
);


ALTER TABLE public.purchase_order_items OWNER TO admin;

--
-- TOC entry 334 (class 1259 OID 45037)
-- Name: purchase_orders; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.purchase_orders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    pr_id uuid,
    supplier_id uuid NOT NULL,
    status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    sent_at timestamp without time zone,
    sent_via character varying(10),
    expected_delivery_date date,
    code character varying(30) DEFAULT ('PO-'::text || lpad((nextval('public.purchase_order_code_seq'::regclass))::text, 5, '0'::text)) NOT NULL,
    CONSTRAINT purchase_orders_sent_via_check CHECK (((sent_via)::text = ANY ((ARRAY['email'::character varying, 'zalo'::character varying, 'manual'::character varying])::text[]))),
    CONSTRAINT purchase_orders_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'sent'::character varying, 'partially_received'::character varying, 'closed'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.purchase_orders OWNER TO admin;

--
-- TOC entry 358 (class 1259 OID 101596)
-- Name: purchase_requisition_code_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.purchase_requisition_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.purchase_requisition_code_seq OWNER TO admin;

--
-- TOC entry 333 (class 1259 OID 45019)
-- Name: purchase_requisition_items; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.purchase_requisition_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    pr_id uuid NOT NULL,
    material_id uuid NOT NULL,
    qty numeric(18,4) NOT NULL,
    approved_qty numeric(18,4),
    CONSTRAINT purchase_requisition_items_approved_qty_check CHECK ((approved_qty >= (0)::numeric)),
    CONSTRAINT purchase_requisition_items_qty_check CHECK ((qty > (0)::numeric))
);


ALTER TABLE public.purchase_requisition_items OWNER TO admin;

--
-- TOC entry 332 (class 1259 OID 44993)
-- Name: purchase_requisitions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.purchase_requisitions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_type character varying(20) DEFAULT 'manual'::character varying NOT NULL,
    source_id uuid,
    requested_by uuid NOT NULL,
    status character varying(20) DEFAULT 'pending_approval'::character varying NOT NULL,
    approved_by uuid,
    rejected_reason text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    deleted_at timestamp without time zone,
    reason text DEFAULT ''::text NOT NULL,
    code character varying(30) DEFAULT ('PR-'::text || lpad((nextval('public.purchase_requisition_code_seq'::regclass))::text, 5, '0'::text)) NOT NULL,
    CONSTRAINT purchase_requisitions_source_type_check CHECK (((source_type)::text = ANY ((ARRAY['material_request'::character varying, 'manual'::character varying])::text[]))),
    CONSTRAINT purchase_requisitions_status_check CHECK (((status)::text = ANY ((ARRAY['pending_approval'::character varying, 'approved'::character varying, 'rejected'::character varying, 'partially_converted'::character varying, 'converted'::character varying, 'closed'::character varying])::text[])))
);


ALTER TABLE public.purchase_requisitions OWNER TO admin;

--
-- TOC entry 273 (class 1259 OID 31954)
-- Name: push_device_tokens; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.push_device_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token text NOT NULL,
    platform text DEFAULT 'web'::text NOT NULL,
    user_agent text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.push_device_tokens OWNER TO admin;

--
-- TOC entry 347 (class 1259 OID 45326)
-- Name: qc_records; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.qc_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ref_type character varying(20) NOT NULL,
    ref_id uuid NOT NULL,
    result character varying(10) NOT NULL,
    inspector uuid NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT qc_records_ref_type_check CHECK (((ref_type)::text = ANY ((ARRAY['goods_receipt'::character varying, 'work_order'::character varying])::text[]))),
    CONSTRAINT qc_records_result_check CHECK (((result)::text = ANY ((ARRAY['pass'::character varying, 'fail'::character varying])::text[])))
);


ALTER TABLE public.qc_records OWNER TO admin;

--
-- TOC entry 274 (class 1259 OID 31963)
-- Name: rbac_audit_logs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.rbac_audit_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    action_type character varying(50) NOT NULL,
    performed_by uuid NOT NULL,
    target_user_id uuid,
    target_role_id uuid,
    target_permission_id uuid,
    target_organization_id uuid,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.rbac_audit_logs OWNER TO admin;

--
-- TOC entry 315 (class 1259 OID 37802)
-- Name: request_comments; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.request_comments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    request_kind character varying(32) NOT NULL,
    request_id uuid NOT NULL,
    author_id uuid NOT NULL,
    body text DEFAULT ''::text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT request_comments_request_kind_check CHECK (((request_kind)::text = ANY ((ARRAY['activation'::character varying, 'return'::character varying, 'lock'::character varying, 'transfer'::character varying])::text[])))
);


ALTER TABLE public.request_comments OWNER TO admin;

--
-- TOC entry 275 (class 1259 OID 31970)
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.role_permissions (
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL
);


ALTER TABLE public.role_permissions OWNER TO admin;

--
-- TOC entry 276 (class 1259 OID 31973)
-- Name: roles; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    data_scope public.data_scope DEFAULT 'SELF'::public.data_scope NOT NULL,
    kind character varying(20) DEFAULT 'system'::character varying NOT NULL,
    organization_id uuid,
    description character varying(500) DEFAULT ''::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    owner_customer_id uuid,
    CONSTRAINT chk_roles_kind_owner CHECK (((((kind)::text = 'system'::text) AND (owner_customer_id IS NULL) AND ((organization_id IS NULL) OR ((code)::text ~~ 'agent\_%'::text))) OR (((kind)::text = 'product'::text) AND (owner_customer_id IS NOT NULL))))
);


ALTER TABLE public.roles OWNER TO admin;

--
-- TOC entry 277 (class 1259 OID 31984)
-- Name: roles_owner_scope_rollback; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.roles_owner_scope_rollback (
    role_id uuid NOT NULL,
    organization_id uuid
);


ALTER TABLE public.roles_owner_scope_rollback OWNER TO admin;

--
-- TOC entry 278 (class 1259 OID 31987)
-- Name: sales_round_robin_state; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.sales_round_robin_state (
    id smallint DEFAULT 1 NOT NULL,
    last_assigned_sales_id uuid,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT sales_round_robin_state_id_check CHECK ((id = 1))
);


ALTER TABLE public.sales_round_robin_state OWNER TO admin;

--
-- TOC entry 279 (class 1259 OID 31993)
-- Name: sales_users; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.sales_users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    full_name character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    phone character varying(20),
    "position" character varying(100),
    status character varying(20) DEFAULT 'active'::character varying,
    organization_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone
);


ALTER TABLE public.sales_users OWNER TO admin;

--
-- TOC entry 280 (class 1259 OID 32002)
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.schema_migrations (
    version bigint NOT NULL,
    dirty boolean NOT NULL
);


ALTER TABLE public.schema_migrations OWNER TO admin;

--
-- TOC entry 281 (class 1259 OID 32005)
-- Name: service_logs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.service_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid,
    work_order_id uuid,
    service_date timestamp without time zone DEFAULT now() NOT NULL,
    service_type character varying(50) NOT NULL,
    issue_description text,
    action_taken text NOT NULL,
    parts_replaced jsonb,
    technician_id uuid,
    customer_notes text,
    internal_notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    source_comment_id uuid,
    event_type character varying(50),
    event_metadata jsonb,
    CONSTRAINT service_logs_event_type_matches_service_type CHECK ((((service_type)::text = 'event'::text) = (event_type IS NOT NULL)))
);


ALTER TABLE public.service_logs OWNER TO admin;

--
-- TOC entry 282 (class 1259 OID 32015)
-- Name: sessions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    refresh_token_hash text NOT NULL,
    access_token_jti uuid NOT NULL,
    device_info text,
    ip_address character varying(45),
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    revoked_at timestamp without time zone
);


ALTER TABLE public.sessions OWNER TO admin;

--
-- TOC entry 283 (class 1259 OID 32022)
-- Name: sso_tickets; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.sso_tickets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    token_hash text NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.sso_tickets OWNER TO admin;

--
-- TOC entry 322 (class 1259 OID 44751)
-- Name: stock; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.stock (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    material_id uuid NOT NULL,
    warehouse_id uuid NOT NULL,
    qty numeric(18,4) DEFAULT 0 NOT NULL,
    unit_cost numeric(18,4) DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT stock_qty_check CHECK ((qty >= (0)::numeric))
);


ALTER TABLE public.stock OWNER TO admin;

--
-- TOC entry 324 (class 1259 OID 44802)
-- Name: stock_movements; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.stock_movements (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    type character varying(10) NOT NULL,
    material_id uuid NOT NULL,
    warehouse_id uuid NOT NULL,
    qty numeric(18,4) NOT NULL,
    serial_lot_id uuid,
    source_type character varying(20),
    source_id uuid,
    reason text,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    related_warehouse_id uuid,
    CONSTRAINT stock_movements_source_type_check CHECK (((source_type IS NULL) OR ((source_type)::text = ANY ((ARRAY['goods_receipt'::character varying, 'goods_issue'::character varying, 'material_request'::character varying, 'work_order'::character varying, 'stocktake'::character varying, 'manual'::character varying, 'goods_return'::character varying])::text[])))),
    CONSTRAINT stock_movements_type_check CHECK (((type)::text = ANY ((ARRAY['in'::character varying, 'out'::character varying, 'transfer'::character varying, 'adjust'::character varying])::text[])))
);


ALTER TABLE public.stock_movements OWNER TO admin;

--
-- TOC entry 352 (class 1259 OID 84087)
-- Name: stocktake_code_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.stocktake_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stocktake_code_seq OWNER TO admin;

--
-- TOC entry 330 (class 1259 OID 44961)
-- Name: stocktake_lines; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.stocktake_lines (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    stocktake_id uuid NOT NULL,
    material_id uuid NOT NULL,
    system_qty numeric(18,4) NOT NULL,
    actual_qty numeric(18,4)
);


ALTER TABLE public.stocktake_lines OWNER TO admin;

--
-- TOC entry 329 (class 1259 OID 44940)
-- Name: stocktakes; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.stocktakes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    warehouse_id uuid NOT NULL,
    stocktake_date date DEFAULT CURRENT_DATE NOT NULL,
    status character varying(10) DEFAULT 'open'::character varying NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    code character varying(30) DEFAULT ('KK-'::text || lpad((nextval('public.stocktake_code_seq'::regclass))::text, 5, '0'::text)) NOT NULL,
    CONSTRAINT stocktakes_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'completed'::character varying])::text[])))
);


ALTER TABLE public.stocktakes OWNER TO admin;

--
-- TOC entry 284 (class 1259 OID 32029)
-- Name: students; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.students (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    full_name character varying(255) NOT NULL,
    email character varying(255),
    phone character varying(50) NOT NULL,
    business_field text,
    deposit_agreed boolean DEFAULT false NOT NULL,
    status character varying(20) DEFAULT 'registered'::character varying NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    deleted_at timestamp without time zone,
    source_campaign_id uuid
);


ALTER TABLE public.students OWNER TO admin;

--
-- TOC entry 331 (class 1259 OID 44983)
-- Name: suppliers; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.suppliers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    phone character varying(20),
    email character varying(255),
    address text,
    payment_terms character varying(255),
    rating numeric(3,2),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.suppliers OWNER TO admin;

--
-- TOC entry 285 (class 1259 OID 32039)
-- Name: support_appointments; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_appointments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    product_item_id uuid,
    customer_user_id uuid NOT NULL,
    support_user_id uuid,
    support_organization_id uuid,
    start_at_utc timestamp without time zone NOT NULL,
    end_at_utc timestamp without time zone NOT NULL,
    customer_timezone character varying(50) NOT NULL,
    status character varying(20) DEFAULT 'requested'::character varying NOT NULL,
    meeting_url text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    reminder_sent_at timestamp without time zone,
    start_notified_at timestamp without time zone
);


ALTER TABLE public.support_appointments OWNER TO admin;

--
-- TOC entry 286 (class 1259 OID 32048)
-- Name: support_assignments; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_assignments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    assigned_to uuid,
    support_organization_id uuid,
    is_current boolean DEFAULT true NOT NULL,
    assigned_by uuid,
    created_at timestamp without time zone DEFAULT now(),
    accepted_at timestamp with time zone,
    CONSTRAINT chk_support_assignments_target CHECK (((assigned_to IS NOT NULL) OR (support_organization_id IS NOT NULL)))
);


ALTER TABLE public.support_assignments OWNER TO admin;

--
-- TOC entry 287 (class 1259 OID 32055)
-- Name: support_attachments; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_attachments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    message_id uuid,
    file_id uuid NOT NULL,
    uploaded_by uuid,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.support_attachments OWNER TO admin;

--
-- TOC entry 288 (class 1259 OID 32060)
-- Name: support_cancel_requests; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_cancel_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    requested_by uuid NOT NULL,
    reason text,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    kind character varying(10) DEFAULT 'cancel'::character varying NOT NULL
);


ALTER TABLE public.support_cancel_requests OWNER TO admin;

--
-- TOC entry 289 (class 1259 OID 32070)
-- Name: support_case_events; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_case_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    old_value text,
    new_value text,
    actor_id uuid,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.support_case_events OWNER TO admin;

--
-- TOC entry 290 (class 1259 OID 32077)
-- Name: support_cases; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_cases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_number character varying(50) NOT NULL,
    product_item_id uuid,
    customer_organization_id uuid,
    created_by uuid NOT NULL,
    category character varying(30) NOT NULL,
    priority character varying(20) DEFAULT 'normal'::character varying NOT NULL,
    status character varying(30) DEFAULT 'new'::character varying NOT NULL,
    subject character varying(255) NOT NULL,
    description text,
    first_response_at timestamp without time zone,
    resolved_at timestamp without time zone,
    closed_at timestamp without time zone,
    document_id uuid,
    document_version character varying(50),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone,
    period_started_at timestamp without time zone DEFAULT now() NOT NULL,
    long_session_notified_at timestamp without time zone,
    work_order_id uuid,
    support_mode text DEFAULT 'video_call'::text NOT NULL,
    customer_hidden_at timestamp without time zone,
    session_ended_at timestamp with time zone,
    session_started_at timestamp with time zone,
    session_minutes_charged integer DEFAULT 0 NOT NULL,
    session_exhausted_at timestamp with time zone,
    overtime_due_at timestamp with time zone,
    overtime_asked_at timestamp with time zone,
    reject_reason text
);


ALTER TABLE public.support_cases OWNER TO admin;

--
-- TOC entry 291 (class 1259 OID 32090)
-- Name: support_entitlement_transactions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_entitlement_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    entitlement_id uuid NOT NULL,
    case_id uuid,
    time_entry_id uuid,
    type character varying(20) NOT NULL,
    delta_minutes integer NOT NULL,
    balance_after_minutes integer NOT NULL,
    description text,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now(),
    kind character varying(20) DEFAULT 'minutes'::character varying NOT NULL,
    delta_messages integer DEFAULT 0 NOT NULL,
    balance_after_messages integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.support_entitlement_transactions OWNER TO admin;

--
-- TOC entry 292 (class 1259 OID 32100)
-- Name: support_entitlements; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_entitlements (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_item_id uuid NOT NULL,
    included_minutes integer DEFAULT 0 NOT NULL,
    used_minutes integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    low_balance_notified_at timestamp without time zone,
    included_messages integer DEFAULT 0 NOT NULL,
    used_messages integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.support_entitlements OWNER TO admin;

--
-- TOC entry 293 (class 1259 OID 32110)
-- Name: support_messages; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    sender_id uuid,
    type character varying(20) NOT NULL,
    body text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    translated_body text,
    translated_lang character varying(8),
    translated_at timestamp without time zone,
    translated_source character varying(20),
    reply_to_id uuid,
    recalled_at timestamp with time zone,
    recalled_by uuid
);


ALTER TABLE public.support_messages OWNER TO admin;

--
-- TOC entry 294 (class 1259 OID 32117)
-- Name: support_ratings; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_ratings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    resolution character varying(30),
    score smallint NOT NULL,
    comment text,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now(),
    product_item_id uuid,
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT support_ratings_score_check CHECK (((score >= 1) AND (score <= 5)))
);


ALTER TABLE public.support_ratings OWNER TO admin;

--
-- TOC entry 295 (class 1259 OID 32126)
-- Name: support_time_entries; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_time_entries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    appointment_id uuid,
    source character varying(20) NOT NULL,
    duration_minutes integer NOT NULL,
    occurred_at timestamp without time zone NOT NULL,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.support_time_entries OWNER TO admin;

--
-- TOC entry 307 (class 1259 OID 33416)
-- Name: support_waiting_message_events; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_waiting_message_events (
    id uuid NOT NULL,
    message_id uuid NOT NULL,
    type text NOT NULL,
    actor_id uuid,
    target_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.support_waiting_message_events OWNER TO admin;

--
-- TOC entry 308 (class 1259 OID 33434)
-- Name: support_waiting_message_helpers; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_waiting_message_helpers (
    message_id uuid NOT NULL,
    user_id uuid NOT NULL,
    added_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.support_waiting_message_helpers OWNER TO admin;

--
-- TOC entry 296 (class 1259 OID 32131)
-- Name: support_waiting_message_replies; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_waiting_message_replies (
    id uuid NOT NULL,
    message_id uuid NOT NULL,
    author_id uuid NOT NULL,
    content text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    reply_to_id uuid,
    recalled_at timestamp with time zone,
    recalled_by uuid
);


ALTER TABLE public.support_waiting_message_replies OWNER TO admin;

--
-- TOC entry 297 (class 1259 OID 32137)
-- Name: support_waiting_message_views; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_waiting_message_views (
    message_id uuid NOT NULL,
    user_id uuid NOT NULL,
    seen_at timestamp with time zone DEFAULT now() NOT NULL,
    marked_unread boolean DEFAULT false NOT NULL
);


ALTER TABLE public.support_waiting_message_views OWNER TO admin;

--
-- TOC entry 298 (class 1259 OID 32142)
-- Name: support_waiting_messages; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.support_waiting_messages (
    id uuid NOT NULL,
    product_item_id uuid,
    created_by uuid NOT NULL,
    title character varying(255) NOT NULL,
    content text DEFAULT ''::text NOT NULL,
    status character varying(20) DEFAULT 'waiting'::character varying NOT NULL,
    handled_by uuid,
    handled_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    assigned_to uuid,
    assigned_by uuid,
    assigned_at timestamp with time zone,
    escalated_at timestamp with time zone,
    escalated_by uuid,
    customer_seen_at timestamp with time zone,
    customer_marked_unread boolean DEFAULT false NOT NULL,
    staff_deleted_at timestamp with time zone,
    customer_deleted_at timestamp with time zone,
    customer_id uuid NOT NULL
);


ALTER TABLE public.support_waiting_messages OWNER TO admin;

--
-- TOC entry 319 (class 1259 OID 44686)
-- Name: tasks; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid,
    phase_id uuid,
    title character varying(255) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    priority character varying(20) DEFAULT 'medium'::character varying NOT NULL,
    due_date date,
    status character varying(20) DEFAULT 'todo'::character varying NOT NULL,
    parent_task_id uuid,
    assignee_id uuid NOT NULL,
    estimated_finish_date date,
    source_type character varying(20),
    source_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT tasks_priority_check CHECK (((priority)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'urgent'::character varying])::text[]))),
    CONSTRAINT tasks_source_type_check CHECK (((source_type IS NULL) OR ((source_type)::text = ANY ((ARRAY['support_case'::character varying, 'work_order'::character varying])::text[])))),
    CONSTRAINT tasks_status_check CHECK (((status)::text = ANY ((ARRAY['todo'::character varying, 'in_progress'::character varying, 'done'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.tasks OWNER TO admin;

--
-- TOC entry 299 (class 1259 OID 32151)
-- Name: user_organizations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.user_organizations (
    user_id uuid NOT NULL,
    organization_id uuid NOT NULL
);


ALTER TABLE public.user_organizations OWNER TO admin;

--
-- TOC entry 353 (class 1259 OID 87113)
-- Name: user_permissions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.user_permissions (
    user_id uuid NOT NULL,
    permission_id uuid NOT NULL,
    granted_by uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_permissions OWNER TO admin;

--
-- TOC entry 300 (class 1259 OID 32154)
-- Name: user_profiles; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.user_profiles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    first_name character varying(255),
    last_name character varying(255),
    avatar_url character varying(500),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.user_profiles OWNER TO admin;

--
-- TOC entry 301 (class 1259 OID 32162)
-- Name: user_roles; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.user_roles (
    user_id uuid NOT NULL,
    role_id uuid NOT NULL
);


ALTER TABLE public.user_roles OWNER TO admin;

--
-- TOC entry 302 (class 1259 OID 32165)
-- Name: user_role_permissions; Type: VIEW; Schema: public; Owner: admin
--

CREATE VIEW public.user_role_permissions AS
 SELECT ur.user_id,
    ur.role_id,
    rp.permission_id
   FROM (public.user_roles ur
     JOIN public.role_permissions rp ON ((rp.role_id = ur.role_id)));


ALTER VIEW public.user_role_permissions OWNER TO admin;

--
-- TOC entry 303 (class 1259 OID 32169)
-- Name: user_types; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.user_types (
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.user_types OWNER TO admin;

--
-- TOC entry 304 (class 1259 OID 32175)
-- Name: verification_codes; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.verification_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    auth_user_id uuid,
    type character varying(20) NOT NULL,
    target character varying(255) NOT NULL,
    code character varying(10) NOT NULL,
    code_hash character varying(255) NOT NULL,
    purpose character varying(50) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    verified_at timestamp without time zone,
    attempts integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.verification_codes OWNER TO admin;

--
-- TOC entry 351 (class 1259 OID 84077)
-- Name: warehouse_code_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.warehouse_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.warehouse_code_seq OWNER TO admin;

--
-- TOC entry 321 (class 1259 OID 44743)
-- Name: warehouses; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.warehouses (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    address text DEFAULT ''::text NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    code character varying(30) DEFAULT ('KHO-'::text || lpad((nextval('public.warehouse_code_seq'::regclass))::text, 3, '0'::text)) NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    CONSTRAINT warehouses_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'paused'::character varying, 'closed'::character varying])::text[])))
);


ALTER TABLE public.warehouses OWNER TO admin;

--
-- TOC entry 343 (class 1259 OID 45238)
-- Name: wo_operations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.wo_operations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    work_order_id uuid NOT NULL,
    step_name character varying(255) NOT NULL,
    step_order integer DEFAULT 0 NOT NULL,
    assignee_id uuid,
    status character varying(20) DEFAULT 'todo'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT wo_operations_status_check CHECK (((status)::text = ANY ((ARRAY['todo'::character varying, 'in_progress'::character varying, 'done'::character varying])::text[])))
);


ALTER TABLE public.wo_operations OWNER TO admin;

--
-- TOC entry 305 (class 1259 OID 32183)
-- Name: work_order_comments; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.work_order_comments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    work_order_id uuid NOT NULL,
    author_id uuid NOT NULL,
    content text NOT NULL,
    is_internal boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    deleted_at timestamp without time zone,
    CONSTRAINT work_order_comments_content_check CHECK ((length(btrim(content)) > 0))
);


ALTER TABLE public.work_order_comments OWNER TO admin;

--
-- TOC entry 306 (class 1259 OID 32193)
-- Name: work_orders; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.work_orders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    order_number character varying(50) NOT NULL,
    product_item_id uuid,
    type character varying(50) NOT NULL,
    priority character varying(20) DEFAULT 'normal'::character varying,
    assigned_to uuid,
    description text,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    scheduled_date date,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    deleted_at timestamp without time zone
);


ALTER TABLE public.work_orders OWNER TO admin;

--
-- TOC entry 4405 (class 2606 OID 32204)
-- Name: activities activities_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT activities_pkey PRIMARY KEY (id);


--
-- TOC entry 4410 (class 2606 OID 32206)
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (key);


--
-- TOC entry 4412 (class 2606 OID 32208)
-- Name: auth_users auth_users_email_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.auth_users
    ADD CONSTRAINT auth_users_email_key UNIQUE (email);


--
-- TOC entry 4414 (class 2606 OID 32210)
-- Name: auth_users auth_users_phone_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.auth_users
    ADD CONSTRAINT auth_users_phone_key UNIQUE (phone);


--
-- TOC entry 4416 (class 2606 OID 32212)
-- Name: auth_users auth_users_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.auth_users
    ADD CONSTRAINT auth_users_pkey PRIMARY KEY (id);


--
-- TOC entry 4418 (class 2606 OID 32214)
-- Name: auth_users auth_users_username_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.auth_users
    ADD CONSTRAINT auth_users_username_key UNIQUE (username);


--
-- TOC entry 4933 (class 2606 OID 45190)
-- Name: bom_components bom_components_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.bom_components
    ADD CONSTRAINT bom_components_pkey PRIMARY KEY (id);


--
-- TOC entry 4930 (class 2606 OID 45176)
-- Name: boms boms_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.boms
    ADD CONSTRAINT boms_pkey PRIMARY KEY (id);


--
-- TOC entry 4424 (class 2606 OID 32216)
-- Name: business_fields business_fields_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.business_fields
    ADD CONSTRAINT business_fields_pkey PRIMARY KEY (id);


--
-- TOC entry 4427 (class 2606 OID 32218)
-- Name: campaign_registrations campaign_registrations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaign_registrations
    ADD CONSTRAINT campaign_registrations_pkey PRIMARY KEY (id);


--
-- TOC entry 4431 (class 2606 OID 32220)
-- Name: campaign_visits campaign_visits_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaign_visits
    ADD CONSTRAINT campaign_visits_pkey PRIMARY KEY (id);


--
-- TOC entry 4434 (class 2606 OID 32222)
-- Name: campaigns campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_pkey PRIMARY KEY (id);


--
-- TOC entry 4436 (class 2606 OID 32224)
-- Name: campaigns campaigns_slug_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_slug_key UNIQUE (slug);


--
-- TOC entry 4813 (class 2606 OID 37566)
-- Name: chat_conversations chat_conversations_direct_key_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_conversations
    ADD CONSTRAINT chat_conversations_direct_key_key UNIQUE (direct_key);


--
-- TOC entry 4815 (class 2606 OID 37564)
-- Name: chat_conversations chat_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_conversations
    ADD CONSTRAINT chat_conversations_pkey PRIMARY KEY (id);


--
-- TOC entry 4821 (class 2606 OID 37598)
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- TOC entry 4817 (class 2606 OID 37577)
-- Name: chat_participants chat_participants_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_participants
    ADD CONSTRAINT chat_participants_pkey PRIMARY KEY (conversation_id, user_id);


--
-- TOC entry 4807 (class 2606 OID 33546)
-- Name: company_doc_node_products company_doc_node_products_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_node_products
    ADD CONSTRAINT company_doc_node_products_pkey PRIMARY KEY (node_id, product_id);


--
-- TOC entry 4440 (class 2606 OID 32226)
-- Name: company_doc_node_versions company_doc_node_versions_node_id_version_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_node_versions
    ADD CONSTRAINT company_doc_node_versions_node_id_version_key UNIQUE (node_id, version);


--
-- TOC entry 4442 (class 2606 OID 32228)
-- Name: company_doc_node_versions company_doc_node_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_node_versions
    ADD CONSTRAINT company_doc_node_versions_pkey PRIMARY KEY (id);


--
-- TOC entry 4445 (class 2606 OID 32230)
-- Name: company_doc_nodes company_doc_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_nodes
    ADD CONSTRAINT company_doc_nodes_pkey PRIMARY KEY (id);


--
-- TOC entry 4453 (class 2606 OID 32232)
-- Name: contact_messages contact_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.contact_messages
    ADD CONSTRAINT contact_messages_pkey PRIMARY KEY (id);


--
-- TOC entry 4457 (class 2606 OID 32234)
-- Name: customer_business_fields customer_business_fields_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_business_fields
    ADD CONSTRAINT customer_business_fields_pkey PRIMARY KEY (customer_id, business_field_id);


--
-- TOC entry 4461 (class 2606 OID 32236)
-- Name: customer_customer_groups customer_customer_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_customer_groups
    ADD CONSTRAINT customer_customer_groups_pkey PRIMARY KEY (customer_id, customer_group_id);


--
-- TOC entry 4465 (class 2606 OID 32238)
-- Name: customer_groups customer_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_groups
    ADD CONSTRAINT customer_groups_pkey PRIMARY KEY (id);


--
-- TOC entry 4468 (class 2606 OID 32240)
-- Name: customer_logs customer_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_logs
    ADD CONSTRAINT customer_logs_pkey PRIMARY KEY (id);


--
-- TOC entry 4472 (class 2606 OID 32242)
-- Name: customer_new_interactions customer_new_interactions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_new_interactions
    ADD CONSTRAINT customer_new_interactions_pkey PRIMARY KEY (customer_id);


--
-- TOC entry 4474 (class 2606 OID 32244)
-- Name: customer_status_groups customer_status_groups_name_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_status_groups
    ADD CONSTRAINT customer_status_groups_name_key UNIQUE (name);


--
-- TOC entry 4476 (class 2606 OID 32246)
-- Name: customer_status_groups customer_status_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_status_groups
    ADD CONSTRAINT customer_status_groups_pkey PRIMARY KEY (id);


--
-- TOC entry 4478 (class 2606 OID 32248)
-- Name: customer_statuses customer_statuses_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_statuses
    ADD CONSTRAINT customer_statuses_pkey PRIMARY KEY (id);


--
-- TOC entry 4481 (class 2606 OID 32250)
-- Name: customer_team_members customer_team_members_customer_user_uniq; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_team_members
    ADD CONSTRAINT customer_team_members_customer_user_uniq UNIQUE (customer_id, auth_user_id);


--
-- TOC entry 4483 (class 2606 OID 32252)
-- Name: customer_team_members customer_team_members_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_team_members
    ADD CONSTRAINT customer_team_members_pkey PRIMARY KEY (id);


--
-- TOC entry 4486 (class 2606 OID 32254)
-- Name: customer_views customer_views_customer_id_sales_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_views
    ADD CONSTRAINT customer_views_customer_id_sales_id_key UNIQUE (customer_id, sales_id);


--
-- TOC entry 4488 (class 2606 OID 32256)
-- Name: customer_views customer_views_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_views
    ADD CONSTRAINT customer_views_pkey PRIMARY KEY (id);


--
-- TOC entry 4493 (class 2606 OID 32258)
-- Name: customers customers_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_code_key UNIQUE (code);


--
-- TOC entry 4495 (class 2606 OID 32260)
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- TOC entry 4497 (class 2606 OID 32262)
-- Name: customers customers_self_of_organization_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_self_of_organization_id_key UNIQUE (self_of_organization_id);


--
-- TOC entry 4513 (class 2606 OID 32264)
-- Name: file_links file_links_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.file_links
    ADD CONSTRAINT file_links_pkey PRIMARY KEY (id);


--
-- TOC entry 4515 (class 2606 OID 32266)
-- Name: file_links file_links_unique_entity_file_purpose; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.file_links
    ADD CONSTRAINT file_links_unique_entity_file_purpose UNIQUE (file_id, entity_type, entity_id, purpose);


--
-- TOC entry 4519 (class 2606 OID 32268)
-- Name: files files_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);


--
-- TOC entry 4521 (class 2606 OID 32270)
-- Name: files files_storage_key_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_storage_key_key UNIQUE (storage_key);


--
-- TOC entry 4961 (class 2606 OID 45366)
-- Name: finished_goods_receipt_items finished_goods_receipt_items_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.finished_goods_receipt_items
    ADD CONSTRAINT finished_goods_receipt_items_pkey PRIMARY KEY (id);


--
-- TOC entry 4959 (class 2606 OID 45350)
-- Name: finished_goods_receipts finished_goods_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.finished_goods_receipts
    ADD CONSTRAINT finished_goods_receipts_pkey PRIMARY KEY (id);


--
-- TOC entry 4887 (class 2606 OID 44911)
-- Name: goods_issue_items goods_issue_items_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issue_items
    ADD CONSTRAINT goods_issue_items_pkey PRIMARY KEY (id);


--
-- TOC entry 4882 (class 2606 OID 101517)
-- Name: goods_issues goods_issues_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issues
    ADD CONSTRAINT goods_issues_code_key UNIQUE (code);


--
-- TOC entry 4884 (class 2606 OID 44886)
-- Name: goods_issues goods_issues_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issues
    ADD CONSTRAINT goods_issues_pkey PRIMARY KEY (id);


--
-- TOC entry 4879 (class 2606 OID 44864)
-- Name: goods_receipt_items goods_receipt_items_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipt_items
    ADD CONSTRAINT goods_receipt_items_pkey PRIMARY KEY (id);


--
-- TOC entry 4875 (class 2606 OID 101513)
-- Name: goods_receipts goods_receipts_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipts
    ADD CONSTRAINT goods_receipts_code_key UNIQUE (code);


--
-- TOC entry 4877 (class 2606 OID 44845)
-- Name: goods_receipts goods_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipts
    ADD CONSTRAINT goods_receipts_pkey PRIMARY KEY (id);


--
-- TOC entry 4927 (class 2606 OID 45152)
-- Name: goods_return_items goods_return_items_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_return_items
    ADD CONSTRAINT goods_return_items_pkey PRIMARY KEY (id);


--
-- TOC entry 4925 (class 2606 OID 45128)
-- Name: goods_returns goods_returns_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_returns
    ADD CONSTRAINT goods_returns_pkey PRIMARY KEY (id);


--
-- TOC entry 4525 (class 2606 OID 32272)
-- Name: iot_devices iot_devices_device_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_devices
    ADD CONSTRAINT iot_devices_device_id_key UNIQUE (device_id);


--
-- TOC entry 4527 (class 2606 OID 32274)
-- Name: iot_devices iot_devices_mac_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_devices
    ADD CONSTRAINT iot_devices_mac_key UNIQUE (mac);


--
-- TOC entry 4529 (class 2606 OID 32276)
-- Name: iot_devices iot_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_devices
    ADD CONSTRAINT iot_devices_pkey PRIMARY KEY (id);


--
-- TOC entry 4531 (class 2606 OID 32278)
-- Name: iot_devices iot_devices_user_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_devices
    ADD CONSTRAINT iot_devices_user_id_key UNIQUE (user_id);


--
-- TOC entry 4811 (class 2606 OID 37538)
-- Name: iot_firmware_updates iot_firmware_updates_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_firmware_updates
    ADD CONSTRAINT iot_firmware_updates_pkey PRIMARY KEY (id);


--
-- TOC entry 4533 (class 2606 OID 32280)
-- Name: iot_firmwares iot_firmwares_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_firmwares
    ADD CONSTRAINT iot_firmwares_pkey PRIMARY KEY (id);


--
-- TOC entry 4535 (class 2606 OID 32282)
-- Name: iot_firmwares iot_firmwares_version_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_firmwares
    ADD CONSTRAINT iot_firmwares_version_key UNIQUE (version);


--
-- TOC entry 4538 (class 2606 OID 32284)
-- Name: issue_reports issue_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.issue_reports
    ADD CONSTRAINT issue_reports_pkey PRIMARY KEY (id);


--
-- TOC entry 4545 (class 2606 OID 32286)
-- Name: keygen_history keygen_history_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.keygen_history
    ADD CONSTRAINT keygen_history_pkey PRIMARY KEY (id);


--
-- TOC entry 4548 (class 2606 OID 32288)
-- Name: leads leads_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.leads
    ADD CONSTRAINT leads_pkey PRIMARY KEY (id);


--
-- TOC entry 4552 (class 2606 OID 32290)
-- Name: lock_requests lock_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.lock_requests
    ADD CONSTRAINT lock_requests_pkey PRIMARY KEY (id);


--
-- TOC entry 4555 (class 2606 OID 32292)
-- Name: manualhub_activities manualhub_activities_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manualhub_activities
    ADD CONSTRAINT manualhub_activities_pkey PRIMARY KEY (id);


--
-- TOC entry 4558 (class 2606 OID 32294)
-- Name: manualhub_document_versions manualhub_document_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manualhub_document_versions
    ADD CONSTRAINT manualhub_document_versions_pkey PRIMARY KEY (id);


--
-- TOC entry 4566 (class 2606 OID 32296)
-- Name: manualhub_documents manualhub_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manualhub_documents
    ADD CONSTRAINT manualhub_documents_pkey PRIMARY KEY (id);


--
-- TOC entry 4939 (class 2606 OID 45209)
-- Name: manufacturing_work_orders manufacturing_work_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manufacturing_work_orders
    ADD CONSTRAINT manufacturing_work_orders_pkey PRIMARY KEY (id);


--
-- TOC entry 4945 (class 2606 OID 45267)
-- Name: material_consumptions material_consumptions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_consumptions
    ADD CONSTRAINT material_consumptions_pkey PRIMARY KEY (id);


--
-- TOC entry 4965 (class 2606 OID 45380)
-- Name: material_serial_lot_consumptions material_serial_lot_consumptions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_serial_lot_consumptions
    ADD CONSTRAINT material_serial_lot_consumptions_pkey PRIMARY KEY (id);


--
-- TOC entry 4867 (class 2606 OID 44790)
-- Name: material_serial_lots material_serial_lots_label_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_serial_lots
    ADD CONSTRAINT material_serial_lots_label_code_key UNIQUE (label_code);


--
-- TOC entry 4869 (class 2606 OID 44788)
-- Name: material_serial_lots material_serial_lots_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_serial_lots
    ADD CONSTRAINT material_serial_lots_pkey PRIMARY KEY (id);


--
-- TOC entry 4971 (class 2606 OID 101560)
-- Name: material_suppliers material_suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_suppliers
    ADD CONSTRAINT material_suppliers_pkey PRIMARY KEY (material_id, supplier_id);


--
-- TOC entry 4853 (class 2606 OID 44740)
-- Name: materials materials_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_pkey PRIMARY KEY (id);


--
-- TOC entry 4855 (class 2606 OID 44742)
-- Name: materials materials_sku_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_sku_key UNIQUE (sku);


--
-- TOC entry 4570 (class 2606 OID 32298)
-- Name: notification_delivery_log notification_delivery_log_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.notification_delivery_log
    ADD CONSTRAINT notification_delivery_log_pkey PRIMARY KEY (id);


--
-- TOC entry 4575 (class 2606 OID 32300)
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- TOC entry 4580 (class 2606 OID 32302)
-- Name: organizations organizations_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_code_key UNIQUE (code);


--
-- TOC entry 4582 (class 2606 OID 32304)
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- TOC entry 4587 (class 2606 OID 32306)
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- TOC entry 4589 (class 2606 OID 32308)
-- Name: permissions permissions_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_code_key UNIQUE (code);


--
-- TOC entry 4591 (class 2606 OID 32310)
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- TOC entry 4838 (class 2606 OID 44658)
-- Name: phases phases_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.phases
    ADD CONSTRAINT phases_pkey PRIMARY KEY (id);


--
-- TOC entry 4923 (class 2606 OID 45106)
-- Name: po_backorders po_backorders_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.po_backorders
    ADD CONSTRAINT po_backorders_pkey PRIMARY KEY (id);


--
-- TOC entry 4919 (class 2606 OID 45089)
-- Name: po_goods_receipts po_goods_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.po_goods_receipts
    ADD CONSTRAINT po_goods_receipts_pkey PRIMARY KEY (id);


--
-- TOC entry 4594 (class 2606 OID 32312)
-- Name: product_agents product_agents_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_agents
    ADD CONSTRAINT product_agents_pkey PRIMARY KEY (id);


--
-- TOC entry 4601 (class 2606 OID 32314)
-- Name: product_item_activation_requests product_item_activation_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_activation_requests
    ADD CONSTRAINT product_item_activation_requests_pkey PRIMARY KEY (id);


--
-- TOC entry 4604 (class 2606 OID 32316)
-- Name: product_item_aliases product_item_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_aliases
    ADD CONSTRAINT product_item_aliases_pkey PRIMARY KEY (id);


--
-- TOC entry 4606 (class 2606 OID 32318)
-- Name: product_item_aliases product_item_aliases_product_item_id_owner_customer_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_aliases
    ADD CONSTRAINT product_item_aliases_product_item_id_owner_customer_id_key UNIQUE (product_item_id, owner_customer_id);


--
-- TOC entry 4611 (class 2606 OID 32320)
-- Name: product_item_logs product_item_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_logs
    ADD CONSTRAINT product_item_logs_pkey PRIMARY KEY (id);


--
-- TOC entry 4615 (class 2606 OID 32322)
-- Name: product_item_recall_requests product_item_recall_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_recall_requests
    ADD CONSTRAINT product_item_recall_requests_pkey PRIMARY KEY (id);


--
-- TOC entry 4620 (class 2606 OID 32324)
-- Name: product_item_return_requests product_item_return_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_return_requests
    ADD CONSTRAINT product_item_return_requests_pkey PRIMARY KEY (id);


--
-- TOC entry 4628 (class 2606 OID 32326)
-- Name: product_items product_items_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_items
    ADD CONSTRAINT product_items_pkey PRIMARY KEY (id);


--
-- TOC entry 4825 (class 2606 OID 37703)
-- Name: product_ownership_transfer_requests product_ownership_transfer_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownership_transfer_requests
    ADD CONSTRAINT product_ownership_transfer_requests_pkey PRIMARY KEY (id);


--
-- TOC entry 4632 (class 2606 OID 32328)
-- Name: product_ownerships product_ownerships_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownerships
    ADD CONSTRAINT product_ownerships_pkey PRIMARY KEY (id);


--
-- TOC entry 4635 (class 2606 OID 32330)
-- Name: product_support_limits product_support_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_support_limits
    ADD CONSTRAINT product_support_limits_pkey PRIMARY KEY (product_id);


--
-- TOC entry 4641 (class 2606 OID 32332)
-- Name: product_user_access product_user_access_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_user_access
    ADD CONSTRAINT product_user_access_pkey PRIMARY KEY (id);


--
-- TOC entry 4649 (class 2606 OID 32334)
-- Name: products products_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_code_key UNIQUE (code);


--
-- TOC entry 4651 (class 2606 OID 32336)
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- TOC entry 4954 (class 2606 OID 45313)
-- Name: project_asset_components project_asset_components_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_asset_components
    ADD CONSTRAINT project_asset_components_pkey PRIMARY KEY (id);


--
-- TOC entry 4948 (class 2606 OID 45288)
-- Name: project_assets project_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_assets
    ADD CONSTRAINT project_assets_pkey PRIMARY KEY (id);


--
-- TOC entry 4950 (class 2606 OID 45290)
-- Name: project_assets project_assets_serial_no_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_assets
    ADD CONSTRAINT project_assets_serial_no_key UNIQUE (serial_no);


--
-- TOC entry 4842 (class 2606 OID 44671)
-- Name: project_members project_members_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_pkey PRIMARY KEY (id);


--
-- TOC entry 4844 (class 2606 OID 44673)
-- Name: project_members project_members_project_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_project_id_user_id_key UNIQUE (project_id, user_id);


--
-- TOC entry 4833 (class 2606 OID 44635)
-- Name: projects projects_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_code_key UNIQUE (code);


--
-- TOC entry 4835 (class 2606 OID 44633)
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- TOC entry 4916 (class 2606 OID 45071)
-- Name: purchase_order_items purchase_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_pkey PRIMARY KEY (id);


--
-- TOC entry 4911 (class 2606 OID 101525)
-- Name: purchase_orders purchase_orders_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_code_key UNIQUE (code);


--
-- TOC entry 4913 (class 2606 OID 45046)
-- Name: purchase_orders purchase_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_pkey PRIMARY KEY (id);


--
-- TOC entry 4907 (class 2606 OID 45025)
-- Name: purchase_requisition_items purchase_requisition_items_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_requisition_items
    ADD CONSTRAINT purchase_requisition_items_pkey PRIMARY KEY (id);


--
-- TOC entry 4902 (class 2606 OID 101599)
-- Name: purchase_requisitions purchase_requisitions_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_requisitions
    ADD CONSTRAINT purchase_requisitions_code_key UNIQUE (code);


--
-- TOC entry 4904 (class 2606 OID 45006)
-- Name: purchase_requisitions purchase_requisitions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_requisitions
    ADD CONSTRAINT purchase_requisitions_pkey PRIMARY KEY (id);


--
-- TOC entry 4654 (class 2606 OID 32338)
-- Name: push_device_tokens push_device_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.push_device_tokens
    ADD CONSTRAINT push_device_tokens_pkey PRIMARY KEY (id);


--
-- TOC entry 4656 (class 2606 OID 32340)
-- Name: push_device_tokens push_device_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.push_device_tokens
    ADD CONSTRAINT push_device_tokens_token_key UNIQUE (token);


--
-- TOC entry 4957 (class 2606 OID 45336)
-- Name: qc_records qc_records_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.qc_records
    ADD CONSTRAINT qc_records_pkey PRIMARY KEY (id);


--
-- TOC entry 4662 (class 2606 OID 32342)
-- Name: rbac_audit_logs rbac_audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rbac_audit_logs
    ADD CONSTRAINT rbac_audit_logs_pkey PRIMARY KEY (id);


--
-- TOC entry 4829 (class 2606 OID 37812)
-- Name: request_comments request_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.request_comments
    ADD CONSTRAINT request_comments_pkey PRIMARY KEY (id);


--
-- TOC entry 4666 (class 2606 OID 32344)
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_id);


--
-- TOC entry 4675 (class 2606 OID 32346)
-- Name: roles_owner_scope_rollback roles_owner_scope_rollback_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.roles_owner_scope_rollback
    ADD CONSTRAINT roles_owner_scope_rollback_pkey PRIMARY KEY (role_id);


--
-- TOC entry 4670 (class 2606 OID 32348)
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- TOC entry 4677 (class 2606 OID 32350)
-- Name: sales_round_robin_state sales_round_robin_state_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sales_round_robin_state
    ADD CONSTRAINT sales_round_robin_state_pkey PRIMARY KEY (id);


--
-- TOC entry 4680 (class 2606 OID 32352)
-- Name: sales_users sales_users_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sales_users
    ADD CONSTRAINT sales_users_code_key UNIQUE (code);


--
-- TOC entry 4682 (class 2606 OID 32354)
-- Name: sales_users sales_users_email_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sales_users
    ADD CONSTRAINT sales_users_email_key UNIQUE (email);


--
-- TOC entry 4684 (class 2606 OID 32356)
-- Name: sales_users sales_users_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sales_users
    ADD CONSTRAINT sales_users_pkey PRIMARY KEY (id);


--
-- TOC entry 4686 (class 2606 OID 32358)
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- TOC entry 4694 (class 2606 OID 32360)
-- Name: service_logs service_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.service_logs
    ADD CONSTRAINT service_logs_pkey PRIMARY KEY (id);


--
-- TOC entry 4701 (class 2606 OID 32362)
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- TOC entry 4706 (class 2606 OID 32364)
-- Name: sso_tickets sso_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sso_tickets
    ADD CONSTRAINT sso_tickets_pkey PRIMARY KEY (id);


--
-- TOC entry 4873 (class 2606 OID 44812)
-- Name: stock_movements stock_movements_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_pkey PRIMARY KEY (id);


--
-- TOC entry 4864 (class 2606 OID 44762)
-- Name: stock stock_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock
    ADD CONSTRAINT stock_pkey PRIMARY KEY (id);


--
-- TOC entry 4894 (class 2606 OID 44966)
-- Name: stocktake_lines stocktake_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stocktake_lines
    ADD CONSTRAINT stocktake_lines_pkey PRIMARY KEY (id);


--
-- TOC entry 4896 (class 2606 OID 44968)
-- Name: stocktake_lines stocktake_lines_stocktake_id_material_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stocktake_lines
    ADD CONSTRAINT stocktake_lines_stocktake_id_material_id_key UNIQUE (stocktake_id, material_id);


--
-- TOC entry 4890 (class 2606 OID 84094)
-- Name: stocktakes stocktakes_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stocktakes
    ADD CONSTRAINT stocktakes_code_key UNIQUE (code);


--
-- TOC entry 4892 (class 2606 OID 44950)
-- Name: stocktakes stocktakes_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stocktakes
    ADD CONSTRAINT stocktakes_pkey PRIMARY KEY (id);


--
-- TOC entry 4709 (class 2606 OID 32366)
-- Name: students students_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_pkey PRIMARY KEY (id);


--
-- TOC entry 4898 (class 2606 OID 44992)
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (id);


--
-- TOC entry 4715 (class 2606 OID 32368)
-- Name: support_appointments support_appointments_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_appointments
    ADD CONSTRAINT support_appointments_pkey PRIMARY KEY (id);


--
-- TOC entry 4718 (class 2606 OID 32370)
-- Name: support_assignments support_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_assignments
    ADD CONSTRAINT support_assignments_pkey PRIMARY KEY (id);


--
-- TOC entry 4722 (class 2606 OID 32372)
-- Name: support_attachments support_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_attachments
    ADD CONSTRAINT support_attachments_pkey PRIMARY KEY (id);


--
-- TOC entry 4727 (class 2606 OID 32374)
-- Name: support_cancel_requests support_cancel_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cancel_requests
    ADD CONSTRAINT support_cancel_requests_pkey PRIMARY KEY (id);


--
-- TOC entry 4730 (class 2606 OID 32376)
-- Name: support_case_events support_case_events_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_case_events
    ADD CONSTRAINT support_case_events_pkey PRIMARY KEY (id);


--
-- TOC entry 4737 (class 2606 OID 32378)
-- Name: support_cases support_cases_case_number_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cases
    ADD CONSTRAINT support_cases_case_number_key UNIQUE (case_number);


--
-- TOC entry 4739 (class 2606 OID 32380)
-- Name: support_cases support_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cases
    ADD CONSTRAINT support_cases_pkey PRIMARY KEY (id);


--
-- TOC entry 4743 (class 2606 OID 32382)
-- Name: support_entitlement_transactions support_entitlement_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_entitlement_transactions
    ADD CONSTRAINT support_entitlement_transactions_pkey PRIMARY KEY (id);


--
-- TOC entry 4745 (class 2606 OID 32384)
-- Name: support_entitlements support_entitlements_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_entitlements
    ADD CONSTRAINT support_entitlements_pkey PRIMARY KEY (id);


--
-- TOC entry 4750 (class 2606 OID 32386)
-- Name: support_messages support_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_pkey PRIMARY KEY (id);


--
-- TOC entry 4753 (class 2606 OID 32388)
-- Name: support_ratings support_ratings_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_ratings
    ADD CONSTRAINT support_ratings_pkey PRIMARY KEY (id);


--
-- TOC entry 4756 (class 2606 OID 32390)
-- Name: support_time_entries support_time_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_time_entries
    ADD CONSTRAINT support_time_entries_pkey PRIMARY KEY (id);


--
-- TOC entry 4802 (class 2606 OID 33423)
-- Name: support_waiting_message_events support_waiting_message_events_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_events
    ADD CONSTRAINT support_waiting_message_events_pkey PRIMARY KEY (id);


--
-- TOC entry 4805 (class 2606 OID 33439)
-- Name: support_waiting_message_helpers support_waiting_message_helpers_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_helpers
    ADD CONSTRAINT support_waiting_message_helpers_pkey PRIMARY KEY (message_id, user_id);


--
-- TOC entry 4760 (class 2606 OID 32392)
-- Name: support_waiting_message_replies support_waiting_message_replies_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_replies
    ADD CONSTRAINT support_waiting_message_replies_pkey PRIMARY KEY (id);


--
-- TOC entry 4762 (class 2606 OID 32394)
-- Name: support_waiting_message_views support_waiting_message_views_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_views
    ADD CONSTRAINT support_waiting_message_views_pkey PRIMARY KEY (message_id, user_id);


--
-- TOC entry 4767 (class 2606 OID 32396)
-- Name: support_waiting_messages support_waiting_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_messages
    ADD CONSTRAINT support_waiting_messages_pkey PRIMARY KEY (id);


--
-- TOC entry 4851 (class 2606 OID 44701)
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- TOC entry 4771 (class 2606 OID 32398)
-- Name: user_organizations user_organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_organizations
    ADD CONSTRAINT user_organizations_pkey PRIMARY KEY (user_id, organization_id);


--
-- TOC entry 4968 (class 2606 OID 87118)
-- Name: user_permissions user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_pkey PRIMARY KEY (user_id, permission_id);


--
-- TOC entry 4774 (class 2606 OID 32400)
-- Name: user_profiles user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (id);


--
-- TOC entry 4776 (class 2606 OID 32402)
-- Name: user_profiles user_profiles_user_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_user_id_key UNIQUE (user_id);


--
-- TOC entry 4780 (class 2606 OID 32404)
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);


--
-- TOC entry 4782 (class 2606 OID 32406)
-- Name: user_types user_types_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_types
    ADD CONSTRAINT user_types_pkey PRIMARY KEY (code);


--
-- TOC entry 4787 (class 2606 OID 32408)
-- Name: verification_codes verification_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.verification_codes
    ADD CONSTRAINT verification_codes_pkey PRIMARY KEY (id);


--
-- TOC entry 4858 (class 2606 OID 84086)
-- Name: warehouses warehouses_code_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.warehouses
    ADD CONSTRAINT warehouses_code_key UNIQUE (code);


--
-- TOC entry 4860 (class 2606 OID 44750)
-- Name: warehouses warehouses_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.warehouses
    ADD CONSTRAINT warehouses_pkey PRIMARY KEY (id);


--
-- TOC entry 4942 (class 2606 OID 45248)
-- Name: wo_operations wo_operations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.wo_operations
    ADD CONSTRAINT wo_operations_pkey PRIMARY KEY (id);


--
-- TOC entry 4791 (class 2606 OID 32410)
-- Name: work_order_comments work_order_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.work_order_comments
    ADD CONSTRAINT work_order_comments_pkey PRIMARY KEY (id);


--
-- TOC entry 4797 (class 2606 OID 32412)
-- Name: work_orders work_orders_order_number_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_order_number_key UNIQUE (order_number);


--
-- TOC entry 4799 (class 2606 OID 32414)
-- Name: work_orders work_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_pkey PRIMARY KEY (id);


--
-- TOC entry 4819 (class 1259 OID 37619)
-- Name: chat_messages_conversation_created; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX chat_messages_conversation_created ON public.chat_messages USING btree (conversation_id, created_at);


--
-- TOC entry 4818 (class 1259 OID 37588)
-- Name: chat_participants_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX chat_participants_user ON public.chat_participants USING btree (user_id);


--
-- TOC entry 4406 (class 1259 OID 32415)
-- Name: idx_activities_activityable; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_activities_activityable ON public.activities USING btree (activityable_type, activityable_id);


--
-- TOC entry 4407 (class 1259 OID 32416)
-- Name: idx_activities_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_activities_created_at ON public.activities USING btree (created_at DESC);


--
-- TOC entry 4408 (class 1259 OID 32417)
-- Name: idx_activities_sales_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_activities_sales_id ON public.activities USING btree (sales_id);


--
-- TOC entry 4419 (class 1259 OID 32418)
-- Name: idx_auth_users_email; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_auth_users_email ON public.auth_users USING btree (email) WHERE (email IS NOT NULL);


--
-- TOC entry 4420 (class 1259 OID 32419)
-- Name: idx_auth_users_email_verified; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_auth_users_email_verified ON public.auth_users USING btree (email_verified_at) WHERE (email IS NOT NULL);


--
-- TOC entry 4421 (class 1259 OID 32420)
-- Name: idx_auth_users_phone; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_auth_users_phone ON public.auth_users USING btree (phone) WHERE (phone IS NOT NULL);


--
-- TOC entry 4422 (class 1259 OID 32421)
-- Name: idx_auth_users_phone_verified; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_auth_users_phone_verified ON public.auth_users USING btree (phone_verified_at) WHERE (phone IS NOT NULL);


--
-- TOC entry 4934 (class 1259 OID 45196)
-- Name: idx_bom_components_bom; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_bom_components_bom ON public.bom_components USING btree (bom_id);


--
-- TOC entry 4931 (class 1259 OID 45182)
-- Name: idx_boms_product; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_boms_product ON public.boms USING btree (product_id);


--
-- TOC entry 4425 (class 1259 OID 32422)
-- Name: idx_business_fields_name; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_business_fields_name ON public.business_fields USING btree (name);


--
-- TOC entry 4428 (class 1259 OID 32423)
-- Name: idx_campaign_registrations_campaign; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_campaign_registrations_campaign ON public.campaign_registrations USING btree (campaign_id, created_at);


--
-- TOC entry 4429 (class 1259 OID 32424)
-- Name: idx_campaign_registrations_customer; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_campaign_registrations_customer ON public.campaign_registrations USING btree (customer_id);


--
-- TOC entry 4432 (class 1259 OID 32425)
-- Name: idx_campaign_visits_campaign_id_visited_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_campaign_visits_campaign_id_visited_at ON public.campaign_visits USING btree (campaign_id, visited_at);


--
-- TOC entry 4437 (class 1259 OID 32426)
-- Name: idx_campaigns_assigned_person_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_campaigns_assigned_person_id ON public.campaigns USING btree (assigned_person_id);


--
-- TOC entry 4438 (class 1259 OID 32427)
-- Name: idx_campaigns_org; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_campaigns_org ON public.campaigns USING btree (organization_id) WHERE (deleted_at IS NULL);


--
-- TOC entry 4808 (class 1259 OID 33557)
-- Name: idx_company_doc_node_products_product; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_company_doc_node_products_product ON public.company_doc_node_products USING btree (product_id);


--
-- TOC entry 4443 (class 1259 OID 32428)
-- Name: idx_company_doc_node_versions_node_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_company_doc_node_versions_node_id ON public.company_doc_node_versions USING btree (node_id);


--
-- TOC entry 4446 (class 1259 OID 32429)
-- Name: idx_company_doc_nodes_lineage_current; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_company_doc_nodes_lineage_current ON public.company_doc_nodes USING btree (root_id) WHERE (is_current AND (status = 'released'::text));


--
-- TOC entry 4447 (class 1259 OID 32430)
-- Name: idx_company_doc_nodes_lineage_version; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_company_doc_nodes_lineage_version ON public.company_doc_nodes USING btree (root_id, lineage_version) WHERE (status = 'released'::text);


--
-- TOC entry 4448 (class 1259 OID 32431)
-- Name: idx_company_doc_nodes_manualhub_doc_slot; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_company_doc_nodes_manualhub_doc_slot ON public.company_doc_nodes USING btree (manualhub_product_id, manualhub_document_type, manualhub_language) WHERE ((manualhub_product_id IS NOT NULL) AND (manualhub_document_type IS NOT NULL) AND (manualhub_language IS NOT NULL) AND (node_type = 'document'::text));


--
-- TOC entry 4449 (class 1259 OID 32432)
-- Name: idx_company_doc_nodes_manualhub_product_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_company_doc_nodes_manualhub_product_id ON public.company_doc_nodes USING btree (manualhub_product_id) WHERE ((manualhub_product_id IS NOT NULL) AND (node_type = 'folder'::text));


--
-- TOC entry 4450 (class 1259 OID 32433)
-- Name: idx_company_doc_nodes_parent_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_company_doc_nodes_parent_id ON public.company_doc_nodes USING btree (parent_id);


--
-- TOC entry 4451 (class 1259 OID 32434)
-- Name: idx_company_doc_nodes_root_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_company_doc_nodes_root_id ON public.company_doc_nodes USING btree (root_id);


--
-- TOC entry 4454 (class 1259 OID 32435)
-- Name: idx_contact_messages_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_contact_messages_created_at ON public.contact_messages USING btree (created_at DESC);


--
-- TOC entry 4455 (class 1259 OID 32436)
-- Name: idx_contact_messages_customer; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_contact_messages_customer ON public.contact_messages USING btree (customer_id);


--
-- TOC entry 4458 (class 1259 OID 32437)
-- Name: idx_customer_business_fields_customer_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_business_fields_customer_id ON public.customer_business_fields USING btree (customer_id);


--
-- TOC entry 4459 (class 1259 OID 32438)
-- Name: idx_customer_business_fields_field_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_business_fields_field_id ON public.customer_business_fields USING btree (business_field_id);


--
-- TOC entry 4462 (class 1259 OID 32439)
-- Name: idx_customer_customer_groups_customer_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_customer_groups_customer_id ON public.customer_customer_groups USING btree (customer_id);


--
-- TOC entry 4463 (class 1259 OID 32440)
-- Name: idx_customer_customer_groups_group_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_customer_groups_group_id ON public.customer_customer_groups USING btree (customer_group_id);


--
-- TOC entry 4466 (class 1259 OID 32441)
-- Name: idx_customer_groups_name; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_groups_name ON public.customer_groups USING btree (name);


--
-- TOC entry 4469 (class 1259 OID 32442)
-- Name: idx_customer_logs_actor_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_logs_actor_id ON public.customer_logs USING btree (actor_id);


--
-- TOC entry 4470 (class 1259 OID 32443)
-- Name: idx_customer_logs_customer_id_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_logs_customer_id_created_at ON public.customer_logs USING btree (customer_id, created_at DESC);


--
-- TOC entry 4479 (class 1259 OID 32444)
-- Name: idx_customer_statuses_name; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_statuses_name ON public.customer_statuses USING btree (name);


--
-- TOC entry 4484 (class 1259 OID 32445)
-- Name: idx_customer_team_members_customer; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_team_members_customer ON public.customer_team_members USING btree (customer_id);


--
-- TOC entry 4489 (class 1259 OID 32446)
-- Name: idx_customer_views_customer_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_views_customer_id ON public.customer_views USING btree (customer_id);


--
-- TOC entry 4490 (class 1259 OID 32447)
-- Name: idx_customer_views_sales_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_views_sales_id ON public.customer_views USING btree (sales_id);


--
-- TOC entry 4491 (class 1259 OID 32448)
-- Name: idx_customer_views_viewed_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customer_views_viewed_at ON public.customer_views USING btree (viewed_at DESC);


--
-- TOC entry 4498 (class 1259 OID 32449)
-- Name: idx_customers_assigned_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_assigned_at ON public.customers USING btree (assigned_at DESC);


--
-- TOC entry 4499 (class 1259 OID 32450)
-- Name: idx_customers_assigned_sales_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_assigned_sales_id ON public.customers USING btree (assigned_sales_id);


--
-- TOC entry 4500 (class 1259 OID 32451)
-- Name: idx_customers_code_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_code_trgm ON public.customers USING gin (code public.gin_trgm_ops);


--
-- TOC entry 4501 (class 1259 OID 32452)
-- Name: idx_customers_company_coalesce_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_company_coalesce_trgm ON public.customers USING gin (COALESCE(company_name, ''::character varying) public.gin_trgm_ops);


--
-- TOC entry 4502 (class 1259 OID 32453)
-- Name: idx_customers_customer_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_customer_type ON public.customers USING btree (customer_type) WHERE (deleted_at IS NULL);


--
-- TOC entry 4503 (class 1259 OID 32454)
-- Name: idx_customers_full_name_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_full_name_trgm ON public.customers USING gin (full_name public.gin_trgm_ops);


--
-- TOC entry 4504 (class 1259 OID 32455)
-- Name: idx_customers_last_contact_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_last_contact_at ON public.customers USING btree (last_contact_at DESC);


--
-- TOC entry 4505 (class 1259 OID 33460)
-- Name: idx_customers_last_inbound_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_last_inbound_at ON public.customers USING btree (last_inbound_at DESC);


--
-- TOC entry 4506 (class 1259 OID 32456)
-- Name: idx_customers_merged_into_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_merged_into_id ON public.customers USING btree (merged_into_id);


--
-- TOC entry 4507 (class 1259 OID 32457)
-- Name: idx_customers_organization_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_organization_id ON public.customers USING btree (organization_id);


--
-- TOC entry 4508 (class 1259 OID 32458)
-- Name: idx_customers_phone_coalesce_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_phone_coalesce_trgm ON public.customers USING gin (COALESCE(phone, ''::character varying) public.gin_trgm_ops);


--
-- TOC entry 4509 (class 1259 OID 32459)
-- Name: idx_customers_phone_last9; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_phone_last9 ON public.customers USING btree ("right"(regexp_replace((COALESCE(phone, ''::character varying))::text, '[^0-9]'::text, ''::text, 'g'::text), 9)) WHERE (deleted_at IS NULL);


--
-- TOC entry 4510 (class 1259 OID 32460)
-- Name: idx_customers_phone_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_phone_trgm ON public.customers USING gin (phone public.gin_trgm_ops);


--
-- TOC entry 4511 (class 1259 OID 32461)
-- Name: idx_customers_status_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_customers_status_id ON public.customers USING btree (status_id);


--
-- TOC entry 4567 (class 1259 OID 32462)
-- Name: idx_delivery_log_status_created; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_delivery_log_status_created ON public.notification_delivery_log USING btree (status, created_at DESC);


--
-- TOC entry 4568 (class 1259 OID 32463)
-- Name: idx_delivery_log_user_created; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_delivery_log_user_created ON public.notification_delivery_log USING btree (user_id, created_at DESC);


--
-- TOC entry 4740 (class 1259 OID 32464)
-- Name: idx_entitlement_tx_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_entitlement_tx_case ON public.support_entitlement_transactions USING btree (case_id);


--
-- TOC entry 4741 (class 1259 OID 32465)
-- Name: idx_entitlement_tx_entitlement; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_entitlement_tx_entitlement ON public.support_entitlement_transactions USING btree (entitlement_id);


--
-- TOC entry 4962 (class 1259 OID 45372)
-- Name: idx_fgr_items_fgr; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_fgr_items_fgr ON public.finished_goods_receipt_items USING btree (finished_goods_receipt_id);


--
-- TOC entry 4516 (class 1259 OID 32466)
-- Name: idx_file_links_entity; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_file_links_entity ON public.file_links USING btree (entity_type, entity_id, purpose);


--
-- TOC entry 4517 (class 1259 OID 32467)
-- Name: idx_file_links_file_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_file_links_file_id ON public.file_links USING btree (file_id);


--
-- TOC entry 4522 (class 1259 OID 32468)
-- Name: idx_files_uploaded_by; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_files_uploaded_by ON public.files USING btree (uploaded_by) WHERE (deleted_at IS NULL);


--
-- TOC entry 4523 (class 1259 OID 32469)
-- Name: idx_files_visibility; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_files_visibility ON public.files USING btree (visibility) WHERE (deleted_at IS NULL);


--
-- TOC entry 4888 (class 1259 OID 44927)
-- Name: idx_goods_issue_items_issue; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_goods_issue_items_issue ON public.goods_issue_items USING btree (goods_issue_id);


--
-- TOC entry 4885 (class 1259 OID 44902)
-- Name: idx_goods_issues_source; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_goods_issues_source ON public.goods_issues USING btree (source_type, source_id);


--
-- TOC entry 4880 (class 1259 OID 44875)
-- Name: idx_goods_receipt_items_receipt; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_goods_receipt_items_receipt ON public.goods_receipt_items USING btree (goods_receipt_id);


--
-- TOC entry 4928 (class 1259 OID 45163)
-- Name: idx_goods_return_items_return; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_goods_return_items_return ON public.goods_return_items USING btree (return_id);


--
-- TOC entry 4536 (class 1259 OID 32470)
-- Name: idx_issue_reports_product_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_issue_reports_product_item ON public.issue_reports USING btree (product_item_id);


--
-- TOC entry 4539 (class 1259 OID 32471)
-- Name: idx_keygen_history_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_keygen_history_created_at ON public.keygen_history USING btree (created_at DESC);


--
-- TOC entry 4540 (class 1259 OID 32472)
-- Name: idx_keygen_history_generated_by; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_keygen_history_generated_by ON public.keygen_history USING btree (generated_by);


--
-- TOC entry 4541 (class 1259 OID 32473)
-- Name: idx_keygen_history_org; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_keygen_history_org ON public.keygen_history USING btree (organization_id);


--
-- TOC entry 4542 (class 1259 OID 32474)
-- Name: idx_keygen_history_product_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_keygen_history_product_item ON public.keygen_history USING btree (product_item_id) WHERE (product_item_id IS NOT NULL);


--
-- TOC entry 4543 (class 1259 OID 32475)
-- Name: idx_keygen_history_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_keygen_history_type ON public.keygen_history USING btree (key_type);


--
-- TOC entry 4546 (class 1259 OID 32476)
-- Name: idx_leads_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_leads_created_at ON public.leads USING btree (created_at DESC) WHERE (deleted_at IS NULL);


--
-- TOC entry 4549 (class 1259 OID 32477)
-- Name: idx_lock_requests_one_pending; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_lock_requests_one_pending ON public.lock_requests USING btree (product_item_id) WHERE ((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('pending_admin'::character varying)::text]));


--
-- TOC entry 4550 (class 1259 OID 32478)
-- Name: idx_lock_requests_product_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_lock_requests_product_item ON public.lock_requests USING btree (product_item_id);


--
-- TOC entry 4553 (class 1259 OID 32479)
-- Name: idx_manualhub_activities_document_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manualhub_activities_document_id ON public.manualhub_activities USING btree (document_id);


--
-- TOC entry 4556 (class 1259 OID 32480)
-- Name: idx_manualhub_document_versions_document_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manualhub_document_versions_document_id ON public.manualhub_document_versions USING btree (document_id);


--
-- TOC entry 4559 (class 1259 OID 32481)
-- Name: idx_manualhub_documents_group_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manualhub_documents_group_id ON public.manualhub_documents USING btree (document_group_id);


--
-- TOC entry 4560 (class 1259 OID 32482)
-- Name: idx_manualhub_documents_lineage_version; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_manualhub_documents_lineage_version ON public.manualhub_documents USING btree (root_id, version) WHERE (released_at IS NOT NULL);


--
-- TOC entry 4561 (class 1259 OID 32483)
-- Name: idx_manualhub_documents_parent_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manualhub_documents_parent_id ON public.manualhub_documents USING btree (parent_id);


--
-- TOC entry 4562 (class 1259 OID 32484)
-- Name: idx_manualhub_documents_product_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manualhub_documents_product_id ON public.manualhub_documents USING btree (product_id);


--
-- TOC entry 4563 (class 1259 OID 32485)
-- Name: idx_manualhub_documents_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manualhub_documents_status ON public.manualhub_documents USING btree (status);


--
-- TOC entry 4564 (class 1259 OID 32486)
-- Name: idx_manualhub_documents_title_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manualhub_documents_title_trgm ON public.manualhub_documents USING gin (title public.gin_trgm_ops);


--
-- TOC entry 4935 (class 1259 OID 45237)
-- Name: idx_manufacturing_work_orders_product_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manufacturing_work_orders_product_item ON public.manufacturing_work_orders USING btree (product_item_id);


--
-- TOC entry 4936 (class 1259 OID 45235)
-- Name: idx_manufacturing_work_orders_project; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manufacturing_work_orders_project ON public.manufacturing_work_orders USING btree (project_id);


--
-- TOC entry 4937 (class 1259 OID 45236)
-- Name: idx_manufacturing_work_orders_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_manufacturing_work_orders_task ON public.manufacturing_work_orders USING btree (task_id);


--
-- TOC entry 4943 (class 1259 OID 45278)
-- Name: idx_material_consumptions_wo; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_material_consumptions_wo ON public.material_consumptions USING btree (work_order_id);


--
-- TOC entry 4969 (class 1259 OID 101572)
-- Name: idx_material_suppliers_supplier; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_material_suppliers_supplier ON public.material_suppliers USING btree (supplier_id);


--
-- TOC entry 4963 (class 1259 OID 45386)
-- Name: idx_mslc_output; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_mslc_output ON public.material_serial_lot_consumptions USING btree (output_type, output_id);


--
-- TOC entry 4571 (class 1259 OID 32487)
-- Name: idx_notifications_device_open; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_notifications_device_open ON public.notifications USING btree (created_at) WHERE ((device_pushed_at IS NOT NULL) AND (device_acked_at IS NULL) AND (device_dismissed_at IS NULL));


--
-- TOC entry 4572 (class 1259 OID 32488)
-- Name: idx_notifications_user_created; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_notifications_user_created ON public.notifications USING btree (user_id, created_at DESC);


--
-- TOC entry 4573 (class 1259 OID 32489)
-- Name: idx_notifications_user_unread; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_notifications_user_unread ON public.notifications USING btree (user_id) WHERE (read_at IS NULL);


--
-- TOC entry 4576 (class 1259 OID 32490)
-- Name: idx_organizations_name_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_organizations_name_trgm ON public.organizations USING gin (name public.gin_trgm_ops);


--
-- TOC entry 4577 (class 1259 OID 32491)
-- Name: idx_organizations_parent_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_organizations_parent_id ON public.organizations USING btree (parent_id);


--
-- TOC entry 4578 (class 1259 OID 32492)
-- Name: idx_organizations_path; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_organizations_path ON public.organizations USING btree (path);


--
-- TOC entry 4596 (class 1259 OID 32493)
-- Name: idx_par_request_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_par_request_type ON public.product_item_activation_requests USING btree (request_type);


--
-- TOC entry 4597 (class 1259 OID 32494)
-- Name: idx_par_sales; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_par_sales ON public.product_item_activation_requests USING btree (sales_user_id);


--
-- TOC entry 4598 (class 1259 OID 32495)
-- Name: idx_par_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_par_status ON public.product_item_activation_requests USING btree (status);


--
-- TOC entry 4599 (class 1259 OID 32496)
-- Name: idx_par_submitted_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_par_submitted_at ON public.product_item_activation_requests USING btree (submitted_at DESC);


--
-- TOC entry 4583 (class 1259 OID 32497)
-- Name: idx_password_reset_tokens_expires_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_password_reset_tokens_expires_at ON public.password_reset_tokens USING btree (expires_at);


--
-- TOC entry 4584 (class 1259 OID 32498)
-- Name: idx_password_reset_tokens_token_hash; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_password_reset_tokens_token_hash ON public.password_reset_tokens USING btree (token_hash);


--
-- TOC entry 4585 (class 1259 OID 32499)
-- Name: idx_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- TOC entry 4836 (class 1259 OID 44664)
-- Name: idx_phases_project; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_phases_project ON public.phases USING btree (project_id, phase_order);


--
-- TOC entry 4612 (class 1259 OID 32500)
-- Name: idx_pirecall_customer; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pirecall_customer ON public.product_item_recall_requests USING btree (customer_id, status);


--
-- TOC entry 4613 (class 1259 OID 32501)
-- Name: idx_pirecall_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pirecall_status ON public.product_item_recall_requests USING btree (status);


--
-- TOC entry 4617 (class 1259 OID 32502)
-- Name: idx_pirr_org; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pirr_org ON public.product_item_return_requests USING btree (organization_id);


--
-- TOC entry 4618 (class 1259 OID 32503)
-- Name: idx_pirr_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pirr_status ON public.product_item_return_requests USING btree (status);


--
-- TOC entry 4920 (class 1259 OID 45118)
-- Name: idx_po_backorders_material_open; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_po_backorders_material_open ON public.po_backorders USING btree (material_id) WHERE ((status)::text = 'open'::text);


--
-- TOC entry 4921 (class 1259 OID 45117)
-- Name: idx_po_backorders_po; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_po_backorders_po ON public.po_backorders USING btree (po_id);


--
-- TOC entry 4917 (class 1259 OID 45095)
-- Name: idx_po_goods_receipts_po; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_po_goods_receipts_po ON public.po_goods_receipts USING btree (po_id);


--
-- TOC entry 4914 (class 1259 OID 45082)
-- Name: idx_po_items_po; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_po_items_po ON public.purchase_order_items USING btree (po_id);


--
-- TOC entry 4908 (class 1259 OID 45063)
-- Name: idx_po_pr; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_po_pr ON public.purchase_orders USING btree (pr_id);


--
-- TOC entry 4909 (class 1259 OID 45062)
-- Name: idx_po_supplier; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_po_supplier ON public.purchase_orders USING btree (supplier_id);


--
-- TOC entry 4822 (class 1259 OID 37730)
-- Name: idx_potr_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_potr_item ON public.product_ownership_transfer_requests USING btree (product_item_id);


--
-- TOC entry 4823 (class 1259 OID 37729)
-- Name: idx_potr_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_potr_status ON public.product_ownership_transfer_requests USING btree (status, created_at DESC);


--
-- TOC entry 4905 (class 1259 OID 45036)
-- Name: idx_pr_items_pr; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pr_items_pr ON public.purchase_requisition_items USING btree (pr_id);


--
-- TOC entry 4899 (class 1259 OID 45017)
-- Name: idx_pr_source; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pr_source ON public.purchase_requisitions USING btree (source_type, source_id);


--
-- TOC entry 4900 (class 1259 OID 45018)
-- Name: idx_pr_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pr_status ON public.purchase_requisitions USING btree (status);


--
-- TOC entry 4592 (class 1259 OID 32504)
-- Name: idx_product_agents_product; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_agents_product ON public.product_agents USING btree (product_item_id);


--
-- TOC entry 4602 (class 1259 OID 32505)
-- Name: idx_product_item_aliases_owner; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_item_aliases_owner ON public.product_item_aliases USING btree (owner_customer_id);


--
-- TOC entry 4607 (class 1259 OID 32506)
-- Name: idx_product_item_logs_actor; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_item_logs_actor ON public.product_item_logs USING btree (actor_id) WHERE (actor_id IS NOT NULL);


--
-- TOC entry 4608 (class 1259 OID 32507)
-- Name: idx_product_item_logs_event_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_item_logs_event_type ON public.product_item_logs USING btree (event_type);


--
-- TOC entry 4609 (class 1259 OID 32508)
-- Name: idx_product_item_logs_item_occurred; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_item_logs_item_occurred ON public.product_item_logs USING btree (product_item_id, occurred_at DESC);


--
-- TOC entry 4621 (class 1259 OID 32509)
-- Name: idx_product_items_code; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_product_items_code ON public.product_items USING btree (code) WHERE (deleted_at IS NULL);


--
-- TOC entry 4622 (class 1259 OID 32510)
-- Name: idx_product_items_code_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_items_code_trgm ON public.product_items USING gin (code public.gin_trgm_ops);


--
-- TOC entry 4623 (class 1259 OID 32511)
-- Name: idx_product_items_customer; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_items_customer ON public.product_items USING btree (customer_id) WHERE (deleted_at IS NULL);


--
-- TOC entry 4624 (class 1259 OID 32512)
-- Name: idx_product_items_product; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_items_product ON public.product_items USING btree (product_id) WHERE (deleted_at IS NULL);


--
-- TOC entry 4625 (class 1259 OID 32513)
-- Name: idx_product_items_refurbished_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_items_refurbished_at ON public.product_items USING btree (refurbished_at) WHERE (refurbished_at IS NOT NULL);


--
-- TOC entry 4626 (class 1259 OID 32514)
-- Name: idx_product_items_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_items_status ON public.product_items USING btree (status) WHERE (deleted_at IS NULL);


--
-- TOC entry 4629 (class 1259 OID 32515)
-- Name: idx_product_ownerships_owner; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_ownerships_owner ON public.product_ownerships USING btree (owner_customer_id);


--
-- TOC entry 4630 (class 1259 OID 32516)
-- Name: idx_product_ownerships_product; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_ownerships_product ON public.product_ownerships USING btree (product_item_id);


--
-- TOC entry 4636 (class 1259 OID 32517)
-- Name: idx_product_user_access_product; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_user_access_product ON public.product_user_access USING btree (product_item_id);


--
-- TOC entry 4637 (class 1259 OID 32518)
-- Name: idx_product_user_access_product_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_user_access_product_user ON public.product_user_access USING btree (product_item_id, auth_user_id) WHERE (deleted_at IS NULL);


--
-- TOC entry 4638 (class 1259 OID 32519)
-- Name: idx_product_user_access_role; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_user_access_role ON public.product_user_access USING btree (role_id) WHERE ((role_id IS NOT NULL) AND (deleted_at IS NULL));


--
-- TOC entry 4639 (class 1259 OID 32520)
-- Name: idx_product_user_access_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_product_user_access_user ON public.product_user_access USING btree (auth_user_id);


--
-- TOC entry 4644 (class 1259 OID 32521)
-- Name: idx_products_code; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_products_code ON public.products USING btree (code) WHERE (deleted_at IS NULL);


--
-- TOC entry 4645 (class 1259 OID 32522)
-- Name: idx_products_code_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_products_code_trgm ON public.products USING gin (code public.gin_trgm_ops);


--
-- TOC entry 4646 (class 1259 OID 32523)
-- Name: idx_products_deleted_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_products_deleted_at ON public.products USING btree (deleted_at);


--
-- TOC entry 4647 (class 1259 OID 32524)
-- Name: idx_products_name_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_products_name_trgm ON public.products USING gin (name public.gin_trgm_ops);


--
-- TOC entry 4951 (class 1259 OID 45324)
-- Name: idx_project_asset_components_asset; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_project_asset_components_asset ON public.project_asset_components USING btree (project_asset_id);


--
-- TOC entry 4952 (class 1259 OID 45325)
-- Name: idx_project_asset_components_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_project_asset_components_item ON public.project_asset_components USING btree (product_item_id);


--
-- TOC entry 4946 (class 1259 OID 45306)
-- Name: idx_project_assets_project; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_project_assets_project ON public.project_assets USING btree (project_id);


--
-- TOC entry 4839 (class 1259 OID 44684)
-- Name: idx_project_members_project; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_project_members_project ON public.project_members USING btree (project_id);


--
-- TOC entry 4840 (class 1259 OID 44685)
-- Name: idx_project_members_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_project_members_user ON public.project_members USING btree (user_id);


--
-- TOC entry 4830 (class 1259 OID 44647)
-- Name: idx_projects_customer; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_projects_customer ON public.projects USING btree (customer_id);


--
-- TOC entry 4831 (class 1259 OID 44646)
-- Name: idx_projects_owner; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_projects_owner ON public.projects USING btree (owner_id);


--
-- TOC entry 4652 (class 1259 OID 32525)
-- Name: idx_push_device_tokens_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_push_device_tokens_user ON public.push_device_tokens USING btree (user_id);


--
-- TOC entry 4955 (class 1259 OID 45342)
-- Name: idx_qc_records_ref; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_qc_records_ref ON public.qc_records USING btree (ref_type, ref_id);


--
-- TOC entry 4657 (class 1259 OID 32526)
-- Name: idx_rbac_audit_action_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_rbac_audit_action_type ON public.rbac_audit_logs USING btree (action_type);


--
-- TOC entry 4658 (class 1259 OID 32527)
-- Name: idx_rbac_audit_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_rbac_audit_created_at ON public.rbac_audit_logs USING btree (created_at DESC);


--
-- TOC entry 4659 (class 1259 OID 32528)
-- Name: idx_rbac_audit_performed_by; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_rbac_audit_performed_by ON public.rbac_audit_logs USING btree (performed_by);


--
-- TOC entry 4660 (class 1259 OID 32529)
-- Name: idx_rbac_audit_target_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_rbac_audit_target_user ON public.rbac_audit_logs USING btree (target_user_id);


--
-- TOC entry 4827 (class 1259 OID 37818)
-- Name: idx_request_comments_request; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_request_comments_request ON public.request_comments USING btree (request_kind, request_id, created_at);


--
-- TOC entry 4663 (class 1259 OID 32530)
-- Name: idx_role_permissions_permission_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_role_permissions_permission_id ON public.role_permissions USING btree (permission_id);


--
-- TOC entry 4664 (class 1259 OID 32531)
-- Name: idx_role_permissions_role_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_role_permissions_role_id ON public.role_permissions USING btree (role_id);


--
-- TOC entry 4667 (class 1259 OID 32532)
-- Name: idx_roles_kind_owner; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_roles_kind_owner ON public.roles USING btree (owner_customer_id) WHERE ((kind)::text = 'product'::text);


--
-- TOC entry 4678 (class 1259 OID 32533)
-- Name: idx_sales_users_organization_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_sales_users_organization_id ON public.sales_users USING btree (organization_id);


--
-- TOC entry 4865 (class 1259 OID 44801)
-- Name: idx_serial_lots_material; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_serial_lots_material ON public.material_serial_lots USING btree (material_id, status);


--
-- TOC entry 4687 (class 1259 OID 32534)
-- Name: idx_service_logs_date; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_service_logs_date ON public.service_logs USING btree (service_date);


--
-- TOC entry 4688 (class 1259 OID 32535)
-- Name: idx_service_logs_event_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_service_logs_event_type ON public.service_logs USING btree (event_type) WHERE (event_type IS NOT NULL);


--
-- TOC entry 4689 (class 1259 OID 32536)
-- Name: idx_service_logs_product_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_service_logs_product_item ON public.service_logs USING btree (product_item_id);


--
-- TOC entry 4690 (class 1259 OID 32537)
-- Name: idx_service_logs_source_comment; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_service_logs_source_comment ON public.service_logs USING btree (source_comment_id) WHERE (source_comment_id IS NOT NULL);


--
-- TOC entry 4691 (class 1259 OID 32538)
-- Name: idx_service_logs_technician; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_service_logs_technician ON public.service_logs USING btree (technician_id);


--
-- TOC entry 4692 (class 1259 OID 32539)
-- Name: idx_service_logs_work_order; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_service_logs_work_order ON public.service_logs USING btree (work_order_id);


--
-- TOC entry 4695 (class 1259 OID 32540)
-- Name: idx_sessions_access_token_jti; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_sessions_access_token_jti ON public.sessions USING btree (access_token_jti);


--
-- TOC entry 4696 (class 1259 OID 32541)
-- Name: idx_sessions_expires_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_sessions_expires_at ON public.sessions USING btree (expires_at);


--
-- TOC entry 4697 (class 1259 OID 32542)
-- Name: idx_sessions_refresh_token_hash; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_sessions_refresh_token_hash ON public.sessions USING btree (refresh_token_hash);


--
-- TOC entry 4698 (class 1259 OID 32543)
-- Name: idx_sessions_revoked_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_sessions_revoked_at ON public.sessions USING btree (revoked_at) WHERE (revoked_at IS NULL);


--
-- TOC entry 4699 (class 1259 OID 32544)
-- Name: idx_sessions_user_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_sessions_user_id ON public.sessions USING btree (user_id);


--
-- TOC entry 4702 (class 1259 OID 32545)
-- Name: idx_sso_tickets_expires_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_sso_tickets_expires_at ON public.sso_tickets USING btree (expires_at);


--
-- TOC entry 4703 (class 1259 OID 32546)
-- Name: idx_sso_tickets_token_hash; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_sso_tickets_token_hash ON public.sso_tickets USING btree (token_hash);


--
-- TOC entry 4704 (class 1259 OID 32547)
-- Name: idx_sso_tickets_user_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_sso_tickets_user_id ON public.sso_tickets USING btree (user_id);


--
-- TOC entry 4861 (class 1259 OID 44775)
-- Name: idx_stock_material; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_stock_material ON public.stock USING btree (material_id);


--
-- TOC entry 4862 (class 1259 OID 101439)
-- Name: idx_stock_material_warehouse; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_stock_material_warehouse ON public.stock USING btree (material_id, warehouse_id);


--
-- TOC entry 4870 (class 1259 OID 44834)
-- Name: idx_stock_movements_material; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_stock_movements_material ON public.stock_movements USING btree (material_id, warehouse_id);


--
-- TOC entry 4871 (class 1259 OID 44937)
-- Name: idx_stock_movements_source; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_stock_movements_source ON public.stock_movements USING btree (source_type, source_id);


--
-- TOC entry 4707 (class 1259 OID 32548)
-- Name: idx_students_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_students_created_at ON public.students USING btree (created_at DESC) WHERE (deleted_at IS NULL);


--
-- TOC entry 4710 (class 1259 OID 32549)
-- Name: idx_support_appointments_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_appointments_case ON public.support_appointments USING btree (case_id);


--
-- TOC entry 4711 (class 1259 OID 32550)
-- Name: idx_support_appointments_reminder_scan; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_appointments_reminder_scan ON public.support_appointments USING btree (start_at_utc) WHERE (((status)::text = 'confirmed'::text) AND (reminder_sent_at IS NULL));


--
-- TOC entry 4712 (class 1259 OID 32551)
-- Name: idx_support_appointments_start_scan; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_appointments_start_scan ON public.support_appointments USING btree (start_at_utc) WHERE (((status)::text = 'confirmed'::text) AND (start_notified_at IS NULL));


--
-- TOC entry 4713 (class 1259 OID 32552)
-- Name: idx_support_appointments_support_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_appointments_support_user ON public.support_appointments USING btree (support_user_id, start_at_utc);


--
-- TOC entry 4716 (class 1259 OID 32553)
-- Name: idx_support_assignments_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_assignments_case ON public.support_assignments USING btree (case_id);


--
-- TOC entry 4720 (class 1259 OID 32554)
-- Name: idx_support_attachments_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_attachments_case ON public.support_attachments USING btree (case_id);


--
-- TOC entry 4723 (class 1259 OID 32555)
-- Name: idx_support_cancel_requests_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_cancel_requests_case ON public.support_cancel_requests USING btree (case_id);


--
-- TOC entry 4724 (class 1259 OID 32556)
-- Name: idx_support_cancel_requests_one_pending_per_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX idx_support_cancel_requests_one_pending_per_case ON public.support_cancel_requests USING btree (case_id) WHERE ((status)::text = 'pending'::text);


--
-- TOC entry 4725 (class 1259 OID 32557)
-- Name: idx_support_cancel_requests_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_cancel_requests_status ON public.support_cancel_requests USING btree (status);


--
-- TOC entry 4728 (class 1259 OID 32558)
-- Name: idx_support_case_events_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_case_events_case ON public.support_case_events USING btree (case_id);


--
-- TOC entry 4731 (class 1259 OID 32559)
-- Name: idx_support_cases_case_number_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_cases_case_number_trgm ON public.support_cases USING gin (case_number public.gin_trgm_ops);


--
-- TOC entry 4732 (class 1259 OID 32560)
-- Name: idx_support_cases_created_by; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_cases_created_by ON public.support_cases USING btree (created_by);


--
-- TOC entry 4733 (class 1259 OID 32561)
-- Name: idx_support_cases_product; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_cases_product ON public.support_cases USING btree (product_item_id);


--
-- TOC entry 4734 (class 1259 OID 32562)
-- Name: idx_support_cases_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_cases_status ON public.support_cases USING btree (status);


--
-- TOC entry 4735 (class 1259 OID 32563)
-- Name: idx_support_cases_subject_trgm; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_cases_subject_trgm ON public.support_cases USING gin (subject public.gin_trgm_ops);


--
-- TOC entry 4747 (class 1259 OID 32564)
-- Name: idx_support_messages_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_messages_case ON public.support_messages USING btree (case_id);


--
-- TOC entry 4748 (class 1259 OID 32565)
-- Name: idx_support_messages_untranslated; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_messages_untranslated ON public.support_messages USING btree (case_id) WHERE ((translated_body IS NULL) AND ((type)::text <> 'internal_note'::text));


--
-- TOC entry 4751 (class 1259 OID 32566)
-- Name: idx_support_ratings_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_ratings_case ON public.support_ratings USING btree (case_id);


--
-- TOC entry 4754 (class 1259 OID 32567)
-- Name: idx_support_time_entries_case; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_time_entries_case ON public.support_time_entries USING btree (case_id);


--
-- TOC entry 4800 (class 1259 OID 33429)
-- Name: idx_support_waiting_message_events_message; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_waiting_message_events_message ON public.support_waiting_message_events USING btree (message_id, created_at);


--
-- TOC entry 4803 (class 1259 OID 33455)
-- Name: idx_support_waiting_message_helpers_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_waiting_message_helpers_user ON public.support_waiting_message_helpers USING btree (user_id);


--
-- TOC entry 4757 (class 1259 OID 32568)
-- Name: idx_support_waiting_message_replies_message; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_waiting_message_replies_message ON public.support_waiting_message_replies USING btree (message_id, created_at);


--
-- TOC entry 4758 (class 1259 OID 33411)
-- Name: idx_support_waiting_message_replies_reply_to; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_waiting_message_replies_reply_to ON public.support_waiting_message_replies USING btree (reply_to_id);


--
-- TOC entry 4763 (class 1259 OID 32569)
-- Name: idx_support_waiting_messages_created_by; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_waiting_messages_created_by ON public.support_waiting_messages USING btree (created_by, created_at DESC);


--
-- TOC entry 4764 (class 1259 OID 33401)
-- Name: idx_support_waiting_messages_customer; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_waiting_messages_customer ON public.support_waiting_messages USING btree (customer_id, created_at DESC);


--
-- TOC entry 4765 (class 1259 OID 32570)
-- Name: idx_support_waiting_messages_status_created; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_support_waiting_messages_status_created ON public.support_waiting_messages USING btree (status, created_at DESC);


--
-- TOC entry 4845 (class 1259 OID 44725)
-- Name: idx_tasks_assignee; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_assignee ON public.tasks USING btree (assignee_id);


--
-- TOC entry 4846 (class 1259 OID 44726)
-- Name: idx_tasks_parent; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_parent ON public.tasks USING btree (parent_task_id);


--
-- TOC entry 4847 (class 1259 OID 44724)
-- Name: idx_tasks_phase; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_phase ON public.tasks USING btree (phase_id);


--
-- TOC entry 4848 (class 1259 OID 44723)
-- Name: idx_tasks_project; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_project ON public.tasks USING btree (project_id);


--
-- TOC entry 4849 (class 1259 OID 44722)
-- Name: idx_tasks_source; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_source ON public.tasks USING btree (source_type, source_id);


--
-- TOC entry 4768 (class 1259 OID 32571)
-- Name: idx_user_organizations_organization_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_user_organizations_organization_id ON public.user_organizations USING btree (organization_id);


--
-- TOC entry 4769 (class 1259 OID 32572)
-- Name: idx_user_organizations_user_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_user_organizations_user_id ON public.user_organizations USING btree (user_id);


--
-- TOC entry 4966 (class 1259 OID 87134)
-- Name: idx_user_permissions_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_user_permissions_user ON public.user_permissions USING btree (user_id);


--
-- TOC entry 4772 (class 1259 OID 32573)
-- Name: idx_user_profiles_user_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_user_profiles_user_id ON public.user_profiles USING btree (user_id);


--
-- TOC entry 4777 (class 1259 OID 32574)
-- Name: idx_user_roles_role_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_user_roles_role_id ON public.user_roles USING btree (role_id);


--
-- TOC entry 4778 (class 1259 OID 32575)
-- Name: idx_user_roles_user_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_user_roles_user_id ON public.user_roles USING btree (user_id);


--
-- TOC entry 4783 (class 1259 OID 32576)
-- Name: idx_verification_codes_expires; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_verification_codes_expires ON public.verification_codes USING btree (expires_at);


--
-- TOC entry 4784 (class 1259 OID 32577)
-- Name: idx_verification_codes_target; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_verification_codes_target ON public.verification_codes USING btree (target, type, purpose) WHERE (verified_at IS NULL);


--
-- TOC entry 4785 (class 1259 OID 32578)
-- Name: idx_verification_codes_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_verification_codes_user ON public.verification_codes USING btree (auth_user_id) WHERE (verified_at IS NULL);


--
-- TOC entry 4940 (class 1259 OID 45259)
-- Name: idx_wo_operations_wo; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_wo_operations_wo ON public.wo_operations USING btree (work_order_id, step_order);


--
-- TOC entry 4788 (class 1259 OID 32579)
-- Name: idx_work_order_comments_author; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_work_order_comments_author ON public.work_order_comments USING btree (author_id) WHERE (deleted_at IS NULL);


--
-- TOC entry 4789 (class 1259 OID 32580)
-- Name: idx_work_order_comments_thread; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_work_order_comments_thread ON public.work_order_comments USING btree (work_order_id, created_at) WHERE (deleted_at IS NULL);


--
-- TOC entry 4792 (class 1259 OID 32581)
-- Name: idx_work_orders_assigned; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_work_orders_assigned ON public.work_orders USING btree (assigned_to) WHERE (deleted_at IS NULL);


--
-- TOC entry 4793 (class 1259 OID 32582)
-- Name: idx_work_orders_number; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_work_orders_number ON public.work_orders USING btree (order_number);


--
-- TOC entry 4794 (class 1259 OID 32583)
-- Name: idx_work_orders_product_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_work_orders_product_item ON public.work_orders USING btree (product_item_id) WHERE (deleted_at IS NULL);


--
-- TOC entry 4795 (class 1259 OID 32584)
-- Name: idx_work_orders_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_work_orders_status ON public.work_orders USING btree (status) WHERE (deleted_at IS NULL);


--
-- TOC entry 4809 (class 1259 OID 37549)
-- Name: iot_firmware_updates_open_device; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX iot_firmware_updates_open_device ON public.iot_firmware_updates USING btree (device_id) WHERE (closed_at IS NULL);


--
-- TOC entry 4668 (class 1259 OID 32585)
-- Name: roles_agent_org_code_key; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX roles_agent_org_code_key ON public.roles USING btree (organization_id, lower((code)::text)) WHERE (((kind)::text = 'system'::text) AND (organization_id IS NOT NULL));


--
-- TOC entry 4671 (class 1259 OID 32586)
-- Name: roles_product_code_key; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX roles_product_code_key ON public.roles USING btree (owner_customer_id, lower((code)::text)) WHERE ((kind)::text = 'product'::text);


--
-- TOC entry 4672 (class 1259 OID 32587)
-- Name: roles_product_name_key; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX roles_product_name_key ON public.roles USING btree (owner_customer_id, lower((name)::text)) WHERE ((kind)::text = 'product'::text);


--
-- TOC entry 4673 (class 1259 OID 32588)
-- Name: roles_system_code_key; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX roles_system_code_key ON public.roles USING btree (lower((code)::text)) WHERE (((kind)::text = 'system'::text) AND (organization_id IS NULL));


--
-- TOC entry 4972 (class 1259 OID 101571)
-- Name: uq_material_suppliers_primary; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_material_suppliers_primary ON public.material_suppliers USING btree (material_id) WHERE is_primary;


--
-- TOC entry 4616 (class 1259 OID 32589)
-- Name: uq_pirecall_pending; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_pirecall_pending ON public.product_item_recall_requests USING btree (product_item_id) WHERE (status = 'pending'::text);


--
-- TOC entry 4826 (class 1259 OID 37731)
-- Name: uq_potr_item_pending; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_potr_item_pending ON public.product_ownership_transfer_requests USING btree (product_item_id) WHERE ((status)::text = 'pending'::text);


--
-- TOC entry 4595 (class 1259 OID 32590)
-- Name: uq_product_agents_role; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_product_agents_role ON public.product_agents USING btree (product_item_id, agent_role) WHERE (deleted_at IS NULL);


--
-- TOC entry 4633 (class 1259 OID 32591)
-- Name: uq_product_ownerships_current; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_product_ownerships_current ON public.product_ownerships USING btree (product_item_id) WHERE (is_current AND (deleted_at IS NULL));


--
-- TOC entry 4642 (class 1259 OID 32592)
-- Name: uq_product_user_access_builtin; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_product_user_access_builtin ON public.product_user_access USING btree (product_item_id, auth_user_id) WHERE ((role_id IS NULL) AND (deleted_at IS NULL));


--
-- TOC entry 4643 (class 1259 OID 32593)
-- Name: uq_product_user_access_role; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_product_user_access_role ON public.product_user_access USING btree (product_item_id, auth_user_id, role_id) WHERE ((role_id IS NOT NULL) AND (deleted_at IS NULL));


--
-- TOC entry 4719 (class 1259 OID 32594)
-- Name: uq_support_assignments_current; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_support_assignments_current ON public.support_assignments USING btree (case_id) WHERE is_current;


--
-- TOC entry 4746 (class 1259 OID 32595)
-- Name: uq_support_entitlements_product; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_support_entitlements_product ON public.support_entitlements USING btree (product_item_id);


--
-- TOC entry 4856 (class 1259 OID 101612)
-- Name: uq_warehouses_default; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_warehouses_default ON public.warehouses USING btree (is_default) WHERE is_default;


--
-- TOC entry 5235 (class 2620 OID 32596)
-- Name: user_roles trg_user_roles_reject_product; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER trg_user_roles_reject_product BEFORE INSERT ON public.user_roles FOR EACH ROW EXECUTE FUNCTION public.roles_reject_product_role_assignment();


--
-- TOC entry 4973 (class 2606 OID 32597)
-- Name: activities activities_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT activities_sales_id_fkey FOREIGN KEY (sales_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5050 (class 2606 OID 32602)
-- Name: product_items assets_activated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_items
    ADD CONSTRAINT assets_activated_by_fkey FOREIGN KEY (activated_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5051 (class 2606 OID 32607)
-- Name: product_items assets_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_items
    ADD CONSTRAINT assets_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5052 (class 2606 OID 32612)
-- Name: product_items assets_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_items
    ADD CONSTRAINT assets_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- TOC entry 5209 (class 2606 OID 45191)
-- Name: bom_components bom_components_bom_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.bom_components
    ADD CONSTRAINT bom_components_bom_id_fkey FOREIGN KEY (bom_id) REFERENCES public.boms(id) ON DELETE CASCADE;


--
-- TOC entry 5210 (class 2606 OID 81068)
-- Name: bom_components bom_components_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.bom_components
    ADD CONSTRAINT bom_components_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5207 (class 2606 OID 78077)
-- Name: boms boms_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.boms
    ADD CONSTRAINT boms_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5208 (class 2606 OID 45177)
-- Name: boms boms_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.boms
    ADD CONSTRAINT boms_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- TOC entry 4974 (class 2606 OID 32617)
-- Name: campaign_registrations campaign_registrations_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaign_registrations
    ADD CONSTRAINT campaign_registrations_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.campaigns(id) ON DELETE CASCADE;


--
-- TOC entry 4975 (class 2606 OID 32622)
-- Name: campaign_registrations campaign_registrations_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaign_registrations
    ADD CONSTRAINT campaign_registrations_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- TOC entry 4976 (class 2606 OID 32627)
-- Name: campaign_visits campaign_visits_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaign_visits
    ADD CONSTRAINT campaign_visits_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.campaigns(id) ON DELETE CASCADE;


--
-- TOC entry 4977 (class 2606 OID 32632)
-- Name: campaigns campaigns_assigned_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_assigned_person_id_fkey FOREIGN KEY (assigned_person_id) REFERENCES public.auth_users(id);


--
-- TOC entry 4978 (class 2606 OID 32637)
-- Name: campaigns campaigns_business_field_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_business_field_id_fkey FOREIGN KEY (business_field_id) REFERENCES public.business_fields(id);


--
-- TOC entry 4979 (class 2606 OID 32642)
-- Name: campaigns campaigns_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 4980 (class 2606 OID 32647)
-- Name: campaigns campaigns_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 4981 (class 2606 OID 32652)
-- Name: campaigns campaigns_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- TOC entry 5141 (class 2606 OID 37567)
-- Name: chat_conversations chat_conversations_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_conversations
    ADD CONSTRAINT chat_conversations_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5142 (class 2606 OID 37639)
-- Name: chat_conversations chat_conversations_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_conversations
    ADD CONSTRAINT chat_conversations_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5145 (class 2606 OID 37599)
-- Name: chat_messages chat_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.chat_conversations(id) ON DELETE CASCADE;


--
-- TOC entry 5146 (class 2606 OID 37614)
-- Name: chat_messages chat_messages_pinned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pinned_by_fkey FOREIGN KEY (pinned_by) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5147 (class 2606 OID 37609)
-- Name: chat_messages chat_messages_reply_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_reply_to_id_fkey FOREIGN KEY (reply_to_id) REFERENCES public.chat_messages(id) ON DELETE SET NULL;


--
-- TOC entry 5148 (class 2606 OID 37604)
-- Name: chat_messages chat_messages_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5143 (class 2606 OID 37578)
-- Name: chat_participants chat_participants_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_participants
    ADD CONSTRAINT chat_participants_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.chat_conversations(id) ON DELETE CASCADE;


--
-- TOC entry 5144 (class 2606 OID 37583)
-- Name: chat_participants chat_participants_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_participants
    ADD CONSTRAINT chat_participants_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5137 (class 2606 OID 33547)
-- Name: company_doc_node_products company_doc_node_products_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_node_products
    ADD CONSTRAINT company_doc_node_products_node_id_fkey FOREIGN KEY (node_id) REFERENCES public.company_doc_nodes(id) ON DELETE CASCADE;


--
-- TOC entry 5138 (class 2606 OID 33552)
-- Name: company_doc_node_products company_doc_node_products_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_node_products
    ADD CONSTRAINT company_doc_node_products_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- TOC entry 4982 (class 2606 OID 32657)
-- Name: company_doc_node_versions company_doc_node_versions_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_node_versions
    ADD CONSTRAINT company_doc_node_versions_node_id_fkey FOREIGN KEY (node_id) REFERENCES public.company_doc_nodes(id) ON DELETE CASCADE;


--
-- TOC entry 4983 (class 2606 OID 32662)
-- Name: company_doc_nodes company_doc_nodes_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_nodes
    ADD CONSTRAINT company_doc_nodes_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 4984 (class 2606 OID 32667)
-- Name: company_doc_nodes company_doc_nodes_manualhub_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_nodes
    ADD CONSTRAINT company_doc_nodes_manualhub_document_id_fkey FOREIGN KEY (manualhub_document_id) REFERENCES public.manualhub_documents(id) ON DELETE CASCADE;


--
-- TOC entry 4985 (class 2606 OID 32672)
-- Name: company_doc_nodes company_doc_nodes_manualhub_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_nodes
    ADD CONSTRAINT company_doc_nodes_manualhub_product_id_fkey FOREIGN KEY (manualhub_product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- TOC entry 4986 (class 2606 OID 32677)
-- Name: company_doc_nodes company_doc_nodes_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_nodes
    ADD CONSTRAINT company_doc_nodes_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.company_doc_nodes(id) ON DELETE CASCADE;


--
-- TOC entry 4987 (class 2606 OID 32682)
-- Name: company_doc_nodes company_doc_nodes_pdf_cache_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_nodes
    ADD CONSTRAINT company_doc_nodes_pdf_cache_file_id_fkey FOREIGN KEY (pdf_cache_file_id) REFERENCES public.files(id) ON DELETE SET NULL;


--
-- TOC entry 4988 (class 2606 OID 32687)
-- Name: company_doc_nodes company_doc_nodes_root_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.company_doc_nodes
    ADD CONSTRAINT company_doc_nodes_root_id_fkey FOREIGN KEY (root_id) REFERENCES public.company_doc_nodes(id) ON DELETE SET NULL;


--
-- TOC entry 4989 (class 2606 OID 32692)
-- Name: contact_messages contact_messages_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.contact_messages
    ADD CONSTRAINT contact_messages_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- TOC entry 4990 (class 2606 OID 32697)
-- Name: customer_business_fields customer_business_fields_business_field_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_business_fields
    ADD CONSTRAINT customer_business_fields_business_field_id_fkey FOREIGN KEY (business_field_id) REFERENCES public.business_fields(id) ON DELETE CASCADE;


--
-- TOC entry 4991 (class 2606 OID 32702)
-- Name: customer_business_fields customer_business_fields_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_business_fields
    ADD CONSTRAINT customer_business_fields_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- TOC entry 4992 (class 2606 OID 32707)
-- Name: customer_customer_groups customer_customer_groups_customer_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_customer_groups
    ADD CONSTRAINT customer_customer_groups_customer_group_id_fkey FOREIGN KEY (customer_group_id) REFERENCES public.customer_groups(id) ON DELETE CASCADE;


--
-- TOC entry 4993 (class 2606 OID 32712)
-- Name: customer_customer_groups customer_customer_groups_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_customer_groups
    ADD CONSTRAINT customer_customer_groups_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- TOC entry 4994 (class 2606 OID 32717)
-- Name: customer_logs customer_logs_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_logs
    ADD CONSTRAINT customer_logs_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.auth_users(id);


--
-- TOC entry 4995 (class 2606 OID 32722)
-- Name: customer_logs customer_logs_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_logs
    ADD CONSTRAINT customer_logs_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- TOC entry 4996 (class 2606 OID 32727)
-- Name: customer_new_interactions customer_new_interactions_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_new_interactions
    ADD CONSTRAINT customer_new_interactions_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- TOC entry 4997 (class 2606 OID 32732)
-- Name: customer_statuses customer_statuses_status_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_statuses
    ADD CONSTRAINT customer_statuses_status_group_id_fkey FOREIGN KEY (status_group_id) REFERENCES public.customer_status_groups(id);


--
-- TOC entry 4998 (class 2606 OID 32737)
-- Name: customer_team_members customer_team_members_auth_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_team_members
    ADD CONSTRAINT customer_team_members_auth_user_id_fkey FOREIGN KEY (auth_user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 4999 (class 2606 OID 32742)
-- Name: customer_team_members customer_team_members_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_team_members
    ADD CONSTRAINT customer_team_members_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5000 (class 2606 OID 32747)
-- Name: customer_team_members customer_team_members_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_team_members
    ADD CONSTRAINT customer_team_members_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- TOC entry 5001 (class 2606 OID 32752)
-- Name: customer_views customer_views_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_views
    ADD CONSTRAINT customer_views_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- TOC entry 5002 (class 2606 OID 32757)
-- Name: customer_views customer_views_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customer_views
    ADD CONSTRAINT customer_views_sales_id_fkey FOREIGN KEY (sales_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5003 (class 2606 OID 32762)
-- Name: customers customers_assigned_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_assigned_sales_id_fkey FOREIGN KEY (assigned_sales_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5004 (class 2606 OID 32767)
-- Name: customers customers_merged_into_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_merged_into_id_fkey FOREIGN KEY (merged_into_id) REFERENCES public.customers(id);


--
-- TOC entry 5005 (class 2606 OID 32772)
-- Name: customers customers_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5006 (class 2606 OID 32777)
-- Name: customers customers_self_of_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_self_of_organization_id_fkey FOREIGN KEY (self_of_organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- TOC entry 5007 (class 2606 OID 32782)
-- Name: customers customers_source_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_source_campaign_id_fkey FOREIGN KEY (source_campaign_id) REFERENCES public.campaigns(id);


--
-- TOC entry 5010 (class 2606 OID 32787)
-- Name: file_links file_links_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.file_links
    ADD CONSTRAINT file_links_file_id_fkey FOREIGN KEY (file_id) REFERENCES public.files(id) ON DELETE CASCADE;


--
-- TOC entry 5011 (class 2606 OID 32792)
-- Name: files files_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5228 (class 2606 OID 45367)
-- Name: finished_goods_receipt_items finished_goods_receipt_items_finished_goods_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.finished_goods_receipt_items
    ADD CONSTRAINT finished_goods_receipt_items_finished_goods_receipt_id_fkey FOREIGN KEY (finished_goods_receipt_id) REFERENCES public.finished_goods_receipts(id) ON DELETE CASCADE;


--
-- TOC entry 5226 (class 2606 OID 45356)
-- Name: finished_goods_receipts finished_goods_receipts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.finished_goods_receipts
    ADD CONSTRAINT finished_goods_receipts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5227 (class 2606 OID 45351)
-- Name: finished_goods_receipts finished_goods_receipts_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.finished_goods_receipts
    ADD CONSTRAINT finished_goods_receipts_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.manufacturing_work_orders(id);


--
-- TOC entry 5008 (class 2606 OID 32797)
-- Name: customers fk_customers_created_by; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT fk_customers_created_by FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5009 (class 2606 OID 32802)
-- Name: customers fk_customers_status_id; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT fk_customers_status_id FOREIGN KEY (status_id) REFERENCES public.customer_statuses(id);


--
-- TOC entry 5102 (class 2606 OID 32807)
-- Name: support_entitlement_transactions fk_entitlement_tx_case; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_entitlement_transactions
    ADD CONSTRAINT fk_entitlement_tx_case FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5103 (class 2606 OID 32812)
-- Name: support_entitlement_transactions fk_entitlement_tx_time_entry; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_entitlement_transactions
    ADD CONSTRAINT fk_entitlement_tx_time_entry FOREIGN KEY (time_entry_id) REFERENCES public.support_time_entries(id);


--
-- TOC entry 5113 (class 2606 OID 32817)
-- Name: support_time_entries fk_time_entries_appointment; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_time_entries
    ADD CONSTRAINT fk_time_entries_appointment FOREIGN KEY (appointment_id) REFERENCES public.support_appointments(id);


--
-- TOC entry 5183 (class 2606 OID 44912)
-- Name: goods_issue_items goods_issue_items_goods_issue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issue_items
    ADD CONSTRAINT goods_issue_items_goods_issue_id_fkey FOREIGN KEY (goods_issue_id) REFERENCES public.goods_issues(id) ON DELETE CASCADE;


--
-- TOC entry 5184 (class 2606 OID 44917)
-- Name: goods_issue_items goods_issue_items_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issue_items
    ADD CONSTRAINT goods_issue_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5185 (class 2606 OID 44922)
-- Name: goods_issue_items goods_issue_items_serial_lot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issue_items
    ADD CONSTRAINT goods_issue_items_serial_lot_id_fkey FOREIGN KEY (serial_lot_id) REFERENCES public.material_serial_lots(id);


--
-- TOC entry 5179 (class 2606 OID 44897)
-- Name: goods_issues goods_issues_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issues
    ADD CONSTRAINT goods_issues_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5180 (class 2606 OID 44892)
-- Name: goods_issues goods_issues_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issues
    ADD CONSTRAINT goods_issues_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5181 (class 2606 OID 90158)
-- Name: goods_issues goods_issues_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issues
    ADD CONSTRAINT goods_issues_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5182 (class 2606 OID 44887)
-- Name: goods_issues goods_issues_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_issues
    ADD CONSTRAINT goods_issues_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5176 (class 2606 OID 44865)
-- Name: goods_receipt_items goods_receipt_items_goods_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipt_items
    ADD CONSTRAINT goods_receipt_items_goods_receipt_id_fkey FOREIGN KEY (goods_receipt_id) REFERENCES public.goods_receipts(id) ON DELETE CASCADE;


--
-- TOC entry 5177 (class 2606 OID 44870)
-- Name: goods_receipt_items goods_receipt_items_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipt_items
    ADD CONSTRAINT goods_receipt_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5178 (class 2606 OID 101493)
-- Name: goods_receipt_items goods_receipt_items_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipt_items
    ADD CONSTRAINT goods_receipt_items_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- TOC entry 5173 (class 2606 OID 44851)
-- Name: goods_receipts goods_receipts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipts
    ADD CONSTRAINT goods_receipts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5174 (class 2606 OID 90153)
-- Name: goods_receipts goods_receipts_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipts
    ADD CONSTRAINT goods_receipts_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5175 (class 2606 OID 44846)
-- Name: goods_receipts goods_receipts_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_receipts
    ADD CONSTRAINT goods_receipts_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5205 (class 2606 OID 45158)
-- Name: goods_return_items goods_return_items_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_return_items
    ADD CONSTRAINT goods_return_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5206 (class 2606 OID 45153)
-- Name: goods_return_items goods_return_items_return_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_return_items
    ADD CONSTRAINT goods_return_items_return_id_fkey FOREIGN KEY (return_id) REFERENCES public.goods_returns(id) ON DELETE CASCADE;


--
-- TOC entry 5202 (class 2606 OID 45139)
-- Name: goods_returns goods_returns_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_returns
    ADD CONSTRAINT goods_returns_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5203 (class 2606 OID 45129)
-- Name: goods_returns goods_returns_po_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_returns
    ADD CONSTRAINT goods_returns_po_id_fkey FOREIGN KEY (po_id) REFERENCES public.purchase_orders(id);


--
-- TOC entry 5204 (class 2606 OID 45134)
-- Name: goods_returns goods_returns_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.goods_returns
    ADD CONSTRAINT goods_returns_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5012 (class 2606 OID 32822)
-- Name: iot_devices iot_devices_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_devices
    ADD CONSTRAINT iot_devices_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5139 (class 2606 OID 37539)
-- Name: iot_firmware_updates iot_firmware_updates_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_firmware_updates
    ADD CONSTRAINT iot_firmware_updates_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.iot_devices(device_id) ON DELETE CASCADE;


--
-- TOC entry 5140 (class 2606 OID 37544)
-- Name: iot_firmware_updates iot_firmware_updates_firmware_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.iot_firmware_updates
    ADD CONSTRAINT iot_firmware_updates_firmware_id_fkey FOREIGN KEY (firmware_id) REFERENCES public.iot_firmwares(id) ON DELETE CASCADE;


--
-- TOC entry 5013 (class 2606 OID 32827)
-- Name: issue_reports issue_reports_converted_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.issue_reports
    ADD CONSTRAINT issue_reports_converted_case_id_fkey FOREIGN KEY (converted_case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5014 (class 2606 OID 32832)
-- Name: issue_reports issue_reports_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.issue_reports
    ADD CONSTRAINT issue_reports_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5015 (class 2606 OID 32837)
-- Name: issue_reports issue_reports_reporter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.issue_reports
    ADD CONSTRAINT issue_reports_reporter_id_fkey FOREIGN KEY (reporter_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5016 (class 2606 OID 32842)
-- Name: issue_reports issue_reports_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.issue_reports
    ADD CONSTRAINT issue_reports_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5017 (class 2606 OID 32847)
-- Name: keygen_history keygen_history_generated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.keygen_history
    ADD CONSTRAINT keygen_history_generated_by_fkey FOREIGN KEY (generated_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5018 (class 2606 OID 32852)
-- Name: keygen_history keygen_history_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.keygen_history
    ADD CONSTRAINT keygen_history_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5019 (class 2606 OID 32857)
-- Name: keygen_history keygen_history_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.keygen_history
    ADD CONSTRAINT keygen_history_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5020 (class 2606 OID 32862)
-- Name: leads leads_source_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.leads
    ADD CONSTRAINT leads_source_campaign_id_fkey FOREIGN KEY (source_campaign_id) REFERENCES public.campaigns(id);


--
-- TOC entry 5021 (class 2606 OID 32867)
-- Name: lock_requests lock_requests_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.lock_requests
    ADD CONSTRAINT lock_requests_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5022 (class 2606 OID 32872)
-- Name: lock_requests lock_requests_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.lock_requests
    ADD CONSTRAINT lock_requests_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5023 (class 2606 OID 32877)
-- Name: lock_requests lock_requests_requester_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.lock_requests
    ADD CONSTRAINT lock_requests_requester_id_fkey FOREIGN KEY (requester_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5024 (class 2606 OID 32882)
-- Name: manualhub_activities manualhub_activities_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manualhub_activities
    ADD CONSTRAINT manualhub_activities_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.manualhub_documents(id) ON DELETE SET NULL;


--
-- TOC entry 5025 (class 2606 OID 32887)
-- Name: manualhub_document_versions manualhub_document_versions_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manualhub_document_versions
    ADD CONSTRAINT manualhub_document_versions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.manualhub_documents(id) ON DELETE CASCADE;


--
-- TOC entry 5026 (class 2606 OID 32892)
-- Name: manualhub_documents manualhub_documents_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manualhub_documents
    ADD CONSTRAINT manualhub_documents_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.manualhub_documents(id) ON DELETE SET NULL;


--
-- TOC entry 5027 (class 2606 OID 32897)
-- Name: manualhub_documents manualhub_documents_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manualhub_documents
    ADD CONSTRAINT manualhub_documents_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- TOC entry 5028 (class 2606 OID 32902)
-- Name: manualhub_documents manualhub_documents_root_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manualhub_documents
    ADD CONSTRAINT manualhub_documents_root_id_fkey FOREIGN KEY (root_id) REFERENCES public.manualhub_documents(id) ON DELETE SET NULL;


--
-- TOC entry 5211 (class 2606 OID 45215)
-- Name: manufacturing_work_orders manufacturing_work_orders_bom_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manufacturing_work_orders
    ADD CONSTRAINT manufacturing_work_orders_bom_id_fkey FOREIGN KEY (bom_id) REFERENCES public.boms(id);


--
-- TOC entry 5212 (class 2606 OID 45230)
-- Name: manufacturing_work_orders manufacturing_work_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manufacturing_work_orders
    ADD CONSTRAINT manufacturing_work_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5213 (class 2606 OID 45210)
-- Name: manufacturing_work_orders manufacturing_work_orders_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manufacturing_work_orders
    ADD CONSTRAINT manufacturing_work_orders_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- TOC entry 5214 (class 2606 OID 45220)
-- Name: manufacturing_work_orders manufacturing_work_orders_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manufacturing_work_orders
    ADD CONSTRAINT manufacturing_work_orders_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- TOC entry 5215 (class 2606 OID 45225)
-- Name: manufacturing_work_orders manufacturing_work_orders_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.manufacturing_work_orders
    ADD CONSTRAINT manufacturing_work_orders_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id);


--
-- TOC entry 5218 (class 2606 OID 45273)
-- Name: material_consumptions material_consumptions_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_consumptions
    ADD CONSTRAINT material_consumptions_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5219 (class 2606 OID 45268)
-- Name: material_consumptions material_consumptions_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_consumptions
    ADD CONSTRAINT material_consumptions_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.manufacturing_work_orders(id);


--
-- TOC entry 5229 (class 2606 OID 45381)
-- Name: material_serial_lot_consumptions material_serial_lot_consumptions_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_serial_lot_consumptions
    ADD CONSTRAINT material_serial_lot_consumptions_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.manufacturing_work_orders(id);


--
-- TOC entry 5166 (class 2606 OID 44791)
-- Name: material_serial_lots material_serial_lots_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_serial_lots
    ADD CONSTRAINT material_serial_lots_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5167 (class 2606 OID 44796)
-- Name: material_serial_lots material_serial_lots_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_serial_lots
    ADD CONSTRAINT material_serial_lots_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5233 (class 2606 OID 101561)
-- Name: material_suppliers material_suppliers_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_suppliers
    ADD CONSTRAINT material_suppliers_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id) ON DELETE CASCADE;


--
-- TOC entry 5234 (class 2606 OID 101566)
-- Name: material_suppliers material_suppliers_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.material_suppliers
    ADD CONSTRAINT material_suppliers_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- TOC entry 5029 (class 2606 OID 32907)
-- Name: notification_delivery_log notification_delivery_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.notification_delivery_log
    ADD CONSTRAINT notification_delivery_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5030 (class 2606 OID 32912)
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5031 (class 2606 OID 32917)
-- Name: organizations organizations_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5032 (class 2606 OID 32922)
-- Name: organizations organizations_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.organizations(id);


--
-- TOC entry 5033 (class 2606 OID 32927)
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5157 (class 2606 OID 44659)
-- Name: phases phases_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.phases
    ADD CONSTRAINT phases_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- TOC entry 5200 (class 2606 OID 45112)
-- Name: po_backorders po_backorders_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.po_backorders
    ADD CONSTRAINT po_backorders_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5201 (class 2606 OID 45107)
-- Name: po_backorders po_backorders_po_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.po_backorders
    ADD CONSTRAINT po_backorders_po_id_fkey FOREIGN KEY (po_id) REFERENCES public.purchase_orders(id);


--
-- TOC entry 5199 (class 2606 OID 45090)
-- Name: po_goods_receipts po_goods_receipts_po_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.po_goods_receipts
    ADD CONSTRAINT po_goods_receipts_po_id_fkey FOREIGN KEY (po_id) REFERENCES public.purchase_orders(id);


--
-- TOC entry 5034 (class 2606 OID 32932)
-- Name: product_agents product_agents_agent_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_agents
    ADD CONSTRAINT product_agents_agent_organization_id_fkey FOREIGN KEY (agent_organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5035 (class 2606 OID 32937)
-- Name: product_agents product_agents_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_agents
    ADD CONSTRAINT product_agents_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5036 (class 2606 OID 32942)
-- Name: product_agents product_agents_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_agents
    ADD CONSTRAINT product_agents_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5037 (class 2606 OID 32947)
-- Name: product_item_activation_requests product_item_activation_requests_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_activation_requests
    ADD CONSTRAINT product_item_activation_requests_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE RESTRICT;


--
-- TOC entry 5038 (class 2606 OID 32952)
-- Name: product_item_activation_requests product_item_activation_requests_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_activation_requests
    ADD CONSTRAINT product_item_activation_requests_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- TOC entry 5039 (class 2606 OID 32957)
-- Name: product_item_activation_requests product_item_activation_requests_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_activation_requests
    ADD CONSTRAINT product_item_activation_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5040 (class 2606 OID 32962)
-- Name: product_item_activation_requests product_item_activation_requests_sales_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_activation_requests
    ADD CONSTRAINT product_item_activation_requests_sales_user_id_fkey FOREIGN KEY (sales_user_id) REFERENCES public.auth_users(id) ON DELETE RESTRICT;


--
-- TOC entry 5041 (class 2606 OID 32967)
-- Name: product_item_aliases product_item_aliases_owner_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_aliases
    ADD CONSTRAINT product_item_aliases_owner_customer_id_fkey FOREIGN KEY (owner_customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5042 (class 2606 OID 32972)
-- Name: product_item_aliases product_item_aliases_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_aliases
    ADD CONSTRAINT product_item_aliases_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5043 (class 2606 OID 32977)
-- Name: product_item_logs product_item_logs_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_logs
    ADD CONSTRAINT product_item_logs_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5044 (class 2606 OID 32982)
-- Name: product_item_logs product_item_logs_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_logs
    ADD CONSTRAINT product_item_logs_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE SET NULL;


--
-- TOC entry 5045 (class 2606 OID 32987)
-- Name: product_item_logs product_item_logs_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_logs
    ADD CONSTRAINT product_item_logs_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id) ON DELETE CASCADE;


--
-- TOC entry 5046 (class 2606 OID 32992)
-- Name: product_item_recall_requests product_item_recall_requests_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_recall_requests
    ADD CONSTRAINT product_item_recall_requests_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id) ON DELETE CASCADE;


--
-- TOC entry 5047 (class 2606 OID 32997)
-- Name: product_item_return_requests product_item_return_requests_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_return_requests
    ADD CONSTRAINT product_item_return_requests_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5048 (class 2606 OID 33002)
-- Name: product_item_return_requests product_item_return_requests_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_return_requests
    ADD CONSTRAINT product_item_return_requests_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5049 (class 2606 OID 33007)
-- Name: product_item_return_requests product_item_return_requests_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_item_return_requests
    ADD CONSTRAINT product_item_return_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5149 (class 2606 OID 37709)
-- Name: product_ownership_transfer_requests product_ownership_transfer_requests_from_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownership_transfer_requests
    ADD CONSTRAINT product_ownership_transfer_requests_from_customer_id_fkey FOREIGN KEY (from_customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5150 (class 2606 OID 37704)
-- Name: product_ownership_transfer_requests product_ownership_transfer_requests_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownership_transfer_requests
    ADD CONSTRAINT product_ownership_transfer_requests_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5151 (class 2606 OID 37719)
-- Name: product_ownership_transfer_requests product_ownership_transfer_requests_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownership_transfer_requests
    ADD CONSTRAINT product_ownership_transfer_requests_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5152 (class 2606 OID 37724)
-- Name: product_ownership_transfer_requests product_ownership_transfer_requests_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownership_transfer_requests
    ADD CONSTRAINT product_ownership_transfer_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5153 (class 2606 OID 37714)
-- Name: product_ownership_transfer_requests product_ownership_transfer_requests_to_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownership_transfer_requests
    ADD CONSTRAINT product_ownership_transfer_requests_to_customer_id_fkey FOREIGN KEY (to_customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5053 (class 2606 OID 33012)
-- Name: product_ownerships product_ownerships_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownerships
    ADD CONSTRAINT product_ownerships_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5054 (class 2606 OID 33017)
-- Name: product_ownerships product_ownerships_owner_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownerships
    ADD CONSTRAINT product_ownerships_owner_customer_id_fkey FOREIGN KEY (owner_customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5055 (class 2606 OID 33022)
-- Name: product_ownerships product_ownerships_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownerships
    ADD CONSTRAINT product_ownerships_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5056 (class 2606 OID 33027)
-- Name: product_ownerships product_ownerships_transferred_from_ownership_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_ownerships
    ADD CONSTRAINT product_ownerships_transferred_from_ownership_id_fkey FOREIGN KEY (transferred_from_ownership_id) REFERENCES public.product_ownerships(id);


--
-- TOC entry 5057 (class 2606 OID 33032)
-- Name: product_support_limits product_support_limits_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_support_limits
    ADD CONSTRAINT product_support_limits_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- TOC entry 5058 (class 2606 OID 33037)
-- Name: product_user_access product_user_access_auth_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_user_access
    ADD CONSTRAINT product_user_access_auth_user_id_fkey FOREIGN KEY (auth_user_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5059 (class 2606 OID 33042)
-- Name: product_user_access product_user_access_invited_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_user_access
    ADD CONSTRAINT product_user_access_invited_by_fkey FOREIGN KEY (invited_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5060 (class 2606 OID 33047)
-- Name: product_user_access product_user_access_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_user_access
    ADD CONSTRAINT product_user_access_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5061 (class 2606 OID 33052)
-- Name: product_user_access product_user_access_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.product_user_access
    ADD CONSTRAINT product_user_access_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- TOC entry 5223 (class 2606 OID 45314)
-- Name: project_asset_components project_asset_components_project_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_asset_components
    ADD CONSTRAINT project_asset_components_project_asset_id_fkey FOREIGN KEY (project_asset_id) REFERENCES public.project_assets(id) ON DELETE CASCADE;


--
-- TOC entry 5224 (class 2606 OID 45319)
-- Name: project_asset_components project_asset_components_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_asset_components
    ADD CONSTRAINT project_asset_components_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.manufacturing_work_orders(id);


--
-- TOC entry 5220 (class 2606 OID 45301)
-- Name: project_assets project_assets_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_assets
    ADD CONSTRAINT project_assets_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5221 (class 2606 OID 45291)
-- Name: project_assets project_assets_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_assets
    ADD CONSTRAINT project_assets_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- TOC entry 5222 (class 2606 OID 45296)
-- Name: project_assets project_assets_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_assets
    ADD CONSTRAINT project_assets_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.manufacturing_work_orders(id);


--
-- TOC entry 5158 (class 2606 OID 44674)
-- Name: project_members project_members_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- TOC entry 5159 (class 2606 OID 44679)
-- Name: project_members project_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5155 (class 2606 OID 44636)
-- Name: projects projects_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5156 (class 2606 OID 44641)
-- Name: projects projects_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5197 (class 2606 OID 45077)
-- Name: purchase_order_items purchase_order_items_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5198 (class 2606 OID 45072)
-- Name: purchase_order_items purchase_order_items_po_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_po_id_fkey FOREIGN KEY (po_id) REFERENCES public.purchase_orders(id) ON DELETE CASCADE;


--
-- TOC entry 5194 (class 2606 OID 45057)
-- Name: purchase_orders purchase_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5195 (class 2606 OID 45047)
-- Name: purchase_orders purchase_orders_pr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_pr_id_fkey FOREIGN KEY (pr_id) REFERENCES public.purchase_requisitions(id);


--
-- TOC entry 5196 (class 2606 OID 45052)
-- Name: purchase_orders purchase_orders_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- TOC entry 5192 (class 2606 OID 45031)
-- Name: purchase_requisition_items purchase_requisition_items_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_requisition_items
    ADD CONSTRAINT purchase_requisition_items_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5193 (class 2606 OID 45026)
-- Name: purchase_requisition_items purchase_requisition_items_pr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_requisition_items
    ADD CONSTRAINT purchase_requisition_items_pr_id_fkey FOREIGN KEY (pr_id) REFERENCES public.purchase_requisitions(id) ON DELETE CASCADE;


--
-- TOC entry 5190 (class 2606 OID 45012)
-- Name: purchase_requisitions purchase_requisitions_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_requisitions
    ADD CONSTRAINT purchase_requisitions_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5191 (class 2606 OID 45007)
-- Name: purchase_requisitions purchase_requisitions_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_requisitions
    ADD CONSTRAINT purchase_requisitions_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5062 (class 2606 OID 33057)
-- Name: push_device_tokens push_device_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.push_device_tokens
    ADD CONSTRAINT push_device_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5225 (class 2606 OID 45337)
-- Name: qc_records qc_records_inspector_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.qc_records
    ADD CONSTRAINT qc_records_inspector_fkey FOREIGN KEY (inspector) REFERENCES public.auth_users(id);


--
-- TOC entry 5063 (class 2606 OID 33062)
-- Name: rbac_audit_logs rbac_audit_logs_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rbac_audit_logs
    ADD CONSTRAINT rbac_audit_logs_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5064 (class 2606 OID 33067)
-- Name: rbac_audit_logs rbac_audit_logs_target_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rbac_audit_logs
    ADD CONSTRAINT rbac_audit_logs_target_organization_id_fkey FOREIGN KEY (target_organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5065 (class 2606 OID 33072)
-- Name: rbac_audit_logs rbac_audit_logs_target_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rbac_audit_logs
    ADD CONSTRAINT rbac_audit_logs_target_permission_id_fkey FOREIGN KEY (target_permission_id) REFERENCES public.permissions(id);


--
-- TOC entry 5066 (class 2606 OID 33077)
-- Name: rbac_audit_logs rbac_audit_logs_target_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rbac_audit_logs
    ADD CONSTRAINT rbac_audit_logs_target_role_id_fkey FOREIGN KEY (target_role_id) REFERENCES public.roles(id) ON DELETE SET NULL;


--
-- TOC entry 5067 (class 2606 OID 33082)
-- Name: rbac_audit_logs rbac_audit_logs_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rbac_audit_logs
    ADD CONSTRAINT rbac_audit_logs_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5154 (class 2606 OID 37813)
-- Name: request_comments request_comments_author_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.request_comments
    ADD CONSTRAINT request_comments_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5068 (class 2606 OID 33087)
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id);


--
-- TOC entry 5069 (class 2606 OID 33092)
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- TOC entry 5070 (class 2606 OID 33097)
-- Name: roles roles_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5071 (class 2606 OID 33102)
-- Name: roles roles_owner_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_owner_customer_id_fkey FOREIGN KEY (owner_customer_id) REFERENCES public.customers(id);


--
-- TOC entry 5072 (class 2606 OID 33107)
-- Name: sales_round_robin_state sales_round_robin_state_last_assigned_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sales_round_robin_state
    ADD CONSTRAINT sales_round_robin_state_last_assigned_sales_id_fkey FOREIGN KEY (last_assigned_sales_id) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5073 (class 2606 OID 33112)
-- Name: sales_users sales_users_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sales_users
    ADD CONSTRAINT sales_users_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5074 (class 2606 OID 33117)
-- Name: service_logs service_logs_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.service_logs
    ADD CONSTRAINT service_logs_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5075 (class 2606 OID 33122)
-- Name: service_logs service_logs_source_comment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.service_logs
    ADD CONSTRAINT service_logs_source_comment_id_fkey FOREIGN KEY (source_comment_id) REFERENCES public.work_order_comments(id) ON DELETE CASCADE;


--
-- TOC entry 5076 (class 2606 OID 33127)
-- Name: service_logs service_logs_technician_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.service_logs
    ADD CONSTRAINT service_logs_technician_id_fkey FOREIGN KEY (technician_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5077 (class 2606 OID 33132)
-- Name: service_logs service_logs_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.service_logs
    ADD CONSTRAINT service_logs_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id);


--
-- TOC entry 5078 (class 2606 OID 33137)
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5079 (class 2606 OID 33142)
-- Name: sso_tickets sso_tickets_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.sso_tickets
    ADD CONSTRAINT sso_tickets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5164 (class 2606 OID 44763)
-- Name: stock stock_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock
    ADD CONSTRAINT stock_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5168 (class 2606 OID 44828)
-- Name: stock_movements stock_movements_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5169 (class 2606 OID 44813)
-- Name: stock_movements stock_movements_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5170 (class 2606 OID 44932)
-- Name: stock_movements stock_movements_related_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_related_warehouse_id_fkey FOREIGN KEY (related_warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5171 (class 2606 OID 44823)
-- Name: stock_movements stock_movements_serial_lot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_serial_lot_id_fkey FOREIGN KEY (serial_lot_id) REFERENCES public.material_serial_lots(id);


--
-- TOC entry 5172 (class 2606 OID 44818)
-- Name: stock_movements stock_movements_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5165 (class 2606 OID 44768)
-- Name: stock stock_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock
    ADD CONSTRAINT stock_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5188 (class 2606 OID 44974)
-- Name: stocktake_lines stocktake_lines_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stocktake_lines
    ADD CONSTRAINT stocktake_lines_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- TOC entry 5189 (class 2606 OID 44969)
-- Name: stocktake_lines stocktake_lines_stocktake_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stocktake_lines
    ADD CONSTRAINT stocktake_lines_stocktake_id_fkey FOREIGN KEY (stocktake_id) REFERENCES public.stocktakes(id) ON DELETE CASCADE;


--
-- TOC entry 5186 (class 2606 OID 44956)
-- Name: stocktakes stocktakes_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stocktakes
    ADD CONSTRAINT stocktakes_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5187 (class 2606 OID 44951)
-- Name: stocktakes stocktakes_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stocktakes
    ADD CONSTRAINT stocktakes_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(id);


--
-- TOC entry 5080 (class 2606 OID 33147)
-- Name: students students_source_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_source_campaign_id_fkey FOREIGN KEY (source_campaign_id) REFERENCES public.campaigns(id);


--
-- TOC entry 5081 (class 2606 OID 33152)
-- Name: support_appointments support_appointments_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_appointments
    ADD CONSTRAINT support_appointments_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5082 (class 2606 OID 33157)
-- Name: support_appointments support_appointments_customer_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_appointments
    ADD CONSTRAINT support_appointments_customer_user_id_fkey FOREIGN KEY (customer_user_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5083 (class 2606 OID 33162)
-- Name: support_appointments support_appointments_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_appointments
    ADD CONSTRAINT support_appointments_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5084 (class 2606 OID 33167)
-- Name: support_appointments support_appointments_support_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_appointments
    ADD CONSTRAINT support_appointments_support_organization_id_fkey FOREIGN KEY (support_organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5085 (class 2606 OID 33172)
-- Name: support_appointments support_appointments_support_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_appointments
    ADD CONSTRAINT support_appointments_support_user_id_fkey FOREIGN KEY (support_user_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5086 (class 2606 OID 33177)
-- Name: support_assignments support_assignments_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_assignments
    ADD CONSTRAINT support_assignments_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5087 (class 2606 OID 33182)
-- Name: support_assignments support_assignments_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_assignments
    ADD CONSTRAINT support_assignments_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.auth_users(id);


--
-- TOC entry 5088 (class 2606 OID 33187)
-- Name: support_assignments support_assignments_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_assignments
    ADD CONSTRAINT support_assignments_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5089 (class 2606 OID 33192)
-- Name: support_assignments support_assignments_support_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_assignments
    ADD CONSTRAINT support_assignments_support_organization_id_fkey FOREIGN KEY (support_organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5090 (class 2606 OID 33197)
-- Name: support_attachments support_attachments_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_attachments
    ADD CONSTRAINT support_attachments_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5091 (class 2606 OID 33202)
-- Name: support_attachments support_attachments_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_attachments
    ADD CONSTRAINT support_attachments_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.support_messages(id);


--
-- TOC entry 5092 (class 2606 OID 33207)
-- Name: support_attachments support_attachments_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_attachments
    ADD CONSTRAINT support_attachments_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5093 (class 2606 OID 33212)
-- Name: support_cancel_requests support_cancel_requests_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cancel_requests
    ADD CONSTRAINT support_cancel_requests_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5094 (class 2606 OID 33217)
-- Name: support_cancel_requests support_cancel_requests_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cancel_requests
    ADD CONSTRAINT support_cancel_requests_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5095 (class 2606 OID 33222)
-- Name: support_cancel_requests support_cancel_requests_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cancel_requests
    ADD CONSTRAINT support_cancel_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5096 (class 2606 OID 33227)
-- Name: support_case_events support_case_events_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_case_events
    ADD CONSTRAINT support_case_events_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5097 (class 2606 OID 33232)
-- Name: support_case_events support_case_events_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_case_events
    ADD CONSTRAINT support_case_events_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5098 (class 2606 OID 33237)
-- Name: support_cases support_cases_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cases
    ADD CONSTRAINT support_cases_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5099 (class 2606 OID 33242)
-- Name: support_cases support_cases_customer_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cases
    ADD CONSTRAINT support_cases_customer_organization_id_fkey FOREIGN KEY (customer_organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5100 (class 2606 OID 33247)
-- Name: support_cases support_cases_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cases
    ADD CONSTRAINT support_cases_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5101 (class 2606 OID 33252)
-- Name: support_cases support_cases_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_cases
    ADD CONSTRAINT support_cases_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id);


--
-- TOC entry 5104 (class 2606 OID 33257)
-- Name: support_entitlement_transactions support_entitlement_transactions_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_entitlement_transactions
    ADD CONSTRAINT support_entitlement_transactions_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5105 (class 2606 OID 33262)
-- Name: support_entitlement_transactions support_entitlement_transactions_entitlement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_entitlement_transactions
    ADD CONSTRAINT support_entitlement_transactions_entitlement_id_fkey FOREIGN KEY (entitlement_id) REFERENCES public.support_entitlements(id);


--
-- TOC entry 5106 (class 2606 OID 33267)
-- Name: support_entitlements support_entitlements_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_entitlements
    ADD CONSTRAINT support_entitlements_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5107 (class 2606 OID 33272)
-- Name: support_messages support_messages_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5108 (class 2606 OID 33277)
-- Name: support_messages support_messages_reply_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_reply_to_id_fkey FOREIGN KEY (reply_to_id) REFERENCES public.support_messages(id) ON DELETE SET NULL;


--
-- TOC entry 5109 (class 2606 OID 33282)
-- Name: support_messages support_messages_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5110 (class 2606 OID 33287)
-- Name: support_ratings support_ratings_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_ratings
    ADD CONSTRAINT support_ratings_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5111 (class 2606 OID 33292)
-- Name: support_ratings support_ratings_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_ratings
    ADD CONSTRAINT support_ratings_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5112 (class 2606 OID 33297)
-- Name: support_ratings support_ratings_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_ratings
    ADD CONSTRAINT support_ratings_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5114 (class 2606 OID 33302)
-- Name: support_time_entries support_time_entries_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_time_entries
    ADD CONSTRAINT support_time_entries_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.support_cases(id);


--
-- TOC entry 5115 (class 2606 OID 33307)
-- Name: support_time_entries support_time_entries_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_time_entries
    ADD CONSTRAINT support_time_entries_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5133 (class 2606 OID 33424)
-- Name: support_waiting_message_events support_waiting_message_events_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_events
    ADD CONSTRAINT support_waiting_message_events_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.support_waiting_messages(id) ON DELETE CASCADE;


--
-- TOC entry 5134 (class 2606 OID 33450)
-- Name: support_waiting_message_helpers support_waiting_message_helpers_added_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_helpers
    ADD CONSTRAINT support_waiting_message_helpers_added_by_fkey FOREIGN KEY (added_by) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5135 (class 2606 OID 33440)
-- Name: support_waiting_message_helpers support_waiting_message_helpers_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_helpers
    ADD CONSTRAINT support_waiting_message_helpers_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.support_waiting_messages(id) ON DELETE CASCADE;


--
-- TOC entry 5136 (class 2606 OID 33445)
-- Name: support_waiting_message_helpers support_waiting_message_helpers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_helpers
    ADD CONSTRAINT support_waiting_message_helpers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5116 (class 2606 OID 33312)
-- Name: support_waiting_message_replies support_waiting_message_replies_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_replies
    ADD CONSTRAINT support_waiting_message_replies_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.support_waiting_messages(id) ON DELETE CASCADE;


--
-- TOC entry 5117 (class 2606 OID 33406)
-- Name: support_waiting_message_replies support_waiting_message_replies_reply_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_replies
    ADD CONSTRAINT support_waiting_message_replies_reply_to_id_fkey FOREIGN KEY (reply_to_id) REFERENCES public.support_waiting_message_replies(id) ON DELETE SET NULL;


--
-- TOC entry 5118 (class 2606 OID 33317)
-- Name: support_waiting_message_views support_waiting_message_views_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_views
    ADD CONSTRAINT support_waiting_message_views_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.support_waiting_messages(id) ON DELETE CASCADE;


--
-- TOC entry 5119 (class 2606 OID 33322)
-- Name: support_waiting_message_views support_waiting_message_views_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_message_views
    ADD CONSTRAINT support_waiting_message_views_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5120 (class 2606 OID 33327)
-- Name: support_waiting_messages support_waiting_messages_escalated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_messages
    ADD CONSTRAINT support_waiting_messages_escalated_by_fkey FOREIGN KEY (escalated_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5121 (class 2606 OID 33332)
-- Name: support_waiting_messages support_waiting_messages_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.support_waiting_messages
    ADD CONSTRAINT support_waiting_messages_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5160 (class 2606 OID 44717)
-- Name: tasks tasks_assignee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_assignee_id_fkey FOREIGN KEY (assignee_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5161 (class 2606 OID 44712)
-- Name: tasks tasks_parent_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_parent_task_id_fkey FOREIGN KEY (parent_task_id) REFERENCES public.tasks(id);


--
-- TOC entry 5162 (class 2606 OID 44707)
-- Name: tasks tasks_phase_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_phase_id_fkey FOREIGN KEY (phase_id) REFERENCES public.phases(id);


--
-- TOC entry 5163 (class 2606 OID 44702)
-- Name: tasks tasks_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- TOC entry 5122 (class 2606 OID 33337)
-- Name: user_organizations user_organizations_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_organizations
    ADD CONSTRAINT user_organizations_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- TOC entry 5123 (class 2606 OID 33342)
-- Name: user_organizations user_organizations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_organizations
    ADD CONSTRAINT user_organizations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5230 (class 2606 OID 87129)
-- Name: user_permissions user_permissions_granted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_granted_by_fkey FOREIGN KEY (granted_by) REFERENCES public.auth_users(id) ON DELETE SET NULL;


--
-- TOC entry 5231 (class 2606 OID 87124)
-- Name: user_permissions user_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id) ON DELETE CASCADE;


--
-- TOC entry 5232 (class 2606 OID 87119)
-- Name: user_permissions user_permissions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5124 (class 2606 OID 33347)
-- Name: user_profiles user_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id) ON DELETE CASCADE;


--
-- TOC entry 5125 (class 2606 OID 33352)
-- Name: user_roles user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- TOC entry 5126 (class 2606 OID 33357)
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5127 (class 2606 OID 33362)
-- Name: verification_codes verification_codes_auth_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.verification_codes
    ADD CONSTRAINT verification_codes_auth_user_id_fkey FOREIGN KEY (auth_user_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5216 (class 2606 OID 45254)
-- Name: wo_operations wo_operations_assignee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.wo_operations
    ADD CONSTRAINT wo_operations_assignee_id_fkey FOREIGN KEY (assignee_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5217 (class 2606 OID 45249)
-- Name: wo_operations wo_operations_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.wo_operations
    ADD CONSTRAINT wo_operations_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.manufacturing_work_orders(id) ON DELETE CASCADE;


--
-- TOC entry 5128 (class 2606 OID 33367)
-- Name: work_order_comments work_order_comments_author_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.work_order_comments
    ADD CONSTRAINT work_order_comments_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.auth_users(id);


--
-- TOC entry 5129 (class 2606 OID 33372)
-- Name: work_order_comments work_order_comments_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.work_order_comments
    ADD CONSTRAINT work_order_comments_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE;


--
-- TOC entry 5130 (class 2606 OID 33377)
-- Name: work_orders work_orders_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.auth_users(id);


--
-- TOC entry 5131 (class 2606 OID 33382)
-- Name: work_orders work_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_users(id);


--
-- TOC entry 5132 (class 2606 OID 33387)
-- Name: work_orders work_orders_product_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_product_item_id_fkey FOREIGN KEY (product_item_id) REFERENCES public.product_items(id);


--
-- TOC entry 5388 (class 0 OID 0)
-- Dependencies: 8
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: admin
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;


-- Completed on 2026-11-10 07:07:51 UTC

--
-- PostgreSQL database dump complete
--

\unrestrict O6dD4haqu3c6AWhBoOll6pLaTTcNL3beqez8vKmIo8y2WrGCktnuDfPokhuPow4

