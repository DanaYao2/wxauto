#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =========================================================
# @file        : sessionbox.py.py
# @author      : dana
# @contact     : dana2777@163.com
# @created_at  : 2026/10/13 11:47
# @description : 会话相关
# =========================================================
from __future__ import annotations

import random
from datetime import datetime, timedelta
from lib2to3.fixes.fix_input import context

from .component import CMenuWnd

from wxauto.param import (
    WxParam,
    WxResponse,
)
from wxauto.languages import *
from wxauto.utils import SetClipboardText, time_it
from wxauto.logger import wxlog
from wxauto.uia import Control
from wxauto.utils.tools import roll_into_view
from typing import List, Union, Optional
import time
import re


class SessionBox:
    def __init__(self, control, parent):
        self.control: Control = control
        self.root = parent.root
        self.parent = parent
        self.top_control = control.GetTopLevelControl()
        self._search_box: Optional[Control] = None  # 搜索控件
        self._session_list: Optional[Control] = None  # 会话列表控件

        self.init()

    def _lang(self, text: str) -> str:
        return WECHAT_SESSION_BOX.get(text, {WxParam.LANGUAGE: text}).get(WxParam.LANGUAGE)

    def init(self):
        self._search_box = self.control.EditControl(Name=self._lang('搜索'), searchDepth=10)
        self._session_list = self.control.ListControl(Name=self._lang('会话'), searchDepth=7)

    @classmethod
    @time_it
    def get_session_control(cls, control: Optional[Control]) -> Optional[Control]:
        """
        获取会话区域(包含搜索区域)
        Args:
            control: 指定控件
        Returns:
        """
        if control is None or not control.Exists():
            return None
        session_box_control = control.ListControl(Name="会话", searchDepth=15)
        # while session_box_control and session_box_control.Exists(0):
        #     if session_box_control.EditControl(Name="搜索").Exists(0):
        #         break
        #     session_box_control = session_box_control.GetParentControl()
        if session_box_control and session_box_control.Exists(0):
            session_box_control = session_box_control.GetAncestorControl(
                lambda _control, _depth: _control.EditControl(Name="搜索", searchDepth=8).Exists(0))
        return session_box_control if session_box_control and session_box_control.Exists() else None

    @property
    def search_box(self):
        """
        搜索区域
        Returns:

        """
        if self._search_box and self._search_box.Exists(0):
            return self._search_box
        self._search_box = None
        if (
                (control := self.control) and control.Exists(0)
                and (control := control.EditControl(Name=self._lang('搜索'), searchDepth=10)) and control.Exists(0)
        ):
            self._search_box = control
        return self._search_box

    @property
    def session_list(self):
        """
        会话列表区域
        Returns:
        """
        if self._session_list and self._session_list.Exists(0):
            return self._session_list
        self._session_list = None
        if (
                (control := self.control) and control.Exists(0)
                and (control := control.ListControl(Name=self._lang('会话'), searchDepth=7)) and control.Exists(0)
        ):
            self._session_list = control
        return self._session_list

    def get_session(self) -> List[SessionElement]:
        """
        获取会话列表
        Returns:
        """
        if self.session_list and self.session_list.Exists(0):
            session_list = self.session_list.ListItemControl().GetParentControl()
            return [SessionElement(i, self) for i in session_list.GetChildren()]
        else:
            return []

    def roll_up(self, n: int = 5):
        # 向上滚动
        self.control.WheelUp(waitTime=n)

    def roll_down(self, n: int = 5):
        # 向下滚动
        self.control.WheelDown(waitTime=n)

    # 清空搜索内容
    def clear_search_content(self):
        """
        清空搜索内容
        Returns:
        """
        clear_con = self.control.GetParentControl().ButtonControl(Name="清空搜索内容", searchDepth=7)
        if clear_con and clear_con.Exists():
            clear_con.Click()
        return True

    def switch_chat(self, keywords: str, company: Optional[str] = None, is_wx=False):
        """
        切换聊天(目前只支持联系人搜索)
        Args:
            keywords: 别名
            company: 公司名字
            is_wx:是否是微信
        Returns:
        """
        wxlog.debug(f"切换聊天窗口: {keywords=}, {company=},{is_wx}")
        self.root._show()
        _keywords = keywords

        if company and _keywords.find('@') == -1:
            _keywords = f'{_keywords}@{company}'
        if is_wx and _keywords.find('@') == -1:
            _keywords = f'{_keywords}@微信'

        sessions = self.get_session()
        for session in sessions:
            if _keywords == session.name and session.control.BoundingRectangle.height():
                # 当前会话有该关键词
                wxlog.debug(f"{keywords} 匹配到联系人：{session.name}")
                session.switch()
                return _keywords

        self.clear_search_content()
        # 复制待搜索内容到搜索框
        self.search_box.RightClick()
        # 搜索词需要去除姓名和公司等消息 搜索出错
        SetClipboardText(keywords.split('(')[0].split('@')[0])
        menu = CMenuWnd(self)
        menu.select('粘贴')
        # 随机等待
        time.sleep(random.uniform(1.0, 2.0))

        search_result = self.root.control.ListItemControl(Name='联系人').GetParentControl()
        t0 = time.time()
        results = []
        has_user = False
        while time.time() - t0 < WxParam.SEARCH_CHAT_TIMEOUT:
            if not (search_result and search_result.Exists(0)):
                break
            search_result_items = search_result.GetChildren()
            for search_result_item in search_result_items:
                if search_result_item.ControlTypeName != "ListItemControl":
                    continue
                item_name = search_result_item.Name
                if not item_name:
                    continue
                if item_name == "群聊":
                    break
                if item_name == "联系人":
                    has_user = True

                if item_name.find(keywords) > -1:
                    name = (item_name.split(" ")[0] or "").strip()
                    wxlog.debug(f"{keywords} 匹配到联系人：{name}")
                    if name == _keywords:  # 完美匹配
                        wxlog.debug(f"{_keywords} 完整匹配")
                        search_result_item.Click()
                        return name
                    results.append(search_result_item)

            # 尽量完整匹配
            for search_result_item in results:
                item_name = search_result_item.Name
                name = (item_name.split(" ")[0] or "").strip()
                if name.startswith(_keywords):  # 完美匹配
                    wxlog.debug(f"{_keywords} 前置匹配到联系人: {name}")
                    search_result_item.Click()
                    return name

            if has_user:
                break

        if results:
            wxlog.debug(f"{keywords} 匹配到多个结果，返回第一个")
            results[0].Click()
            return results[0].Name

        if search_result.Exists(0):
            search_result.SendKeys('{Esc}')

    def open_separate_window(self, name: str):
        """
        打开独立聊天窗口
        Args:
            name: 会话名字
        Returns:
        """
        wxlog.debug(f"打开独立窗口: {name}")
        sessions = self.get_session()
        for session in sessions:
            if session.name == name:
                wxlog.debug(f"找到会话: {name}")
                while session.control.BoundingRectangle.height():
                    try:
                        session.click()
                        session.double_click()
                    except:
                        pass
                    time.sleep(0.1)
                else:
                    return WxResponse.success(data={'nickname': name})
        wxlog.debug(f"未找到会话: {name}")
        return WxResponse.failure('未找到会话')

    def go_top(self):
        """
        返回会话列表顶部
        Returns:
        """
        wxlog.debug("回到会话列表顶部")
        session_list = self.session_list.ListItemControl().GetParentControl()
        first_session_name = session_list.GetChildren()[0].Name.split(" ")[0]
        while True:
            self.control.WheelUp(wheelTimes=3)
            time.sleep(0.1)
            if session_list.GetChildren()[0].Name.split(" ")[0] == first_session_name:
                break
            else:
                first_session_name = session_list.GetChildren()[0].Name


