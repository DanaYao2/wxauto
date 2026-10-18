#!/usr/bin/python3
# -*- coding:utf-8 -*-
# -------------------------------
# @author: dana
# @contact: dana2777@163.com
# @file: browser.py
# @time: 2026/10/18 15:48
# @desc: 
# -------------------------------
from wxauto.utils import (
    FindWindow,
    SetClipboardText
)
from wxauto.languages import *
from wxauto.ui.base import BaseUIWnd
from wxauto.uia import uiautomation as uia
from wxauto.uia import ControlFromHandle, PatternId
from wxauto.param import WxResponse, WxParam
from .component import SelectContactWnd
from wxauto.utils import print_control_tree
from wxauto.logger import wxlog
import time


class WxBrowser(BaseUIWnd):
    _ui_cls_name: str = 'Chrome_WidgetWin_0'
    _ui_name: str = '微信'

    def __init__(self, hwnd: int = None):
        if hwnd is None:
            hwnd = FindWindow(classname=self._ui_cls_name, name=self._ui_name)
        if hwnd:
            self.control = ControlFromHandle(hwnd)
        self.more_button = self.control.PaneControl(searchDepth=1, ClassName='').MenuItemControl(Name="更多")
        self.close_button = self.control.PaneControl(searchDepth=1, ClassName='').ButtonControl(Name="关闭")

    def _lang(self, text: str):
        return WECHAT_BROWSER.get(text, {WxParam.LANGUAGE: text}).get(WxParam.LANGUAGE)

    def Show(self):
        """显示窗口"""
        self._show()

    def search(self, url):
        search_btn_eles = [
            i for i in self.control.TabControl().GetChildren()
            if i.BoundingRectangle.height() == i.BoundingRectangle.width()
        ]
        t0 = time.time()
        while time.time() - t0 < 10:
            if search_btn_eles:
                search_btn_eles[0].Click()
                edit = self.control.TabControl().EditControl(Name='地址和搜索栏')
                SetClipboardText(url)
                edit.ShortcutPaste()
                edit.SendKeys('{Enter}')
                return True
            time.sleep(0.1)
        return False

    def forward(self, friend):
        """
        链接转发给其它人
        """
        t0 = time.time()
        while True:
            if time.time() - t0 > 10:
                # wxbrowser.PaneControl(searchDepth=1, ClassName='').ButtonControl(Name="关闭").Click()
                raise  # '[链接]无法获取url'
            self.more_button.Click()
            time.sleep(0.5)
            copyurl = self.control.PaneControl(ClassName='Chrome_WidgetWin_0').MenuItemControl(Name='转发给朋友')
            if copyurl.Exists(0):
                copyurl.Click()
                break
            self.control.PaneControl(ClassName='Chrome_WidgetWin_0').SendKeys('{Esc}')
        sendwnd = SelectContactWnd()
        return sendwnd.send(friend)

    def send_card(self, url, friend):
        try:
            if self.search(url):
                return self.forward(friend)
        except Exception as e:
            return WxResponse.failure(msg=str(e))
        finally:
            self.close()

    def switch_to_tab(self, name) -> 'WxResponse':
        """
        切换到指定标签页
        :param name:标签页名字
        :return bool
        """
        self.Show()  # 需要激活才能获取到正确的窗口
        try:
            tab_item = self.control.TabControl().TabItemControl(Name=name)
            if tab_item.ButtonControl(Name=self._lang("关闭")).Exists():
                return WxResponse.success(msg="已经是目标页面，不需要切换")
            index = 1
            while True:
                if len(self.control.TabControl().FindAll(control_type='TabItemControl')) <= index:
                    # 未找到指定的标签页
                    return WxResponse.failure(msg="未找打指定的标签页")
                tab_item.Click()
                time.sleep(0.5)
                if tab_item.ButtonControl(Name=self._lang("关闭")).Exists():
                    wxlog.debug(f"""切换到 {name} 标签页成功""")
                    return WxResponse.success(msg=f"""切换到 {name} 标签页成功""")
                index += 1
                time.sleep(0.5)
        except Exception as e:
            wxlog.exception(f"切换标签页异常,{e.__str__()}")
            return WxResponse.error(msg=f"切换标签页异常,{e.__str__()}")

    def get_all_tab(self) -> 'WxResponse':
        """
        获取所有标签页名字
        """
        self.Show()  # 需要激活才能获取到正确的窗口
        try:
            tab_names = []
            tab_ele = self.control.TabControl()
            if not tab_ele.Exists():
                return WxResponse.failure(msg="`TabControl`不存在", data=tab_names)
            tab_item = tab_ele.TabItemControl()
            if not tab_item.Exists():
                return WxResponse.failure(msg="`TabItemControl`不存在", data=tab_names)
            for _tab_item in tab_item.GetParentControl().GetChildren():
                # print(_tab_item)
                if _tab_item and _tab_item.Name:
                    tab_names.append(_tab_item.Name)
            return WxResponse.success(data=tab_names)
        except Exception as e:
            wxlog.exception(f"获取所有标签页名字异常,{e.__str__()}")
            return WxResponse.error(msg=f"获取所有标签页名字异常,{e.__str__()}")

    def close_tab(self, name=None) -> 'WxResponse':
        """
        关闭标签页
        :param name: 如果没用指定时默认关闭当前标签页
        """
        if name:
            self.switch_to_tab(name)
        try:
            tab_ele = self.control.TabItemControl().GetParentControl().ButtonControl(Name=self._lang('关闭'))
            if tab_ele.Exists():
                tab_name = tab_ele.GetParentControl().Name
                tab_ele.Click()
                wxlog.debug(f"""视频号-标签页`{tab_name}`关闭成功""")
        except Exception as e:
            wxlog.exception(f"关闭标签页异常,{e.__str__()}")
            return WxResponse.error(msg=f"关闭标签页异常,{e.__str__()}")

    def close(self):
        try:
            self.close_button.Click(move=True, return_pos=False)
        except:
            pass


