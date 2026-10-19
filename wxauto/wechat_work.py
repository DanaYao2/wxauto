#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =========================================================
# @file        : wechat_work.py
# @author      : dana
# @contact     : dana2777@163.com
# @created_at  : 2026/10/13 11:53
# @description : 企业微信主入口
# =========================================================
import concurrent.futures._base as __concurrent_futures__base
import json
from .ui import base as __wxautox_ui_base
from .ui.wechat_work.main import WeChatMainWnd, WeChatSubWnd, WeChatLoginWnd
from .ui.wechat_work.component import CMenuWnd
from .param import (
    WxResponse,
    WxParam,
    PROJECT_NAME
)
from .logger import wxlog
from typing import (
    Union,
    List,
    Dict,
    Callable,
    TYPE_CHECKING
)

from abc import ABC, abstractmethod
import threading
import traceback
import time
import sys
import wxauto.uia as uia

from wxauto.utils.tools import (
    get_file_dir,
    roll_into_view,
)
from wxauto.utils import (
    FindWindow,
    SetClipboardText,
    ReadClipboardData,
    GetAllWindows,
    FindWindows,
    GetCursorWindow,
    get_active_window,
)
from wxauto.ui.wechat_work.browser import WxVideo, WxInvite
from typing import Optional

if TYPE_CHECKING:
    from wxauto.msgs.base import Message
    from wxauto.ui.wechat_work.sessionbox import SessionElement

__cached__ = None
WX_CLIENTS: Dict[str, 'WeChatWork'] = dict()


# functions


class Listener(ABC):
    def _listener_start(self):
        wxlog.debug('开始监听')
        self._listener_is_listening = True
        self._listener_messages = {}
        self._lock = threading.RLock()
        self._listener_stop_event = threading.Event()
        self._listener_thread = threading.Thread(target=self._listener_listen, daemon=True)
        self._listener_thread.start()

    def _listener_listen(self):
        self._excutor = ThreadPoolExecutor(max_workers=WxParam.LISTENER_EXCUTOR_WORKERS)
        if not hasattr(self, 'listen') or not self.listen:
            self.listen = {}
        while not self._listener_stop_event.is_set():
            try:
                self._get_listen_messages()
            except KeyboardInterrupt:
                wxlog.debug("监听消息终止")
                self._listener_stop()
                break
            except:
                wxlog.debug(f'监听消息失败：{traceback.format_exc()}')
            time.sleep(WxParam.LISTEN_INTERVAL)

    def _safe_callback(self, callback: Callable[['Message', 'Chat'], None], msg: 'Message', chat: 'Chat'):
        try:
            callback(msg, chat)
        except Exception as e:
            wxlog.debug(f"监听消息回调发生错误：{traceback.format_exc()}")

    def _listener_stop(self):
        self._listener_is_listening = False
        self._listener_stop_event.set()
        self._listener_thread.join()
        self._excutor.shutdown(wait=True)

    @abstractmethod
    def _get_listen_messages(self):
        ...