class SessionElement:
    def __init__(self, control: Control, parent: SessionBox):
        self.root = parent.root
        self.parent = parent
        self.control = control
        self.name = None  # 会话名称
        self.time = None  # 最后一条消息时间
        self.content = None  # 最后一条消息内容
        self.is_mute = None  # 是否免打扰
        self.is_new = False  # 是否有新消息
        self.new_count = 0  # 新消息数
        # 更新记录
        self._get_base_info()

        self.info = {
            'name': self.name,
            'time': self.time,
            'content': self.content,
            'is_new': self.is_new,
            'new_count': self.new_count,
            'is_mute': self.is_mute
        }

    def _lang(self, text: str) -> str:
        return self.parent._lang(text)

    def _get_base_info(self):
        """
        获取基础信息
        Returns:
        """
        result = {}
        if not self.control or not self.control.Exists():
            return result

        base_info = (self.control.Name or "").split(" ")
        wxlog.debug(f"会话信息:{' '.join(base_info)}")
        # 会话昵称
        name = base_info[0] or ""  # 会话显示的昵称(完整显示)
        if name:
            self.name = name
            result["name"] = name

        # 初始下标
        start_index = 1
        end_index = len(base_info) - 1

        # 处理前部数据
        if len(base_info) > start_index:
            text = base_info[start_index]
            # 处理未读消息
            if start_index < 2 and text.endswith("条未读"):
                # 有未读消息
                start_index += 1
                new_count = int(re.findall(r'\d+', text)[0])
                if new_count:
                    self.new_count = new_count
                    self.is_new = True
                    result["new_count"] = new_count
                    result["is_new"] = True
            elif text and text == "有未读消息":
                # 有未读消息 但不清楚是几条
                start_index += 1
                self.new_count = 999
                self.is_new = True
                result["new_count"] = self.new_count
                result["is_new"] = self.is_new

        # 处理后部数据 主要是最后一条的时间
        if end_index > start_index:
            now_time = datetime.now()
            for index in range(end_index, start_index, -1):
                text = base_info[index]
                # 最后一条
                if text and text in ('当前会话', '置顶聊天', '消息免打扰'):
                    if text == "消息免打扰":
                        self.is_mute = True
                    end_index = index - 1

                # 日期相关
                if text and text == "刚刚":
                    self.time = now_time.strftime("%Y-%m-%d %H:%M:%S")
                    result["time"] = self.time
                    end_index = index - 1
                    break
                elif text and text.endswith("分钟前"):
                    num = int(re.findall(r'\d+', text)[0])
                    self.time = (now_time - timedelta(minutes=num)).strftime("%Y-%m-%d %H:%M:%S")
                    result["time"] = self.time
                    end_index = index - 1
                    break
                elif text and re.fullmatch(r"^\d{4}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])$", text):
                    # 显示 年/月/日
                    self.time = f"{text.replace('/', '-')} 00:00:00"
                    result["time"] = self.time
                    end_index = index - 1
                    break
                elif text and re.fullmatch(r"^(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])$", text):
                    # 显示 月/日
                    self.time = f"{now_time.year}-{text.replace('/', '-')} 00:00:00"
                    result["time"] = self.time
                    end_index = index - 1
                    break
                elif text and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", text):
                    # 显示 时:分
                    self.time = f"{now_time.strftime('%Y-%m-%d')} {text.zfill(5)}:00"
                    result["time"] = self.time
                    end_index = index - 1
                    break
                elif text and text == "昨天":
                    self.time = f"{(now_time - timedelta(days=1)).strftime('%Y-%m-%d')} 00:00:00"
                    result["time"] = self.time
                    end_index = index - 1
                    break
                elif text and text == "前天":
                    self.time = f"{(now_time - timedelta(days=2)).strftime('%Y-%m-%d')} 00:00:00"
                    result["time"] = self.time
                    end_index = index - 1
                    break
                elif text and text.startswith("星期"):
                    text_to_weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"].index(
                        text) + 1
                    current_weekday = now_time.isoweekday()
                    if text_to_weekday < current_weekday:
                        diff_day = current_weekday - text_to_weekday
                    else:
                        diff_day = current_weekday - text_to_weekday + 7
                    self.time = f"{(now_time - timedelta(days=diff_day)).strftime('%Y-%m-%d')} 00:00:00"
                    result["time"] = self.time
                    end_index = index - 1
                    break

        if start_index > end_index:
            content = ""  # 没有聊天内容
        elif start_index == end_index:
            content = base_info[start_index]
        else:
            content = " ".join(base_info[start_index:end_index])
        self.content = content
        result["content"] = content
        result["is_mute"] = self.is_mute
        return result

    def roll_into_view(self):
        self.root._show()
        roll_into_view(self.control.GetParentControl(), self.control)

    def _click(self, right: bool = False, double: bool = False):
        self.roll_into_view()
        if right:
            self.control.RightClick()
        elif double:
            self.control.DoubleClick()
        else:
            self.control.Click()

    def click(self):
        self._click()

    def right_click(self):
        self._click(right=True)

    def double_click(self):
        self._click(double=True)

    def switch(self):
        self.click()
