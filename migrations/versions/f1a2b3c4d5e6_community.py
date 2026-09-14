"""community: 社区域（圈子/帖子/评论/点赞/公告）

Revision ID: f1a2b3c4d5e6
Revises: e5f3b1a7c904
Create Date: 2026-09-13 14:00:00.000000

综合社区页面（/community）数据层：
- community_circles：话题圈子
- community_posts：帖子
- community_comments：评论（支持楼中楼）
- community_likes：点赞记录（幂等 toggle）
- community_announcements：官方公告

upgrade 末尾插入种子数据（6 圈子 + 2 公告 + 4 官方示例帖），使首屏非空。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'e5f3b1a7c904'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'community_circles',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('slug', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=32), nullable=False),
        sa.Column('icon', sa.String(length=16), nullable=False),
        sa.Column('description', sa.String(length=128), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_community_circles_slug', 'community_circles', ['slug'])

    op.create_table(
        'community_posts',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('author_name', sa.String(length=64), nullable=False),
        sa.Column('circle_slug', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('images', sa.Text(), nullable=False),
        sa.Column('topic_tags', sa.Text(), nullable=False),
        sa.Column('like_count', sa.Integer(), nullable=False),
        sa.Column('comment_count', sa.Integer(), nullable=False),
        sa.Column('view_count', sa.Integer(), nullable=False),
        sa.Column('is_pinned', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_posts_author_id', 'community_posts', ['author_id'])
    op.create_index('ix_community_posts_circle_slug', 'community_posts', ['circle_slug'])
    op.create_index('ix_community_posts_created_at', 'community_posts', ['created_at'])

    op.create_table(
        'community_comments',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('author_name', sa.String(length=64), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('like_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_comments_post_id', 'community_comments', ['post_id'])
    op.create_index('ix_community_comments_parent_id', 'community_comments', ['parent_id'])

    op.create_table(
        'community_likes',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('target_type', sa.String(length=16), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'target_type', 'target_id', name='uq_community_likes_user_target'),
    )
    op.create_index('ix_community_likes_user_id', 'community_likes', ['user_id'])
    op.create_index('ix_community_likes_target_type', 'community_likes', ['target_type'])
    op.create_index('ix_community_likes_target_id', 'community_likes', ['target_id'])

    op.create_table(
        'community_announcements',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('pinned', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_announcements_created_at', 'community_announcements', ['created_at'])

    # ===================== 种子数据 =====================
    bind = op.get_bind()
    # 圈子
    circles = [
        ('bazi', '八字命理', '☯️', '四柱八字 · 五行喜忌 · 运势解读', 1),
        ('tarot', '塔罗牌', '🃏', '牌阵占卜 · 心灵指引 · 每日一抽', 2),
        ('name', '姓名学问', '✍️', '起名测名 · 五行补缺 · 音形义', 3),
        ('healing', '心灵疗愈', '🪷', '情绪疏导 · 冥想修行 · 同修共行', 4),
        ('dream', '梦境解析', '🌙', '周公解梦 · 潜意识 · 寓意启示', 5),
        ('fengshui', '风水堪舆', '🏡', '居家布局 · 择日纳吉 · 气场调和', 6),
    ]
    for slug, name, icon, desc, order in circles:
        bind.execute(
            text(
                "INSERT INTO community_circles (slug, name, icon, description, sort_order, created_at) "
                "VALUES (:slug, :name, :icon, :desc, :order, now())"
            ),
            {"slug": slug, "name": name, "icon": icon, "desc": desc, "order": order},
        )

    # 公告
    announcements = [
        (True, '🪷 玄镜社区正式开张',
         '欢迎来到玄镜同修圈！这里汇聚八字、塔罗、姓名、疗愈、解梦、风水六大圈子。\n'
         '分享你的占卜故事、起名心得与修行感悟，与千万同修共行。发帖与互动需登录后参与。'),
        (False, '📜 社区公约',
         '1）友善交流，尊重不同流派观点；2）禁止迷信诈骗与医疗建议；3）原创内容欢迎分享，转载请注明出处。\n'
         '违规内容将被隐藏，情节严重者封禁账号。'),
    ]
    for pinned, title, content in announcements:
        bind.execute(
            text(
                "INSERT INTO community_announcements (title, content, author_id, pinned, created_at) "
                "VALUES (:title, :content, NULL, :pinned, now())"
            ),
            {"title": title, "content": content, "pinned": pinned},
        )

    # 官方示例帖子（author_id=NULL 表示官方）
    posts = [
        ('bazi', '新手必读 · 如何看懂自己的八字五行',
         '很多同修拿到八字排盘后一头雾水。其实核心就看三件事：\n'
         '①日主强弱——你是金木水火土哪一种，旺还是弱；\n'
         '②五行缺什么、什么过旺；③喜用神选对方向补运。\n'
         '欢迎在评论区贴出你的日主，一起探讨～',
         '["新手","五行","喜用神"]', 36),
        ('tarot', '每日一抽 · 今天你抽到的是「星星」',
         '正位的星星牌，是希望与疗愈的预告。\n'
         '经历过低谷之后，宇宙正在为你重新点亮前路。保持耐心，答案会慢慢浮现。\n'
         '你今天抽到什么牌？来聊聊牌面给你的感觉。',
         '["每日一抽","希望"]', 58),
        ('name', '起名避坑 · 别让生僻字拖累孩子',
         '起名时很多家长偏爱生僻字显得有文化，但实测有两个坑：\n'
         '①生僻字拼音/输入法覆盖率低，孩子从小到大填表、办证、考试都麻烦；\n'
         '②音形义要兼顾，五行补缺不是唯一标准。\n'
         '好名字 = 好听 + 好写 + 有寓意 + 五行调和。',
         '["起名","避坑"]', 27),
        ('healing', '睡前 3 分钟 · 放下一天的情绪',
         '今晚试试：关灯后深呼吸 5 次，把今天最重的一件事「放』在呼气里吐出去。\n'
         '不必解决它，只是先放下。修行不是没有情绪，而是不被情绪卷走。\n'
         '愿你我都被这世界温柔以待。🪷',
         '["冥想","情绪"]', 41),
    ]
    for slug, title, content, tags, likes in posts:
        bind.execute(
            text(
                "INSERT INTO community_posts "
                "(author_id, author_name, circle_slug, title, content, images, topic_tags, "
                " like_count, comment_count, view_count, is_pinned, status, created_at, updated_at) "
                "VALUES (NULL, '玄镜小助手', :slug, :title, :content, '[]', :tags, "
                " :likes, 0, 0, FALSE, 'published', now(), now())"
            ),
            {"slug": slug, "title": title, "content": content, "tags": tags, "likes": likes},
        )


def downgrade() -> None:
    op.drop_table('community_announcements')
    op.drop_table('community_likes')
    op.drop_table('community_comments')
    op.drop_table('community_posts')
    op.drop_table('community_circles')
