#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =========================================================
# @file        : chatbox.py
# @author      : dana
# @contact     : dana2777@163.com
# @created_at  : 2026/10/13 11:45
# @description : 消息相关
# =========================================================
import threading
import datetime
import random

from ..base import BaseUISubWnd
from .schemas import WXWorkMessage
from wxauto.ui.component import (
    CMenuWnd,
)
from wxauto.param import (
    WxParam,
    WxResponse,
)
from wxauto.languages import *
from wxauto.utils import (
    SetClipboardText,
    SetClipboardFiles,
    GetAllWindowExs,
)
from wxauto.msgs import parse_msg
from wxauto.uia import uiautomation as uia
from wxauto.logger import wxlog
from wxauto.uia import Control
from wxauto.utils import time_it
from wxauto.utils.tools import roll_into_view
from wxauto.utils.tool_md5 import compute_md5
import time
import os
from typing import Optional, List, Dict, Tuple, Generator
from loguru import logger

USED_MSG_IDS = {}

# 记录每个用户最新的一条消息
USER_LATEST_MSG_IDS: Dict[str, Tuple[str, int]] = {}


class ChatBox(BaseUISubWnd):
    def __init__(self, control: Optional[Control], parent):
        self._control: Optional[Control] = control
        self.root = parent
        self.parent = parent  # `wx` or `chat`
        self._msg_box: Optional[Control] = None  # 消息区
        self._msg_box_lock = threading.RLock()
        self._editbox: Optional[Control] = None  # 待发送消息编辑区
        self._editbox_lock = threading.RLock()
        self._send_btn: Optional[Control] = None  # 发送按钮
        self._send_btn_lock = threading.RLock()
        self._tools: Optional[Control] = None  # 工具区
        self._tools_lock = threading.RLock()
        self._msg_history_box: Optional[Control] = None

        self.init()

    @classmethod
    @time_it
    def get_chat_control(cls, control: Optional[Control]) -> Optional[Control]:
        """
        获取聊天区域
        Args:
            control: 指定控件
        Returns:
        """
        if control is None or not control.Exists():
            return None
        chatbox_control = control.GroupControl(Name="聊天信息", searchDepth=18)
        # while chatbox_control and chatbox_control.Exists():
        #     if chatbox_control.ListControl().Exists():
        #         break
        #     chatbox_control = chatbox_control.GetParentControl()
        if chatbox_control and chatbox_control.Exists(0):
            chatbox_control = chatbox_control.GetAncestorControl(
                lambda _control, _depth: _control.ListControl(Name="消息", searchDepth=10).Exists(0))
        return chatbox_control if chatbox_control and chatbox_control.Exists(0) else None

    @property
    def control(self):
        if self._control and self._control.Exists(0):
            return self._control
        self._control = self.get_chat_control(self.parent.control)
        # self.init()
        return self._control

    def init(self):
        if not self._control or not self._control.Exists(0):
            return
        # control = self._control
        # self.msg_box = control.ListControl(Name=self._lang("消息"))

        # self.editbox = control.EditControl()
        # self.sendbtn = control.ButtonControl(Name=self._lang('发送(S)'))
        # self.tools = control.ToolBarControl(Name=self._lang('消息发送'))
        # self.id = self.msgbox.runtimeid
        # if (cid := self.id) and cid not in USED_MSG_IDS:
        #     USED_MSG_IDS[self.id] = tuple((i.runtimeid for i in self.msg_box.GetChildren()))

    @property
    def msg_box(self) -> Optional[Control]:
        """
        消息列表区域
        Returns:
        """
        if self._msg_box and self._msg_box.Exists(0):
            return self._msg_box
        self._msg_box = None
        with self._msg_box_lock:
            # 再确认下
            if self._msg_box and self._msg_box.Exists(0):
                return self._msg_box
            control = self.control
            if control and (control := control.ListControl(Name=self._lang("消息"))) and control and control.Exists(0):
                self._msg_box = control
        return self._msg_box

    @property
    def editbox(self) -> Optional[Control]:
        """
        内容编辑区域
        Returns:
        """
        if self._editbox and self._editbox.Exists(0):
            return self._editbox
        self._editbox = None
        with self._editbox_lock:
            # 再确认下
            if self._editbox and self._editbox.Exists(0):
                return self._editbox
            control = self.control
            if control and (control := control.EditControl()) and control and control.Exists(0):
                self._editbox = control
        return self._editbox

    @property
    def sendbtn(self) -> Optional[Control]:
        """
        发送按钮
        Returns:
        """
        if self._send_btn and self._send_btn.Exists(0):
            return self._send_btn
        self._send_btn = None
        with self._send_btn_lock:
            # 再确认下
            if self._send_btn and self._send_btn.Exists(0):
                return self._send_btn
            control = self.control
            if control and (
                    control := control.ButtonControl(Name=self._lang('发送(S)'))) and control and control.Exists(0):
                self._send_btn = control
        return self._send_btn

    @property
    def tools(self) -> Optional[Control]:
        """
        工具区
        Returns:
        """
        if self._tools and self._tools.Exists(0):
            return self._tools
        self._tools = None
        with self._tools_lock:
            # 再确认下
            if self._tools and self._tools.Exists(0):
                return self._tools
            control = self.control
            if control and (
                    control := control.ToolBarControl(Name=self._lang('消息发送'))) and control and control.Exists(0):
                self._tools = control
        return self._tools

    @property
    def has_box(self) -> bool:
        if self.msg_box:
            return True
        else:
            return False

    def _lang(self, text: str) -> str:
        return WECHAT_CHAT_BOX.get(text, {WxParam.LANGUAGE: text}).get(WxParam.LANGUAGE)

    def _update_used_msg_ids(self):
        # todo 待确认
        USED_MSG_IDS[self.id] = tuple((i.runtimeid for i in self.msg_box.GetChildren()))

    def _parse_msg(self, msg_ele: uia.Control, now_time=None) -> Optional[WXWorkMessage]:
        """
        解析消息
        Args:
            msg_ele:
        Returns:
        """
        now_time = now_time or datetime.datetime.now()
        if msg_ele.ControlTypeName != 'ListItemControl':
            return None
        source_text = msg_ele.Name.strip()
        if not source_text:
            return None

        # 判断是否是系统消息
        if source_text.find("/") > -1 and source_text.find(':') > -1 and source_text.find(" ") > -1:
            is_system_msg = False
        else:
            is_system_msg = True

        # 提取会话名字
        if is_system_msg:
            send_name = ""
            _text = source_text
        else:
            send_name, _text = source_text.split(' ', 1)
            if send_name == "未下载":
                source_text = _text
                send_name, _text = source_text.split(' ', 1)

        _text = _text.strip()
        # 提取日期
        if is_system_msg:
            msg_time = None
        else:
            date_str, _text = _text.split(' ', 1)
            if date_str.count('/') == 1:
                date_str = f"{now_time.year}/{date_str}"
            elif date_str.count('/') == 0:
                logger.warning(
                    f"解析聊天内容出错，请检查会话显示模式是否为`消息气泡左对齐`，当前内容:{source_text=}")
                return WxResponse.failure("解析聊天内容出错，请检查会话显示模式是否为`消息气泡左对齐`")
            # 提取时间
            time_str, _text = _text.split(' ', 1)
            # 组装日期和时间
            msg_time = datetime.datetime(*map(int, date_str.split('/')), *map(int, time_str.split(":")))

        msg_id = compute_md5(source_text)
        wxlog.debug(f"提取到消息内容:{msg_id=};{send_name=};{msg_time=};content={_text}")
        return WXWorkMessage(
            msg_id=msg_id,
            runtime_id=msg_ele.runtimeid,
            send_name=send_name,
            session_name=self.who,
            is_system=is_system_msg,
            msg_time=msg_time,
            content=_text,
        )

    def _update_used_last_msg_ids(self):
        """
        更新最新一条消息信息
        Returns:
        """
        if not (user_id := self.id):
            # 没有用户 不处理
            return

        control = self.msg_box.GetLastChildControl()
        old_last_msg_id = self.user_latest_msg_id
        while True:
            if not control or not control.Exists(0):
                # 无效数据
                return

            # 唯一id
            runtime_id = control.runtimeid
            if old_last_msg_id and old_last_msg_id[0] == runtime_id:
                return

            msg_info = self._parse_msg(control)

            if not msg_info or msg_info.is_system:
                # 获取上一个兄弟节点
                control = control.GetPreviousSiblingControl
                continue

            # 有效消息(不是系统消息)
            if not old_last_msg_id or msg_info.msg_timestamp >= old_last_msg_id[1]:
                # 没有旧消息或者消息时间大于当前记录的消息时间 更新数据
                USER_LATEST_MSG_IDS[user_id] = tuple((runtime_id, msg_info.msg_timestamp))
                return
            # 小于当前记录的时间,说明不是最新消息,不用继续处理了
            return

    def _open_chat_more_info(self):
        # todo 待确认
        for chatinfo_control, depth in uia.WalkControl(self.control):
            if chatinfo_control.Name == self._lang('聊天信息'):
                chatinfo_control.Click()
                break
        else:
            return WxResponse.failure('未找到聊天信息按钮')
        return ChatRoomDetailWnd(self)

    def _activate_editbox(self):
        """
        激活内容编辑区
        Returns:
        """
        if not self.editbox.HasKeyboardFocus:
            self.editbox.MiddleClick()

    @property
    def who(self):
        """
        当前会话名字
        Returns:
        """
        if control := self.editbox:
            return control.Name.strip()
        return ""

    @property
    def id(self):
        """
        用户唯一id
        Returns:
        """
        if name := self.who:
            return compute_md5(name)
        return None

    @property
    def used_msg_ids(self):
        return USED_MSG_IDS[self.id]

    @property
    def user_latest_msg_id(self):
        return USER_LATEST_MSG_IDS.get(self.id)

    @property
    def msg_history_box(self) -> Optional[Control]:
        """
        聊天记录 区域
        可以获取到每条聊天的时间
        Returns:
        """
        self._open_msg_history_box()
        return self._msg_history_box

    def _open_msg_history_box(self):
        """
        打开历史聊天记录
        Returns:
        """
        if self._msg_history_box and self._msg_history_box.Exists(0):
            return
        self._msg_history_box = None
        for i in range(3):
            # 找到 聊天记录 区域
            control = self.control.GroupControl(Name="聊天记录", searchDepth=5)
            if control and control.Exists(0):
                self._msg_history_box = control
                wxlog.debug("找到 聊天记录 区域")
                return
            # 操作打开 聊天记录区域
            if (control := self.tools.ButtonControl(Name='查找聊天记录', searchDepth=5)) and control and control.Exists(
                    0):
                control.Click()
                wxlog.debug(f"[{i}]点击 消息区>工具>查找聊天记录 成功")
                time.sleep(random.uniform(0.5, 0.8))
                continue
            wxlog.debug(f"[{i}] `消息区>工具`栏`查找聊天记录`按钮查找失败")

    def get_info(self):
        """
        会话信息
        类型
        名字
        群成员数
        Returns:
        """
        self.parent._show()
        chat_info = {}
        if not self.msg_box:
            return chat_info
        if ((top_control := self.control.GroupControl(Name="聊天信息", searchDepth=3))
                and top_control.ButtonControl(Name="发起群聊", searchDepth=8).Exists(0)):
            if top_control.ButtonControl(Name="聊天信息", searchDepth=8).Exists(0):
                # 群聊
                chat_info['chat_name'] = self.who
                chat_info['chat_type'] = 'group'
                if not (group_control := self.control.ListControl(Name="群成员")):
                    if (control := self.tools.ButtonControl(Name='查找聊天记录', searchDepth=5)) and control.Exists(0):
                        control.Click()
                        time.sleep(random.uniform(0.5, 0.8))
                    group_control = self.control.ListControl(Name="群成员")
                second_text = group_control.TextControl(Name="群成员").Name
                chat_info['group_member_count'] = int(second_text.replace("群成员 · ", ""))
            else:
                # 单聊
                chat_info['chat_name'] = self.who
                chat_info['chat_type'] = 'friend'
        else:
            if top_control and (title_control := top_control.TextControl(searchDepth=10)) and title_control.Exists(0):
                title_text = title_control.Name.strip()
                if self.tools:
                    chat_info['chat_name'] = title_text
                    chat_info['chat_type'] = 'system'
                else:
                    chat_info['chat_name'] = title_text
                    chat_info['chat_type'] = 'system'

            else:
                chat_info['chat_name'] = ""
                chat_info['chat_type'] = 'other'

        self._info = chat_info
        return chat_info

    def get_edit_box_content(self):
        """
        获取编辑框内容，过滤空字符串和占位文本
        Returns:
        """
        text = self.editbox.GetValuePattern().Value.strip()
        if not text or text == "空白":
            return ""
        return text

    def input_at(self, at_list):
        """
        艾特指定人
        注意:单聊不能艾特人
        Args:
            at_list:
        Returns:

        """
        # todo 待完善
        self._show()
        if isinstance(at_list, str):
            at_list = [at_list]
        self._activate_editbox()
        for friend in at_list:
            self.editbox.SendKeys('@' + friend.replace(' ', ''))
            atmenu = AtMenu(self)
            atmenu.select(friend)

    def clear_edit(self) -> bool:
        """
        清除编辑区
        Returns:
            True:清除内容成功
            False:清除内容失败
        """
        self.parent._show()
        # 先尝试用
        for i in range(4):
            if not (text := self.get_edit_box_content()):
                return True
            if i % 2 == 0:
                is_api = True
            else:
                is_api = False
            self.editbox.Click()
            self.editbox.SendKeys('{Ctrl}a', waitTime=0, api=is_api)
            self.editbox.SendKeys('{DELETE}', api=is_api)
            logger.debug(f"清空编辑内容第{i + 1}次，{is_api=},编辑器内容:{text=}")
            time.sleep(random.uniform(1, 2))
        return False

    def send_text(self, content: str):
        """
        发送消息(文本内容)
        Args:
            content: 需要发送的内容
        Returns:
        """
        self.parent._show()
        t0 = time.time()

        # 输入内容到编辑区
        while True:
            if time.time() - t0 > 10:
                return WxResponse.failure(f'Timeout --> {self.who} - {content}')
            SetClipboardText(content)
            self._activate_editbox()
            # 粘贴内容
            # 第一次 api处理
            self.editbox.SendKeys('{Ctrl}v')
            time.sleep(random.uniform(0.5, 0.8))
            if self.get_edit_box_content():
                break
            # 第二次 非api处理
            self.editbox.SendKeys('{Ctrl}v', api=False)
            time.sleep(random.uniform(0.5, 0.8))
            if self.get_edit_box_content():
                break
            # 第三次 鼠标右键 粘贴
            self.editbox.RightClick()
            menu = CMenuWnd(self)
            menu.select('粘贴')
            if self.get_edit_box_content():
                break

        # 点击发送
        t0 = time.time()
        while self.get_edit_box_content():
            if time.time() - t0 > 10:
                return WxResponse.failure(f'Timeout --> {self.who} - {content}')
            self._activate_editbox()

            self.sendbtn.Click()
            time.sleep(random.uniform(0.5, 0.8))
            if not self.get_edit_box_content():
                return WxResponse.success(f"success")

    def send_msg(self, content: str, clear: bool = True, at=None):
        """
        发送消息
        Args:
            content: 发送的文本内容
            clear: 是否清除历史内容
            at: 艾特信息
        Returns:
        """

        if not content and not at:
            return WxResponse.failure(f"参数 `content` 和 `at` 不能同时为空")

        if clear:
            self.clear_edit()
        if at:
            self.input_at(at)

        return self.send_text(content)

    def send_file(self, file_path):
        """
        发送文件
        Args:
            file_path: 文件地址
        Returns:
        """
        return WxResponse.failure("暂不支持发送文件")
        # todo 待确认
        self._show()
        if isinstance(file_path, str):
            file_path = [file_path]
        file_path = [os.path.abspath(f) for f in file_path]
        SetClipboardFiles(file_path)
        self._activate_editbox()
        self.editbox.SendKeys('{Ctrl}v')
        self.sendbtn.Click()

    def load_more(self, interval=0.3):
        """
        向上滚动加载更多消息
        Args:
            interval: 间隔时间
        Returns:
        """
        self.parent._show()
        if not self.msg_box:
            return WxResponse.failure("没有更多消息了")

        load_more_ele = self.msg_box.GetFirstChildControl()
        if not load_more_ele:
            return WxResponse.failure("没有更多消息了")

        load_more_id = load_more_ele.runtimeid
        load_more_top = load_more_ele.BoundingRectangle.top

        while True:
            # 最上面一条消息出现变化或消息总数出现变化则说明加载到了更多的消息了
            logger.debug(f"消息id:{load_more_ele.runtimeid},消息内容:{load_more_ele.Name}")
            # 向上滚动
            self.msg_box.WheelUp(wheelTimes=random.randint(3, 6),
                                 waitTime=random.uniform(0.12, 0.3)
                                 )
            time.sleep(max(0.3, interval))

            load_more_ele = self.msg_box.GetFirstChildControl()
            new_load_more_id = load_more_ele.runtimeid
            new_load_more_top = load_more_ele.BoundingRectangle.top

            if new_load_more_top == load_more_top and new_load_more_id == load_more_id:
                # 滚到头了
                is_load = False
                break

            if new_load_more_id != load_more_id:
                # 有新数据了
                is_load = True
                break

            load_more_top = new_load_more_top

        self.msg_box.WheelUp(wheelTimes=1, waitTime=0.1)
        if is_load:
            return WxResponse.success()
        else:
            return WxResponse.failure("没有更多消息了")

    def iter_msgs(self, reverse: bool = False) -> Generator[WXWorkMessage, None, None]:
        """
        迭代读取消息。

        会话显示模型需要切换为 `消息气泡左对齐`，
        否则无法获取消息时间和人物。
        Args:
            reverse: 是否反向遍历，默认 False。
        Yields:
            解析成功的单条消息。
        """
        if not self.msg_box:
            return

        now_time = datetime.datetime.now()

        if reverse:
            msg_control = self.msg_box.GetLastChildControl()
            get_next = lambda control: control.GetPreviousSiblingControl()
        else:
            msg_control = self.msg_box.GetFirstChildControl()
            get_next = lambda control: control.GetNextSiblingControl()

        while msg_control:
            msg_info = self._parse_msg(msg_control, now_time=now_time)
            if msg_info:
                yield msg_info

            msg_control = get_next(msg_control)

    @time_it
    def get_msgs(self) -> WxResponse:
        """
        读取消息
        会话显示模型需要切换为 `消息气泡左对齐` 否则无法获取消息时间和人物
        Returns:
        """

        return WxResponse.success(msg="获取消息成功", data=list(self.iter_msgs(reverse=False)), )

    def get_new_msgs(self):
        """
        获取新消息
        Returns:
        """
        if not self.msg_box:
            return []

        if latest_msg := self.user_latest_msg_id:
            # 加载足够的消息
            msg_control = self.msg_box.GetFirstChildControl()
            # 翻页获取消息
            while msg_control:
                msg_info = self._parse_msg(msg_control)
                if not msg_info or msg_info.is_system:
                    # 系统消息没有时间消息 获取下一条数据
                    msg_control = msg_control.GetNextSiblingControl()
                    continue

                if msg_info.msg_timestamp <= latest_msg.msg_timestamp:
                    # 消息加载完成
                    break

                # 向上翻滚 重新获取
                result = self.load_more()
                if result.is_success:
                    # 翻页完成 继续获取最上一条数据
                    msg_control = self.msg_box.GetFirstChildControl()
                    continue
                else:
                    # 无法加载更多消息了
                    break

        result = []
        for msg_info in self.iter_msgs(reverse=True):
            if msg_info.is_system:
                # 系统消息 跳过处理
                continue

            if not latest_msg:
                # 没有最新消息
                result.append(msg_info)
                continue

            if latest_msg[0] != msg_info.runtime_id and msg_info.msg_timestamp >= latest_msg[1]:
                result.append(msg_info)
                continue

            if latest_msg[0] == msg_info.runtime_id:
                break

            if msg_info.msg_timestamp < latest_msg[1]:
                break

        if result:
            USER_LATEST_MSG_IDS[self.id] = tuple((result[0].runtime_id, result[0].msg_timestamp))

        # 反转顺序
        return [reversed(result)]

    def get_next_new_msgs(self, count=None, last_msg: Optional[WXWorkMessage] = None):
        """
        获取下一条新消息
        Args:
            count: 指定数量
            last_msg: 上一次最新消息
        Returns:

        """
        # 1. 消息列表不存在，则返回空列表
        if not self.msg_box:
            wxlog.debug('消息列表不存在，返回空列表')
            return []

        # 2. 判断是否有新消息按钮，有的话点一下 自动跳到最新消息
        load_new_button = self.control.ButtonControl(RegexName=self._lang('re_新消息按钮'))
        if load_new_button.Exists(0):
            self.parent._show()
            wxlog.debug('检测到新消息按钮，点击加载新消息')
            load_new_button.Click()
            time.sleep(random.uniform(0.5, 1))

        if last_msg is None:
            # 获取从上次记录开始的消息
            return self.get_new_msgs()

        chat_control = self.msg_box.GetFirstChildControl()
        # 翻页获取消息
        while chat_control:
            msg_info = self._parse_msg(chat_control)
            if not msg_info or msg_info.is_system:
                chat_control = chat_control.GetNextSiblingControl()
                continue
            if msg_info.msg_timestamp <= last_msg.msg_timestamp:
                # 消息加载完成
                break
            # 向上翻滚 重新获取
            result = self.load_more()
            if result.is_success:
                chat_control = self.msg_box.GetFirstChildControl()
                continue
            else:
                # 无法加载更多数据了
                break

        result = []
        for msg_info in self.iter_msgs(reverse=True):
            if msg_info.is_system:
                # 系统消息 跳过处理
                continue

            if last_msg.msg_id != msg_info.msg_id and msg_info.msg_timestamp > last_msg.msg_timestamp:
                result.append(msg_info)
                continue

            if last_msg.msg_id == msg_info.msg_id:
                break

            if msg_info.msg_timestamp <= last_msg.msg_timestamp:
                break

        # 反转顺序
        return [reversed(result)]

    def scroll_to_latest(self):
        """
        滚动到最新位置
        Returns:
        """
        if not self.msg_box:
            return WxResponse.failure("没有消息区域")
        if (but_control := self.control.ButtonControl(Name="回到最新位置", searchDepth=10)) and but_control.Exists(0):
            but_control.Click()
            time.sleep(random.uniform(0.5, 1))
            return WxResponse.success("跳转成功")
        return WxResponse.success("已经是最新消息位置")


class AtMenu(BaseUISubWnd):
    _ui_cls_name = 'ChatContactMenu'

    def __init__(self, parent):
        self.root = parent.root
        self.control = parent.parent.control.PaneControl(ClassName='ChatContactMenu')
        # self.control.Exists(1)

    def clear(self, friend):
        if self.exists():
            self.control.SendKeys('{ESC}')
        for _ in range(len(friend) + 1):
            self.root.chatbox.editbox.SendKeys('{BACK}')

    def select(self, friend):
        friend_ = friend.replace(' ', '')
        if self.exists():
            ateles = self.control.ListControl().GetChildren()
            if len(ateles) == 1:
                ateles[0].Click()
            else:
                atele = self.control.ListItemControl(Name=friend)
                if atele.Exists(0):
                    roll_into_view(self.control, atele)
                    atele.Click()
                else:
                    self.clear(friend_)
        else:
            self.clear(friend_)