class Chat:
    """ 微信聊天窗口实例 """

    def __init__(self, core: WeChatSubWnd = None):
        self.core = core
        self.who = self.core.nickname

    def __repr__(self):
        return f'<{PROJECT_NAME} - {self.__class__.__name__} object("{self.core.nickname}")>'

    def Show(self):
        """显示窗口"""
        self.core._show()

    def minimize_window(self):
        """窗口最小化"""
        try:
            self.core.minimize_window()
        except Exception as e:
            wxlog.error(f"""{self}窗口最小化失败:{e.__str__()}""")

    @property
    def browser_invite(self) -> WxInvite:
        if not getattr(self, '__browser_invite', None):
            time.sleep(0.2)
            # 获取当前激活窗口
            hwnd, window_title, class_name = get_active_window()
            wxlog.debug(f"""获取到的窗口信息({hwnd, class_name, window_title})""")
            if class_name == WxInvite._ui_cls_name and window_title == WxInvite._ui_name:
                setattr(self, "__browser_invite", WxInvite(hwnd))
        return getattr(self, '__browser_invite', None)

    def ChatInfo(self) -> Dict[str, str]:
        """获取聊天窗口信息

        Returns:
            dict: 聊天窗口信息
        """
        return self.core.chatbox.get_info()

    def SendMsg(self, msg: str, who: str = None, clear: bool = True, at: Union[str, List[str]] = None,
                exact: bool = False, ) -> WxResponse:
        """发送消息

        Args:
            msg (str): 消息内容
            who (str, optional): 发送对象，不指定则发送给当前聊天对象，**当子窗口时，该参数无效**
            clear (bool, optional): 发送后是否清空编辑框.
            at (Union[str, List[str]], optional): @对象，不指定则不@任何人
            exact (bool, optional): 搜索who好友时是否精确匹配，默认False，**当子窗口时，该参数无效**

        Returns:
            WxResponse: 是否发送成功
        """
        return self.core.send_msg(msg, who, clear, at, exact)

    def SendFiles(
            self,
            filepath,
            who=None,
            exact=False
    ) -> WxResponse:
        """向当前聊天窗口发送文件

        Args:
            filepath (str|list): 要复制文件的绝对路径
            who (str): 发送对象，不指定则发送给当前聊天对象，**当子窗口时，该参数无效**
            exact (bool, optional): 搜索who好友时是否精确匹配，默认False，**当子窗口时，该参数无效**

        Returns:
            WxResponse: 是否发送成功
        """
        return self.core.send_files(filepath, who, exact)

    def LoadMoreMessage(self, interval: float = 0.3) -> WxResponse:
        """
        加载更多消息
        历史消息
        Args:
            interval (float, optional): 滚动间隔，单位秒，默认0.3
        """
        return self.core.load_more_message(interval)

    def GetAllMessage(self) -> List['Message']:
        """获取当前聊天窗口的所有消息

        Returns:
            List[Message]: 当前聊天窗口的所有消息
        """
        return self.core.get_msgs()

    def GetNewMessage(self) -> List['Message']:
        """获取当前聊天窗口的新消息

        Returns:
            List[Message]: 当前聊天窗口的新消息
        """
        if not hasattr(self, '_last_chat'):
            self._last_chat = self.ChatInfo().get('chat_name')
        if (_last_chat := self.ChatInfo().get('chat_name')) != self._last_chat:
            self._last_chat = _last_chat
            self.core.chatbox._update_used_msg_ids()
            return []
        return self.core.get_new_msgs()

    def GetGroupMembers(self) -> List[str]:
        """获取当前聊天群成员

        Returns:
            list: 当前聊天群成员列表
        """
        return self.core.get_group_members()

    def Close(self) -> None:
        """关闭微信窗口"""
        self.core.close()

    def AddFriendFromGroup(self, index, who=None, addmsg=None, remark=None, tags=None, permission=None,
                           exact=False):  # reliably restored by inspect
        """
        从群聊中添加好友

                Args:
                    index (int): 群聊索引
                    who (str, optional): 添加的好友名
                    addmsg (str, optional): 申请理由，当群主开启验证时需要，不填写则取消申请
                    remark (str, optional): 添加好友后的备注名
                    tags (list, optional): 添加好友后的标签
                    permission (Literal['朋友圈', '仅聊天'], optional): 添加好友后的权限
                    exact (bool, optional): 是否精确匹配群聊名

                Returns:
                    WxResponse: 是否添加成功
        """
        # todo
        pass

    def AddGroupMembers(self, group=None, members=None, reason=None):  # reliably restored by inspect
        """
        添加群成员

                Args:
                    group (str): 群名
                    members (Union[str, List[str]]): 成员名或成员名列表
                    reason (str, optional): 申请理由，当群主开启验证时需要，不填写则取消申请

                Returns:
                    WxResponse: 是否添加成功
        """
        # todo
        pass

    def AtAll(*args, **kwargs):  # reliably restored by inspect
        """
        @所有人

                Args:
                    msg (str): 发送的消息
                    who (str, optional): 发送给谁. Defaults to None.
                    exact (bool, optional): 是否精确匹配. Defaults to False.

                Returns:
                    WxResponse: 发送结果
        """
        # todo
        pass

    def GetDialog(self, wait=3):  # reliably restored by inspect
        """
        获取当前窗口的对话框

                Args:
                    wait (int): 隐性等待时间. 默认3秒
        """
        # todo
        pass

    def GetMessageById(self, msg_id):  # reliably restored by inspect
        """
        根据消息id获取消息

                Args:
                    msg_id (str): 消息id

                Returns:
                    Message: 消息对象
        """
        # todo
        pass

    def GetTopMessage(self):  # reliably restored by inspect
        """ 获取置顶消息 """
        # todo
        pass

    def ManageFriend(self, remark=None, tags=None):  # reliably restored by inspect
        """
        修改备注名或标签

                Args:
                    remark (str, optional): 备注名
                    tags (list, optional): 标签列表

                Returns:
                    WxResponse: 是否成功修改备注名或标签
        """
        # todo
        pass

    def ManageGroup(self, name=None, remark=None, myname=None, notice=None, quit=False):  # reliably restored by inspect
        """
        管理当前聊天页面的群聊

                Args:
                    name (str, optional): 修改群名称
                    remark (str, optional): 备注名
                    myname (str, optional): 我的群昵称
                    notice (str, optional): 群公告
                    quit (bool, optional): 是否退出群，当该项为True时，其他参数无效

                Returns:
                    WxResponse: 修改结果
        """
        # todo
        pass

    def MergeForward(*args, **kwargs):  # reliably restored by inspect
        """
        合并转发

                Args:
                    targets (Union[List[str], str]): 合并转发对象

                Returns:
                    WxResponse: 是否发送成功
        """
        # todo
        pass

    def RemoveGroupMembers(self, group=None, members=None):  # reliably restored by inspect
        """
        移除群成员

                Args:
                    group (str): 群名
                    members (Union[str, List[str]]): 成员名或成员名列表

                Returns:
                    WxResponse: 是否移除成功
        """
        pass

    def ScreenShot(self, dir_path=None):  # reliably restored by inspect
        """ 获取窗口截图 """
        # todo
        pass

    def SendEmotion(*args, **kwargs):  # reliably restored by inspect
        """
        发送自定义表情

                Args:
                    emotion_index (str): 表情索引，从0开始
                    who (str): 发送对象，不指定则发送给当前聊天对象，**当子窗口时，该参数无效**
                    exact (bool, optional): 搜索who好友时是否精确匹配，默认False，**当子窗口时，该参数无效**

                Returns:
                    WxResponse: 是否发送成功
        """
        # todo
        pass

    def SendTypingText(*args, **kwargs):  # reliably restored by inspect
        """
        发送文本消息（打字机模式），支持换行及@功能

                Args:
                    msg (str): 要发送的文本消息
                    who (str): 发送对象，不指定则发送给当前聊天对象，**当子窗口时，该参数无效**
                    clear (bool, optional): 是否清除原本的内容， 默认True
                    exact (bool, optional): 搜索who好友时是否精确匹配，默认False，**当子窗口时，该参数无效**

                Returns:
                    WxResponse: 是否发送成功

                Example:
                    >>> wx = WeChatWork()
                    >>> wx.SendTypingText('你好', who='张三')

                    换行及@功能：
                    >>> wx.SendTypingText('各位下午好')
        {@张三}负责xxx
        {@李四}负责xxxx', who='工作群')
        """
        # todo
        pass


