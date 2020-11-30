# coding=utf-8


import logging
import os
import signal
import random
import re
import threading
import time
import datetime
import wx
import wx.stc as ws
import wx.adv as wa
import configparser
import common_func
import link_hue
import link_redash
from ping3 import ping


def thread_decorator(action_def):
    def action(self, event):
        tmp = threading.Thread(target=action_def, args=(self, event, ))
        tmp.start()
    return action


class MainGui(wx.Frame):
    def __init__(self, link_data, link_type):
        self.link_data = link_data
        self.link_type = link_type
        self.log_path = os.path.dirname(os.path.realpath(__file__))+"\\log"
        self.exec_date = datetime.datetime.now().strftime('%Y%m%d')
        self.is_cancel = 0
        main_app = wx.App()
        main_app.SetExitOnFrameDelete(True)
        super(MainGui, self).__init__(None, title='{0}客户端'.format(self.link_type.capitalize()), size=(800, 600),
                                      style=wx.DEFAULT_FRAME_STYLE)
        self.SetIcon(wx.Icon('image\\mqt.ico'))
        self.Center()
        self.main_panel = wx.Panel(self)

        # 控件定义
        # 预设参数
        self.date_format_list = ['%Y-%m-%d', '%Y%m%d']
        self.step_type_list = ['day', 'month']
        self.repair_list = []
        self.exec_fail_list = []
        self.submit_error_list = []
        self.submit_lose_list = []
        # 参数控件
        self.label_start_date = wx.StaticText(self.main_panel, label="开始日期")
        self.picker_start_date = wa.DatePickerCtrl(self.main_panel, id=-1, style=wa.DP_DROPDOWN | wa.DP_SHOWCENTURY)
        self.label_end_date = wx.StaticText(self.main_panel, label="结束日期")
        self.picker_end_date = wa.DatePickerCtrl(self.main_panel, id=-1, style=wa.DP_DROPDOWN | wa.DP_SHOWCENTURY)
        self.label_date_format = wx.StaticText(self.main_panel, label="时间格式")
        self.combobox_date_format = wx.ComboBox(self.main_panel, choices=self.date_format_list)
        self.combobox_date_format.SetSelection(0)
        self.label_thread_num = wx.StaticText(self.main_panel, label="   线程数")
        self.text_thread_num = wx.TextCtrl(self.main_panel, value="1")
        self.label_step_type = wx.StaticText(self.main_panel, label="跨度周期")
        self.choice_step_type = wx.Choice(self.main_panel, choices=self.step_type_list)
        self.choice_step_type.SetSelection(0)
        self.label_step = wx.StaticText(self.main_panel, label="时间跨度")
        self.text_step = wx.TextCtrl(self.main_panel, value="1")
        self.label_download_path = wx.StaticText(self.main_panel, label="下载路径")
        self.text_download_path = wx.TextCtrl(self.main_panel, value=common_func.get_desktop_path())
        self.label_query_name = wx.StaticText(self.main_panel, label="任务名称")
        self.text_query_name = wx.TextCtrl(self.main_panel)
        # sql控件
        self.label_sql = wx.StaticText(self.main_panel, label="SQL:")
        self.text_sql = ws.StyledTextCtrl(self.main_panel, style=wx.TE_MULTILINE | wx.HSCROLL | wx.TE_RICH)
        self.text_sql.SetValue("""SELECT '#0#' FROM pdw.pdw_account_settle  LIMIT 1""")
        self.text_sql.SetMarginType(1, ws.STC_MARGIN_NUMBER)
        self.text_sql.SetMarginWidth(1, 25)
        # log控件
        self.label_log = wx.StaticText(self.main_panel, label="LOG:")
        self.text_log = wx.TextCtrl(self.main_panel, style=wx.TE_MULTILINE | wx.HSCROLL | wx.TE_RICH | wx.TE_READONLY)
        self.text_log.SetFont(self.text_sql.GetFont())
        # 按钮控件
        self.button_explain = wx.Button(self.main_panel, label="校验")
        self.button_exec = wx.Button(self.main_panel, label="执行")
        self.button_cancel = wx.Button(self.main_panel, label="自杀")
        # help控件
        self.image_help = wx.Image("image\\help.png", wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        m = self.image_help.GetWidth()/self.label_sql.GetCharWidth()/2
        self.image_help = self.image_help.ConvertToImage().Scale(self.image_help.GetWidth()/m,
                                                                 self.image_help.GetHeight()/m)
        self.image_help = self.image_help.ConvertToBitmap()
        self.button_help = wx.BitmapButton(self.main_panel, bitmap=self.image_help, style=wx.BORDER_MASK)
        # 结束提醒
        self.check_finish = wx.CheckBox(self.main_panel, label="SQL结束提醒")
        # 进度控件
        self.label_gauge_total = wx.StaticText(self.main_panel, label="提交进度: ")
        self.gauge_total = wx.Gauge(self.main_panel, -1, 100)
        self.label_value_total = wx.StaticText(self.main_panel, label="{0}/{1}:{2}%".
                                               format(str(0).rjust(3), str(0).ljust(3), str(0.00).rjust(5)))
        # 错误线程修复对话框
        self.dialog_repair = wx.Dialog(self, title="修复", size=(250, 150),
                                       style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.CLOSE_BOX)
        # self.dialog_repair = wx.Dialog(self, title="修复", size=(250, 150), style=wx.DEFAULT_DIALOG_STYLE)
        self.dialog_repair.SetIcon(wx.Icon('image\\mqt.ico'))
        self.dialog_repair.Center()
        self.dialog_repair_panel = wx.Panel(self.dialog_repair)
        self.check_lose = wx.CheckBox(self.dialog_repair_panel, label="尚未提交")
        self.check_submit_error = wx.CheckBox(self.dialog_repair_panel, label="提交异常")
        self.check_fail = wx.CheckBox(self.dialog_repair_panel, label="执行错误")
        self.button_repair = wx.Button(self.dialog_repair_panel, label="重新提交")
        self.dialog_repair_vbox = wx.BoxSizer(wx.VERTICAL)
        self.dialog_repair_vbox.Add(self.check_lose, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=3)
        self.dialog_repair_vbox.Add(self.check_submit_error, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=3)
        self.dialog_repair_vbox.Add(self.check_fail, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=3)
        self.dialog_repair_vbox.Add(self.button_repair, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=3)
        self.dialog_repair_hbox = wx.BoxSizer()
        self.dialog_repair_hbox.Add(self.dialog_repair_vbox, proportion=1, flag=wx.ALIGN_CENTER)
        self.dialog_repair_panel.SetSizer(self.dialog_repair_hbox)

        logging.basicConfig(stream=self.text_log, format='%(asctime)s [%(levelname)s]: %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
        # logging.warning('123')

        # 绑定执行事件
        self.Bind(wx.EVT_CLOSE, self.is_close)
        self.button_explain.Bind(wx.EVT_BUTTON, self.sql_explain)
        self.button_exec.Bind(wx.EVT_BUTTON, self.sql_exec)
        self.button_cancel.Bind(wx.EVT_BUTTON, self.suicide)
        self.button_help.Bind(wx.EVT_ENTER_WINDOW, self.label_help_show)
        self.button_help.Bind(wx.EVT_LEAVE_WINDOW, self.label_help_close)
        self.button_repair.Bind(wx.EVT_BUTTON, self.repair)
        self.dialog_repair.Bind(wx.EVT_CLOSE, self.repair_close)

        # 页面布置
        main_hbox_config_1 = wx.BoxSizer()
        main_hbox_config_1.Add(self.label_start_date, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        main_hbox_config_1.Add(self.picker_start_date, proportion=1, flag=wx.RIGHT, border=5)
        main_hbox_config_1.Add(self.label_end_date, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        main_hbox_config_1.Add(self.picker_end_date, proportion=1, flag=wx.RIGHT, border=5)
        main_hbox_config_1.Add(self.label_date_format, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        main_hbox_config_1.Add(self.combobox_date_format, proportion=1, flag=wx.RIGHT, border=5)
        main_hbox_config_1.Add(self.label_thread_num, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        main_hbox_config_1.Add(self.text_thread_num, proportion=1)
        main_hbox_config_2 = wx.BoxSizer()
        main_hbox_config_2.Add(self.label_step_type, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        main_hbox_config_2.Add(self.choice_step_type, proportion=1, flag=wx.RIGHT, border=5)
        main_hbox_config_2.Add(self.label_step, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        main_hbox_config_2.Add(self.text_step, proportion=1, flag=wx.RIGHT, border=5)
        main_hbox_config_2.Add(self.label_download_path, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        main_hbox_config_2.Add(self.text_download_path, proportion=1, flag=wx.RIGHT, border=5)
        main_hbox_config_2.Add(self.label_query_name, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        main_hbox_config_2.Add(self.text_query_name, proportion=1)
        main_hbox_log = wx.BoxSizer()
        main_hbox_log.Add(self.label_log, proportion=1, flag=wx.ALIGN_LEFT)
        main_hbox_log.Add(self.check_finish, proportion=0, flag=wx.ALIGN_RIGHT)
        main_vbox_button = wx.BoxSizer(wx.VERTICAL)
        main_vbox_button.Add(self.button_explain, proportion=1)
        main_vbox_button.Add(self.button_exec, proportion=1)
        main_vbox_button.Add(self.button_cancel, proportion=1)
        main_hbox_button = wx.BoxSizer()
        main_hbox_button.Add(self.text_log, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=5)
        main_hbox_button.Add(main_vbox_button, proportion=0, flag=wx.EXPAND)
        main_hbox_sql = wx.BoxSizer()
        main_hbox_sql.Add(self.label_sql, proportion=1, flag=wx.ALIGN_LEFT)
        main_hbox_sql.Add(self.button_help, proportion=0, flag=wx.ALIGN_RIGHT)
        main_hbox_total_gauge = wx.BoxSizer()
        main_hbox_total_gauge.Add(self.label_gauge_total, proportion=0)
        main_hbox_total_gauge.Add(self.gauge_total, proportion=1)
        main_hbox_total_gauge.Add(self.label_value_total, proportion=0, flag=wx.LEFT | wx.RIGHT, border=7)
        main_vbox = wx.BoxSizer(wx.VERTICAL)
        main_vbox.Add(main_hbox_config_1, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=5)
        main_vbox.Add(main_hbox_config_2, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=5)
        main_vbox.Add(main_hbox_sql, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=5)
        main_vbox.Add(self.text_sql, proportion=3, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=5)
        main_vbox.Add(main_hbox_log, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT, border=5)
        main_vbox.Add(main_hbox_button, proportion=2, flag=wx.EXPAND | wx.TOP | wx.LEFT, border=5)
        main_vbox.Add(main_hbox_total_gauge, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                      border=5)
        self.main_panel.SetSizer(main_vbox)

        self.Show(True)
        main_app.MainLoop()

    def sql_explain(self, event):
        """hue sql检验"""
        query_name = self.text_query_name.GetValue()
        self.text_log.Clear()
        if self.link_type == 'hue':
            self.button_explain.SetLabel("校验...")
            sql = self.text_sql.GetValue()
            query_hue = link_hue.QueryHue(hue_data=self.link_data, query_name=query_name, log_path=self.log_path)
            query_hue.explain(sql)
            time.sleep(1)
            self.button_explain.SetLabel("校验")
        else:
            self.text_log.SetLabel("当前连接不支持sql校验")

    def thread_exec(self, exec_date_list, sql, date_format, query_mqt, download_path, thread_num):
        """
        多线程执行块
        :param exec_date_list:
        :param sql:
        :param date_format:
        :param query_mqt:
        :param download_path:
        :param thread_num:
        :return:
        """
        cnt_num = 0
        exec_date_num = len(exec_date_list)
        self.label_value_total.SetLabel("{0}/{1}".format(str(cnt_num), str(exec_date_num)))
        logging.info(sql)
        for exec_date_value in exec_date_list:
            # 此处的date_format与输出的时间格式一致（因）
            print(self.is_cancel)
            if self.is_cancel == 0:
                exec_sql_value = common_func.sql_format(exec_sql=sql, exec_date=exec_date_value,
                                                        date_format=date_format)
                query_threading = threading.Thread(target=query_mqt.query, kwargs={'exec_sql': exec_sql_value,
                                                                                   'download_path': download_path,
                                                                                   'exec_date': exec_date_value})
                query_threading.setDaemon(True)
                cnt_num = cnt_num + 1
                gauge_value = round(1.0*cnt_num/exec_date_num*100, 2)
                logging.info("当前执行日期: {0} 提交进度{1}%".format(exec_date_value, str(gauge_value)))
                self.gauge_total.SetValue(gauge_value)
                self.label_value_total.SetLabel("{0}/{1}:{2}%".format(str(cnt_num).rjust(3),
                                                                      str(exec_date_num).ljust(3),
                                                                      str(gauge_value).rjust(5)))
                query_threading.start()
                if cnt_num % thread_num == 0:
                    query_threading.join()
                # 避免提交过快导致提交重复
                time.sleep(1.5)
            else:
                break
        query_threading.join()
        # print(threading.active_count())
        # print(threading.current_thread())
        # print(threading.enumerate())

    @thread_decorator
    def sql_exec(self, event):
        """sql多线程执行"""
        # 获取设置值
        date_format = self.combobox_date_format.GetValue()
        start_date = self.picker_start_date.GetValue().Format(date_format)
        end_date = self.picker_end_date.GetValue().Format(date_format)
        step_type = self.step_type_list[self.choice_step_type.GetSelection()]
        thread_num = int(self.text_thread_num.GetValue())
        step = int(self.text_step.GetValue())
        download_path = self.text_download_path.GetValue()
        query_name = self.text_query_name.GetValue()
        sql = self.text_sql.GetValue()

        # 修复线程判断
        if len(self.repair_list) > 0:
            exec_date_list = self.repair_list
            if step > 0:
                exec_date_list.sort()
            else:
                exec_date_list.reverse()
        else:
            exec_date_list = common_func.exec_date(start_date=start_date, end_date=end_date, step=step,
                                                   date_format=date_format, step_type=step_type)
            # 重置
            self.is_cancel = 0
            self.button_exec.SetLabel("执行...")
            self.gauge_total.SetValue(0)
            self.label_value_total.SetLabel("{0}/{1}:{2}%".format(str(0).rjust(3), str(0).ljust(3), str(0.00).rjust(5)))
            self.text_log.Clear()

        # 执行预设
        query_mqt = None
        if self.link_type == 'hue':
            query_mqt = link_hue.QueryHue(hue_data=self.link_data, query_name=query_name, log_path=self.log_path)
        elif self.link_type == 'redash':
            query_mqt = link_redash.QueryRedash(redash_data=self.link_data, query_name=query_name,
                                                log_path=self.log_path)
        else:
            exit(1)
        # query_mqt.login()
        start_time = datetime.datetime.now()

        # 多线程执行
        self.thread_exec(exec_date_list, sql, date_format, query_mqt, download_path, thread_num)

        # 返回执行失败的日期
        query_name = self.text_query_name.GetValue()
        if query_name.strip() == '':
            file_name = '{0}_{1}'.format(self.link_type.lower(), self.exec_date)
        else:
            file_name = '{0}_{1}_{2}'.format(self.link_type.lower(), query_name, self.exec_date)
        log = open("{0}\\{1}.log".format(self.log_path, file_name), 'r')
        read_log = log.read()
        log.close()
        last_log = re.search(r'((.*\n)+.+(The end is the beginning!|#*线程修复#*)\n)?((.*\n)*?)$', read_log).group(4)
        print(last_log)
        will_submit_list = [i[0] for i in re.findall(r'当前执行日期: ((\d-?)+)', last_log)]
        submit_list = [i[2] for i in re.findall(r'result_id:((\w-?)+)> ((\d-?)+) 提交成功', last_log)]
        success_list = [i[2] for i in re.findall(r'result_id:((\w-?)+)> ((\d-?)+) 执行成功', last_log)]
        self.exec_fail_list = [i[2] for i in re.findall(r'result_id:((\w-?)+)> ((\d-?)+) 执行失败', last_log)]
        self.submit_lose_list = []
        self.submit_error_list = []
        lose_success_list = []
        repair_status = 0
        for i in exec_date_list:
            if i not in will_submit_list:
                self.submit_lose_list.append(i)
            elif i not in submit_list:
                self.submit_error_list.append(i)
            elif i not in success_list and i not in self.exec_fail_list:
                print(i)
                watch_result = query_mqt.watch(i)
                is_success = watch_result[0]
                if is_success is True:
                    lose_success_list.append(i)
                else:
                    self.exec_fail_list.append(i)
        self.exec_fail_list = list(set(self.exec_fail_list))
        if len(lose_success_list) > 0:
            logging.info("{0} 本次漏发执行成功的日期:{1}".format(query_name, ','.join(lose_success_list)))
        if len(self.submit_lose_list) > 0:
            logging.warning("{0} 本次未提交的日期:{1}".format(query_name, ','.join(self.submit_lose_list)))
            repair_status += 1
        if len(self.submit_error_list) > 0:
            logging.warning("{0} 本次提交异常的日期:{1}".format(query_name, ','.join(self.submit_error_list)))
            repair_status += 2
        if len(self.exec_fail_list) > 0:
            logging.warning("{0} 本次执行失败的日期:{1}".format(query_name, ','.join(self.exec_fail_list)))
            repair_status += 4

        # 错误日期再次提交
        if repair_status > 0:
            dr = self.dialog_repair.ShowModal()
            if dr == wx.EVT_CLOSE or dr == wx.ID_YES:
                self.dialog_repair.EndModal(wx.ID_OK)
            else:
                pass
        else:
            self.dialog_repair.EndModal(wx.ID_OK)

        # 线程结束
        end_time = datetime.datetime.now()
        logging.info("{0} 累计耗时 {1}".format(query_name, str(end_time-start_time)).lstrip())
        logging.info("The end is the beginning!")

        self.button_exec.SetLabel("执行")
        if self.check_finish.GetValue() is True:
            dialog_close = wx.MessageDialog(None, message="SQL已执行完毕！！！", caption="提醒",
                                            style=wx.OK | wx.ICON_WARNING)
            # dialog_close.Center()
            dialog_close.ShowModal()

    @thread_decorator
    def repair(self, event):
        # 执行修复
        self.repair_list = []
        if self.check_lose.GetValue() is True:
            for submit_lose in self.submit_lose_list:
                self.repair_list.append(submit_lose)
        if self.check_submit_error.GetValue() is True:
            for submit_error in self.submit_error_list:
                self.repair_list.append(submit_error)
        if self.check_fail.GetValue() is True:
            for exec_fail in self.exec_fail_list:
                self.repair_list.append(exec_fail)
        self.repair_list = list(set(self.repair_list))
        if len(self.repair_list) > 0:
            logging.warning("###############################线程修复###############################")
            print(self.repair_list)
            self.dialog_repair.EndModal(wx.ID_OK)
            self.sql_exec(event)
        else:
            self.dialog_repair.Destroy()
            logging.warning("线程无需修复")
            logging.info("The end is the beginning!")
            self.button_exec.SetLabel("执行")
            if self.check_finish.GetValue() is True:
                dialog_close = wx.MessageDialog(None, message="SQL已执行完毕！！！", caption="提醒",
                                                style=wx.OK | wx.ICON_WARNING)
                # dialog_close.Center()
                dialog_close.ShowModal()
        return self.repair_list

    def repair_close(self, event):
        self.dialog_repair.EndModal(wx.ID_OK)
        print('线程修复关闭')
        logging.info("The end is the beginning!")
        self.button_exec.SetLabel("执行")

    @thread_decorator
    def suicide(self, event):
        """
        自杀任务，通过读取日志中进行中的任务，并杀死任务，直至所有剩余任务结束
        :param event:
        :return:
        """
        # 执行预设
        self.is_cancel = 1
        self.button_cancel.SetLabel('自杀...')
        cancel_list = []
        query_name = self.text_query_name.GetValue()
        if query_name.strip() == '':
            file_name = '{0}_{1}'.format(self.link_type.lower(), self.exec_date)
        else:
            file_name = '{0}_{1}_{2}'.format(self.link_type.lower(), query_name, self.exec_date)
        if self.link_type == 'hue':
            query_mqt = link_hue.QueryHue(hue_data=self.link_data, query_name=query_name, log_path=self.log_path)
        elif self.link_type == 'redash':
            query_mqt = link_redash.QueryRedash(redash_data=self.link_data, query_name=query_name,
                                                log_path=self.log_path)
        else:
            exit(1)
        query_mqt.login()

        while 1 == 1:
            log = open("{0}\\{1}.log".format(self.log_path, file_name), 'r')
            read_log = log.read()
            log.close()
            last_log = re.search(r'((.*\n)+.+The end is the beginning!\n)*((.*\n)*?)$', read_log).group(3)
            submit_list = [i[0] for i in re.findall(r'result_id:((\w-?)+)> (\d-?)+ 提交成功', last_log, 0)]
            exec_list = [i[0] for i in re.findall(r'result_id:((\w-?)+)> (\d-?)+ 执行', last_log, 0)]
            print(submit_list, exec_list)
            # 自杀后线程显示执行成功或返回成功
            if len(submit_list) == len(exec_list):
                break
            for i in submit_list:
                if i in exec_list or i in cancel_list:
                    pass
                else:
                    cancel_result = query_mqt.cancel(i)
                    if cancel_result == 1:
                        cancel_list.append(i)
            time.sleep(2)
        self.button_cancel.SetLabel('自杀')
        dialog_suicide = wx.MessageDialog(None, message="SQL已自杀完毕！！！", caption="提醒",
                                          style=wx.OK | wx.ICON_WARNING)
        ds = dialog_suicide.ShowModal()
        if ds == wx.EVT_CLOSE or ds == wx.ID_YES:
            # 确保程序完整退出，无残留
            dialog_suicide.Destroy()
        else:
            pass
        self.button_exec.SetLabel("执行")

    def is_close(self, event):
        """主框架窗口关闭提醒"""
        message_list = [
            "醉不成欢惨将别，别时茫茫江浸月 \n                                           —— 白居易",
            "天下伤心处，劳劳送客亭 \n                                           —— 李白",
            "丈夫非无泪，不洒离别间 \n                                           —— 陆龟蒙",
            "一曲离歌两行泪，不知何地再逢君 \n                                           —— 韦庄",
            "人生不相见，动如参与商 \n                                           —— 杜甫",
            "仰天大笑出门去，我辈岂是蓬蒿人 \n                                           —— 李白",
            "弃我去者，昨日之日不可留 \n                                           —— 李白",
            "寒雨连江夜入吴，平明送客楚山孤 \n                                         —— 王昌龄",
            "轮台东门送君去，雪上空留马行处 \n                                          —— 岑参",
            "一看肠一断，好去莫回头 \n                                          —— 白居易",
            "最是人间留不住，朱颜辞镜花辞树 \n                                          —— 王国维",
            "直须看尽洛城花，始共春风容易别 \n                                          —— 欧阳修",
            "挥手自兹去，萧萧班马鸣 \n                                           —— 李白"
        ]
        dialog_close = wx.MessageDialog(None, message=message_list[int(random.random()*5)], caption="关闭",
                                        style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
        dc = dialog_close.ShowModal()
        if dc == wx.EVT_CLOSE or dc == wx.ID_YES:
            dialog_close.Destroy()
            # 确保程序完整退出，无残留
            print(os.getpid())
            os.kill(os.getpid(), signal.SIGINT)
        else:
            pass

    def label_help_show(self, event):
        global label_help
        label_help = wx.StaticText(self.main_panel)
        label_help.SetLabel(u"""
        使用条例：
        1.执行前请先填写本次执行的任务名称，以便保存记录 
        2.代码多线程执行前请先校验，校验通过后再执行 
        3.程序执行日志保存在程序所在的文件夹 
        4.若中途发现执行错误，请选择自杀 
        5.如要强制关闭，请到任务管理器中结束进程 
        6.日期通配符 #n# ,n表示距今天数
        """)
        label_help.SetPosition((self.button_help.GetPosition()[0]-label_help.GetSize()[0],
                                self.button_help.GetPosition()[1]))
        label_help.SetBackgroundColour('#3299CC')
        label_help.SetForegroundColour('white')

    def label_help_close(self, event):
        global label_help
        label_help.Destroy()


class LoginGui(wx.Frame):
    def __init__(self):
        # 变量预设
        self.is_main_start = 0
        self.label_login_error_mark = 0
        self.link_type_list = ['hue', 'redash']
        self.link_type = None
        self.link_data = None
        self.link_info = configparser.ConfigParser()
        if os.path.exists('link_info.ini'):
            self.link_info.read('link_info.ini')
        login_app = wx.App()
        login_app.SetExitOnFrameDelete(True)
        super(LoginGui, self).__init__(None, title='MQT Login', size=(320, 250), style=wx.CAPTION | wx.CLOSE_BOX)

        self.SetIcon(wx.Icon('image\\mqt.ico'))
        self.SetBackgroundColour("#FFFFFF")
        self.Center()
        self.login_panel = wx.Panel(self)

        self.check_remeber = wx.CheckBox(self.login_panel, label="Remeber", size=(75, 30))
        self.label_username = wx.StaticText(self.login_panel, label='Username:', size=(70, 30))
        self.text_username = wx.TextCtrl(self.login_panel)
        self.text_username.SetForegroundColour("#9e9e9e")
        self.label_password = wx.StaticText(self.login_panel, label='Password:', size=(70, 30))
        self.text_password = wx.TextCtrl(self.login_panel, style=wx.TE_PASSWORD)
        self.text_password.SetForegroundColour("#9e9e9e")
        self.label_host = wx.StaticText(self.login_panel, label='Host:', size=(70, 30))
        self.text_host = wx.TextCtrl(self.login_panel)
        self.text_host.SetForegroundColour("#9e9e9e")
        self.button_login = wx.Button(self.login_panel, label='Login', size=(100, 30))
        self.combobox_link_type = wx.ComboBox(self.login_panel, value="Link Type", size=(80, 30),
                                              choices=self.link_type_list, style=wx.CB_DROPDOWN)

        # 按钮绑定
        self.combobox_link_type.Bind(wx.EVT_COMBOBOX, self.link_chioce)
        self.button_login.Bind(wx.EVT_BUTTON, self.login)
        self.text_username.Bind(wx.EVT_TEXT, self.destroy)
        self.text_password.Bind(wx.EVT_TEXT, self.destroy)

        self.login_hbox1 = wx.BoxSizer()
        self.login_hbox1.Add(self.label_username, flag=wx.ALL, border=2)
        self.login_hbox1.Add(self.text_username)
        self.login_hbox2 = wx.BoxSizer()
        self.login_hbox2.Add(self.label_password, flag=wx.ALL, border=2)
        self.login_hbox2.Add(self.text_password)
        self.login_hbox4 = wx.BoxSizer()
        self.login_hbox4.Add(self.label_host, flag=wx.ALL, border=2)
        self.login_hbox4.Add(self.text_host)
        self.login_hbox3 = wx.BoxSizer()
        self.login_hbox3.Add(self.combobox_link_type, flag=wx.RIGHT, border=10)
        self.login_hbox3.Add(self.check_remeber, flag=wx.LEFT, border=10)
        self.login_vbox1 = wx.BoxSizer(wx.VERTICAL)
        self.login_vbox1.Add(self.login_hbox1, flag=wx.ALIGN_CENTER_HORIZONTAL)
        self.login_vbox1.Add(self.login_hbox2, flag=wx.ALIGN_CENTER_HORIZONTAL)
        self.login_vbox1.Add(self.login_hbox4, flag=wx.ALIGN_CENTER_HORIZONTAL)
        self.login_vbox1.Add(self.login_hbox3, flag=wx.ALIGN_CENTER_HORIZONTAL)
        self.login_vbox1.Add(self.button_login, flag=wx.ALIGN_CENTER_HORIZONTAL)
        self.login_vbox2 = wx.BoxSizer(wx.VERTICAL)
        self.login_vbox2.Add(self.login_vbox1, flag=wx.ALIGN_CENTER | wx.ALL, border=20)
        self.login_panel.SetSizer(self.login_vbox2)
        self.Show()
        login_app.MainLoop()

    def link_chioce(self, event):
        """LinkType 进行选择时自动填写账号密码"""
        self.link_type = self.combobox_link_type.GetValue()
        link_data = dict(self.link_info.items(self.link_type))
        if link_data['ip'] != '' and link_data['username'] != '' and link_data['password'] != '':
            self.text_host.SetValue(link_data['ip'])
            self.text_username.SetValue(common_func.encryption(link_data['username'], 0))
            self.text_password.SetValue(common_func.encryption(link_data['password'], 0))
            self.check_remeber.SetValue(True)
        else:
            pass

    def auto_destroy(self, lable):
        """错误信息五秒关闭"""
        if self.label_login_error_mark == 1:
            self.button_login.SetLabel("Login")
            time.sleep(5)
            wx.CallAfter(lable.Destroy)
            self.label_login_error_mark = 0
        return self.label_login_error_mark

    def destroy(self, event):
        """错误信息输入关闭"""
        if self.label_login_error_mark == 1:
            self.label_login_error.Destroy()
            self.label_login_error_mark = 0
            self.button_login.SetLabel("Login")
        else:
            pass
        return self.label_login_error_mark

    def login(self, event):
        self.button_login.SetLabel("Login...")

        def login_error(error_info):
            button_login_pos = self.button_login.GetPosition()
            button_login_size = self.button_login.GetSize()
            self.label_login_error = wx.StaticText(self.login_panel, label=error_info)
            label_login_error_size = self.label_login_error.GetSize()
            self.label_login_error.SetPosition((button_login_pos[0]+button_login_size[0]/2-label_login_error_size[0]/2,
                                                button_login_pos[1]+button_login_size[1]+5))
            self.label_login_error.SetForegroundColour("white")
            self.label_login_error.SetBackgroundColour("red")
            self.label_login_error_mark = 1
            error_msg = threading.Thread(target=self.auto_destroy, args=(self.label_login_error,))
            error_msg.setDaemon(True)
            error_msg.start()

        self.link_type = self.combobox_link_type.GetValue()
        if self.link_type == 'Link Type':
            login_error(" Error: LinkType is empty")
        else:
            self.link_data = dict(self.link_info.items(self.link_type))
            self.link_data['username'] = self.text_username.GetValue()
            self.link_data['password'] = self.text_password.GetValue()
            self.link_data['ip'] = self.text_host.GetValue()

            if self.link_type in self.link_type_list:
                if self.link_type == 'hue':
                    link_mqt = link_hue.QueryHue(hue_data=self.link_data, is_log=0)
                elif self.link_type == 'redash':
                    link_mqt = link_redash.QueryRedash(redash_data=self.link_data, is_log=0)
                else:
                    exit(1)
                login_info_file = '{0}_login_info'.format(self.link_type)
                if os.path.exists(login_info_file):
                    os.remove(login_info_file)
                try:
                    login_status = link_mqt.login()
                    print('{0}连接成功'.format(self.link_type))
                    print(login_status)
                    if self.check_remeber.GetValue() is True:
                        self.link_info.set(self.link_type, 'ip', self.text_host.GetValue())
                        self.link_info.set(self.link_type, 'username', common_func.encryption(
                            self.text_username.GetValue(), 1))
                        self.link_info.set(self.link_type, 'password', common_func.encryption(
                            self.text_password.GetValue(), 1))
                        self.link_info.write(open('link_info.ini', 'r+', encoding="utf-8"))
                    self.Destroy()
                    MainGui(self.link_data, self.link_type)
                    # self.is_main_start = 1

                except Exception as e:
                    if ping(self.link_data['ip']):
                        login_error(" Error: Invalid Username or Password ")
                    else:
                        login_error(" Error: Host Is Error ")
                    logging.warning(e)
            else:
                login_error(" Error: Invalid LinkType ")

        return self.label_login_error_mark


if __name__ == '__main__':
    LoginGui()

