#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =========================================================
# @file        : main.py
# @author      : dana
# @contact     : dana2777@163.com
# @created_at  : 2026/10/13 11:43
# @description :
# =========================================================
from ..base import (
    BaseUIWnd,
    BaseUISubWnd
)
# from wxauto import uiautomation as uia
from wxauto.uia import uiautomation as uia
from wxauto.param import WxResponse
from .chatbox import ChatBox
from .sessionbox import SessionBox
from .navigationbox import NavigationBox
from wxauto.param import (
    WxParam,
    WxResponse,
    PROJECT_NAME
)
from wxauto.languages import *
from wxauto.utils import (
    GetAllWindows,
    FindWindow,
    FindTopLevelControl,
    get_windows_by_pid,
    time_it
)
from wxauto.utils.tools import now_time
from wxauto.logger import wxlog
from typing import Union, List, Optional
import time
import winreg
import random
import os
import sys

from wxauto.utils import print_control_tree, inspect_hwnds


class WeChatSubWnd(BaseUISubWnd):
    _ui_cls_name: str = 'WwStandaloneConversationWnd'
    chatbox: ChatBox = None
    nickname: str = ''

    def __init__(self, key: Union[str, int], parent: 'WeChatMainWnd', timeout: int = 3):
        self.root = self
        self.parent = parent
        if isinstance(key, str):
            _key = key.split('@')[0]
            hwnd = FindWindow(classname=self._ui_cls_name, name=key, timeout=timeout)
        else:
            hwnd = key
        self.control = uia.ControlFromHandle(hwnd)
        if self.control is not None:
            chatbox_control = ChatBox.get_chat_control(self.control)
            if isinstance(key, int) or (
                    (control := chatbox_control.TextControl(searchDepth=10)) and control and control.Exists(
                0) and control.Name == key):
                self.chatbox = ChatBox(chatbox_control, self)
                self.nickname = self.chatbox.who

    def __repr__(self):
        return f'<{PROJECT_NAME} - {self.__class__.__name__} object("{self.nickname}")>'

    @property
    def pid(self):
        if not hasattr(self, '_pid'):
            self._pid = self.control.ProcessId
        return self._pid

    def minimize_window(self):
        try:
            but_ele = self.control.ButtonControl(Name="最小化")
            if but_ele.Exists():
                but_ele.Click()
                wxlog.info(f"""{self}窗口最小化成功""")
        except Exception as e:
            wxlog.error(f"""{self}窗口最小化失败：{e.__str__()}""")

    def _get_chatbox(self, nickname: str = None, exact: bool = False) -> Optional[ChatBox]:
        return self.chatbox

    def chat_info(self):
        return self.chatbox.get_info()

    def load_more_message(self, interval=0.3) -> WxResponse:
        return self.chatbox.load_more(interval)

    def send_msg(self, msg: str, who: str = None, clear: bool = True, at: Union[str, List[str]] = None,
                 exact: bool = False, ) -> WxResponse:
        chatbox = self._get_chatbox(who, exact)
        if not chatbox:
            return WxResponse.failure(f'未找到会话: {who}')
        return chatbox.send_msg(msg, clear=clear, at=at)

    def send_files(
            self,
            filepath,
            who=None,
            exact=False
    ) -> WxResponse:
        chatbox = self._get_chatbox(who, exact)
        if not chatbox:
            return WxResponse.failure(f'未找到会话: {who}')
        return chatbox.send_file(filepath)

    def get_group_members(
            self,
            who: str = None,
            exact: bool = False
    ) -> List[str]:
        chatbox = self._get_chatbox(who, exact)
        if not chatbox:
            return WxResponse.failure(f'未找到会话: {who}')
        return chatbox.get_group_members()

    def get_msgs(self):
        chatbox = self._get_chatbox()
        if chatbox:
            return chatbox.get_msgs()
        return []

    def get_new_msgs(self):
        return self._get_chatbox().get_new_msgs()