class WxVideo(WxBrowser):
    """
    视频号
    """

    def clear_search(self):
        try:
            search_clear_ele = self.control.EditControl(Name="搜索").GetNextSiblingControl()
            if search_clear_ele:
                # search_clear_ele.Click(move=True, return_pos=False)
                search_clear_ele.Click()  # 不占用鼠标
                time.sleep(0.5)
                wxlog.debug(f"""清空搜索框数据""")
            else:
                wxlog.debug(f"""搜索框内没有内容，不需要处理""")
        except Exception as e:
            wxlog.exception(f"""清空搜索框失败，{e.__str__()}""")

    def search(self, text) -> 'WxResponse':
        self.clear_search()
        try:
            wxlog.debug(f"""[+]输入搜索内容:{text}""")
            # self.Show()
            search_edit_ele = self.control.EditControl(Name="搜索")
            t0 = time.time()
            while time.time() - t0 < 10:
                if search_edit_ele:
                    # search_edit_ele.Click(move=True, return_pos=False)
                    search_edit_ele.Click()
                    search_edit_ele.SendKeys(text, api=False)
                    search_edit_ele.SendKeys('{Enter}', api=False)
                    wxlog.debug(f"""[-]输入搜索内容:{text}""")

                    # # 不占用鼠标操作
                    # search_edit_ele.SendKeys(text, api=True)
                    # search_edit_ele.SendKeys('{Enter}', api=True)
                    return WxResponse.success()
                time.sleep(0.1)
            return WxResponse.failure(msg="超时未完成")
        except Exception as e:
            wxlog.exception(f"""搜索失败，{e.__str__()}""")
            return WxResponse.error(msg=str(e))

    def get_more_channel_name(self) -> 'WxResponse':
        """
        单击获取更多视频号
        """
        try:
            _ele = self.control.TextControl(Name=self._lang("账号"))
            if not _ele.Exists():
                wxlog.warning("未定位到`账号`标签")
                return WxResponse.failure(msg="未定位到`账号`标签")
            _group_ele = _ele.GetParentControl().GetParentControl()
            first_account_count = len(_group_ele.GetChildren())
            more_but_ele = _group_ele.TextControl(Name=self._lang("更多"))
            if not more_but_ele.Exists():
                return WxResponse.success()
            while True:
                # more_but_ele.Click(move=True, return_pos=False) # 占用鼠标
                more_but_ele.Click()  # 不占用鼠标
                if len(_group_ele.GetChildren()) > first_account_count:
                    return WxResponse.success()
                elif len(_group_ele.GetChildren()) == first_account_count:
                    return WxResponse.success()

        except Exception as e:
            wxlog.exception(f"""账号点击更多按钮失败，{e.__str__()}""")
            return WxResponse.error(msg=str(e))

    def get_all_channel_name(self) -> 'WxResponse':
        """
        获取所有视频号昵称
        """
        self.Show()
        res = self.get_more_channel_name()
        if not res.is_success:
            return res
        try:
            _account_parent_ele = self.control.TextControl(
                Name=self._lang("账号")).GetParentControl().GetParentControl()
            channel_names = []
            for _group in _account_parent_ele.GetChildren():
                if len(_group.GetChildren()) < 2:
                    continue
                _name_ele = _group.GetChildren()[1]
                if _name_ele.Name and _name_ele.Name in [self._lang("账号"), self._lang("更多")]:
                    continue
                if _name_ele.Name:
                    channel_names.append(_name_ele.Name)
            return WxResponse.success(data=channel_names)
        except Exception as e:
            wxlog.exception(f"""获取所有视频号昵称异常，{e.__str__()}""")
            return WxResponse.error(msg=str(e))

    def select_channel_name(self, name) -> 'WxResponse':
        """
        选择指定账号
        :param name:指定视频号昵称
        """
        # self.Show()
        self.get_more_channel_name()
        try:
            _ele = self.control.TextControl(Name=self._lang("账号")).GetParentControl().GetParentControl().GroupControl(
                Name=name)
            if not _ele.Exists():
                wxlog.info(f"""未找到对应的视频号""")
                return WxResponse.failure(msg="未找到对应的视频号")

            # _ele.Click(move=True, return_pos=False)
            _ele.Click()
            return WxResponse.success()
        except Exception as e:
            wxlog.exception(f"""选择账号({name})异常，{e.__str__()}""")
            return WxResponse.error(msg=str(e))

    def follow_video_channel(self, name) -> 'WxResponse':
        """
        关注视频号 仅实现点击关注功能
        :param name:视频号昵称
        """
        try:
            channel_info_ele = self.control.TextControl().GetParentControl().GetParentControl().GetChildren()[2]
            nick_name = channel_info_ele.TextControl().Name
            if nick_name != name:
                wxlog.info(f"""视频号昵称不一致，当前视频号:{nick_name}，目标视频号:{name}""")
                return WxResponse.failure(msg=f"""视频号昵称不一致，当前视频号:{nick_name}，目标视频号:{name}""")
            # 已关注按钮
            but_ele = self.control.ButtonControl(Name="已关注", foundIndex=1)
            if but_ele.Exists() and but_ele.Name == self._lang("已关注"):
                wxlog.debug(f"""视频号`{name}`已关注，不需要重复关注""")
                time.sleep(0.5)
                return WxResponse.success(msg=f"""视频号`{name}`已关注，不需要重复关注""")

            # 关注按钮
            but_ele = None
            for i in range(10):
                _but_ele = self.control.ButtonControl(Name="关注", foundIndex=i + 1)
                if _but_ele.Exists() and _but_ele.IsOffscreen == 0:
                    but_ele = _but_ele
                    break
                elif _but_ele.Exists():
                    continue
                else:
                    break

            if but_ele and but_ele.Exists():
                # but_ele.Click(move=True, return_pos=False)
                but_ele.Click()
                time.sleep(0.5)
                # 检查是否关注成功
                if self.control.ButtonControl(Name="已关注", foundIndex=1).Exists():
                    wxlog.debug(f"""关注视频号`{name}`成功""")
                    return WxResponse.success(msg=f"""关注视频号`{name}`成功""")

            from wxauto.utils import print_control_tree
            print_control_tree(channel_info_ele.GetParentControl())
            return WxResponse.failure(msg="未知按钮")
        except Exception as e:
            wxlog.exception(f"点击关注按钮失败,{e.__str__()}")
            return WxResponse.error(msg=f"点击关注按钮失败,{e.__str__()}")


