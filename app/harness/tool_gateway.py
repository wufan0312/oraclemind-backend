"""
玄镜 backend · Harness tool-gateway
落点：oraclemind-backend/app/harness/tool_gateway.py

职责：
- 工具 allowlist 注册（只有注册过的工具可被调用）
- 调用前对入参做 JSON Schema 强校验（jsonschema 可用时；缺失则降级为仅 allowlist + 危险拦截）
- 危险操作拦截（文件写 / 网络出口 / eval-exec / pickle 等）
- 每次调用写审计日志
- 高风险工具（卜卦 / 付费 / 外发）需经 approval gate（Human-in-the-loop，P1 接入）

与 ai-py 的 BoundaryValidator 互补：
- BoundaryValidator 校验「模型产出」；ToolGateway 校验「模型要调用的工具入参」+ 网关级安全兜底。

注意：backend 当前依赖不含 jsonschema。本模块做成「可选依赖」——若运行时
import jsonschema 成功则启用入参强校验，否则仅做 allowlist + 危险拦截 + 审批 + 审计
（仍可挡住未注册工具与危险调用）。生产建议在 requirements.txt 增加 `jsonschema>=4.0`
以启用完整的入参契约校验。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set

try:  # 可选依赖：生产建议在 requirements.txt 加 jsonschema 启用参数强校验
    from jsonschema import Draft7Validator

    _HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover - 依赖缺失时优雅降级
    Draft7Validator = None  # type: ignore[assignment]
    _HAS_JSONSCHEMA = False


# 危险信号兜底（工具实现层也应防御，这里做网关级拦截）
_DANGEROUS_PATTERNS = [
    re.compile(r"\b(open|write|os\.remove|shutil)\b", re.I),
    re.compile(r"\b(requests\.(get|post)|urllib|httpx)\b", re.I),
    re.compile(r"\b(eval|exec|subprocess|os\.system|__import__)\b", re.I),
    re.compile(r"\b(pickle|marshal|yaml\.load)\b", re.I),
]
_DANGEROUS_TAGS = {"__dangerous__", "shell", "fs_write", "network_egress"}


@dataclass
class ToolSpec:
    name: str
    handler: Callable[..., Any]
    param_schema: Optional[dict] = None
    risk: str = "low"  # low | medium | high
    requires_approval: bool = False  # 高风险需人工审批（P1）
    tags: Set[str] = field(default_factory=set)


class ToolGatewayError(Exception):
    pass


class ToolGateway:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self._validators: Dict[str, Any] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ToolGatewayError(f"工具已注册: {spec.name}")
        self._tools[spec.name] = spec
        if spec.param_schema and _HAS_JSONSCHEMA:
            self._validators[spec.name] = Draft7Validator(spec.param_schema)

    def list_tools(self):
        return [
            {"name": t.name, "risk": t.risk, "requires_approval": t.requires_approval}
            for t in self._tools.values()
        ]

    def _guard(self, spec: ToolSpec) -> None:
        for tag in spec.tags:
            if tag in _DANGEROUS_TAGS:
                raise ToolGatewayError(f"工具 {spec.name} 命中危险标签 {tag}，已拦截")
        try:
            src = f"{spec.handler.__module__}.{spec.handler.__qualname__}"
        except Exception:
            src = ""
        for pat in _DANGEROUS_PATTERNS:
            if pat.search(src):
                raise ToolGatewayError(f"工具 {spec.name} 实现疑似危险调用，已拦截")

    def dispatch(self, name: str, args: dict, *, approved: bool = False) -> Any:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolGatewayError(f"未知/未授权工具: {name}")
        if not isinstance(args, dict):
            raise ToolGatewayError(f"工具 {name} 入参必须是 JSON 对象")

        # 1) 参数强校验（jsonschema 可用才做）
        validator = self._validators.get(name)
        if validator is not None:
            errors = sorted(
                validator.iter_errors(args),
                key=lambda e: "/".join(map(str, e.absolute_path)),
            )
            if errors:
                detail = "; ".join(
                    f"{'/'.join(map(str, e.absolute_path)) or 'root'}: {e.message}" for e in errors
                )
                raise ToolGatewayError(f"工具 {name} 入参校验失败: {detail}")

        # 2) 危险拦截 / 审批
        if spec.requires_approval and not approved:
            raise ToolGatewayError(f"工具 {spec.name} 需要人工审批，当前未通过 approval gate")
        self._guard(spec)

        # 3) 审计日志（TODO: 接 Redis/PG 审计表，Observability P0-2）
        self._audit(name, args, spec.risk)

        # 4) 执行
        return spec.handler(**args)

    def _audit(self, name: str, args: dict, risk: str) -> None:
        print(f"[tool-gateway][audit] name={name} risk={risk} args={args!r}")