class WeChatMainWnd(WeChatSubWnd):
    _ui_cls_name: str = 'WeWorkWindow'
    _ui_name: str = '企业微信'

    def __init__(self, hwnd: int = None):
        self.root = self
        self.parent = self
        self.control: Optional[uia.Control] = None
        if hwnd:
            self._setup_ui(hwnd)
        else:
            hwnd = FindWindow(classname=self._ui_cls_name)
            if not hwnd:
                raise Exception(f'未找到企业微信窗口')
            self._setup_ui(hwnd)

        wxlog.info(f'初始化成功，获取到已登录窗口：{self.nickname}')

    @time_it
    def _setup_ui(self, hwnd: int):
        self.HWND = hwnd
        self.control = uia.ControlFromHandle(hwnd)
        # 打印树状结构
        self.Show()
        # inspect_hwnds(self.HWND)
        # print_control_tree(self.control)

        # 获取导航区域
        navigation_control = self.control.ToolBarControl(Name="导航")
        # 获取会话区域
        session_box_control = SessionBox.get_session_control(self.control)
        # print_control_tree(session_box_control)
        # 获取聊天信息区域(有可能会没有 要动态获取)
        chatbox_control = ChatBox.get_chat_control(self.control)

        # if chatbox_control and chatbox_control.Exists():
        #     print_control_tree(chatbox_control)

        self.navigation = NavigationBox(navigation_control, self)
        self.session_box = SessionBox(session_box_control, self)
        self.chatbox = ChatBox(chatbox_control, self)
        self.NavigationBox = self.navigation.control
        self.SessionBox = self.session_box.control
        self.ChatBox = self.chatbox.control

    def __repr__(self):
        return f'<{PROJECT_NAME} - {self.__class__.__name__} object("{self.nickname}")>'

    @property
    def nickname(self):
        return self.navigation.nick_name

    def Show(self):
        if hasattr(self, 'HWND'):
            import win32gui
            win32gui.ShowWindow(self.HWND, 1)
            win32gui.SetWindowPos(self.HWND, -1, 0, 0, 0, 0, 3)
            win32gui.SetWindowPos(self.HWND, -2, 0, 0, 0, 0, 3)
        self.control.SwitchToThisWindow()

    def _lang(self, text: str, main_type="WECHAT_MAIN") -> str:
        return eval(main_type).get(text, {WxParam.LANGUAGE: text}).get(WxParam.LANGUAGE)

    def _get_chatbox(self, nickname: Optional[str] = None, exact: bool = False, company: Optional[str] = None,
                     is_wx=False) -> Optional[ChatBox]:
        """
        获取聊天窗口(含悬浮窗)
        Args:
            nickname:会话昵称
            # exact:
            company: 公司
            is_wx: 是否来自微信
        Returns:

        """
        keywords = nickname
        if keywords and company and keywords.find('@') == -1:
            keywords = f'{keywords}@{company}'
        if keywords and is_wx and keywords.find('@') == -1:
            keywords = f'{keywords}@微信'

        if keywords and (chatbox := WeChatSubWnd(keywords, self, timeout=0)).nickname:
            return chatbox.chatbox
        else:
            if keywords:
                switch_result = self.session_box.switch_chat(keywords=keywords, company=company, is_wx=is_wx)
                if not switch_result:
                    return None
            if self.chatbox.has_box:
                return self.chatbox
        return None

    def switch_chat(self, keywords: str, company: Optional[str] = None, is_wx: bool = False):
        """
        切换聊天窗口
        Args:
            keywords: 关键词
            company: 公司
            is_wx: 是否来自微信
        Returns:
        """
        return self.session_box.switch_chat(keywords, company=company, is_wx=is_wx)

    def get_all_sub_wnds(self):
        """
        获取所有聊天悬浮窗口
        Returns:
        """
        sub_wxs = [i for i in GetAllWindows() if i[1] == WeChatSubWnd._ui_cls_name]
        return {obj.nickname: obj for i in sub_wxs if (obj := WeChatSubWnd(i[0], self)) and obj.nickname}

    def get_sub_wnd(self, who: str, timeout: int = 0):
        return self.get_all_sub_wnds().get(who)

    def open_separate_window(self, keywords: str) -> WeChatSubWnd:
        """
        打开独立聊天窗口
        Args:
            keywords:

        Returns:

        """
        if subwin := self.get_sub_wnd(keywords):
            wxlog.debug(f"{keywords} 获取到已存在的子窗口: {subwin}")
            return subwin

        self._show()
        if nickname := self.session_box.switch_chat(keywords):
            wxlog.debug(f"{keywords} 切换到聊天窗口: {nickname}")
            if subwin := self.get_sub_wnd(nickname):
                wxlog.debug(f"{nickname} 获取到已存在的子窗口: {subwin}")
                return subwin
            else:
                keywords = nickname

        if result := self.session_box.open_separate_window(keywords):
            find_nickname = result['data'].get('nickname', keywords)
            return WeChatSubWnd(find_nickname, self)

    def _get_next_new_message(self, chat_page_tab, filter_mute: bool = False):
        """
        获取下一条新消息
        Args:
            chat_page_tab:指定标签页
            filter_mute: 是否过滤掉免打扰消息
        Returns:

        """

        def get_new_message(session):
            last_content = session.content
            new_count = session.new_count
            chat_name = session.name
            session.click()
            return self.chatbox.get_next_new_msgs(new_count, last_content)

        def get_new_session(filter_mute):
            sessions = self.session_box.get_session()
            new_sessions = [i for i in sessions if i.is_new]
            if filter_mute:
                new_sessions = [i for i in new_sessions if i.is_mute == False]
            return new_sessions

        self.navigation.switch_to_tab_chat_page(chat_page_tab)
        if new_msgs := self.chatbox.get_new_msgs():
            wxlog.debug("获取当前页面新消息")
            return new_msgs
        elif new_sessions := get_new_session(filter_mute):
            wxlog.debug("当前会话列表获取新消息")
            return get_new_message(new_sessions[0])
        else:
            self.session_box.go_top()
            if new_sessions := get_new_session(filter_mute):
                wxlog.debug("当前会话列表获取新消息")
                return get_new_message(new_sessions[0])
            else:
                # self.navigation.chat_icon.DoubleClick()
                self.navigation.switch_to_tab_chat_page(chat_page_tab)

            if new_sessions := get_new_session(filter_mute):
                wxlog.debug("翻页会话列表获取新消息")
                return get_new_message(new_sessions[0])
            else:
                wxlog.debug("没有新消息")
                return []

    def get_next_new_message(self, chat_page_tab, filter_mute: bool = False):
        """
        获取下一条新消息
        Args:
            chat_page_tab:指定分组
            filter_mute: 是否过滤掉免打扰消息
        Returns:
        """
        self.navigation.switch_to_tab_chat_page(name=chat_page_tab)
        if filter_mute and not self.navigation.has_new_message():
            return {}
        new_msgs = self._get_next_new_message(chat_page_tab, filter_mute)
        if new_msgs:
            chat_info = self.chatbox.get_info()
            return {
                'chat_name': chat_info['chat_name'],
                'chat_type': chat_info['chat_type'],
                'msg': new_msgs
            }
        else:
            return {}

    def close(self):
        """
        关闭窗口
        Returns:
        """
        try:
            if not hasattr(self, 'control'):
                return True
            if not self.control or not self.control.Exists():
                return True
            close_ele = self.control.ButtonControl(Name="关闭")
            if not close_ele.Exists():
                return True
            close_ele.Click()
            wxlog.info(f"""{self}窗口关闭""")
            return True
        except Exception as e:
            wxlog.error(f"""{self}窗口关闭失败:{e.__str__()}""")
            return False


