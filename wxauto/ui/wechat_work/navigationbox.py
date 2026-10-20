#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =========================================================
# @file        : navigationbox.py
# @author      : dana
# @contact     : dana2777@163.com
# @created_at  : 2026/10/13 11:49
# @description : 侧边菜单
# =========================================================
from __future__ import annotations

import random
import re
import time
from typing import Optional

from wxauto.param import (
    WxParam,
)
from wxauto.utils import get_active_window, print_control_tree, time_it
from wxauto.utils.tool_md5 import compute_md5
from wxauto.languages import *
from wxauto.uia import Control, uiautomation as uia
from loguru import logger


class NavigationBox:
    def __init__(self, control, parent):
        self.control: Control = control
        self.root = parent.root
        self.parent = parent
        self.top_control = control.GetTopLevelControl()
        self._my_icon = None  # 我的信息
        self._chat_icon = None  # 消息菜单栏
        self._tab_single_chat_icon = None  # 分组>单聊
        self._tab_external_chat_icon = None  # 分组>外部聊天

        self._nick_name = None
        self._real_name = None
        self._company = None
        self._verified = None

        self.init()

    @property
    def user_id(self):
        text = self.nick_name
        if not text:
            return ""
        if real_name := self.real_name:
            text = f"{text}({real_name})"
        if company := self.company:
            text = f"{text};{company}"
        return compute_md5(text)

    @property
    def nick_name(self) -> str:
        """
        别名
        Returns:

        """
        if self._nick_name:
            return self._nick_name
        self._get_user_info()
        return self._nick_name or ""

    @property
    def real_name(self) -> str:
        """
        姓名
        Returns:

        """
        if self._real_name is not None:
            return self._real_name
        self._get_user_info()
        return self._real_name or ""

    @property
    def company(self) -> str:
        """
        公司
        Returns:

        """
        if self._company is not None:
            return self._company
        self._get_user_info()
        return self._company or ""

    @property
    def verified(self) -> bool:
        """
        是否认证
        Returns:

        """
        if self._verified is not None:
            return self._verified
        self._get_user_info()
        return self._verified or False

    @property
    def my_icon(self) -> Optional[Control]:
        """我的信息"""
        if self._my_icon and self._my_icon.Exists(0):
            return self._my_icon
        if (control := self.control) and control.Exists(0) and (
                control := control.ButtonControl(Name=self._lang('我的信息'))) and control.Exists(0):
            self._my_icon = control
        return self._my_icon if self._my_icon and self._my_icon.Exists(0) else None

    @property
    def chat_icon(self) -> Optional[Control]:
        """导航栏>消息"""
        if self._chat_icon and self._chat_icon.Exists(0):
            return self._chat_icon
        if (control := self.control) and control.Exists(0) and (
                control := control.ButtonControl(Name=self._lang('消息'))) and control.Exists(0):
            self._chat_icon = control
        return self._chat_icon if self._chat_icon and self._chat_icon.Exists(0) else None

    @property
    def tab_single_chat_icon(self) -> Optional[Control]:
        """导航栏>分组>单聊"""
        if self._tab_single_chat_icon and self._tab_single_chat_icon.Exists(0):
            return self._tab_single_chat_icon
        if (control := self.control) and control.Exists(0) and (
                control := control.ButtonControl(Name=self._lang('单聊'))) and control.Exists(0):
            self._tab_single_chat_icon = control
        return self._tab_single_chat_icon if self._tab_single_chat_icon and self._tab_single_chat_icon.Exists(
            0) else None

    @property
    def tab_external_chat_icon(self) -> Optional[Control]:
        """导航栏>分组>外部聊天"""
        if self._tab_external_chat_icon and self._tab_external_chat_icon.Exists(0):
            return self._tab_external_chat_icon
        if (control := self.control) and control.Exists(0) and (
                control := control.ButtonControl(Name=self._lang('外部聊天'))) and control.Exists(0):
            self._tab_external_chat_icon = control
        return self._tab_external_chat_icon if (self._tab_external_chat_icon
                                                and self._tab_external_chat_icon.Exists(0)) else None

    @time_it
    def _get_user_info(self):
        """
        从我的信息中提取 基础信息
        Returns: 别名、姓名、公司、是否已认证
        """
        self.parent._show()
        # 单击我的信息
        self.my_icon.Click()
        hwnd, window_title, class_name = get_active_window()
        logger.debug(f"""获取到的窗口信息({hwnd, class_name, window_title})""")
        if class_name == "WXworkWindow":
            control = uia.ControlFromHandle(hwnd)
            ele = control.GroupControl().ButtonControl(searchDepth=8)
            if ele and ele.Exists():
                con_name = ele.Name or ""
                pattern = re.compile(
                    r"我的信息\s*"
                    r"(?P<alias>[^()]*?)"
                    r"(?:\((?P<name>[^)]*)\))?"
                    r"(?:\s+(?P<company>.*?))?"
                    r"(?:\s+(?P<verified>已认证))?"
                    r"\s*$"
                )
                match = pattern.search(con_name)

                if match:
                    alias = match.group("alias").strip()  # 别名
                    name = (match.group("name") or "").strip()  # 姓名
                    company = (match.group("company") or "").strip()  # 公司
                    verified = bool(match.group("verified"))  # 是否认证
                else:
                    alias = name = company = verified = None

                if alias:
                    self._nick_name = alias

                if name:
                    self._real_name = name
                else:
                    self._real_name = ""

                if company:
                    self._company = company
                else:
                    self._company = ""

                if verified:
                    self._verified = verified
                else:
                    self._verified = False

                return alias, name, company, verified
        return None, None, None, None

    def _lang(self, text: str) -> str:
        return WECHAT_NAVIGATION_BOX.get(text, {WxParam.LANGUAGE: text}).get(WxParam.LANGUAGE)

    def init(self):
        # self.my_icon = self.control.ButtonControl(Name=self._lang('我的信息'))
        # self.chat_icon = self.control.ButtonControl(Name=self._lang('消息'))
        # # 单聊
        # self.tab_single_chat_icon = self.control.ButtonControl(Name="单聊")
        # self.tab_external_chat_icon = self.control.ButtonControl(Name="外部聊天")
        pass

    def user_info(self):
        """
        用户信息
        Returns:
        """
        return {
            "user_id": self.user_id,
            "nick_name": self.nick_name,
            "real_name": self.real_name,
            "company": self.company,
            "verified": self.verified
        }

    def get_description(self):
        pattern = self.control.GetLegacyIAccessiblePattern()
        description = pattern.Description if pattern else None
        logger.debug(f"当前导航栏>{description}")
        return description

    def get_current_page(self):
        description = self.get_description()
        if not description:
            return ""

        description = description.split(" ")[0] if description else None
        return description

    def switch_to_tab_chat_page(self, name="所有"):
        """
        切换聊天分组
        Args:
            name: 分组名字 所有:所有聊天
        Returns:
        """
        ele = None
        if name == "所有":
            ele = self.chat_icon
        elif name == "单聊":
            ele = self.tab_single_chat_icon
        elif name == "外部聊天":
            ele = self.tab_external_chat_icon
        else:
            logger.warning(f"""未知聊天分组:{name=},无法切换""")

        if not ele:
            return False
        for i in range(3):
            current_page = self.get_current_page()
            if current_page == name:
                return True
            # 切换聊天
            self.parent._show()  # 激活窗口
            ele.Click()
            time.sleep(random.uniform(0.5, 1.5))
            continue
        logger.warning(f"切换聊天分组失败:{name=}")
        return True

    # 是否有新消息
    def has_new_message(self):
        description = self.get_description()
        if not description:
            return 0

        msg_count = re.findall(r'\s?(\d*)条未读', description)
        logger.debug(f"未读消息数:{msg_count}")
        msg_count = msg_count[0] if msg_count else 0
        if msg_count:
            return int(msg_count)
        else:
            return 0
