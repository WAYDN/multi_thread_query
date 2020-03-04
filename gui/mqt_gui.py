# coding=utf-8


import logging
import os
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
import sys


def thread_decorator(action_def):
    def action(event):
        tmp = threading.Thread(target=action_def, args=(event, ))
        tmp.start()
    return action


class MainGui:
    def __init__(self, link_data, link_type):
        self.link_data = link_data
        self.link_type = link_type
        self.log_path = os.path.dirname(os.path.realpath(__file__))+"\\log"
        self.exec_date = datetime.datetime.now().strftime('%Y%m%d')

    def main_app(self):
        mgt = wx.App()
        mgt.SetExitOnFrameDelete(True)
        main_frame = wx.Frame(None, title='{0}客户端'.format(self.link_type), size=(800, 600),
                              style=wx.DEFAULT_FRAME_STYLE)
        main_frame.SetIcon(wx.Icon('image\\mqt.ico'))
        main_frame.Center()
        main_panel = wx.Panel(main_frame)

        # 控件定义
        # 预设参数
        date_format_list = ['%Y-%m-%d', '%Y%m%d']
        step_type_list = ['day', 'month']
        # 参数控件
        label_start_date = wx.StaticText(main_panel, label="开始日期")
        picker_start_date = wa.DatePickerCtrl(main_panel, id=-1, style=wa.DP_DROPDOWN | wa.DP_SHOWCENTURY)
        label_end_date = wx.StaticText(main_panel, label="结束日期")
        picker_end_date = wa.DatePickerCtrl(main_panel, id=-1, style=wa.DP_DROPDOWN | wa.DP_SHOWCENTURY)
        label_date_format = wx.StaticText(main_panel, label="时间格式")
        combobox_date_format = wx.ComboBox(main_panel, choices=date_format_list)
        combobox_date_format.SetSelection(0)
        label_thread_num = wx.StaticText(main_panel, label="   线程数")
        text_thread_num = wx.TextCtrl(main_panel, value="1")
        label_step_type = wx.StaticText(main_panel, label="跨度周期")
        choice_step_type = wx.Choice(main_panel, choices=step_type_list)
        choice_step_type.SetSelection(0)
        label_step = wx.StaticText(main_panel, label="时间跨度")
        text_step = wx.TextCtrl(main_panel, value="1")
        label_download_path = wx.StaticText(main_panel, label="下载路径")
        text_download_path = wx.TextCtrl(main_panel, value=common_func.get_desktop_path())
        label_query_name = wx.StaticText(main_panel, label="任务名称")
        text_query_name = wx.TextCtrl(main_panel)
        # sql控件
        label_sql = wx.StaticText(main_panel, label="SQL:")
        text_sql = ws.StyledTextCtrl(main_panel, style=wx.TE_MULTILINE | wx.HSCROLL | wx.TE_RICH)
        text_sql.SetValue("""SELECT '#0#' FROM pdw.pdw_account_settle  LIMIT 1""")
        text_sql.SetMarginType(1, ws.STC_MARGIN_NUMBER)
        text_sql.SetMarginWidth(1, 25)
        # log控件
        label_log = wx.StaticText(main_panel, label="LOG:")
        text_log = wx.TextCtrl(main_panel, style=wx.TE_MULTILINE | wx.HSCROLL | wx.TE_RICH | wx.TE_READONLY)
        text_log.SetFont(text_sql.GetFont())
        # 按钮控件
        button_explain = wx.Button(main_panel, label="校验")
        button_exec = wx.Button(main_panel, label="执行")
        button_cancel = wx.Button(main_panel, label="自杀")
        # help控件
        image_help = wx.Image("image\\help.png", wx.BITMAP_TYPE_PNG).ConvertToBitmap()
        m = image_help.GetWidth()/label_sql.GetCharWidth()/2
        image_help = image_help.ConvertToImage().Scale(image_help.GetWidth()/m, image_help.GetHeight()/m)
        image_help = image_help.ConvertToBitmap()
        button_help = wx.BitmapButton(main_panel, bitmap=image_help, style=wx.BORDER_MASK)
        # 结束提醒
        check_finish = wx.CheckBox(main_panel, label="SQL结束提醒")
        # 进度控件
        label_gauge_total = wx.StaticText(main_panel, label="总进度: ")
        gauge_total = wx.Gauge(main_panel, -1, 100)
        label_value_total = wx.StaticText(main_panel, label="{0}/{1}:{2}%".
                                          format(str(0).rjust(3), str(0).ljust(3), str(0.00).rjust(5)))

        logging.basicConfig(stream=text_log, format='%(asctime)s [%(levelname)s]: %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
        # logging.warning('123')

        def sql_explain(event):
            """hue sql检验"""
            query_name = text_query_name.GetValue()
            text_log.Clear()
            if self.link_type == 'hue':
                button_explain.SetLabel("校验...")
                sql = text_sql.GetValue()
                query_hue = link_hue.QueryHue(hue_data=self.link_data, query_name=query_name, log_path=self.log_path)
                query_hue.explain(sql)
                time.sleep(1)
                button_explain.SetLabel("校验")
            else:
                text_log.SetLabel("当前连接不支持sql校验")

        @thread_decorator
        def sql_exec(event):
            """sql多线程执行"""
            # 重置
            button_exec.SetLabel("执行...")
            gauge_total.SetValue(0)
            label_value_total.SetLabel("{0}/{1}:{2}%".format(str(0).rjust(3), str(0).ljust(3), str(0.00).rjust(5)))
            text_log.Clear()

            # 获取设置值
            date_format = combobox_date_format.GetValue()
            start_date = picker_start_date.GetValue().Format(date_format)
            end_date = picker_end_date.GetValue().Format(date_format)
            step_type = step_type_list[choice_step_type.GetSelection()]
            thread_num = int(text_thread_num.GetValue())
            step = int(text_step.GetValue())
            download_path = text_download_path.GetValue()
            query_name = text_query_name.GetValue()
            sql = text_sql.GetValue()

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
            cnt_num = 0
            exec_date_list = common_func.exec_date(start_date=start_date, end_date=end_date, step=step,
                                                   date_format=date_format, step_type=step_type)
            exec_date_num = len(exec_date_list)
            label_value_total.SetLabel("{0}/{1}".format(str(cnt_num), str(exec_date_num)))
            logging.info(sql)
            for exec_date_value in exec_date_list:
                # 此处的date_format与输出的时间格式一致（因）
                exec_sql_value = common_func.sql_format(exec_sql=sql, exec_date=exec_date_value,
                                                        date_format=date_format)
                query_threading = threading.Thread(target=query_mqt.query, kwargs={'exec_sql': exec_sql_value,
                                                                                   'download_path': download_path,
                                                                                   'exec_date': exec_date_value})
                cnt_num = cnt_num + 1
                logging.info("当前执行日期:{0},提交进度{1}%".format(exec_date_value, round(1.0*cnt_num/exec_date_num*100, 2)))
                query_threading.start()
                if cnt_num % thread_num == 0:
                    query_threading.join()
                gauge_value = round(1.0*cnt_num/exec_date_num*100, 2)
                gauge_total.SetValue(gauge_value)
                label_value_total.SetLabel("{0}/{1}:{2}%".format(str(cnt_num).rjust(3), str(exec_date_num).ljust(3),
                                                                 str(gauge_value).rjust(5)))
                # 避免提交过快导致提交重复
                time.sleep(1)
            query_threading.join()

            query_name = text_query_name.GetValue()
            if query_name.strip() == '':
                file_name = '{0}_{1}'.format(self.link_type.lower(), self.exec_date)
            else:
                file_name = '{0}_{1}_{2}'.format(self.link_type.lower(), query_name, self.exec_date)

            # 线程结束
            end_time = datetime.datetime.now()
            logging.info("{0} 累计耗时 {1}".format(query_name, str(end_time-start_time)))

            # 返回执行失败的线程
            fail_list = []
            log = open("{0}\\{1}.log".format(self.log_path, file_name), 'r')
            read_log = log.read()
            log.close()
            last_log = re.search(r'((.*\n)+.+The end is the beginning!\n)?((.*\n)*?)$', read_log).group(3)
            fail_list = [i[2] for i in re.findall(r'result_id:((\w-?)+)> ((\d-?)+) 执行失败', last_log)]
            if len(fail_list) == 0:
                pass
            else:
                logging.warning("{0} 本次执行失败信息:{1}".format(query_name, ','.join(fail_list)))
            logging.info("The end is the beginning!")

            button_exec.SetLabel("执行")
            if check_finish.GetValue() is True:
                dialog_close = wx.MessageDialog(None, message="SQL已执行完毕！！！", caption="提醒",
                                                style=wx.OK | wx.ICON_WARNING)
                dialog_close.ShowModal()

        @thread_decorator
        def suicide(event):
            """
            自杀任务，通过读取日志中进行中的任务，并杀死任务，直至所有剩余任务结束
            :param event:
            :return:
            """
            # 执行预设
            button_cancel.SetLabel('自杀...')
            query_name = text_query_name.GetValue()
            if query_name.strip() == '':
                file_name = '{0}_{1}'.format(self.link_type.lower(), self.exec_date)
            else:
                file_name = '{0}_{1}_{2}'.format(self.link_type.lower(), query_name, self.exec_date)
            cancel_list = []
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
                if len(submit_list) == len(exec_list) and last_log == "":
                    break
                for i in submit_list:
                    if i in exec_list or i in cancel_list:
                        pass
                    else:
                        cancel_result = query_mqt.cancel(i)
                        if cancel_result == 1:
                            cancel_list.append(i)
                time.sleep(2)
            button_cancel.SetLabel('自杀')
            dialog_close = wx.MessageDialog(None, message="SQL已自杀完毕！！！", caption="提醒",
                                            style=wx.OK | wx.ICON_WARNING)
            dialog_close.ShowModal()

        def is_close(event):
            """主框架窗口关闭提醒"""
            message_list = [
                "醉不成欢惨将别,别时茫茫江浸月 \n                                           —— 白居易",
                "天下伤心处，劳劳送客亭 \n                                           —— 李白",
                "丈夫非无泪,不洒离别间 \n                                           —— 陆龟蒙",
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
            ret = dialog_close.ShowModal()
            if ret == wx.ID_YES:
                # 确保程序完整退出，无残留
                sys.exit()
                # main_frame.Destroy()
            else:
                pass

        def label_help_show(event):
            global label_help
            label_help = wx.StaticText(main_panel)
            label_help.SetLabel(u"""
    使用条例：
    1.执行前请先填写本次执行的任务名称，以便保存记录
    2.代码多线程执行前请先校验，校验通过后再执行
    3.程序执行日志保存在程序所在的文件夹
    4.若中途发现执行错误，请选择自杀
    5.如要强制关闭，请到任务管理器中结束进程
            """)
            label_help.SetPosition((button_help.GetPosition()[0]-label_help.GetSize()[0], button_help.GetPosition()[1]))
            label_help.SetBackgroundColour('#3299CC')
            label_help.SetForegroundColour('white')

        def label_help_close(event):
            global label_help
            label_help.Destroy()

        # 绑定执行事件
        main_frame.Bind(wx.EVT_CLOSE, is_close)
        button_explain.Bind(wx.EVT_BUTTON, sql_explain)
        button_exec.Bind(wx.EVT_BUTTON, sql_exec)
        button_cancel.Bind(wx.EVT_BUTTON, suicide)
        button_help.Bind(wx.EVT_ENTER_WINDOW, label_help_show)
        button_help.Bind(wx.EVT_LEAVE_WINDOW, label_help_close)

        # 页面布置
        hbox_config_1 = wx.BoxSizer()
        hbox_config_1.Add(label_start_date, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        hbox_config_1.Add(picker_start_date, proportion=1, flag=wx.RIGHT, border=5)
        hbox_config_1.Add(label_end_date, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        hbox_config_1.Add(picker_end_date, proportion=1, flag=wx.RIGHT, border=5)
        hbox_config_1.Add(label_date_format, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        hbox_config_1.Add(combobox_date_format, proportion=1, flag=wx.RIGHT, border=5)
        hbox_config_1.Add(label_thread_num, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        hbox_config_1.Add(text_thread_num, proportion=1)
        hbox_config_2 = wx.BoxSizer()
        hbox_config_2.Add(label_step_type, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        hbox_config_2.Add(choice_step_type, proportion=1, flag=wx.RIGHT, border=5)
        hbox_config_2.Add(label_step, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        hbox_config_2.Add(text_step, proportion=1, flag=wx.RIGHT, border=5)
        hbox_config_2.Add(label_download_path, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        hbox_config_2.Add(text_download_path, proportion=1, flag=wx.RIGHT, border=5)
        hbox_config_2.Add(label_query_name, proportion=0, flag=wx.RIGHT | wx.TOP, border=5)
        hbox_config_2.Add(text_query_name, proportion=1)
        hbox_log = wx.BoxSizer()
        hbox_log.Add(label_log, proportion=1, flag=wx.ALIGN_LEFT)
        hbox_log.Add(check_finish, proportion=0, flag=wx.ALIGN_RIGHT)
        vbox_button = wx.BoxSizer(wx.VERTICAL)
        vbox_button.Add(button_explain, proportion=1)
        vbox_button.Add(button_exec, proportion=1)
        vbox_button.Add(button_cancel, proportion=1)
        hbox_button = wx.BoxSizer()
        hbox_button.Add(text_log, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=5)
        hbox_button.Add(vbox_button, proportion=0, flag=wx.EXPAND)
        hbox_sql = wx.BoxSizer()
        hbox_sql.Add(label_sql, proportion=1, flag=wx.ALIGN_LEFT)
        hbox_sql.Add(button_help, proportion=0, flag=wx.ALIGN_RIGHT)
        hbox_total_gauge = wx.BoxSizer()
        hbox_total_gauge.Add(label_gauge_total, proportion=0)
        hbox_total_gauge.Add(gauge_total, proportion=1)
        hbox_total_gauge.Add(label_value_total, proportion=0, flag=wx.LEFT | wx.RIGHT, border=7)
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(hbox_config_1, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=5)
        vbox.Add(hbox_config_2, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=5)
        vbox.Add(hbox_sql, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=5)
        vbox.Add(text_sql, proportion=3, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=5)
        vbox.Add(hbox_log, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT, border=5)
        vbox.Add(hbox_button, proportion=2, flag=wx.EXPAND | wx.TOP | wx.LEFT, border=5)
        vbox.Add(hbox_total_gauge, proportion=0, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        main_panel.SetSizer(vbox)

        main_frame.Show()
        mgt.MainLoop()


if __name__ == '__main__':
    # 变量预设
    label_login_error_mark = 0
    link_type_list = ['hue', 'redash']
    link_info = configparser.ConfigParser()
    if os.path.exists('link_info.ini'):
        link_info.read('link_info.ini')

    login_app = wx.App()
    login_app.SetExitOnFrameDelete(True)
    login_frame = wx.Frame(None, title='MQT Login', size=(320, 250), style=wx.CAPTION | wx.CLOSE_BOX)
    login_frame.SetIcon(wx.Icon('image\\mqt.ico'))
    login_frame.SetBackgroundColour("#FFFFFF")
    login_frame.Center()
    login_panel = wx.Panel(login_frame)

    label_username = wx.StaticText(login_panel, label='Username:', size=(70, 30))
    text_username = wx.TextCtrl(login_panel)
    text_username.SetForegroundColour("#9e9e9e")
    label_password = wx.StaticText(login_panel, label='Password:', size=(70, 30))
    text_password = wx.TextCtrl(login_panel, style=wx.TE_PASSWORD)
    text_password.SetForegroundColour("#9e9e9e")
    label_host = wx.StaticText(login_panel, label='Host:', size=(70, 30))
    text_host = wx.TextCtrl(login_panel)
    text_host.SetForegroundColour("#9e9e9e")
    button_login = wx.Button(login_panel, label='Login', size=(100, 30), style=wx.BORDER_MASK)
    button_login.SetBackgroundColour("#338BB8")
    button_login.SetForegroundColour("#FFFFFF")
    button_login.SetDefault()
    combobox_link_type = wx.ComboBox(login_panel, value="Link Type", size=(80, 30), choices=link_type_list,
                                     style=wx.CB_DROPDOWN)
    check_remeber = wx.CheckBox(login_panel, label="Remeber", size=(75, 30))


    def link_chioce(event):
        """LinkType 进行选择时自动填写账号密码"""
        link_type = combobox_link_type.GetValue()
        link_data = dict(link_info.items(link_type))
        if link_data['ip'] != '' and link_data['username'] != '' and link_data['password'] != '':
            text_host.SetValue(link_data['ip'])
            text_username.SetValue(common_func.encryption(link_data['username'], 0))
            text_password.SetValue(common_func.encryption(link_data['password'], 0))
            check_remeber.SetValue(True)
        else:
            pass


    def auto_destroy(lable):
        """错误信息五秒关闭"""
        global label_login_error_mark
        if label_login_error_mark == 1:
            button_login.SetLabel("Login")
            time.sleep(5)
            wx.CallAfter(lable.Destroy)
            label_login_error_mark = 0
        return label_login_error_mark


    def destroy(event):
        """错误信息输入关闭"""
        global label_login_error_mark
        if label_login_error_mark == 1:
            label_login_error.Destroy()
            label_login_error_mark = 0
            button_login.SetLabel("Login")
        else:
            pass
        return label_login_error_mark


    def login(event):
        def login_error(error_info):
            global label_login_error, label_login_error_mark
            button_login_pos = button_login.GetPosition()
            button_login_size = button_login.GetSize()
            label_login_error = wx.StaticText(login_panel, label=error_info)
            label_login_error_size = label_login_error.GetSize()
            label_login_error.SetPosition((button_login_pos[0]+button_login_size[0]/2-label_login_error_size[0]/2,
                                           button_login_pos[1]+button_login_size[1]+5))
            label_login_error.SetForegroundColour("white")
            label_login_error.SetBackgroundColour("red")
            label_login_error_mark = 1
            error_msg = threading.Thread(target=auto_destroy, args=(label_login_error,))
            error_msg.setDaemon(True)
            error_msg.start()

        button_login.SetLabel("Login...")
        link_type = combobox_link_type.GetValue()
        link_data = dict(link_info.items(link_type))
        link_data['username'] = text_username.GetValue()
        link_data['password'] = text_password.GetValue()
        link_data['ip'] = text_host.GetValue()

        if link_type in link_type_list:
            # if link_type == 'hue':
            #     link_mqt = link_hue.QueryHue(hue_data=link_data, is_log=0)
            # elif link_type == 'redash':
            #     link_mqt = link_redash.QueryRedash(redash_data=link_data, is_log=0)
            # else:
            #     exit(1)
            #
            # login_info_file = '{0}_login_info'.format(link_type)
            # if os.path.exists(login_info_file):
            #     os.remove(login_info_file)

            # if link_mqt.login():
            #     print('{0}连接成功'.format(link_type))
            #     print(link_mqt.login())
            if 1==1:
                if check_remeber.GetValue() is True:
                    link_info.set(link_type, 'ip', text_host.GetValue())
                    link_info.set(link_type, 'username', common_func.encryption(text_username.GetValue(), 1))
                    link_info.set(link_type, 'password', common_func.encryption(text_password.GetValue(), 1))
                    link_info.write(open('link_info.ini', 'r+', encoding="utf-8"))
                login_frame.Destroy()
                main = MainGui(link_data, link_type)
                main.main_app()
            else:
                login_error(" Error: Invalid Username or Password or Host")
        else:
            login_error(" Error: Invalid LinkType ")

        return label_login_error_mark


    combobox_link_type.Bind(wx.EVT_COMBOBOX, link_chioce)
    button_login.Bind(wx.EVT_BUTTON, login)
    text_username.Bind(wx.EVT_TEXT, destroy)
    text_password.Bind(wx.EVT_TEXT, destroy)

    h_box1 = wx.BoxSizer()
    h_box1.Add(label_username, flag=wx.ALL, border=2)
    h_box1.Add(text_username)
    h_box2 = wx.BoxSizer()
    h_box2.Add(label_password, flag=wx.ALL, border=2)
    h_box2.Add(text_password)
    h_box4 = wx.BoxSizer()
    h_box4.Add(label_host, flag=wx.ALL, border=2)
    h_box4.Add(text_host)
    h_box3 = wx.BoxSizer()
    h_box3.Add(combobox_link_type, flag=wx.RIGHT, border=10)
    h_box3.Add(check_remeber, flag=wx.LEFT, border=10)
    v_box1 = wx.BoxSizer(wx.VERTICAL)
    v_box1.Add(h_box1, flag=wx.ALIGN_CENTER_HORIZONTAL)
    v_box1.Add(h_box2, flag=wx.ALIGN_CENTER_HORIZONTAL)
    v_box1.Add(h_box4, flag=wx.ALIGN_CENTER_HORIZONTAL)
    v_box1.Add(h_box3, flag=wx.ALIGN_CENTER_HORIZONTAL)
    v_box1.Add(button_login, flag=wx.ALIGN_CENTER_HORIZONTAL)
    v_box2 = wx.BoxSizer(wx.VERTICAL)
    v_box2.Add(v_box1, flag=wx.ALIGN_CENTER | wx.ALL, border=20)
    login_panel.SetSizer(v_box2)

    login_frame.Show()
    login_app.MainLoop()