class LoginWnd:
    def __init__(self, app_path=None, hwnd=None):
        self._api = WeChatLoginWnd(app_path=app_path, hwnd=hwnd)

    def exists(self, wait: int = 0):
        return self._api.exists(wait)

    def login(self, timeout: int = 10):
        return self._api.login(timeout=timeout)

    def get_qrcode(self, path=None):
        """获取登录二维码

        Args:
            path (str): 二维码图片的保存路径，默认为None，即本地目录下的wxauto_qrcode文件夹


        Returns:
            str: 二维码图片的保存路径
        """
        return self._api.get_qrcode(path=path)

    def reopen(self):
        """重新打开"""
        return self._api.reopen()

    def open(self):
        return self._api.open()

    def close(self):
        """关闭微信"""
        return self._api.close()


class MomentsWnd(__wxautox_ui_base.BaseUISubWnd):
    """朋友圈窗口实例"""
    _abc_impl = None  # (!) real value is '<_abc._abc_data object at 0x00000278C815FB00>'
    _ui_cls_name = 'SnsWnd'
    __abstractmethods__ = frozenset()

    def __init__(self, parent, timeout=3):  # reliably restored by inspect
        # no doc
        # todo
        pass

    def __repr__(self):  # reliably restored by inspect
        # no doc
        # todo
        pass

    # no doc
    def GetMoments(self, next_page=False, speed1=3, speed2=1):  # reliably restored by inspect
        # no doc
        # todo
        pass

    def Refresh(self):  # reliably restored by inspect
        # no doc
        # todo
        pass


