# coding=utf-8

import requests
import json
import time
import datetime
import common_func
from xml.sax.saxutils import unescape
import re
import os
import logging
import threading


class QueryRedash:
    def __init__(self, redash_data, query_name=None, is_log=1, log_path='E:\\log'):
        """
        redash连接信息，及日志打印存放地址
        :param redash_data string/redash执行信息
        :param query_name string/查询名称,用作日志文件名
        :param is_log int/是否打印日志
        :param log_path string/日志存储地址
        :return:
        """

        self.fail_date = []
        self.session_opener = requests.session()
        self.exec_date = datetime.datetime.now().strftime('%Y%m%d')
        self.session_url = redash_data['ip'] + redash_data['session_path']
        self.login_url = redash_data['ip'] + redash_data['login_path']
        self.query_url = redash_data['ip'] + redash_data['query_path']
        self.watch_url = redash_data['ip'] + redash_data['watch_path']
        self.results_url = redash_data['ip'] + redash_data['result_path']

        self.login_data = {
            'email': redash_data['username'],
            'password': redash_data['password']
        }
        self.query_results_data = {
            'data_source_id': 56,
            'max_age': 0,
            'query': "select 1"
        }
        self.execute_data = {
            'action': "execute",
            'object_type': "query",
            'time': time.time()
        }

        self.headers = {
            'Referer': redash_data['ip'] + redash_data['new_path'],
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3472.3 Safari/537.36',
            'Content-Type': 'application/json;charset=UTF-8'
        }

        # 声明日志
        if is_log == 1:
            if query_name is None or query_name.strip() == '':
                self.file_name = 'redash_{0}'.format(self.exec_date)
            else:
                self.file_name = 'redash_{0}_{1}'.format(query_name, self.exec_date)
            common_func.log(self.file_name, log_path)
        else:
            pass

    def login(self):
        self.session_opener.post(url=self.login_url, data=self.login_data)
        session_results = self.session_opener.get(url=self.session_url)
        if session_results.status_code == 200:
            return True
        else:
            return False

    def query(self, exec_sql=None, download_path=None, exec_date=None):
        """
        查询提交
        :param exec_sql:执行sql/string
        :param download_path:数据下载地址/string
        :param exec_date:执行时间，用作日志区分/string
        :return: status:执行状态
        """
        # 查询开始
        start_time = datetime.datetime.now()

        # 参数设置
        self.query_results_data['query'] = exec_sql
        result_data = None

        # 向服务器提交sql
        query_results = self.session_opener.post(url=self.query_url, data=json.dumps(self.query_results_data),
                                                 headers=self.headers)
        # 执行状态判断1:查询等待中 2：查询执行中 3：查询结束并返回结果 4：查询取消或失败
        status = 1
        if query_results.status_code == 200:
            watch_id = json.loads(query_results.content)['job']['id']
            logging.info("<result_id:{0}> {1} 提交成功".format(watch_id, exec_date))
            while status < 3:
                watch_data = self.session_opener.get(url=self.watch_url.format(watch_id))
                if watch_data.status_code == 200:
                    # 获取当前执行状态码
                    status = json.loads(watch_data.content)['job']['status']
                else:
                    logging.warning("<result_id:{0}> {1}网络请求返回码:{2}".
                                    format(watch_id, exec_date, watch_data.status_code))
                # 3秒刷新
                time.sleep(3)
            else:
                if status == 3:
                    query_results_data = self.session_opener.get(
                        url=self.results_url.format(json.loads(watch_data.content)['job']['query_result_id']))
                    result = json.loads(query_results_data.content)['query_result']['data']
                    result_columns = [i['friendly_name'] for i in result['columns']]
                    result_data = [[i[j] for j in result_columns] for i in result['rows']]
                    logging.info("<result_id:{0}> {1} 执行成功".format(watch_id, exec_date))
                elif status == 4:
                    logging.warning("<result_id:{0}> {1} 执行失败".format(watch_id, exec_date))
                    logging.warning("<result_id:{0}> {1} error:{2}".
                                    format(watch_id, exec_date, json.loads(watch_data.content)['job']['error']))
                    self.fail_date.append(exec_date)
        else:
            logging.warning("{0} {1}网络请求返回码:{2}".format(exec_date, self.query_url, query_results.status_code))

        if download_path is None or re.search(r"(create|drop|insert)", exec_sql) is not None or status != 3:
            pass
        else:
            result_text = ''
            for result_value in result_data:
                result_text = result_text + '\n' + '\t'.join([str(i) for i in result_value])
            if not os.path.exists(download_path):
                os.mkdir(download_path)
            file_path = '{0}/{1}.txt'.format(download_path, self.file_name)

            if not os.path.exists(file_path):
                result_text = '\t'.join(result_columns) + result_text
            result_text = unescape(result_text).replace('&nbsp;', ' ')
            result_file = open(file_path, 'a+', encoding='utf-8')
            result_file.write(result_text)
            result_file.close()
            logging.info("<result_id:{0}> {1} 数据下载成功".format(watch_id, exec_date))

        # 查询结束
        end_time = datetime.datetime.now()
        logging.info("<result_id:{0}> {1} 查询耗时:{2}".format(watch_id, exec_date, str(end_time-start_time)))

    def query_thread(self, exec_sql, start_date, end_date,
                     step=1, date_format='%Y%m%d', step_type='day', thread_num=2, download_path=None):
        """
        多线程执行提交sql
        :param start_date: int,string/开始日期
        :param end_date: int,string/结束日期
        :param step: int/时间跨度，默认1
        :param date_format: string/输入输出的时间格式，默认'%Y%m%d'
        :param step_type: string/时间跨度周期类型，默认'day',否则为'month'
        :param thread_num: int/线程数
        :param download_path: string/结果下载路径，None表示不进行下载操作
        :param query_name: string/本次查询名称，将作为保存文件的文件名（同名则数据结果合并保存）
        :return: 无，结果集以文件形式写入
        """
        # 线城开始
        start_time = datetime.datetime.now()

        # 前置判断
        if exec_sql is None:
            logging.error('所提交的sql为空')
            exit(-1)

        # 声明参数
        cnt_num = 0
        # 此处的date_format与输入的时间格式一致，如果后期输入的日期格式固定，这里就需要先对start_date/end_date处理成date_format格式（果）
        exec_date_list = common_func.exec_date(start_date=start_date, end_date=end_date, step=step,
                                               date_format=date_format, step_type=step_type)
        exec_date_num = len(exec_date_list)

        self.login()
        logging.info(exec_sql)
        for exec_date_value in exec_date_list:
            # 此处的date_format与输出的时间格式一致（因）
            exec_sql_value = common_func.sql_format(exec_sql=exec_sql, exec_date=exec_date_value,
                                                    date_format=date_format)
            query_threading = threading.Thread(name=self.file_name, target=self.query,
                                               args=(exec_sql_value, download_path, exec_date_value))
            cnt_num = cnt_num + 1
            logging.info("当前执行日期:{0},提交进度{1}%".format(exec_date_value, round(1.0*cnt_num/exec_date_num*100, 2)))
            query_threading.start()
            if cnt_num % thread_num == 0:
                query_threading.join()
            # 避免提交过快导致提交重复
            time.sleep(1)
        query_threading.join()
        # time.sleep(1)

        # 线程结束
        end_time = datetime.datetime.now()
        if len(self.fail_date) > 0:
            logging.info("本次执行中查询失败的日期:{0}".format(",".join(self.fail_date)))
        logging.info(u"{0} 累计耗时 {1}".format(self.file_name, str(end_time-start_time)))
        logging.info("The end is the beginning!")

    def cancel(self, result_id):
        # 配置查询信息
        cancel_rep = self.session_opener.delete(url=self.watch_url.format(result_id))
        if cancel_rep.status_code == 200:
            logging.info("<result_id:{0}> 任务自杀成功".format(result_id))
            return 1
        else:
            logging.warning("<result_id:{0}> 任务自杀失败".format(result_id))
            return 0


if __name__ == '__main__':
    import configparser
    link_info = configparser.ConfigParser()
    link_info.read(os.getcwd()+'/gui/link_info.ini')
    redash_data = dict(link_info.items('redash'))
    redash_data['ip'] = ''
    redash_data['username'] = ''
    redash_data['password'] = ''
    redash = QueryRedash(redash_data, '123')
    redash.login()
    redash.query_thread('select 123', '2018-12-12', '2018-12-12', 1, '%Y-%m-%d', 'day', 2, 'C:\\Users\\ernes\\Desktop')
