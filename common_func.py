# coding=utf-8

import datetime
import re
import logging
import os
import winreg
import requests
import json


def exec_date(start_date, end_date, step=1, date_format='%Y%m%d', step_type='day'):
    """
    执行日期列表
    :param start_date: int,string/开始日期
    :param end_date: int,string/结束日期
    :param step: int/时间跨度，默认1
    :param date_format: string/输入输出的时间格式，默认'%Y%m%d'
    :param step_type: string/时间跨度周期类型，默认'day',否则为'month'(返回每月的第一天)
    :return: list/执行日期列表
    """
    exec_date_list = []
    tmp_date_list = []
    try:
        start_date = datetime.datetime.strptime(str(start_date), date_format)
        end_date = datetime.datetime.strptime(str(end_date), date_format)
    except Exception as error_info:
        return error_info
    diff_days = (end_date - start_date).days
    if step_type == 'day':
        strf_format = date_format
    else:
        strf_format = re.sub('%d', '01', date_format)
    for i in range(diff_days+1):
        tmp_date = start_date+datetime.timedelta(days=i)
        tmp_date_list.append(tmp_date.strftime(strf_format))
    tmp_date_list = list(set(tmp_date_list))
    if step > 0:
        sign = 0
    else:
        sign = 1
    tmp_date_list.sort(reverse=sign)
    tmp_days = len(tmp_date_list)
    for j in range(0, tmp_days, abs(step)):
        exec_date_list.append(tmp_date_list[j])
    return exec_date_list


# 示例
# print(exec_date(start_date='2018-0501', end_date='2018-0705', date_format='%Y%m%d', step_type='month'))


def sql_format(exec_sql, exec_date, date_format='%Y%m%d'):
    """
    sql日期反转义
    :param exec_sql: 格式化sql
    :param exec_date: 执行日期
    :param date_format: 日期格式
    :return: 应执行的sql
    """
    re_list = re.findall('#(-?\d+)#', exec_sql)
    for i in re_list:
        exec_sql = re.sub('#{0}#'.format(i),
                          (datetime.datetime.strptime(str(exec_date), date_format)
                           + datetime.timedelta(days=int(i))).strftime(date_format), exec_sql)
    exec_sql = re.sub(r'\\', r'\\', exec_sql)

    return exec_sql


# # 示例
# sql = "create table db_test.wq_dws_user_page_online_state_dd_#0#"
# print(sql_format(sql, '2018-05-01', date_format='%Y-%m-%d'))


def log(file_name=None, file_path='E:\\log'):
    """
    日志，如果文件路径不为空，则将logging产生的日志保存到文件
    :param file_name string/日志文件名
    :param file_path string/日志文件夹
    :return
    """
    formatter = logging.Formatter('%(asctime)s [%(filename)s:%(funcName)s line:%(lineno)d] [%(levelname)s]: %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger('')
    logger.setLevel(logging.INFO)

    # 限定当前环境下只允许不超过一个流对象
    while len(logger.handlers) > 1:
        logger.handlers.pop()

    # 新建log文件夹
    if os.path.isdir(file_path):
        pass
    else:
        os.mkdir(file_path)

    # 声明控制台打印
    console_log = logging.StreamHandler()
    # console_log.setLevel(logging.DEBUG)
    console_log.setFormatter(formatter)
    logger.addHandler(console_log)

    if file_name is not None:
        # 声明文件打印
        file_log = logging.FileHandler("{0}/{1}.log".format(file_path, file_name), 'a')
        # file_log.setLevel(logging.DEBUG)
        file_log.setFormatter(formatter)
        logger.addHandler(file_log)
# # 示例
# log()
# logging.error('2131231')
# logging.info('2131231')
# logging.warning('2131231')


def encryption(crypt, mode=1):
    """
    自定义加密，将每个字符进行ascii码表变换成十进制，然后按照最后一个字符的整除3的余数，将字符后移，然后再进行ascii码表变换
    :param crypt string/待处理字符串
    :param mode int/加解密方式
    :return 加/解密文
    """
    if mode == 1:
        tmp = list(crypt)
        tmp_ord = [ord(i) for i in tmp]
        tmp_ord_change = [i - tmp_ord[-1] % 3 for i in tmp_ord]
        tmp_ord_change_chr = [chr(i) for i in tmp_ord_change]
        tmp_ord_change_chr.insert(1, str(tmp_ord[-1] % 3))
        result = ''.join(tmp_ord_change_chr)
    elif mode == 0:
        tmp = list(crypt)
        magic_num = int(tmp[1])
        tmp.pop(1)
        tmp_ord = [ord(i) for i in tmp]
        tmp_ord_change = [i + magic_num for i in tmp_ord]
        result = ''.join([chr(i) for i in tmp_ord_change])
    else:
        result = "加解密方式选择错误"
        exit()
    return result
# 示例
# print encryption('wan gqiang')
# print(encryption('1023456', 0))


def get_desktop_path():
    """
    获取桌面路径
    :return: string/桌面路径
    """
    # 利用系统的注册表
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
    # 返回的是Unicode类型数据
    return winreg.QueryValueEx(key, "Desktop")[0]


def is_true(x):
    """
    如果x不为True则返回False
    :param x:
    :return:
    """
    if x in [True, 'True', 'true', 1, 'TRUE']:
        x = True
    else:
        x = False
    return x


def get_verse():
    """
    获取随机诗句
    """
    session_opener = requests.session()
    session_opener.verify = False
    verse_data = session_opener.get(url='http://v1.alapi.cn/api/shici')
    if verse_data.status_code == 200:
        verse_json = json.loads(verse_data.text)
        return "{0} \n                                           —— {1}".\
            format(re.search('([\u4E00-\u9FA5]|，)+', verse_json['data']['content']).group(),
                   verse_json['data']['author'])
    else:
        print(verse_data.status_code)

# print(get_verse())