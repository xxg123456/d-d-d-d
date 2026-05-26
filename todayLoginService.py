import random
import re


import requests
from urllib3.exceptions import InsecureRequestWarning
from login.Utils import Utils
from login.casLogin import casLogin
from login.iapLogin import iapLogin
from login.RSALogin import RSALogin
from liteTools import TaskError, LL, ProxyGet, reqSession

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class TodayLoginService:
    # 初始化本地登录类
    def __init__(self, userInfo):
        if (
            None == userInfo["username"]
            or "" == userInfo["username"]
            or None == userInfo["password"]
            or "" == userInfo["password"]
            or None == userInfo["schoolName"]
            or "" == userInfo["schoolName"]
        ):
            raise TaskError("初始化类失败，请键入完整的参数（用户名，密码，学校名称）", 301)
        self.username = userInfo["username"]
        self.password = userInfo["password"]
        self.schoolName = userInfo["schoolName"]
        self.session = reqSession()
        headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; Mi 13 Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 cpdaily/9.9.10 wisedu/9.9.10"}
        # headers = {"User-Agent": random.choice(Utils.getUserAgents())}
        # 关闭多余的连接
        self.session.keep_alive = False
        # 增加重试次数
        self.session.adapters.DEFAULT_RETRIES = 5
        self.session.headers = headers
        # 如果设置了用户的代理，那么该用户将走代理的方式进行访问
        pg = userInfo["proxy"]
        pg: ProxyGet
        self.session.proxies = pg.getProxy()
        # 添加hooks进行拦截判断该请求是否被418拦截
        self.session.hooks["response"].append(Utils.checkStatus)
        self.login_url = ""
        self.host = ""
        self.login_host = ""
        self.loginEntity = None

    # # 通过学校名称借助api获取学校的登陆url
    # def getLoginUrlBySchoolName(self):
    #     schools = self.session.get(
    #         "https://mobile.campushoy.com/v6/config/guest/tenant/list",
    #         verify=False,
    #         hooks=dict(response=[Utils.checkStatus]),
    #     ).json()["data"]
    #     flag = True
    #     for item in schools:
    #         if item["name"] == self.schoolName:
    #             if item["joinType"] == "NONE":
    #                 raise TaskError(self.schoolName + "未加入今日校园，请检查...", 301)
    #             else:
    #                 LL.log(1, f"「{self.schoolName}」接入今日校园方式为「{item['joinType']}」")
    #             flag = False
    #             params = {"ids": item["id"]}
    #             data = self.session.get(
    #                 "https://mobile.campushoy.com/v6/config/guest/tenant/info",
    #                 params=params,
    #                 verify=False,
    #                 hooks=dict(response=[Utils.checkStatus]),
    #             ).json()["data"][0]
    #             joinType = data["joinType"]
    #             idsUrl = data["idsUrl"]
    #             ampUrl = data["ampUrl"]
    #             if "campusphere" in ampUrl or "cpdaily" in ampUrl:
    #                 self.host = re.findall("\w{4,5}\:\/\/.*?\/", ampUrl)[0]
    #                 status_code = 0
    #                 while status_code != 200:
    #                     newAmpUrl = self.session.get(
    #                         ampUrl, allow_redirects=False, verify=False
    #                     )
    #                     status_code = newAmpUrl.status_code
    #                     if "Location" in newAmpUrl.headers:
    #                         ampUrl = newAmpUrl.headers["Location"]
    #                 self.login_url = ampUrl
    #                 self.login_host = re.findall("\w{4,5}\:\/\/.*?\/", self.login_url)[
    #                     0
    #                 ]
    #             ampUrl2 = data["ampUrl2"]
    #             if "campusphere" in ampUrl2 or "cpdaily" in ampUrl2:
    #                 self.host = re.findall("\w{4,5}\:\/\/.*?\/", ampUrl2)[0]
    #                 ampUrl2 = self.session.get(ampUrl2, verify=False).url
    #                 self.login_url = ampUrl2
    #                 self.login_host = re.findall(r"\w{4,5}\:\/\/.*?\/", self.login_url)[
    #                     0
    #                 ]
    #             break
          # 通过学校名称借助api获取学校的登陆url
    def getLoginUrlBySchoolName(self):
        schools = self.session.get(
            "https://mobile.campushoy.com/v6/config/guest/tenant/list",
            verify=False,
            hooks=dict(response=[Utils.checkStatus]),
        ).json()["data"]
        
        for item in schools:
            if item["name"] == self.schoolName:
                if item["joinType"] == "NONE":
                    raise TaskError(f"{self.schoolName}未加入今日校园，请检查...", 301)
                else:
                    LL.log(1, f"「{self.schoolName}」接入今日校园方式为「{item['joinType']}」")
                
                params = {"ids": item["id"]}
                data = self.session.get(
                    "https://mobile.campushoy.com/v6/config/guest/tenant/info",
                    params=params,
                    verify=False,
                    hooks=dict(response=[Utils.checkStatus]),
                ).json()["data"][0]
                
                ampUrl = data.get("ampUrl", "")
                ampUrl2 = data.get("ampUrl2", "")
                url_resolved = False
                
                # 1️⃣ 优先尝试 ampUrl (OAuth 跳转)
                if ampUrl and ("campusphere" in ampUrl or "cpdaily" in ampUrl):
                    self.host = re.findall(r"\w{4,5}://.*?/", ampUrl)[0]
                    try:
                        LL.log(1, f"🔄 正在解析登录地址跳转链(ampUrl)...")
                        self.session.get("https://api.campushoy.com/", verify=False, timeout=5)
                        headers = {
                            "User-Agent": self.session.headers.get("User-Agent", ""),
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                            "Referer": "https://campushoy.com/",
                            "Connection": "close"
                        }
                        resp = self.session.get(ampUrl, headers=headers, allow_redirects=True, verify=False, timeout=15)
                        if "authTransit" in resp.url:
                            raise ValueError("网关拦截未跳转(WAF)")
                        self.login_url = resp.url
                        self.login_host = re.findall(r"\w{4,5}://.*?/", self.login_url)[0]
                        LL.log(1, f"✅ 跳转成功: {self.login_url}")
                        url_resolved = True
                    except Exception as e:
                        LL.log(2, f"⚠️ ampUrl 解析失败: {e}")

                # 2️⃣ ampUrl 失败则尝试 ampUrl2
                if not url_resolved and ampUrl2 and ("campusphere" in ampUrl2 or "cpdaily" in ampUrl2):
                    self.host = re.findall(r"\w{4,5}://.*?/", ampUrl2)[0]
                    try:
                        LL.log(1, f"🔄 正在解析登录地址跳转链(ampUrl2)...")
                        headers = {
                            "User-Agent": self.session.headers.get("User-Agent", ""),
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                            "Referer": "https://campushoy.com/",
                            "Connection": "close"
                        }
                        resp2 = self.session.get(ampUrl2, headers=headers, allow_redirects=True, verify=False, timeout=15)
                        self.login_url = resp2.url
                        self.login_host = re.findall(r"\w{4,5}://.*?/", self.login_url)[0]
                        LL.log(1, f"✅ 跳转成功: {self.login_url}")
                        url_resolved = True
                    except Exception as e:
                        LL.log(2, f"⚠️ ampUrl2 解析失败: {e}")

                # 3️⃣ 🔑 核心修复：拦截 authTransit 死循环，直连学校 IAP
                if not url_resolved:
                    target_url = None
                    if ampUrl and ("campusphere" in ampUrl or "cpdaily" in ampUrl):
                        target_url = ampUrl
                    elif ampUrl2 and ("campusphere" in ampUrl2 or "cpdaily" in ampUrl2):
                        target_url = ampUrl2

                    if target_url:
                        try:
                            LL.log(1, f"ℹ️ 正在处理降级地址(阻断 authTransit 循环)...")
                            # ⛔ 禁止自动跟随重定向，防止被踢回 api.campushoy.com
                            resp_fb = self.session.get(target_url, allow_redirects=False, verify=False, timeout=10)
                            location = resp_fb.headers.get("Location", "")

                            if "authTransit" in location or "api.campushoy.com" in location:
                                LL.log(2, f"⚠️ 拦截到 authTransit 重定向，正在提取学校直连 IAP 地址...")
                                # 从原 URL 的 redirect_uri 参数中解析学校主域
                                match = re.search(r"redirect_uri=([^&]+)", target_url)
                                if match:
                                    raw_uri = match.group(1)
                                    # URL解码并提取域名
                                    school_domain = raw_uri.replace('%3A', ':').replace('%2F', '/')
                                    school_domain = re.findall(r"(https?://[^/]+)", school_domain)[0]
                                    self.login_url = f"{school_domain}/iap/login/"
                                else:
                                    school_domain = re.findall(r"(https?://[^/]+)", target_url)[0]
                                    self.login_url = f"{school_domain}/iap/login/"
                            else:
                                # 未触发死循环，使用实际返回地址
                                self.login_url = location if location else resp_fb.url

                            self.login_host = re.findall(r"\w{4,5}://.*?/", self.login_url)[0]
                            LL.log(1, f"✅ 最终登录页: {self.login_url}")
                            url_resolved = True
                        except Exception as e:
                            LL.log(2, f"⚠️ 降级处理异常: {e}")
                            # 极端兜底
                            if not url_resolved and target_url:
                                self.login_url = target_url
                                self.login_host = re.findall(r"\w{4,5}://.*?/", self.login_url)[0]
                                url_resolved = True

                # 4️⃣ 最终校验
                if not url_resolved or not self.login_url:
                    raise TaskError(
                        f"「{self.schoolName}」未能获取有效登录地址。\n"
                        f"可能原因：1.该校已更换独立认证系统(当前joinType={data.get('joinType')})\n"
                        f"2.今日校园API配置异常或该校网关彻底屏蔽自动化请求。", 
                        302
                    )
                break




    # 通过登陆url判断采用哪种登陆方式
    def checkLogin(self):
        LL.log(1, f"学校的教务系统登录地址为「{self.login_url}」")
        if self.login_url.find("/iap") != -1:
            self.loginEntity = iapLogin(
                self.username,
                self.password,
                self.login_url,
                self.login_host,
                self.session,
            )
        elif (
            self.login_url.find("kmu.edu.cn") != -1
            or self.login_url.find("hytc.edu.cn") != -1
        ):
            self.loginEntity = RSALogin(
                self.username,
                self.password,
                self.login_url,
                self.login_host,
                self.session,
            )
        else:
            self.loginEntity = casLogin(
                self.username,
                self.password,
                self.login_url,
                self.login_host,
                self.session,
            )
        # 统一登录流程
        self.session.cookies = self.loginEntity.login()

    # 本地化登陆
    def login(self):
        # 获取学校登陆地址
        self.getLoginUrlBySchoolName()
        self.checkLogin()