class NewFriendElement:  # 新朋友元素
    def __init__(self, control, parent):  # reliably restored by inspect
        self.parent = parent
        self.root = parent.root
        self.control = control
        self.name = self.control.Name
        self.msg = self.control.GetFirstChildControl().PaneControl(SearchDepth=1).GetChildren()[-1].TextControl().Name
        self.NewFriendsBox = self.root.chatbox.control.ListControl(Name='新的朋友').GetParentControl()
        self.status = self.control.GetFirstChildControl().GetChildren()[-1]
        self.acceptable = isinstance(self.status, uia.ButtonControl)

    def __repr__(self):
        return f"<wxauto New Friends Element at {hex(id(self))} ({self.name}: {self.msg})>"

    # no doc
    def accept(self, remark=None, tags=None, permission=None):
        """接受好友请求

        Args:
            remark (str, optional): 备注名
            tags (list, optional): 标签列表
            permission (str, optional): 朋友圈权限, 可选值：'朋友圈', '仅聊天'
        """
        if not self.acceptable:
            wxlog.debug(f"当前好友状态无法接受好友请求：{self.name}")
            return
        wxlog.debug(f"接受好友请求：{self.name}  备注：{remark} 标签：{tags}")
        self.root._show()
        roll_into_view(self.NewFriendsBox, self.status)
        self.status.Click()
        NewFriendsWnd = self.root.control.WindowControl(ClassName='WeUIDialog')
        tipscontrol = NewFriendsWnd.TextControl(Name="你的联系人较多，添加新的朋友时需选择权限")

        permission_sns = NewFriendsWnd.CheckBoxControl(Name='聊天、朋友圈、微信运动等')
        permission_chat = NewFriendsWnd.CheckBoxControl(Name='仅聊天')
        if tipscontrol.Exists(0.5):
            permission_sns = tipscontrol.GetParentControl().GetParentControl().TextControl(Name='朋友圈')
            permission_chat = tipscontrol.GetParentControl().GetParentControl().TextControl(Name='仅聊天')

        if remark:
            remarkedit = NewFriendsWnd.TextControl(Name='备注名').GetParentControl().EditControl()
            remarkedit.Click()
            remarkedit.SendKeys('{Ctrl}a')
            remarkedit.SendKeys(remark)

        if tags:
            tagedit = NewFriendsWnd.TextControl(Name='标签').GetParentControl().EditControl()
            for tag in tags:
                tagedit.Click()
                tagedit.SendKeys(tag)
                NewFriendsWnd.PaneControl(ClassName='DropdownWindow').TextControl().Click()

        if permission == '朋友圈':
            permission_sns.Click()
        elif permission == '仅聊天':
            permission_chat.Click()

        NewFriendsWnd.ButtonControl(Name='确定').Click()

    def delete(self):  # reliably restored by inspect
        wxlog.info(f'删除好友请求: {self.name}')
        roll_into_view(self.NewFriendsBox, self.control)
        self.control.RightClick()
        menu = CMenuWnd(self.root)
        menu.select('删除')

    def get_account(self, wait=5):  # reliably restored by inspect
        """
        获取好友号

        Args:
            wait (int, optional): 等待时间

        Returns:
            str: 好友号，如果获取失败则返回None
        """
        # todo
        pass

    def reply(self, text):  # reliably restored by inspect
        """
        回复消息
        :param text:消息内容
        """
        wxlog.debug(f'回复好友请求: {self.name}')
        roll_into_view(self.NewFriendsBox, self.control)
        self.control.Click()
        self.root.ChatBox.ButtonControl(Name='回复').Click()
        edit = self.root.ChatBox.EditControl()
        edit.Click()
        edit.SendKeys('{Ctrl}a')
        SetClipboardText(text)
        edit.SendKeys('{Ctrl}v')
        time.sleep(0.1)
        self.root.ChatBox.ButtonControl(Name='发送').Click()
        dialog = self.root.UiaAPI.PaneControl(ClassName='WeUIDialog')
        while edit.Exists(0):
            if dialog.Exists(0):
                systext = dialog.TextControl().Name
                wxlog.debug(f'系统提示: {systext}')
                dialog.SendKeys('{Esc}')
                self.root.ChatBox.ButtonControl(Name='').Click()
                return WxResponse.failure(msg=systext)
            time.sleep(0.1)
        self.root.ChatBox.ButtonControl(Name='').Click()
        return WxResponse.success()


