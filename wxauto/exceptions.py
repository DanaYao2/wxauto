class WxAutoError(Exception):
    pass


class WxautoOCRError(WxAutoError):
    ...


class NetWorkError(WxAutoError):
    ...


class WxautoUINotFoundError(WxAutoError):
    ...


class WxautoNoteLoadTimeoutError(WxAutoError):
    ...


class WorkWechatError(WxAutoError):
    pass


class WindowNotFound(WorkWechatError):
    pass


class UIAActivationError(WorkWechatError):
    pass
