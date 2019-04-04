# multi_thread_query
Multi-threaded query tool to reduce the mechanical operation of repeatedly submitting query statements.

![mqt](https://github.com/WAYDN/multi_thread_query/blob/master/gui/mqt.ico)

#### 开发环境
python3.6

#### 目录结构
├─ .gitignore
├─ common_func.py                 // 通用函数
├─ LICENSE         
├─ link_hue.py                    // 连接hue,提交sql
├─ link_redash.py                 // 连接redash,提交sql
│
├─ .idea
│  │  encodings.xml
│  │  misc.xml
│  │  modules.xml
│  │  multi_thread_query.iml
│  │  vcs.xml
│  │  workspace.xml
│  │
│  └─codeStyles
│          codeStyleConfig.xml
│
├─ gui                             // gui界面
│  │  help.png
│  │  link_info.ini                // 配置信息:访问的ip地址及登陆密码
│  │  mqt.ico
│  │  mqt_gui.py                   // gui界面代码
│  │  version_info.txt
│  │  __init__.py


#### 待办事项
- [ ] -将多线程提交代码改为异步提交