class ThreadPoolExecutor(__concurrent_futures__base.Executor):
    def __init__(self, max_workers=None, thread_name_prefix=None, initializer=None, initargs='()'):
        """
        Initializes a new ThreadPoolExecutor instance.

        Args:
            max_workers: The maximum number of threads that can be used to
                execute the given calls.
            thread_name_prefix: An optional name prefix to give our threads.
            initializer: A callable used to initialize worker threads.
            initargs: A tuple of arguments to pass to the initializer.
        """
        # todo
        pass

    # no doc
    def shutdown(self, wait=True, *, cancel_futures=False):  # reliably restored by inspect
        """
        Clean-up the resources associated with the Executor.

                It is safe to call this method several times. Otherwise, no other
                methods can be called after this one.

                Args:
                    wait: If True then shutdown will not return until all running
                        futures have finished executing and the resources used by the
                        executor have been reclaimed.
                    cancel_futures: If True then shutdown will cancel all pending
                        futures. Futures that are completed or running will not be
                        cancelled.
        """
        self._task_scheduler.shutdown(wait=wait, cancel_futures=cancel_futures)

    def submit(self, fn, *args, **kwargs):  # reliably restored by inspect
        """
        Submits a callable to be executed with the given arguments.

        Schedules the callable to be executed as fn(*args, **kwargs) and returns
        a Future instance representing the execution of the callable.

        Returns:
            A Future representing the given call.
        """
        # todo
        pass

    def _adjust_thread_count(self):  # reliably restored by inspect
        # no doc
        pass

    def _counter(self, *args, **kwargs):  # real signature unknown
        """ Implement next(self). """
        pass

    def _initializer_failed(self):  # reliably restored by inspect
        # no doc
        pass


