"""境内地区下单拦截（合规：国内不提供付费 / 供养）。

信号来源（任一为 CN 即拒绝）：
- ``X-Client-Region``：前端 middleware 把 Vercel 边缘注入的
  ``x-vercel-ip-country`` 写入 ``om_region`` Cookie，前端 api.ts 在
  POST /donations、/premium/orders 时带上此头（来自可信前端）。
- ``x-vercel-ip-country``：若后端也部署在 Vercel 边缘，该头由平台自动注入，
  无需前端转发，作为第二重校验。

注意：VPN 可绕过该头，因此它只是「把境内默认态做合规」的兜底，
真正的合规姿态由前端隐藏付费入口 + 不主动在境内推广共同构成。
"""
from fastapi import HTTPException, Request, status


def reject_if_cn(request: Request) -> None:
    """下单前调用：境内来源直接拒绝（403）。"""
    region = (
        request.headers.get("x-client-region")
        or request.headers.get("x-vercel-ip-country")
        or ""
    ).upper()
    if region == "CN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该地区不支持付费购买（region blocked）",
        )
