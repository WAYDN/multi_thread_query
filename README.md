# multi_thread_query
Multi-threaded query tool to reduce the mechanical operation of repeatedly submitting query statements.

#### 应用介绍
多线程查询工具，只为更加高效
- 目前仅支持hue、redash提交执行
- 多线程提交sql，线程数可控，保证时间顺序执行
- 支持日期自定义，正/反向顺序提交日期，跨天/跨月提交日期
- 提供数据缓存下载，执行完成提醒，执行失败预警统计
- 动态显示提交进度

#### 使用条例
- 时间跨度为负数，反向提交执行时间
- \#0#表示执行日期的当天，\#-1#表示执行日期的前一日，\#1#表示执行日期的后一日
- 日期格式定义，%Y:年 %m:月 %d:日

#### 注意条例
- 执行前请先填写本次执行的任务名称，以便保存记录
- 代码多线程执行前请先校验，校验通过后再执行
- 程序执行日志保存在程序所在的文件夹(日志记录所提交的代码及每次执行的结果)
- 若中途发现执行错误，请选择自杀
- 若非正常关闭，进程会有残留，请到任务管理器中结束进程

#### 图标
![图标](https://github.com/WAYDN/multi_thread_query/blob/master/gui/image/mqt.ico)

### 操作界面
登录界面

![登录界面](https://github.com/WAYDN/multi_thread_query/blob/master/gui/image/login.png)

执行界面

![执行界面](https://github.com/WAYDN/multi_thread_query/blob/master/gui/image/execution.png)

#### 开发环境
python3.6

#### 目录结构
- .gitignore
- common_func.py
- LICENSE         
- link_hue.py
- link_redash.py
- gui 
    - help.png
    - link_info.ini
    - mqt.ico
    - mqt_gui.py
    - version_info.txt
    - \_\_init\_\_.py


#### 迭代计划
- [ ] 将多线程提交代码改为异步提交
