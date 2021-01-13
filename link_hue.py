# coding=utf-8

import json
import logging
import math
import os
import re
import threading
import time
import datetime
import requests
from xml.sax.saxutils import unescape
import common_func


class QueryHue:
    """
    exit备注（-1:提交参数错误，1：sql错误，0：系统错误）
    """
    def __init__(self, hue_data, query_name=None, is_log=1, log_path='E:\\log'):
        """
        :param hue_data map/hue执行信息
        :param query_name string/当前查询名称
        :param is_log int/日志启动开关，防止日志错乱
        :param log_path string/日志保存路径
        :return
        """
        # 声明参数
        self.exec_date = datetime.datetime.now().strftime('%Y%m%d')
        # 登录前的csrf中间token值 csrfmiddlewaretoken
        self.csrf_url = hue_data['ip'] + hue_data['csrf_path']
        # csrf的token值
        self.login_url = hue_data['ip'] + hue_data['login_path']
        # sql校验
        self.explain_url = hue_data['ip'] + hue_data['explain_path']
        # sql执行
        self.execute_url = hue_data['ip'] + hue_data['execute_path']
        # sql监控，是否正常执行
        self.watch_url = hue_data['ip'] + hue_data['watch_path']
        # sql结果集
        self.result_url = hue_data['ip'] + hue_data['result_path']
        # sql自杀
        self.cancel_url = hue_data['ip'] + hue_data['cancel_path']
        # 当前用户的query任务
        self.get_running_url = hue_data['ip'] + hue_data['get_running_path']

        self.login_data = {
            "username": hue_data['username'],
            "password": hue_data['password'],
            "next": "/"
        }
        self.csrf_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Origin": hue_data['ip'],
            "Referer": self.csrf_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36"
        }
        self.execute_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": hue_data['ip'],
            "Referer": hue_data['ip'] + hue_data['beeswax_path'],
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36",
        }
        self.download_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36",
        }
        self.execute_data = {
            "query-query": "select 'test'",
            "query-database": hue_data['query-database'],
            "settings-next_form_id": 0,
            "file_resources-next_form_id": 0,
            "functions-next_form_id": 0,
            "query-email_notify": "false",
            "query-is_parameterized": "true"
        }
        self.watch_data = {
            "query-query": "select 'test'",
            "query-database": hue_data['query-database'],
            "log-start-over": "true",
            "settings-next_form_id": 0,
            "file_resources-next_form_id": 0,
            "functions-next_form_id": 0,
            "query-email_notify": "false",
            "query-is_parameterized": "true"
        }
        self.session_opener = requests.session()

        # 声明结果集传值
        self.csrf_token = None
        self.result = None
        self.result_id_list = {}

        # 声明日志
        if is_log == 1:
            if query_name is None or query_name.strip() == '':
                self.file_name = 'hue_{0}'.format(self.exec_date)
            else:
                self.file_name = 'hue_{0}_{1}'.format(query_name, self.exec_date)
            common_func.log(self.file_name, log_path)
        else:
            pass

    def login(self):
        """
        链接登录hue
        :return:
        """
        # 获取 csrfmiddlewaretoken
        csrf_req = self.session_opener.get(self.csrf_url)
        csrf_req_context = csrf_req.text
        csrfmiddlewaretoken = re.search(r"csrfmiddlewaretoken' value='(.*)' />", csrf_req_context).group(1)
        # GUI登录判断
        try:
            # 登录hue,获取新cookie的csrftoken
            self.login_data['csrfmiddlewaretoken'] = csrfmiddlewaretoken
            login_req = self.session_opener.post(url=self.login_url, data=self.login_data, headers=self.csrf_headers)
            login_req_text = login_req.text
            if re.search('errorlist', login_req_text):
                raise Exception(re.search(r'errorlist.*"><li>(.+?)</li>', login_req_text).group(1))
            self.csrf_token = login_req.cookies['csrftoken']
            self.execute_headers['X-CSRFToken'] = self.csrf_token
            self.session_opener.post(url=self.explain_url, data=self.execute_data, headers=self.execute_headers)
            return True
        except Exception as e:
            logging.debug('login-{0}'.format(e))
            return False

    def explain(self, exec_sql=None):
        self.login()
        # 配置查询信息
        self.execute_headers['X-CSRFToken'] = self.csrf_token
        if exec_sql is None:
            logging.error('所提交的sql为空')
        else:
            self.execute_data['query-query'] = exec_sql

        # 校验sql
        explain_req = self.session_opener.post(url=self.explain_url, data=self.execute_data, 
                                               headers=self.execute_headers)
        explain_reuslt = json.loads(explain_req.text)
        if explain_reuslt['status'] == 0:
            logging.info("校验通过")
        else:
            logging.error(explain_reuslt['message'])

    def watch(self, result_id, exec_date=None):
        is_failure = False
        is_success = False
        watch_cnt = 0
        while is_success is not True and is_failure is not True and watch_cnt < 2:
            watch_req = self.session_opener.get(url=self.watch_url.format(result_id), headers=self.execute_headers)
            if watch_req.status_code == 200:
                try:
                    watch_result = json.loads(watch_req.text)
                    is_success = common_func.is_true(watch_result['isSuccess'])
                    is_failure = common_func.is_true(watch_result['isFailure'])
                    # print(watch_result)
                    # print(is_failure, is_success)
                    # print(is_success is not True and is_failure is not True)
                    # logging.info("查询结果：{0},{1}".format(is_finished, result_data))
                except Exception as e:
                    logging.error('{2} watch-{0},{1}'.format(e, self.watch_url.format(result_id), exec_date))
                    watch_cnt += 1
            else:
                logging.error("{2} watch-url:{0},{1}".format(self.watch_url.format(result_id),
                                                             str(watch_req.status_code), exec_date))
                watch_cnt += 1
            time.sleep(5)
        # logging.info("查询结果：{0}".format(result['is_finished']))
        return [is_success, is_failure]

    def query(self, exec_sql=None, is_explain=0, download_path=None, exec_date=None, download_file_name=None):
        """
        向hue提交sql，并以list格式返回数据结果
        :param exec_sql: string/所要查询的sql
        :param is_explain: int/是否在查询前校验sql,默认为0 不进行校验
        :param download_path: string/结果下载路径，None表示不进行下载操作
        :param exec_date: string/仅在多线程中有实际意义
        :param download_file_name: string/结果下载保存用的文件名
        :return: list/返回数据结果
        """
        # 查询开始
        start_time = datetime.datetime.now()
        self.login()

        # 配置查询信息
        self.execute_headers['X-CSRFToken'] = self.csrf_token
        if exec_sql is None:
            logging.error('所提交的sql为空')
            exit(-1)
        else:
            self.execute_data['query-query'] = exec_sql
            self.watch_data['query-query'] = exec_sql
            if re.search('(insert|create) ', exec_sql.lower()) is not None:
                is_skip_load = 1
            else:
                is_skip_load = 0

        # 校验sql
        if type(is_explain) is not int:
            logging.error("参数错误：is_explain is int")
            exit(-1)
        elif is_explain == 1:
            self.explain(exec_sql)
        else:
            pass

        # 提交sql,并获取result_id
        commit_num = 0
        while commit_num < 3:
            commit_num += 1
            execute_req = self.session_opener.post(url=self.execute_url, data=self.execute_data,
                                                   headers=self.execute_headers)
            if execute_req.status_code == 200:
                try:
                    execute_result = json.loads(execute_req.text)
                except:
                    logging.error('<error_date:{0}> error_info:{1}'.format(exec_date, 'json解析错误'))
                    self.login()
                    continue
                if execute_result['status'] == 0:
                    result_id = execute_result['id']
                    if commit_num > 1:
                        logging.info('<result_id:{0}> {1} 重新提交成功'.format(result_id, exec_date))
                    else:
                        logging.info('<result_id:{0}> {1} 提交成功'.format(result_id, exec_date))
                    self.result_id_list[result_id] = 0
                    break
            else:
                time.sleep(3)
                continue
        else:
            logging.error('{0} 提交失败'.format(exec_date))
            exit(1)

        # 获取结果信息
        tmp_data = []
        result_data = []
        result_columns = []
        i = 0
        watch_result = self.watch(result_id)
        is_success = watch_result[0]
        is_failure = watch_result[1]
        if is_success is True:
            logging.info("<result_id:{0}> {1} 执行成功".format(result_id, exec_date))
            self.result_id_list[result_id] = 1
            if is_skip_load == 0:
                while tmp_data != [] or i == 0:
                    if i == 0:
                        logging.info("<result_id:{0}> {1} 数据加载中...".format(result_id, exec_date))
                    # 页面数据预加载上限100
                    result_req = self.session_opener.get(url=self.result_url.format(result_id, i*100))
                    result = json.loads(result_req.text)
                    tmp_data = result['results']
                    result_data += tmp_data
                    result_columns = result['columns']
                    i += 1
                logging.info("<result_id:{0}> {1} 数据加载成功".format(result_id, exec_date))
        else:
            logging.info("<result_id:{0}> {1} 执行失败".format(result_id, exec_date))
            self.result_id_list[result_id] = -1

        if download_path is None or download_path == '' or result_data == [] or is_failure is True:
            pass
        else:
            # 每1000条写入一次数据
            max_col_num = len(result_data)
            if max_col_num > 5000:
                logging.info("<result_id:{0}> {1} {2}条数据写入中...".format(result_id, exec_date, max_col_num))
            for_num = int(math.ceil(max_col_num/1000))
            for for_i in range(for_num):
                result_text = ''
                for result_value in result_data[for_i*1000: min(for_i*1000+1000, max_col_num)]:
                    result_text = result_text + '\n' + '\t'.join([str(i) for i in result_value])
                if not os.path.exists(download_path):
                    os.mkdir(download_path)
                if download_file_name is None:
                    file_path = '{0}/{1}.txt'.format(download_path, self.file_name)
                else:
                    file_path = '{0}/{1}.txt'.format(download_path, download_file_name)
                if not os.path.exists(file_path):
                    result_text = '\t'.join([i['name'] for i in result_columns]) + result_text
                result_text = unescape(result_text).replace('&nbsp;', ' ')
                result_file = open(file_path, 'a+', encoding='utf-8')
                result_file.write(result_text)
                result_file.close()
                # logging.info("<result_id:{0}> {1} 数据写入进度{2}%".
                #              format(result_id, exec_date, 100.0*min(for_i*1000+1000, max_col_num)/max_col_num))
            logging.info("<result_id:{0}> {1} 数据写入成功【{2}】".format(result_id, exec_date, str(max_col_num)))

        # 后期数据操作备用
        self.result = result_data
        self.result.insert(0, [i['name'] for i in result_columns])

        # 查询结束
        end_time = datetime.datetime.now()
        logging.info("<result_id:{0}> {2} 耗时 {1}".format(result_id, str(end_time-start_time), exec_date))
        return self.result

    def query_thread(self, exec_sql, exec_date_list, date_format, thread_num=2, download_path=None):
        """
        多线程执行提交sql
        :param exec_sql: string/待执行的sql
        :param exec_date_list: list/待执行日期组
        :param date_format: string/输入输出的时间格式，默认'%Y%m%d'
        :param thread_num: int/线程数
        :param download_path: string/结果下载路径，None表示不进行下载操作
        :return: 无，结果集以文件形式写入
        """
        # 线程开始
        start_time = datetime.datetime.now()

        # 前置判断
        if exec_sql is None:
            logging.error('所提交的sql为空')
            exit(-1)

        # 声明参数
        cnt_num = 0
        exec_date_num = len(exec_date_list)
        query_threading_list = []
        self.login()
        logging.info(exec_sql)
        for exec_date_value in exec_date_list:
            # 此处的date_format与输出的时间格式一致（因）
            exec_sql_value = common_func.sql_format(exec_sql=exec_sql, exec_date=exec_date_value,
                                                    date_format=date_format)
            query_threading = threading.Thread(target=self.query, args=(exec_sql_value, 0, download_path,
                                                                        exec_date_value))
            cnt_num = cnt_num + 1
            logging.info("当前执行日期:{0} 提交进度{1}%".format(exec_date_value, round(1.0*cnt_num/exec_date_num*100, 2)))
            query_threading.start()
            if cnt_num % thread_num == 0:
                query_threading.join()
            # 避免提交过快导致提交重复
            time.sleep(3)
        query_threading.join()
        # time.sleep(1)

        # 线程结束
        end_time = datetime.datetime.now()
        logging.info(u"{0} 累计耗时 {1}".format(self.file_name, str(end_time-start_time)))
        logging.info("The end is the beginning!\n")

    def cancel(self, result_id):
        # 配置查询信息
        self.execute_headers['X-CSRFToken'] = self.csrf_token

        cancel_rep = self.session_opener.post(url=self.cancel_url.format(result_id), headers=self.execute_headers)
        if cancel_rep.status_code == 200:
            logging.info("<result_id:{0}> 任务自杀成功".format(result_id))
            return 1
        else:
            logging.warning("<result_id:{0}> 任务自杀失败".format(result_id))
            return 0

    def get_running(self):
        # 获取当前用户正在执行的查询
        running_data = self.session_opener.get(url=self.get_running_url, headers=self.execute_headers)
        if running_data.status_code == 200:
            result = running_data.text
        else:
            result = running_data.status_code
        return result


