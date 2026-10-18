#!/usr/bin/python3
# -*- coding:utf-8 -*-
# -------------------------------
# @author: dana
# @contact: xianwen_yao@163.com
# @file: utils_md5.py
# @time: 2024/7/25 下午12:57
# @desc: 数据hash加密生成唯一值
# -------------------------------
def get_md5(data, c_type=0, hash_type='md5'):
    import hashlib
    import json
    hash_type = hash_type.lower()

    if isinstance(data, dict) or isinstance(data, list):
        data = json.dumps(data)
    if isinstance(data, int):
        data = str(data)
    if isinstance(data, str):
        data = data.encode("utf-8")
    if hash_type.lower() == 'md5':
        md = hashlib.md5()
    elif hash_type == 'sha1' or hash_type == 'sha-1':
        md = hashlib.sha1()
    elif hash_type == 'sha256' or hash_type == 'sha-256':
        md = hashlib.sha256()
    elif hash_type == 'sha384' or hash_type == 'sha-384':
        md = hashlib.sha384()
    elif hash_type == 'sha512' or hash_type == 'sha-512':
        md = hashlib.sha512()
    else:
        md = hashlib.md5()
    md.update(data)
    if c_type == 0:
        return md.hexdigest()
    elif c_type == 1:
        return md.digest()


def compute_md5(data):
    """
    计算输入数据的 MD5 哈希，支持字典或字符串。
    字典会序列化为 JSON 字符串（所有层级键排序）后计算哈希。

    Args:
        data: 输入数据，类型为 dict 或 str。

    Returns:
        str: MD5 哈希值（十六进制）。

    Raises:
        TypeError: 如果输入类型不是 dict 或 str。
    """
    import json
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False, sort_keys=True)
    elif isinstance(data, str):
        data = data

    # 计算 MD5 哈希
    return get_md5(data)
