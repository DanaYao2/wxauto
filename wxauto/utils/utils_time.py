#!/usr/bin/python3
# -*- coding:utf-8 -*-
# -------------------------------
# @author: dana
# @contact: xianwen_yao@163.com
# @file: utils_time.py
# @time: 2024/8/28 下午4:21
# @desc: 耗时统计相关
# -------------------------------
import time
import datetime
import inspect
import functools
from typing import Optional, Union
from loguru import logger


def time_it(func):
    """
    这是一个装饰器，用来计算类方法运行的时长，单位秒.
    它会根据传入的函数是同步还是异步来自动选择合适的装饰器。
    """
    func_name = f"{func.__module__}.{func.__qualname__}"
    if inspect.iscoroutinefunction(func):
        return _time_it_async(func, func_name)
    else:
        return _time_it_sync(func, func_name)


def _time_it_sync(func, func_name):
    """
    适用于同步方法的时间测量装饰器。
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        start_time_cpu = time.process_time()
        try:
            return func(*args, **kwargs)
        finally:
            duration = time.perf_counter() - start_time
            duration_cpu = time.process_time() - start_time_cpu
            logger.info(
                f"同步方法 {func_name}>{func.__name__} 运行时长: {duration:.4f} 秒,CPU耗时:{duration_cpu:.4f}秒")

    return wrapper


def _time_it_async(func, func_name):
    """
    适用于异步方法的时间测量装饰器。
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        start_time_cpu = time.process_time()
        try:
            return await func(*args, **kwargs)  # 使用 await 等待异步方法执行完毕
        finally:
            duration = time.perf_counter() - start_time
            duration_cpu = time.process_time() - start_time_cpu
            logger.info(
                f"异步方法 {func_name}>{func.__name__} 运行时长: {duration:.4f} 秒,CPU耗时:{duration_cpu:.4f}秒")

    return wrapper


if __name__ == '__main__':
    pass
