def get_rpm_limit_scan_prefix():
    return "limit:rpm:*"


def get_tpm_limit_scan_prefix():
    return "limit:tpm:*"


def get_rpm_limit_key(user_id, model_name):
    """
    获取请求限流key
    """
    return f"limit:rpm:{user_id}:{model_name}"


def get_rpm_limit_key_by_level_and_model(level, model_name):
    """
    """
    return f"limit:rpm:{level}:{model_name}"


def get_rmp_limit_buckets_key(user_id, model_name):
    """
    获取请求限流key
    """
    return f"limit:buckets:rpm:{user_id}:{model_name}"


def get_tpm_limit_key(user_id, model_name):
    """
    获取token限流key
    """
    return f"limit:tpm:{user_id}_{model_name}"


def get_tpm_limit_key_by_level_and_model(level, model_name):
    """
    """
    return f"limit:tpm:{level}:{model_name}"


def get_tpm_limit_buckets_key(user_id, model_name):
    """
    获取token限流key
    """
    return f"limit:buckets:tpm:{user_id}:{model_name}"


def get_user_level_key(user_id):
    return f"limit:level:{user_id}"