class WeChatWork(Chat, Listener):
    """ 微信主窗口实例 """

    def __init__(self, nickname=None, debug: bool = False, **kwargs):
        hwnd = None
        if 'hwnd' in kwargs:
            hwnd = kwargs['hwnd']
        self.core = WeChatMainWnd(hwnd)
        self.listen = {}
        if debug:
            if hasattr(wxlog, 'set_debug'):
                wxlog.set_debug(True)
                wxlog.debug('Debug mode is on')
        # self._listener_start()
        self.Show()

    @property
    def user_id(self):
        """用户id"""
        return self.core.user_id

    @property
    def nick_name(self):
        """别名"""
        return self.core.nick_name

    @property
    def real_name(self):
        """
        真实名字
        Returns:

        """
        return self.core.real_name

    @property
    def company(self):
        """
        公司信息
        Returns:

        """
        return self.core.company

    @property
    def verified(self):
        return self.core.verified

    def user_info(self):
        """
        获取当前用户信息
        Returns:
        """
        return self.core.user_info()

    def close(self):
        return self.core.close()

    def _get_listen_messages(self):
        """
        监听新消息
        Returns:
        """
        # todo 未完成
        try:
            sys.stdout.flush()
        except:
            pass
        temp_listen = self.listen.copy()
        for who in temp_listen:
            chat, callback = temp_listen.get(who, (None, None))
            try:
                if chat is None or not chat.core.exists():
                    wxlog.debug(f"窗口 {who} 已关闭，移除监听")
                    self.RemoveListenChat(who, close_window=False)
                    continue
            except:
                continue
            with self._lock:
                msgs = chat.GetNewMessage()
                for msg in msgs:
                    wxlog.debug(f"[{msg.attr} {msg.type}]获取到新消息：{who} - {msg.content}")
                    chat.Show()
                    self._safe_callback(callback, msg, chat)

    def GetSession(self) -> List['SessionElement']:
        """
        获取当前会话列表
        Returns:
            List[SessionElement]: 当前会话列表
        """
        return self.core.session_box.get_session()

    def ChatWith(self, who: str, company: Optional[str] = None, is_wx: bool = False):
        """打开聊天窗口

        Args:
            who (str): 要聊天的对象
            company: 公司名字
            is_wx:是否是微信
        """
        return self.core.switch_chat(who, company=company, is_wx=is_wx)

    def AddListenChat(self, nickname: str, callback: Callable[['Message', str], None], ):
        """
        添加监听聊天，将聊天窗口独立出去形成Chat对象子窗口，用于监听
        Args:
            nickname (str): 要监听的聊天对象
            callback (Callable[[Message, str], None]): 回调函数，参数为(Message对象, 聊天名称)
        """
        # todo 未完成
        if nickname in self.listen:
            return WxResponse.failure('该聊天已监听')
        subwin = self.core.open_separate_window(nickname)
        if subwin is None:
            return WxResponse.failure('找不到聊天窗口')
        name = subwin.nickname
        chat = Chat(subwin)
        self.listen[name] = (chat, callback)
        return chat

    def StopListening(self, remove: bool = True) -> None:
        """停止监听

        Args:
            remove (bool, optional): 是否移除监听对象. Defaults to True.
        """
        # todo 未完成
        while self._listener_thread.is_alive():
            self._listener_stop()
        if remove:
            listen = self.listen.copy()
            for who in listen:
                self.RemoveListenChat(who)

    def StartListening(self) -> None:
        """
        开始监听
        Returns:
        """
        # todo 未完成
        if not self._listener_thread.is_alive():
            self._listener_start()

    def RemoveListenChat(self, nickname: str, close_window: bool = True) -> WxResponse:
        """移除监听聊天
        Args:
            nickname (str): 要移除的监听聊天对象
            close_window (bool, optional): 是否关闭聊天窗口. Defaults to True.
        Returns:
            WxResponse: 执行结果
        """
        if nickname not in self.listen:
            return WxResponse.failure('未找到监听对象')
        chat, _ = self.listen[nickname]
        if close_window:
            chat.Close()
        del self.listen[nickname]
        return WxResponse.success()

    def GetNextNewMessage(self, chat_page_tab="所有", filter_mute=False) -> Dict[str, List['Message']]:
        """获取下一个新消息

        Args:
            chat_page_tab:指定消息分组
            filter_mute (bool, optional): 是否过滤掉免打扰消息. Defaults to False.

        Returns:
            Dict[str, List['Message']]: 消息列表
        """
        return self.core.get_next_new_message(chat_page_tab=chat_page_tab, filter_mute=filter_mute)

    def SwitchChatPage(self, name="所有") -> None:
        """切换到联系人页面"""
        return self.core.navigation.switch_to_tab_chat_page(name=name)

    def GetSubWindow(self, nickname: str) -> 'Chat':
        """获取子窗口实例

        Args:
            nickname (str): 要获取的子窗口的昵称

        Returns:
            Chat: 子窗口实例
        """
        if subwin := self.core.get_sub_wnd(nickname):
            return Chat(subwin)

    def GetAllSubWindow(self) -> List['Chat']:
        """
        获取所有子窗口实例

        Returns:
            List[Chat]: 所有子窗口实例
        """
        return [Chat(subwin) for subwin in self.core.get_all_sub_wnds()]

    def KeepRunning(self):
        """ 保持运行 """
        while not self._listener_stop_event.is_set():
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                wxlog.debug(f'wxauto("{self.nick_name}") shutdown')
                self.StopListening(True)
                break

    def AddNewFriend(self, keywords, addmsg=None, remark=None, tags=None, permission=None,
                     timeout=5) -> WxResponse:
        """
        添加新的好友

        Args:
            keywords (str): 搜索关键词，可以是昵称、微信号、手机号等
            addmsg (str, optional): 添加好友时的附加消息，默认为None
            remark (str, optional): 添加好友后的备注，默认为None
            tags (list, optional): 添加好友后的标签，默认为None
            permission (Literal['朋友圈', '仅聊天'], optional): 添加好友后的权限，默认为'朋友圈'
            timeout (int, optional): 搜索好友的超时时间，默认为5秒

        Returns:
            WxResponse: 添加好友的结果
        """
        # todo 未完成
        pass

    def GetAllRecentGroups(self, speed=1, interval=0.05) -> WxResponse | List[str]:
        """
        获取所有最近群聊

        Args:
            speed (int, optional): 获取速度，默认为1
            interval (float, optional): 获取间隔，默认为0.05秒

        Returns:
            WxResponse | List[str]: 失败时返回WxResponse，成功时返回所有最近群聊列表
        """
        # todo
        pass

    def GetContactGroups(self, speed=1, interval=0.1):
        """
        获取通讯录中的所有群聊

        Args:
            speed (int, optional): 获取速度，默认为1
            interval (float, optional): 滚动间隔，默认为0.1秒

        Returns:
            List[str]: 所有群聊列表
        """
        # todo
        pass

    def GetFriendDetails(self, n=None, tag=None, timeout=1048575):
        """
        获取好友详情

        Args:
            n (int, optional): 获取前n个好友详情信息, 默认为None，获取所有好友详情信息
            tag (str, optional): 从指定标签开始获取好友详情信息，如'A'，默认为None即从第一个好友开始获取
            timeout (int, optional): 获取超时时间（秒），超过该时间则直接返回结果

        Returns:
            List[dict]: 所有好友详情信息

        注：1. 该方法运行时间较长，约0.5~1秒一个好友的速度，好友多的话可将n设置为一个较小的值，先测试一下
            2. 如果遇到企业微信的好友且为已离职状态，可能导致微信卡死，需重启（此为微信客户端BUG）
            3. 该方法未经过大量测试，可能存在未知问题，如有问题请微信群内反馈
        """
        # todo
        pass

    def GetMyInfo(self):
        """ 获取我的信息 """
        # todo
        pass

    def GetNewFriends(self, acceptable=True) -> List['NewFriendElement']:
        """
        获取新的好友申请列表

        Args:
            acceptable (bool, optional): 是否过滤掉已接受的好友申请

        Returns:
            List['NewFriendElement']: 新的好友申请列表，元素为NewFriendElement对象，可直接调用Accept方法

        Example:
            >>> wx = WeChatWork()
            >>> newfriends = wx.GetNewFriends(acceptable=True)
            >>> tags = ['标签1', '标签2']
            >>> for friend in newfriends:
            ...     remark = f'备注{friend.name}'
            ...     friend.Accept(remark=remark, tags=tags)  # 接受好友请求，并设置备注和标签
        """
        # todo
        pass

    def IsOnline(self):  # reliably restored by inspect
        """ 判断是否在线 """
        # todo
        pass

    def Moments(self, timeout=3):  # reliably restored by inspect
        """ 进入朋友圈 """
        pass

    def SendUrlCard(self, url, friends, timeout=10):  # reliably restored by inspect
        """
        发送链接卡片

                Args:
                    url (str): 链接地址
                    friends (Union[str, List[str]], optional): 发送对象
                    timeout (int, optional): 等待时间，默认10秒

                Returns:
                    WxResponse: 发送结果
        """
        pass