class WxInvite(WxBrowser):
    """
    视频号邀请
    """

    # 处理视频号运营者邀请
    def accept_invitation(self):
        """
        点击接受邀请
        """
        try:
            # 获取邀请已过期
            text_ele = self.control.TextControl(Name="邀请已过期")
            if text_ele.Exists():
                wxlog.info(f"""邀请已过期！！！""")
                return WxResponse.failure(msg="邀请已过期")

            # 已成为运营者
            text_ele = self.control.TextControl(Name="已成为运营者")
            if text_ele.Exists():
                wxlog.info(f"""已成为运营者""")
                return WxResponse.success(msg=f"""已成为运营者""")

            # 检查是否有 视频号运营者邀请
            text_ele = self.control.TextControl(Name="视频号运营者邀请")
            if not text_ele.Exists():
                wxlog.warning(f"""没有找到`视频号运营者邀请`""")
                print_control_tree(self.control)
                return WxResponse.failure(msg=f"""没有找到`视频号运营者邀请`""")

            # 接受邀请
            but_ele = self.control.TextControl(Name='接受')
            if but_ele.Exists():
                but_ele.Click()
                time.sleep(0.5)
                for i in range(10):  # 获取成功结果
                    if self.control.TextControl(Name="已成为运营者").Exists():
                        return WxResponse.success(msg=f"""接受邀请成功""")
                    else:
                        time.sleep(0.5)
                        continue
                return WxResponse.success(msg=f"""接受邀请成功""")
            print_control_tree(self.control)
            return WxResponse.failure(msg="未知按钮")
        except Exception as e:
            wxlog.exception(f"接受邀请失败,{e.__str__()}")
            return WxResponse.error(msg=f"接受邀请失败,{e.__str__()}")
