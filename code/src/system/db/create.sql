-- CREATE DATABASE imaas WITH OWNER = aicp ENCODING = 'UTF8';

create table public.model
(
    id          varchar(255) not null primary key,
    name        varchar(255) not null,
    icon        text,
    brief       text,
    developer   varchar(255) not null,
    create_time timestamp default CURRENT_TIMESTAMP,
    update_time timestamp default CURRENT_TIMESTAMP,
    creator     varchar(255),
    status      varchar(255) not null
);
alter table public.model owner to aicp;

CREATE TYPE status_enum AS ENUM ('active', 'inactive', 'delete');

create table public.channel
(
    id                   varchar                             not null constraint channel_pk primary key,
    channel_type_id      varchar                             not null,
    name                 varchar                             not null,
    model_redirection    varchar,
    inference_secret_key varchar                             not null,
    inference_service    varchar                             not null,
    update_time          timestamp default CURRENT_TIMESTAMP not null,
    create_time          timestamp default CURRENT_TIMESTAMP not null,
    status               status_enum                         not null
);
alter table public.channel owner to aicp;

create table public.channel_type
(
    id   varchar not null constraint channel_type_pk primary key,
    name varchar not null
);

alter table public.channel_type owner to aicp;

create table public.channel_to_model
(
    channel_id varchar not null references public.channel on delete cascade,
    model_id   varchar not null references public.model on delete cascade
);
alter table public.channel_to_model owner to aicp;

create table public.apikey
(
    id             varchar                             not null constraint apikey_pk primary key,
    creator        varchar                             not null,
    name           varchar,
    ip_restriction varchar,
    update_time    timestamp default CURRENT_TIMESTAMP not null,
    create_time    timestamp default CURRENT_TIMESTAMP not null,
    last_time      timestamp default CURRENT_TIMESTAMP,
    status         status_enum                         not null
);
alter table public.apikey owner to aicp;

create table public.model_param
(
    id        SERIAL primary key,
    key       varchar   not null,
    value     varchar   not null,
    min       varchar,
    max       varchar,
    tag_id    varchar(255) not null,
    model_id  varchar(255)
);
alter table public.model_param owner to aicp;

create table public.files (
    id varchar(255) not null constraint files_pkey1 primary key,
    filename varchar(255) not null,
    purpose varchar(50) not null,
    bytes bigint not null,
    creator_id varchar(255) not null,
    created_at timestamp default CURRENT_TIMESTAMP,
    updated_at timestamp default CURRENT_TIMESTAMP,
    status varchar(20) default 'active'::character varying not null
);

alter table public.files owner to aicp;
create index idx_files_user_id on public.files (creator_id);
create index idx_files_created_at on public.files (created_at);
create index idx_files_status on public.files (status);

INSERT INTO public.model_param (key, value, min, max, tag_id) VALUES ('max_tokens', '4096', '1', '8192','txt2txt');
INSERT INTO public.model_param (key, value, min, max, tag_id) VALUES ('temperature', '0.7', '0', '2','txt2txt');
INSERT INTO public.model_param (key, value, min, max, tag_id) VALUES ('top_p', '0.7', '0.1', '1','txt2txt');
INSERT INTO public.model_param (key, value, min, max, tag_id) VALUES ('top_k', '50', '0', '100','txt2txt');
INSERT INTO public.model_param (key, value, min, max, tag_id) VALUES ('frequency_penalty', '0.0', '-2', '2','txt2txt');

INSERT INTO public.model_param (key, value, min, max, tag_id, model_id) VALUES ('top_p', '0.7', '0.1', '1','txt2txt', 'md-dsr10000');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id) VALUES ('top_k', '50', '0', '100','txt2txt', 'md-dsr10000');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id) VALUES ('frequency_penalty', '0.0', '-2', '2','txt2txt','md-dsr10000');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id) VALUES ('temperature', '0.6', '0', '2','txt2txt','md-dsr10000');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id) VALUES ('max_tokens', '8192', '1', '16384','txt2txt', 'md-dsr10000');

INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('max_tokens', '1024', '1', '8192','txt2txt', 'md-dsv30000');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('temperature', '0.7', '0', '2','txt2txt', 'md-dsv30000');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('top_p', '0.7', '0.1', '1','txt2txt', 'md-dsv30000');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('top_k', '50', '0', '100','txt2txt', 'md-dsv30000');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('frequency_penalty', '0.0', '-2', '2','txt2txt', 'md-dsv30000');

INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('max_tokens', '1024', '1', '4000','txt2txt', 'md-qw2x05bi');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('temperature', '1.0', '0', '2','txt2txt', 'md-qw2x05bi');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('top_p', '0.7', '0.1', '1','txt2txt', 'md-qw2x05bi');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('top_k', '50', '0', '100','txt2txt', 'md-qw2x05bi');
INSERT INTO public.model_param (key, value, min, max, tag_id, model_id)  VALUES ('frequency_penalty', '0.0', '-2', '2','txt2txt', 'md-qw2x05bi');