class WeChatDialog(__wxautox_ui_base.BaseUISubWnd):

    def __init__(self, parent, wait=3):  # reliably restored by inspect
        # no doc
        pass

    # no doc
    def click_button(self, text, move=True):  # reliably restored by inspect
        # no doc
        pass


def get_wx_clients(debug=False):
    """
    获取当前所有微信客户端
    Returns:
        # List[WeChatWork]: 当前所有微信客户端
        Dict[str,WeChatWork]: 微信号,微信客户端
    """
    global WX_CLIENTS
    cls_name = WeChatMainWnd._ui_cls_name
    name = WeChatMainWnd._ui_name
    windows_infos = FindWindows(classname=cls_name, name=name)
    wxlog.debug(f"""当前所有企业微信窗口:{json.dumps(windows_infos, ensure_ascii=False)}""")
    hwnds = list()
    # 加入新对象
    for windows_info in windows_infos:
        hwnd = windows_info[0]
        hwnds.append(str(hwnd))
        if str(hwnd) in WX_CLIENTS:
            continue
        WX_CLIENTS[str(hwnd)] = WeChatWork(hwnd=hwnd, debug=debug)

    if len(WX_CLIENTS.keys()) > len(hwnds):
        old_hwnds = list(WX_CLIENTS.keys())
        for hwnd in old_hwnds:
            if hwnd not in hwnds:
                del WX_CLIENTS[hwnd]

    return {i.user_id: i for i in WX_CLIENTS.values()}


def get_wx_logins() -> List[LoginWnd]:
    win32wins = GetAllWindows()
    return [
        LoginWnd(hwnd=win[0])
        for win in win32wins
        if win[1] == WeChatLoginWnd._ui_cls_name
    ]