class WeChatLoginWnd(BaseUIWnd):
    # _ui_cls_name: str = 'WeChatLoginWndForPC'
    _ui_cls_name: str = 'WeChatLogin'

    def __init__(self, app_path=None, hwnd=None):
        self.app_path = app_path
        if not hwnd:
            hwnd = FindWindow(classname=self._ui_cls_name)
        if hwnd:
            self.control = uia.ControlFromHandle(hwnd)
        else:
            self.open()

    def __repr__(self) -> str:
        return f"<wxauto LoginWnd Object at {hex(id(self))}>"

    def _lang(self, key):
        return key

    @property
    def _app_path(self):
        """获取企业微信应用地址"""
        if self.app_path:
            return self.app_path
        try:
            # 通过注册表获取企业微信路径
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WXWork", 0, winreg.KEY_READ)
            try:
                path, _ = winreg.QueryValueEx(registry_key, "InstallPath")
            except FileNotFoundError:
                path, _ = winreg.QueryValueEx(registry_key, "Executable")
            winreg.CloseKey(registry_key)

            wxpath = os.path.join(path, "WXWork.exe")
            if os.path.exists(wxpath):
                self.app_path = wxpath
                return wxpath
            else:
                raise Exception('nof found')
        except WindowsError:
            print("未找到微信安装路径，请先打开微信启动页面再次尝试运行该方法！")

    def login(self, timeout=15):
        # todo 待确认
        enter_button = self.control.ButtonControl(Name='进入微信')
        qrcode = self.control.ButtonControl(Name='二维码')
        if enter_button.Exists(0.5):
            enter_button.Click()

            dialog = self.control.PaneControl(ClassName='WeUIDialog')
            # wx = uia.WindowControl(ClassName='WeChatMainWndForPC', searchDepth=1)

            t0 = time.time()
            while True:
                if time.time() - t0 > timeout:
                    raise Exception('微信登录超时')
                if FindWindow(classname='WeChatMainWndForPC'):
                    break
                elif dialog.Exists(0):
                    dialog_text = dialog.TextControl().Name
                    wxlog.debug(f"识别到弹窗：{dialog_text}")
                    dialog.SendKeys('{Esc}')
                    time.sleep(0.5)
                    return self.login(timeout)
                elif qrcode.Exists(0):
                    return WxResponse.failure("需扫码登录")
            return WxResponse.success()
        elif qrcode.Exists(0):
            return WxResponse.failure("需扫码登录")
        else:
            return WxResponse.failure("未找到登录按钮")

    def get_qrcode(self, path=None):
        """获取登录二维码

        Args:
            path (str): 二维码图片的保存路径，默认为None，即本地目录下的wxauto_qrcode文件夹


        Returns:
            str: 二维码图片的保存路径
        """
        # todo 待确认
        self._show()
        if path is None:
            default_dir = os.path.realpath('wxauto_qrcode')
            if not os.path.exists(default_dir):
                os.mkdir(default_dir)
            path = os.path.join(default_dir, f'qrcode_{now_time()}.png')
        elif os.path.exists(path) and os.path.isdir(path):
            path = os.path.join(path, f'qrcode_{now_time()}.png')
        elif os.path.exists(os.path.dirname(path)) and path.endswith('.png'):
            pass
        else:
            raise ValueError('请输入正确的路径，或不指定path参数以使用默认路径')
        switch_account_button = self.control.ButtonControl(Name='切换账号')
        if switch_account_button.Exists(0.5):
            switch_account_button.Click()

        qrcode_control = self.control.ButtonControl(Name='二维码')
        qrcode = qrcode_control.ScreenShot(path)
        return qrcode

    def shutdown(self):
        """关闭进程"""
        pid = self.control.ProcessId
        os.system(f'taskkill /f /pid {pid}')

    def reopen(self):
        """重新打开"""
        self.shutdown()
        self.open()

    def open(self):
        path = self._app_path
        os.system(f'"start "" "{path}""')
        hwnd = FindWindow(classname=self._ui_cls_name, timeout=5)
        if hwnd:
            self.control = uia.ControlFromHandle(hwnd)
        if self.control.Exists(10):
            return
        else:
            raise Exception('打开微信失败，请指定微信路径')
