"""共享输入校验工具（S9 visitorId 白名单等）。

visitorId 是匿名身份的所有权凭证，其取值直接决定报告/上云数据的隔离边界，
因此必须严格校验格式与长度，防止异常值（超长、含特殊字符）绕过身份隔离或造成存储异常。
"""

import re

# 字符集白名单：前端生成的 visitorId 为 UUID v4（8-4-4-4-12 十六进制 + 连字符）
# 或降级串 v-{time36}-{rand36}，二者均落在 [A-Za-z0-9_-] 内；
# 长度上限 64 与前端生成 / DB 列宽一致。
VISITOR_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_valid_visitor_id(vid: str | None) -> bool:
    """判断 visitorId 是否符合白名单（非空 + 字符集/长度合规）。"""
    return bool(vid) and bool(VISITOR_ID_RE.match(vid))
