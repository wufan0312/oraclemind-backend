"""进阶内容付费 Pydantic 模型（付费墙：塔罗深度 / 占星完整 / 全站通卡）。

安全要点：
- **服务端定价**：商品目录 PREMIUM_CATALOG 是金额的唯一真源，客户端只传 itemId，
  不传金额，杜绝「改包把 ¥99 改成 ¥0.01」；
- 订单状态只按 out_trade_no 归属校验后返回，不匹配一律 404（不泄露订单存在性）；
- 权益（entitlements）只认 status=paid 的订单，self_claimed 不参与判定。
"""

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validators import is_valid_visitor_id


@dataclass(frozen=True)
class PremiumItem:
    """商品定义（服务端权威定价）。"""

    item_id: str
    name: str
    icon: str
    price_fen: int
    tagline: str
    perks: list[str] = field(default_factory=list)
    # 生效范围：single=绑定单次对象（ref_type/ref_id 必填），site=全站生效
    scope: str = "site"
    # 全站通卡：解锁它等于解锁全部商品
    covers_all: bool = False


# 商品目录 —— 与前端 src/lib/premium.ts 的 PREMIUM_PLANS 保持一致（价格单位：分）
PREMIUM_CATALOG: dict[str, PremiumItem] = {
    "tarot_deep": PremiumItem(
        item_id="tarot_deep",
        name="塔罗深度解读",
        icon="🎴",
        price_fen=3900,
        tagline="单次解锁 · 针对这一局牌面",
        perks=[
            "逐牌长文解读（正逆位 / 牌阵位 / 元素互动）",
            "情境化行动建议与时间点提示",
            "可导出 PDF 留存",
        ],
        scope="single",
    ),
    "astro_full": PremiumItem(
        item_id="astro_full",
        name="占星完整解读",
        icon="🌟",
        price_fen=5900,
        tagline="本命盘 + 年度返照完整报告",
        perks=[
            "本命盘全维度解读（性格 / 事业 / 感情 / 财富）",
            "年度太阳返照主题与月度提示",
            "星盘与报告 PDF 导出",
        ],
        scope="single",
    ),
    "all_access": PremiumItem(
        item_id="all_access",
        name="全站通卡",
        icon="👑",
        price_fen=9900,
        tagline="一次解锁 · 全模块进阶内容",
        perks=[
            "含塔罗深度解读 + 占星完整解读",
            "全模块进阶内容无限次查看",
            "优先体验新功能",
        ],
        scope="site",
        covers_all=True,
    ),
    # ===== 会员类（一次性解锁，非订阅；平台全功能免费，会员仅提供更深陪伴） =====
    "xinzhai_member": PremiumItem(
        item_id="xinzhai_member",
        name="心斋会员",
        icon="🪷",
        price_fen=1900,
        tagline="把心斋的安宁，带在身边",
        perks=[
            "专属心镜 · 每月一次的深度照见",
            "疗愈心斋全模块进阶内容",
            "优先体验冥想 / 共修新功能",
        ],
        scope="site",
    ),
    "dream_member": PremiumItem(
        item_id="dream_member",
        name="解梦会员",
        icon="🌙",
        price_fen=1900,
        tagline="更深的梦境照见 · 互助同梦",
        perks=[
            "解梦全视角深度档案（荣格 / 弗洛伊德 / 认知）",
            "梦境相似匹配与互助社区",
            "优先体验专家人工解读",
        ],
        scope="site",
    ),
    # ===== 合规付费新方向（2026-09-18）：脱离生辰命盘的自评测评，不在 PAUSED_ITEMS =====
    "resilience_assess": PremiumItem(
        item_id="resilience_assess",
        name="复原力测评报告",
        icon="🌱",
        price_fen=990,
        tagline="单份 · 基于你此刻的自评（与生辰命盘无关）",
        perks=[
            "四维自我觉察报告（事业 / 关系 / 家庭 / 自我）",
            "压力—资源平衡快照 + 本周可做的三个微行动",
            "不给诊断、不算吉凶；报告可导出留存",
        ],
        scope="site",
    ),
}

