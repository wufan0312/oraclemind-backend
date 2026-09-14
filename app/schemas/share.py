"""分享服务 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShareCreate(BaseModel):
    """保存/更新分享请求体（字段命名与前端一致：camelCase）。

    - module：模块标识（tarot / bugua / dream），与 (user_id) 构成唯一键
    - title：分享标题/关键词
    - shareText：分享文案
    - imageUrl / imagePrompt：CogView 生成的配图 URL 与提示词（可为空）
    """

    module: str = Field(..., max_length=32, description="模块标识：tarot / bugua / dream")
    title: str = Field(default="", max_length=128, description="分享标题/关键词")
    shareText: str = Field(default="", max_length=4096, description="分享文案")
    imageUrl: str | None = Field(default=None, max_length=1024, description="配图URL（可为空）")
    imagePrompt: str | None = Field(default=None, max_length=1024, description="配图提示词（可为空）")


class ShareOut(ShareCreate):
    """分享记录完整详情。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    userId: int
    created_at: datetime
    updated_at: datetime
