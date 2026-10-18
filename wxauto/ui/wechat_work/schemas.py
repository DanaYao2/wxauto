#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =========================================================
# @file        : schemas.py
# @author      : dana
# @contact     : dana2777@163.com
# @created_at  : 2026/10/15 18:50
# @description :
# =========================================================
import datetime
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, PlainSerializer, Field, computed_field


def to_camel(string: str) -> str:
    parts = string.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",  # 忽略未知字段
        str_strip_whitespace=True
    )


DateTimeField = Annotated[
    Optional[datetime.datetime],
    PlainSerializer(
        lambda value: value.strftime("%Y-%m-%d %H:%M:%S") if value else "",
        return_type=str,
        when_used="json",
    ),
]


class WechatWorkMessage(BaseSchema):
    msg_id: str = Field(..., title="消息id")
    send_name: str = Field(..., title="发送人")
    session_name: str = Field(..., title="会话")
    is_system: bool = Field(False, title="是否是系统消息")
    msg_time: DateTimeField = Field(None, title="消息时间")
    content: str = Field("", title="消息内容")

    @computed_field
    @property
    def is_self(self) -> bool:
        """是否是自己发送的消息"""
        if self.is_system:  # 系统消息
            return False

        if self.send_name != self.session_name:
            return True
        return False

    @property
    def msg_timestamp(self) -> Optional[int]:
        if self.msg_time:
            return int(self.msg_time.timestamp())
        return None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WechatWorkMessage):
            return NotImplemented
        return self.msg_id == other.msg_id
