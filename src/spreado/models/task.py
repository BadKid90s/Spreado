#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一任务模型
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class Task:
    """
    统一发布任务模型

    支持视频和图文两种内容类型，作为发布器的统一输入。
    """

    # --- 基本信息 ---
    type: str = "video"  # "video" 或 "image_text"
    platform: str = ""  # 目标平台名 (如 "douyin", "xiaohongshu")
    title: str = ""  # 标题
    content: str = ""  # 描述/正文
    tags: List[str] = field(default_factory=list)  # 标签列表

    # --- 素材文件 ---
    media_files: List[str] = field(default_factory=list)  # 素材文件路径列表 (视频单个, 图文多个)
    thumbnail_path: Optional[str] = None  # 封面图路径

    # --- 发布设置 ---
    publish_date: Optional[datetime] = None  # 定时发布时间, None 表示立即发布

    # --- 扩展字段 ---
    extra: Dict[str, Any] = field(default_factory=dict)  # 平台特有参数 (如 location, product_link)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        # datetime 需要特殊处理
        if self.publish_date:
            data["publish_date"] = self.publish_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """从字典反序列化"""
        # 处理 datetime 字段
        if "publish_date" in data and isinstance(data["publish_date"], str):
            data["publish_date"] = datetime.fromisoformat(data["publish_date"])
        return cls(**data)

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Task":
        """从 JSON 字符串反序列化"""
        import json
        data = json.loads(json_str)
        return cls.from_dict(data)