if __name__ == '__main__':
    import configparser
    import common_func
    link_info = configparser.ConfigParser()
    link_info.read(os.getcwd()+'/gui/link_info.ini')
    hue_info = dict(link_info.items('hue'))
    hue_info['username'] = common_func.encryption(hue_info['username'], 0)
    hue_info['password'] = common_func.encryption(hue_info['password'], 0)
    hue = QueryHue(hue_info, '123')
    print(hue.login())
    # exec_sql=None, is_explain=0, download_path=None, exec_date=None, download_file_name=None
    sql = """
insert  overwrite table db_tag.dwd_user_follow_stock_tag_dd partition (hp_stat_date = '#-1#')
select  a.user_id,
        a.last_visit_time, --最后查看时间
        a.is_optional, --是否加入自选股
        a.optional_time, --加入自选股时间
        a.is_remind, --是否设置预警
        a.stock_id, --股票id
        a.stock_name, --股票名称
        a.optional_cnt as optional_cnt, --个股关注度总数
        a.visit_cnt_7d as visit_cnt_7d, --最近一周查看次数
        a.frequency, --使用频次
        cast(case when abs((a.score - a.avg_score) / a.stdp_score) > 2 then sign((a.score - a.avg_score) / a.stdp_score) * 2 * 25 + 50 else(a.score - a.avg_score) / a.stdp_score * 25 + 50
                   end as string) as percent, --百分制
        score, --原分值
        a.market_id, --市场id
        a.sec_type, --证券类型
        a.rn, --排名
        current_timestamp() as insert_time --插入时间
  from  (
        select  a.user_id,
                a.scode_id as stock_id,
                b.market_id,
                b.sec_type,
                b.name as stock_name,
                a.last_visit_time,
                case when a.is_optional = 1 then '是' else '否' end as is_optional,
                a.optional_time,
                null as is_remind,
                a.optional_cnt,
                a.visit_cnt_7d,
                case when a.visit_cnt_7d < 3 then '低频率'
                     when a.visit_cnt_7d < 9 then '中频率'
                     else '高频率' end as frequency,
                162 + a.ld_score + a.vc_score + a.cc_score + a.ctc_score + a.tc_score + a.io_score + a.iov_score as score,
                avg(162 + a.ld_score + a.vc_score + a.cc_score + a.ctc_score + a.tc_score + a.io_score + a.iov_score) over (partition by 1) as avg_score,
                stddev_pop(162 + a.ld_score + a.vc_score + a.cc_score + a.ctc_score + a.tc_score + a.io_score + a.iov_score) over (partition by 1) as stdp_score,
                row_number() over (partition by a.user_id order by 162 + a.ld_score + a.vc_score + a.cc_score + a.ctc_score + a.tc_score + a.io_score + a.iov_score desc, a.last_visit_time desc, a.optional_time desc) as rn
          from  (
                select  a.user_id,
                        a.scode_id,
                        a.last_visit_time,
                        a.is_optional,
                        a.optional_time,
                        a.optional_cnt,
                        a.visit_cnt_7d,
                        case when a.level_days <= 0 then 181
                             when a.level_days <= 4 then 6
                             when a.level_days <= 5 then - 40
                             when a.level_days <= 6 then - 97
                             when a.level_days <= 7 then - 139
                              end as ld_score,
                        case when a.visit_cnt_7d <= 0 then - 96
                             when a.visit_cnt_7d <= 1 then - 50
                             when a.visit_cnt_7d <= 2 then 15
                             when a.visit_cnt_7d <= 3 then 53
                             when a.visit_cnt_7d <= 8 then 114
                             else 217 end as vc_score,
                        case when a.change_cnt_7d <= 0 then - 5
                             when a.change_cnt_7d <= 1 then 10
                             else 22 end cc_score,
                        case when a.click_tar_cnt_7d <= 0 then - 1 else 38 end ctc_score,
                        case when a.times_cnt_7d <= 0 then - 65
                             when a.times_cnt_7d <= 1 then - 22
                             when a.times_cnt_7d <= 2 then 50
                             else 125 end as tc_score,
                        case when a.is_optional = 0 then - 203 else 75 end as io_score,
                        case when a.is_optional_visit = 0 then - 1 else 25 end as iov_score
                  from  (
                        select  coalesce(a.user_id, b.user_id) as user_id,
                                coalesce(a.scode_id, b.sdtseccode) as scode_id,
                                coalesce(a.level_days, 7) as level_days,
                                coalesce(a.visit_days_7d, 0) as visit_days_7d,
                                coalesce(a.visit_cnt_7d, 0) as visit_cnt_7d,
                                coalesce(a.change_cnt_7d, 0) as change_cnt_7d,
                                coalesce(a.click_tabbar_cnt_7d, 0) as click_tabbar_cnt_7d,
                                coalesce(a.click_tar_cnt_7d, 0) as click_tar_cnt_7d,
                                coalesce(a.times_cnt_7d, 0) as times_cnt_7d,
                                case when b.sdtseccode is not null then 1 else 0 end as is_optional,
                                coalesce(b.optional_time, '') as optional_time,
                                coalesce(a.last_visit_time, '') as last_visit_time,
                                coalesce(b.optional_cnt, 0) as optional_cnt,
                                coalesce(b.is_optional_visit, 0) as is_optional_visit
                          from  (
                                select  user_id,
                                        scode_id,
                                        max(createtime) as last_visit_time,
                                        min(datediff(date_sub(to_date('#0#'), 1), hp_stat_date)) as level_days,
                                        count(distinct hp_stat_date) as visit_days_7d,
                                        count(case when objects rlike '\\.\\d*(now|day|week|month|min)$' then 1 end) as change_cnt_7d,
                                        count(distinct case when date_format(createtime, 'HH:mm:ss') between '09:30:00' and '11:30:00' then concat(hp_stat_date, '2')
                                                            when date_format(createtime, 'HH:mm:ss') between '13:30:00' and '15:00:00' then concat(hp_stat_date, '2')
                                                            else concat(hp_stat_date, '3') end) as times_cnt_7d,
                                        count(case when objects = 'gzg_fenshi' and action_type = 0 then 1 end) as visit_cnt_7d,
                                        count(case when objects rlike '^gzg_fenshi\\.tabbar' then 1 end) as click_tabbar_cnt_7d,
                                        count(case when objects rlike '^gzg_fenshi\\.tar\\.\\d+\\.change' then 1 end) as click_tar_cnt_7d
                                  from  pdw.fact_stock_client_log
                                 where  hp_stat_date >= date_sub(to_date('#0#'), 7)
                                   and  hp_stat_date <= date_sub(to_date('#0#'), 1)
                                   and  tenant_id = 'YYZQZX'
                                   and  start_object = 'gzg_fenshi'
                                   and  user_id <> 0
                                   and  scode_id is not null
                                 group  by user_id,
                                        scode_id
                                ) a
                          full  join (
                                select  a.user_id,
                                        a.sdtseccode,
                                        a.optional_time,
                                        case when c.user_id is not null then 1 else 0 end as is_optional_visit,
                                        count(1) over (partition by a.user_id) as optional_cnt
                                  from  (
                                        select  user_id,
                                                sdtseccode,
                                                max(start_time) as optional_time
                                          from  db_temp_dt.t_optional_shares_his_news
                                         where  user_id rlike '^\\d+$'
                                           and  user_id <> 0
                                           and  to_date(start_time) <= date_sub(to_date('#0#'), 1)
										   and  to_date(end_time) >= date_sub(to_date('#0#'), 7)
										 group  by user_id,
												sdtseccode
                                        ) a
                                 inner  join (
                                        select  user_id
                                          from  pdw.fact_cnt_stock_login_log
                                         where  hp_stat_date >= date_sub(to_date('#0#'), 7)
                                           and  hp_stat_date <= date_sub(to_date('#0#'), 1)
                                           and  tenant_id = 'YYZQZX'
                                           and  user_id <> 0
                                         group  by user_id
                                        ) b
                                    on  a.user_id = b.user_id
                                  left  join (
                                        select  user_id
                                          from  pdw.fact_stock_client_log
                                         where  hp_stat_date >= date_sub(to_date('#0#'), 7)
                                           and  hp_stat_date <= date_sub(to_date('#0#'), 1)
                                           and  tenant_id = 'YYZQZX'
                                           and  start_object = 'gzg_zixuan'
                                           and  user_id <> 0
                                           and  scode_id is not null
                                         group  by user_id
                                        ) c
                                    on  a.user_id = c.user_id
                                ) b
                            on  a.user_id = b.user_id
                           and  a.scode_id = b.sdtseccode
                        ) a
                ) a
         inner  join (
                select  code,
                        name,
           				market_id,
           			    sec_type
                  from  pdw.dim_stock_dict
                 where  sec_type in ('01', '07')
                   and  status = 1
                ) b
            on  a.scode_id = b.code
        ) a
 where  a.rn <= 10;
    """
    date_list = ['2020-03-27', '2020-06-28', '2020-08-12']
    hue.query_thread(exec_sql=sql, exec_date_list=date_list, date_format="%Y-%m-%d", thread_num=3)
    # hue.explain(exec_sql="select 123")
    # hue.watch('11705')
