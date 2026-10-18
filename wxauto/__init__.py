from .wx import (
    WeChat,
    Chat,
    LoginWnd,
    get_wx_clients
)
from .wechat_work import WeChatWork, get_wx_clients as get_wechat_work_clients
from .param import WxParam
import pythoncom

pythoncom.CoInitialize()

__all__ = [
    'WeChat',
    'Chat',
    'WxParam',
    'LoginWnd',
    'get_wx_clients',
    'WeChatWork',
    'get_wechat_work_clients'
]