# 免费已包含的能力（付费墙必须写清楚，避免用户误以为基础功能要钱）
FREE_PERKS: list[str] = [
    "全部基础占卜与 AI 解读（卜卦 / 塔罗 / 星座 / 数字 / 解梦 / 疗愈）",
    "完整牌阵、每日塔罗、塔罗日记与牌义学习",
    "梦境日记、清醒梦引导、修行成长与签到",
    "报告保存、导出与跨设备同步",
]


def get_item(item_id: str) -> PremiumItem | None:
    """按商品ID取目录项（未知 ID 返回 None，由调用方转 400）。"""
    return PREMIUM_CATALOG.get((item_id or "").strip())


class PremiumPlanOut(BaseModel):
    """商品（前端付费墙卡片数据源，可由后端驱动）。"""

    itemId: str
    name: str
    icon: str
    priceFen: int
    priceYuan: str
    tagline: str
    perks: list[str] = Field(default_factory=list)
    scope: str = "site"


class PremiumPlansOut(BaseModel):
    """商品列表 + 免费权益 + 当前渠道（stub / wechat）。"""

    plans: list[PremiumPlanOut] = Field(default_factory=list)
    freePerks: list[str] = Field(default_factory=list)
    channel: str = "stub"


class PremiumOrderCreate(BaseModel):
    """创建付费订单 —— 只传商品ID，金额由服务端按目录定价。"""

    itemId: str = Field(..., max_length=32, description="商品ID：tarot_deep / astro_full / all_access")
    visitorId: str | None = Field(default=None, max_length=64, description="访客ID（未登录时必填）")
    refType: str | None = Field(default=None, max_length=32, description="关联对象类型：tarot_spread / report / horoscope")
    refId: str | None = Field(default=None, max_length=64, description="关联对象ID（单次解锁类商品绑定这一局）")

    @field_validator("visitorId")
    @classmethod
    def _check_visitor_id(cls, v: str | None) -> str | None:
        # S9 加固：匿名身份凭证格式校验，防止异常值绕过隔离。
        # 登录用户可省略（落空串），空串视为「无访客」放行；仅拒绝非空的非法值。
        if v is not None and v != "" and not is_valid_visitor_id(v):
            raise ValueError("visitorId 格式非法")
        return v


class PremiumOrderOut(BaseModel):
    """订单详情（含支付引导）。"""

    model_config = ConfigDict(from_attributes=True)

    outTradeNo: str
    itemId: str
    itemName: str = ""
    amountFen: int
    amountYuan: str
    channel: str
    status: str
    payUrl: str | None = None
    qrText: str = ""
    checkCode: str = ""
    refType: str = ""
    refId: str = ""
    selfClaimed: bool = False
    createdAt: datetime
    expireAt: datetime
    paidAt: datetime | None = None
    message: str = ""


class PremiumNotify(BaseModel):
    """支付渠道回调（幂等：同一 out_trade_no 重复回调只生效一次）。"""

    outTradeNo: str = Field(..., max_length=64, description="商户订单号")
    transactionId: str | None = Field(default=None, max_length=128, description="渠道交易号")
    success: bool = Field(..., description="支付是否成功")
    sign: str | None = Field(default=None, max_length=256, description="回调签名（stub 渠道可为空）")

    @field_validator("outTradeNo")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()


class PremiumEntitlementItem(BaseModel):
    """单个商品的解锁状态。"""

    itemId: str
    unlocked: bool
    orderNo: str = ""
    channel: str = ""
    paidAt: datetime | None = None
    # 生效范围（单次解锁类需前端按 ref 匹配）
    refType: str = ""
    refId: str = ""


class PremiumEntitlementsOut(BaseModel):
    """当前用户/访客的付费权益集合（服务端发权益的真源）。"""

    visitorId: str = ""
    userId: int | None = None
    unlocked: list[str] = Field(default_factory=list, description="已解锁商品ID列表（含通卡折算）")
    items: list[PremiumEntitlementItem] = Field(default_factory=list)
    channel: str = "stub"
